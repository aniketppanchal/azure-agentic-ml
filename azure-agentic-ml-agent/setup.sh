#!/usr/bin/env bash

set -euo pipefail

# ==============================================================================
# Utility Functions
# ==============================================================================

format_name() {
    echo "$1" | tr '[:upper:]' '[:lower:]' | tr -cd '[:alnum:]' | cut -c 1-15
}

write_step() {
    echo "[$1] $2"
}

# ==============================================================================
# User Input
# ==============================================================================

echo "================================================================="
echo "Azure AgenticML Agent Infrastructure Provisioning"
echo "================================================================="

read -rp "Enter project name (default: agentic-ml-agent): " INPUT_PROJECT
PROJECT_NAME=$(format_name "${INPUT_PROJECT:-agentic-ml-agent}")

read -rp "Enter Azure region (ensure model quota and availability) (default: eastus): " INPUT_LOCATION
LOCATION="${INPUT_LOCATION:-eastus}"

read -rp "Enter resource group name (default: rg-${PROJECT_NAME}): " INPUT_RG
RESOURCE_GROUP="${INPUT_RG:-rg-${PROJECT_NAME}}"

read -rp "Enter MCP URL (default: http://127.0.0.1:7860/gradio_api/mcp/): " INPUT_MCP_URL
MCP_URL="${INPUT_MCP_URL:-http://127.0.0.1:7860/gradio_api/mcp/}"

# ==============================================================================
# Derived Resource Names
# ==============================================================================

UNIQUE_SUFFIX=$(date +%s | tail -c 5)

AI_RESOURCE_NAME="$(format_name "$PROJECT_NAME")ai${UNIQUE_SUFFIX}"
AI_PROJECT_NAME="proj-default"

# ==============================================================================
# Display Deployment Configuration
# ==============================================================================

echo
echo "Deployment configuration"
echo "---------------------------------------------------------------"
echo "Project Name           : $PROJECT_NAME"
echo "Resource Group         : $RESOURCE_GROUP"
echo "Region                 : $LOCATION"
echo "AI Resource            : $AI_RESOURCE_NAME"
echo "AI Project             : $AI_PROJECT_NAME"
echo "MCP URL                : $MCP_URL"
echo "---------------------------------------------------------------"

# ==============================================================================
# Infrastructure Provisioning
# ==============================================================================

echo
echo "Provisioning Azure infrastructure."

SUBSCRIPTION_ID=$(az account show --query "id" --output tsv)
CURRENT_USER_ID=$(az ad signed-in-user show --query id --output tsv)

write_step "1/4" "Creating Resource Group"
az group create \
--name "$RESOURCE_GROUP" \
--location "$LOCATION" \
--only-show-errors \
--output none

write_step "2/4" "Creating Foundry Resource"
az cognitiveservices account create \
--name "$AI_RESOURCE_NAME" \
--resource-group "$RESOURCE_GROUP" \
--location "$LOCATION" \
--kind AIServices \
--sku S0 \
--custom-domain "$AI_RESOURCE_NAME" \
--yes \
--only-show-errors \
--output none

write_step "3/4" "Creating Foundry Project"
az cognitiveservices account project create \
--name "$AI_RESOURCE_NAME" \
--resource-group "$RESOURCE_GROUP" \
--project-name "$AI_PROJECT_NAME" \
--location "$LOCATION" \
--only-show-errors \
--output none

write_step "4/4" "Assigning Azure AI User Role"
az role assignment create \
--role "Azure AI User" \
--assignee-object-id "$CURRENT_USER_ID" \
--scope "/subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RESOURCE_GROUP" \
--only-show-errors \
--output none

# ==============================================================================
# Endpoint Generation
# ==============================================================================

RESOURCE_ENDPOINT=$(az cognitiveservices account show \
    --name "$AI_RESOURCE_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --query "properties.endpoint" \
--output tsv)

PROJECT_ENDPOINT="${RESOURCE_ENDPOINT}api/projects/${AI_PROJECT_NAME}"

DEPLOYMENT_PORTAL_URL="https://ai.azure.com/resource/deployments?wsid=/subscriptions/${SUBSCRIPTION_ID}/resourceGroups/${RESOURCE_GROUP}/providers/Microsoft.CognitiveServices/accounts/${AI_RESOURCE_NAME}/projects/${AI_PROJECT_NAME}"

# ==============================================================================
# Generate .env Configuration File
# ==============================================================================

cat <<EOF > .env
AZURE_AGENTICML_AGENT_PROJECT_ENDPOINT="$PROJECT_ENDPOINT"
AZURE_AGENTICML_AGENT_MODEL_DEPLOYMENT_NAME=""

AZURE_AGENTICML_AGENT_MCP_URL="$MCP_URL"
EOF

# ==============================================================================
# Completion
# ==============================================================================

echo
echo "Deployment completed successfully."
echo "Configuration saved to .env."
echo
echo "Next steps:"
echo "1. Deploy your model at the Microsoft Foundry portal:"
echo "$DEPLOYMENT_PORTAL_URL"
echo
echo "2. Update the following variable in the .env file with the new deployment name:"
echo "AZURE_AGENTICML_AGENT_MODEL_DEPLOYMENT_NAME"
echo
echo "Important:"
echo "Ensure the model is deployed directly in this resource and not in a connected one."
echo "Also ensure that your chosen region ($LOCATION) has sufficient quota for the model."
echo
echo "You can now start the Azure AgenticML Agent."