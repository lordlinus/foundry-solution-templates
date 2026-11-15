param environmentName string
param location string
param foundryAccountName string
param foundryProjectName string
param foundryProjectEndpoint string
param voiceAgentName string
param principalId string
param webExists bool
param appInsightsResourceId string
param logAnalyticsWorkspaceResourceId string

var token = toLower(uniqueString(subscription().id, resourceGroup().id, environmentName))
var tags = { 'azd-env-name': environmentName }
// Foundry User (formerly Azure AI User): invoke agents, including voice sessions.
var foundryUserRole = '53ca6127-db72-4b80-b1b0-d745d6d5456d'
var acrPullRole = '7f951dda-4ed3-4680-a7ca-43fe172d538d'

resource foundryAccount 'Microsoft.CognitiveServices/accounts@2025-06-01' existing = {
  name: foundryAccountName
}

resource foundryProject 'Microsoft.CognitiveServices/accounts/projects@2025-06-01' existing = {
  parent: foundryAccount
  name: foundryProjectName
}

resource registry 'Microsoft.ContainerRegistry/registries@2023-07-01' = {
  name: 'cr${token}'
  location: location
  tags: tags
  sku: { name: 'Basic' }
  properties: { adminUserEnabled: false }
}

resource webIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: 'id-web-${token}'
  location: location
  tags: tags
}

resource webAcrPull 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: registry
  name: guid(registry.id, webIdentity.id, acrPullRole)
  properties: {
    principalId: webIdentity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', acrPullRole)
  }
}

// The web app opens voice sessions on the user's behalf. Browsers never receive a token.
resource webFoundryUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: foundryProject
  name: guid(foundryProject.id, webIdentity.id, foundryUserRole)
  properties: {
    principalId: webIdentity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', foundryUserRole)
  }
}

resource deployerFoundryUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(principalId)) {
  scope: foundryProject
  name: guid(foundryProject.id, principalId, foundryUserRole)
  properties: {
    principalId: principalId
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', foundryUserRole)
  }
}

// Trace-based evaluation reads the voice traces as the project's managed identity: Reader on
// Application Insights, Log Analytics Reader on the workspace, and Privileged Monitoring Data Reader
// for the protected gen-AI content table. Without these, trace eval runs fail validation.
var readerRole = 'acdd72a7-3385-48ef-bd42-f606fba81ae7'
var logAnalyticsReaderRole = '73c42c96-874c-492b-b04d-ab87d138a893'
var privilegedMonitoringDataReaderRole = 'dbc9c667-e97f-4491-aee6-90b9cf960190'

resource appInsights 'Microsoft.Insights/components@2020-02-02' existing = if (!empty(appInsightsResourceId)) {
  name: last(split(appInsightsResourceId, '/'))
}

resource workspace 'Microsoft.OperationalInsights/workspaces@2023-09-01' existing = if (!empty(logAnalyticsWorkspaceResourceId)) {
  name: last(split(logAnalyticsWorkspaceResourceId, '/'))
}

resource projectTraceReader 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(appInsightsResourceId)) {
  scope: appInsights
  name: guid(appInsightsResourceId, foundryProject.id, readerRole)
  properties: {
    principalId: foundryProject.identity.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', readerRole)
  }
}

// Trace evaluation also reads through the Application Insights resource itself.
resource projectAppInsightsLogReader 'Microsoft.Authorization/roleAssignments@2022-04-01' = [
  for role in [logAnalyticsReaderRole, privilegedMonitoringDataReaderRole]: if (!empty(appInsightsResourceId)) {
    scope: appInsights
    name: guid(appInsightsResourceId, foundryProject.id, role)
    properties: {
      principalId: foundryProject.identity.principalId
      principalType: 'ServicePrincipal'
      roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', role)
    }
  }
]

resource projectLogReader 'Microsoft.Authorization/roleAssignments@2022-04-01' = [
  for role in [logAnalyticsReaderRole, privilegedMonitoringDataReaderRole]: if (!empty(logAnalyticsWorkspaceResourceId)) {
    scope: workspace
    name: guid(logAnalyticsWorkspaceResourceId, foundryProject.id, role)
    properties: {
      principalId: foundryProject.identity.principalId
      principalType: 'ServicePrincipal'
      roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', role)
    }
  }
]

resource environment 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: 'cae-${token}'
  location: location
  tags: tags
  properties: {}
}

module webImage 'existing-image.bicep' = {
  name: 'web-image'
  params: { name: 'ca-web-${token}', exists: webExists }
}

resource web 'Microsoft.App/containerApps@2024-03-01' = {
  name: 'ca-web-${token}'
  location: location
  tags: union(tags, { 'azd-service-name': 'web' })
  identity: { type: 'UserAssigned', userAssignedIdentities: { '${webIdentity.id}': {} } }
  dependsOn: [webAcrPull]
  properties: {
    environmentId: environment.id
    configuration: {
      ingress: { external: true, targetPort: 8080, transport: 'auto' }
      registries: [{ server: registry.properties.loginServer, identity: webIdentity.id }]
      // Built-in sign-in uses the managed identity as a federated credential instead of a client secret.
      secrets: [{ name: 'override-use-mi-fic-assertion-client-id', value: webIdentity.properties.clientId }]
    }
    template: {
      containers: [
        {
          name: 'web'
          image: webImage.outputs.image
          resources: { cpu: json('0.5'), memory: '1Gi' }
          env: [
            { name: 'FOUNDRY_PROJECT_ENDPOINT', value: foundryProjectEndpoint }
            { name: 'VOICE_AGENT_NAME', value: voiceAgentName }
            { name: 'AZURE_CLIENT_ID', value: webIdentity.properties.clientId }
          ]
        }
      ]
      // Card actions staged in a call live in this process; one replica keeps a call on one process.
      scale: { minReplicas: 0, maxReplicas: 1 }
    }
  }
}

var issuer = '${az.environment().authentication.loginEndpoint}${tenant().tenantId}/v2.0'

module registration 'app-registration.bicep' = {
  name: 'web-app-registration'
  params: {
    uniqueName: 'voice-multi-agent-service-${token}'
    displayName: 'Voice card service (${environmentName})'
    webUrl: 'https://${web.properties.configuration.ingress.fqdn}'
    federatedIdentityPrincipalId: webIdentity.properties.principalId
    issuer: issuer
  }
}

resource webAuth 'Microsoft.App/containerApps/authConfigs@2024-10-02-preview' = {
  parent: web
  name: 'current'
  properties: {
    platform: { enabled: true }
    globalValidation: {
      unauthenticatedClientAction: 'RedirectToLoginPage'
      redirectToProvider: 'azureactivedirectory'
    }
    identityProviders: {
      azureActiveDirectory: {
        enabled: true
        registration: {
          clientId: registration.outputs.clientId
          clientSecretSettingName: 'override-use-mi-fic-assertion-client-id'
          openIdIssuer: issuer
        }
      }
    }
  }
}

output registryEndpoint string = registry.properties.loginServer
output webUrl string = 'https://${web.properties.configuration.ingress.fqdn}'
output appRegistrationClientId string = registration.outputs.clientId
