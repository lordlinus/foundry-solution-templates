# Foundry infrastructure layer

The `microsoft.foundry` provider (from the `azure.ai.projects` azd extension) provisions the Foundry account, project, and model declared in `azure.yaml`. No Bicep or Terraform files are required in this layer, and this template needs no other infrastructure: Foundry registers the Teams and Microsoft 365 channel itself when the agent is published.
