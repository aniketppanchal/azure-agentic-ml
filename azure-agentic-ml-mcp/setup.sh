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
echo "Azure AgenticML MCP Infrastructure Provisioning"
echo "================================================================="

read -rp "Enter project name (default: agentic-ml-mcp): " INPUT_PROJECT
PROJECT_NAME=$(format_name "${INPUT_PROJECT:-agentic-ml-mcp}")

read -rp "Enter Azure region (default: eastus): " INPUT_LOCATION
LOCATION="${INPUT_LOCATION:-eastus}"

read -rp "Enter resource group name (default: rg-${PROJECT_NAME}): " INPUT_RG
RESOURCE_GROUP="${INPUT_RG:-rg-${PROJECT_NAME}}"

# ==============================================================================
# Derived Resource Names
# ==============================================================================

UNIQUE_SUFFIX=$(date +%s | tail -c 5)

STORAGE_ACCOUNT_NAME="$(format_name "$PROJECT_NAME")store${UNIQUE_SUFFIX}"
FILE_SHARE_NAME="${PROJECT_NAME}-artifacts"

CONTAINER_REGISTRY_NAME="$(format_name "$PROJECT_NAME")acr${UNIQUE_SUFFIX}"
CONTAINER_APPS_ENV_NAME="${PROJECT_NAME}-container-env-${UNIQUE_SUFFIX}"

# ==============================================================================
# Display Deployment Configuration
# ==============================================================================

echo
echo "Deployment configuration"
echo "---------------------------------------------------------------"
echo "Project Name           : $PROJECT_NAME"
echo "Resource Group         : $RESOURCE_GROUP"
echo "Region                 : $LOCATION"
echo "Storage Account        : $STORAGE_ACCOUNT_NAME"
echo "Container Registry     : $CONTAINER_REGISTRY_NAME"
echo "Container Apps Env     : $CONTAINER_APPS_ENV_NAME"
echo "---------------------------------------------------------------"

# ==============================================================================
# Infrastructure Provisioning
# ==============================================================================

echo
echo "Provisioning Azure infrastructure."

SUBSCRIPTION_ID=$(az account show --query "id" --output tsv)

write_step "1/6" "Creating Resource Group"
az group create \
--name "$RESOURCE_GROUP" \
--location "$LOCATION" \
--only-show-errors \
--output none

write_step "2/6" "Creating Storage Account"
az storage account create \
--name "$STORAGE_ACCOUNT_NAME" \
--resource-group "$RESOURCE_GROUP" \
--location "$LOCATION" \
--sku Standard_LRS \
--min-tls-version TLS1_2 \
--only-show-errors \
--output none

STORAGE_ACCOUNT_KEY=$(az storage account keys list \
    --resource-group "$RESOURCE_GROUP" \
    --account-name "$STORAGE_ACCOUNT_NAME" \
    --query "[0].value" \
--output tsv)

write_step "3/6" "Creating Azure File Share"
az storage share create \
--name "$FILE_SHARE_NAME" \
--account-name "$STORAGE_ACCOUNT_NAME" \
--account-key "$STORAGE_ACCOUNT_KEY" \
--only-show-errors \
--output none

write_step "4/6" "Creating Azure Container Registry"
az acr create \
--name "$CONTAINER_REGISTRY_NAME" \
--resource-group "$RESOURCE_GROUP" \
--sku Basic \
--admin-enabled true \
--only-show-errors \
--output none

ACR_LOGIN_SERVER=$(az acr show \
    --name "$CONTAINER_REGISTRY_NAME" \
    --query "loginServer" \
--output tsv)

ACR_USERNAME=$(az acr credential show \
    --name "$CONTAINER_REGISTRY_NAME" \
    --query "username" \
--output tsv)

ACR_PASSWORD=$(az acr credential show \
    --name "$CONTAINER_REGISTRY_NAME" \
    --query "passwords[0].value" \
--output tsv)

write_step "5/6" "Creating Container Apps Environment"
az containerapp env create \
--name "$CONTAINER_APPS_ENV_NAME" \
--resource-group "$RESOURCE_GROUP" \
--location "$LOCATION" \
--only-show-errors \
--output none

CONTAINER_APPS_ENV_ID=$(az containerapp env show \
    --name "$CONTAINER_APPS_ENV_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --query "id" \
--output tsv)

write_step "6/6" "Registering Azure File Share With Container Apps Environment"
az containerapp env storage set \
--name "$CONTAINER_APPS_ENV_NAME" \
--resource-group "$RESOURCE_GROUP" \
--storage-name "$FILE_SHARE_NAME" \
--azure-file-account-name "$STORAGE_ACCOUNT_NAME" \
--azure-file-account-key "$STORAGE_ACCOUNT_KEY" \
--azure-file-share-name "$FILE_SHARE_NAME" \
--access-mode ReadOnly \
--only-show-errors \
--output none

# ==============================================================================
# Build and Push Docker Images
# ==============================================================================

echo
echo "Building and pushing Docker images."

MODEL_TRAINER_IMAGE="azure-agentic-ml-model-trainer:latest"
MODEL_SERVER_IMAGE="azure-agentic-ml-model-server:latest"

write_step "1/2" "Building and Pushing Model Trainer Image"
az acr build \
--registry "$CONTAINER_REGISTRY_NAME" \
--image "$MODEL_TRAINER_IMAGE" \
--no-logs \
--only-show-errors \
containers/model-trainer

write_step "2/2" "Building and Pushing Model Server Image"
az acr build \
--registry "$CONTAINER_REGISTRY_NAME" \
--image "$MODEL_SERVER_IMAGE" \
--no-logs \
--only-show-errors \
containers/model-server

# ==============================================================================
# Generate .env Configuration File
# ==============================================================================

cat <<EOF > .env
AZURE_AGENTICML_MCP_SUBSCRIPTION_ID="$SUBSCRIPTION_ID"
AZURE_AGENTICML_MCP_RESOURCE_GROUP="$RESOURCE_GROUP"
AZURE_AGENTICML_MCP_LOCATION="$LOCATION"

AZURE_AGENTICML_MCP_FILE_SHARE_NAME="$FILE_SHARE_NAME"
AZURE_AGENTICML_MCP_STORAGE_ACCOUNT_NAME="$STORAGE_ACCOUNT_NAME"
AZURE_AGENTICML_MCP_STORAGE_ACCOUNT_KEY="$STORAGE_ACCOUNT_KEY"

AZURE_AGENTICML_MCP_CONTAINER_REGISTRY_SERVER="$ACR_LOGIN_SERVER"
AZURE_AGENTICML_MCP_CONTAINER_REGISTRY_USERNAME="$ACR_USERNAME"
AZURE_AGENTICML_MCP_CONTAINER_REGISTRY_PASSWORD="$ACR_PASSWORD"

AZURE_AGENTICML_MCP_CONTAINER_APP_ENVIRONMENT_ID="$CONTAINER_APPS_ENV_ID"
EOF

# ==============================================================================
# Completion
# ==============================================================================

echo
echo "Deployment completed successfully."
echo "Configuration saved to .env."
echo
echo "You can now start the Azure AgenticML MCP server."