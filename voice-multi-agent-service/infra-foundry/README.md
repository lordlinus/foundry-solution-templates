# Foundry infrastructure layer

The `microsoft.foundry` provider (from the `azure.ai.projects` azd extension) provisions the Foundry account and project declared in `azure.yaml`. The voice agent uses a service-managed realtime model, so this layer deploys no model. No Bicep or Terraform files are required here.
