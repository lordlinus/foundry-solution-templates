targetScope = 'subscription'

@description('azd environment name; seeds resource names.')
param environmentName string
@description('Region for the app resources.')
param location string
@description('Region for Azure AI Search. Empty means the deployment region; set another region when that one has no Search capacity.')
param searchLocation string = ''
@description('Resource group created by the Foundry layer.')
param resourceGroupName string
param foundryAccountName string
param foundryProjectName string
param foundryProjectEndpoint string
@description('Deploying identity; seeds the guidelines index from the postprovision hook.')
param principalId string
@allowed(['User', 'ServicePrincipal'])
param principalType string = 'User'
@description('Hosted agent name; must match the agent service name in azure.yaml.')
param agentName string = 'underwriting-agent'
param searchIndexName string = 'underwriting-guidelines'
param webExists bool = false

module resources 'resources.bicep' = {
  name: 'underwriting-app'
  scope: resourceGroup(resourceGroupName)
  params: {
    environmentName: environmentName
    location: location
    searchLocation: empty(searchLocation) ? location : searchLocation
    foundryAccountName: foundryAccountName
    foundryProjectName: foundryProjectName
    foundryProjectEndpoint: foundryProjectEndpoint
    principalId: principalId
    principalType: principalType
    agentName: agentName
    webExists: webExists
  }
}

output AZURE_CONTAINER_REGISTRY_ENDPOINT string = resources.outputs.registryEndpoint
output WEB_URL string = resources.outputs.webUrl
output WEB_APP_REGISTRATION_CLIENT_ID string = resources.outputs.appRegistrationClientId
output SEARCH_ENDPOINT string = resources.outputs.searchEndpoint
output SEARCH_CONNECTION_ID string = resources.outputs.searchConnectionId
output SEARCH_INDEX_NAME string = searchIndexName
