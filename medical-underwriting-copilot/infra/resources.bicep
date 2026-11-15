param environmentName string
param location string
param foundryAccountName string
param foundryProjectName string
param foundryProjectEndpoint string
param principalId string
param principalType string
param agentName string
param webExists bool

var token = toLower(uniqueString(subscription().id, resourceGroup().id, environmentName))
var tags = { 'azd-env-name': environmentName }
var roles = {
  azureAiUser: '53ca6127-db72-4b80-b1b0-d745d6d5456d'
  acrPull: '7f951dda-4ed3-4680-a7ca-43fe172d538d'
  searchIndexDataReader: '1407120a-92aa-4202-b7e9-c0e197c71c8f'
  searchIndexDataContributor: '8ebe5a00-799e-43f5-93ac-243d3dce84a7'
  searchServiceContributor: '7ca78c08-252a-4471-8644-bb5ff32d4ba0'
}

resource foundryAccount 'Microsoft.CognitiveServices/accounts@2025-06-01' existing = {
  name: foundryAccountName
}

resource foundryProject 'Microsoft.CognitiveServices/accounts/projects@2025-06-01' existing = {
  parent: foundryAccount
  name: foundryProjectName
}

// ── Underwriting guidelines: Azure AI Search, Entra ID only ─────────────────

resource search 'Microsoft.Search/searchServices@2023-11-01' = {
  name: 'srch-${token}'
  location: location
  tags: tags
  sku: { name: 'basic' }
  properties: {
    replicaCount: 1
    partitionCount: 1
    disableLocalAuth: true
  }
}

// The hosted search tool queries through this connection with the project's managed identity.
resource searchConnection 'Microsoft.CognitiveServices/accounts/projects/connections@2025-06-01' = {
  parent: foundryProject
  name: 'underwriting-guidelines'
  properties: {
    category: 'CognitiveSearch'
    target: 'https://${search.name}.search.windows.net'
    authType: 'AAD'
    metadata: {
      ApiType: 'Azure'
      ResourceId: search.id
      location: location
    }
  }
}

resource projectSearchReader 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: search
  name: guid(search.id, foundryProject.id, roles.searchIndexDataReader)
  properties: {
    principalId: foundryProject.identity.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.searchIndexDataReader)
  }
}

// The deploying identity creates the index and uploads the guidelines (scripts/seed_guidelines.py).
resource deployerIndexWriter 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: search
  name: guid(search.id, principalId, roles.searchIndexDataContributor)
  properties: {
    principalId: principalId
    principalType: principalType
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.searchIndexDataContributor)
  }
}

resource deployerServiceWriter 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: search
  name: guid(search.id, principalId, roles.searchServiceContributor)
  properties: {
    principalId: principalId
    principalType: principalType
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.searchServiceContributor)
  }
}

// ── Web app: Container Apps with Entra sign-in ──────────────────────────────

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
  name: guid(registry.id, webIdentity.id, roles.acrPull)
  properties: {
    principalId: webIdentity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.acrPull)
  }
}

// Account scope: agent sessions, session files and responses in the project, and Content Understanding.
resource webFoundryAccess 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: foundryAccount
  name: guid(foundryAccount.id, webIdentity.id, roles.azureAiUser)
  properties: {
    principalId: webIdentity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.azureAiUser)
  }
}

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
      ingress: { external: true, targetPort: 3000, transport: 'auto' }
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
            { name: 'FOUNDRY_AGENT_NAME', value: agentName }
            { name: 'CONTENT_UNDERSTANDING_ENDPOINT', value: foundryAccount.properties.endpoint }
            { name: 'AZURE_CLIENT_ID', value: webIdentity.properties.clientId }
          ]
        }
      ]
      scale: { minReplicas: 0, maxReplicas: 1 }
    }
  }
}

var issuer = '${az.environment().authentication.loginEndpoint}${tenant().tenantId}/v2.0'

module registration 'app-registration.bicep' = {
  name: 'web-app-registration'
  params: {
    uniqueName: 'medical-underwriting-copilot-${token}'
    displayName: 'Medical underwriting copilot (${environmentName})'
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
output searchEndpoint string = 'https://${search.name}.search.windows.net'
output searchConnectionId string = searchConnection.id
