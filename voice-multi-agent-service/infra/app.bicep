targetScope = 'subscription'

@description('azd environment name; seeds resource names.')
param environmentName string
@description('Region for the Container Apps resources.')
param location string
@description('Resource group created by the Foundry layer.')
param resourceGroupName string
param foundryAccountName string
param foundryProjectName string
param foundryProjectEndpoint string
@description('Voice agent name; must match "name" in agent/voice-agent.json.')
param voiceAgentName string = 'card-service-voice'
@description('Deploying user or service principal. Gets Foundry User on the project so the postprovision hook can publish the voice agent. Empty skips it.')
param principalId string = ''
param webExists bool = false
@description('Application Insights connected by the Foundry layer. The project identity gets read access for trace-based evaluation. Empty skips it.')
param appInsightsResourceId string = ''
param logAnalyticsWorkspaceResourceId string = ''

module resources 'resources.bicep' = {
  name: 'voice-app'
  scope: resourceGroup(resourceGroupName)
  params: {
    environmentName: environmentName
    location: location
    foundryAccountName: foundryAccountName
    foundryProjectName: foundryProjectName
    foundryProjectEndpoint: foundryProjectEndpoint
    voiceAgentName: voiceAgentName
    principalId: principalId
    webExists: webExists
    appInsightsResourceId: appInsightsResourceId
    logAnalyticsWorkspaceResourceId: logAnalyticsWorkspaceResourceId
  }
}

output AZURE_CONTAINER_REGISTRY_ENDPOINT string = resources.outputs.registryEndpoint
output WEB_URL string = resources.outputs.webUrl
output WEB_APP_REGISTRATION_CLIENT_ID string = resources.outputs.appRegistrationClientId
output VOICE_AGENT_NAME string = voiceAgentName
