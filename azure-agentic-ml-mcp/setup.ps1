$ErrorActionPreference = "Stop"

# ==============================================================================
# Utility Functions
# ==============================================================================

function Format-Name($Name) {
    $Formatted = ($Name.ToLower() -replace '[^a-z0-9]', '')
    if ($Formatted.Length -gt 15) {
        $Formatted = $Formatted.Substring(0, 15)
    }
    return $Formatted
}

function Write-Step($Step, $Message) {
    Write-Host "[$Step] $Message"
}

# ==============================================================================
# User Input
# ==============================================================================

Write-Host "================================================================="
Write-Host "Azure AgenticML MCP Infrastructure Provisioning"
Write-Host "================================================================="

$INPUT_PROJECT = Read-Host "Enter project name (default: agentic-ml-mcp)"
if ([string]::IsNullOrWhiteSpace($INPUT_PROJECT)) { $INPUT_PROJECT = "agentic-ml-mcp" }
$PROJECT_NAME = Format-Name $INPUT_PROJECT

$INPUT_LOCATION = Read-Host "Enter Azure region (default: eastus)"
if ([string]::IsNullOrWhiteSpace($INPUT_LOCATION)) { $INPUT_LOCATION = "eastus" }
$LOCATION = $INPUT_LOCATION

$INPUT_RG = Read-Host "Enter resource group name (default: rg-$PROJECT_NAME)"
if ([string]::IsNullOrWhiteSpace($INPUT_RG)) { $INPUT_RG = "rg-$PROJECT_NAME" }
$RESOURCE_GROUP = $INPUT_RG

# ==============================================================================
# Derived Resource Names
# ==============================================================================

$UNIX_TIME = [DateTimeOffset]::Now.ToUnixTimeSeconds().ToString()
$UNIQUE_SUFFIX = $UNIX_TIME.Substring($UNIX_TIME.Length - 4)

$STORAGE_ACCOUNT_NAME = "$(Format-Name $PROJECT_NAME)store$UNIQUE_SUFFIX"
$FILE_SHARE_NAME = "${PROJECT_NAME}-artifacts"

$CONTAINER_REGISTRY_NAME = "$(Format-Name $PROJECT_NAME)acr$UNIQUE_SUFFIX"
$CONTAINER_APPS_ENV_NAME = "${PROJECT_NAME}-container-env-${UNIQUE_SUFFIX}"

# ==============================================================================
# Display Deployment Configuration
# ==============================================================================

Write-Host ""
Write-Host "Deployment configuration"
Write-Host "---------------------------------------------------------------"
Write-Host "Project Name           : $PROJECT_NAME"
Write-Host "Resource Group         : $RESOURCE_GROUP"
Write-Host "Region                 : $LOCATION"
Write-Host "Storage Account        : $STORAGE_ACCOUNT_NAME"
Write-Host "Container Registry     : $CONTAINER_REGISTRY_NAME"
Write-Host "Container Apps Env     : $CONTAINER_APPS_ENV_NAME"
Write-Host "---------------------------------------------------------------"

# ==============================================================================
# Infrastructure Provisioning
# ==============================================================================

Write-Host ""
Write-Host "Provisioning Azure infrastructure."

$SUBSCRIPTION_ID = az account show --query "id" --output tsv

Write-Step "1/6" "Creating Resource Group"
az group create `
    --name "$RESOURCE_GROUP" `
    --location "$LOCATION" `
    --only-show-errors `
    --output none

Write-Step "2/6" "Creating Storage Account"
az storage account create `
    --name "$STORAGE_ACCOUNT_NAME" `
    --resource-group "$RESOURCE_GROUP" `
    --location "$LOCATION" `
    --sku Standard_LRS `
    --min-tls-version TLS1_2 `
    --only-show-errors `
    --output none

$STORAGE_ACCOUNT_KEY = az storage account keys list `
    --resource-group "$RESOURCE_GROUP" `
    --account-name "$STORAGE_ACCOUNT_NAME" `
    --query "[0].value" `
    --output tsv

Write-Step "3/6" "Creating Azure File Share"
az storage share create `
    --name "$FILE_SHARE_NAME" `
    --account-name "$STORAGE_ACCOUNT_NAME" `
    --account-key "$STORAGE_ACCOUNT_KEY" `
    --only-show-errors `
    --output none

Write-Step "4/6" "Creating Azure Container Registry"
az acr create `
    --name "$CONTAINER_REGISTRY_NAME" `
    --resource-group "$RESOURCE_GROUP" `
    --sku Basic `
    --admin-enabled true `
    --only-show-errors `
    --output none

$ACR_LOGIN_SERVER = az acr show `
    --name "$CONTAINER_REGISTRY_NAME" `
    --query "loginServer" `
    --output tsv

$ACR_USERNAME = az acr credential show `
    --name "$CONTAINER_REGISTRY_NAME" `
    --query "username" `
    --output tsv

$ACR_PASSWORD = az acr credential show `
    --name "$CONTAINER_REGISTRY_NAME" `
    --query "passwords[0].value" `
    --output tsv

Write-Step "5/6" "Creating Container Apps Environment"
az containerapp env create `
    --name "$CONTAINER_APPS_ENV_NAME" `
    --resource-group "$RESOURCE_GROUP" `
    --location "$LOCATION" `
    --only-show-errors `
    --output none

$CONTAINER_APPS_ENV_ID = az containerapp env show `
    --name "$CONTAINER_APPS_ENV_NAME" `
    --resource-group "$RESOURCE_GROUP" `
    --query "id" `
    --output tsv

Write-Step "6/6" "Registering Azure File Share With Container Apps Environment"
az containerapp env storage set `
    --name "$CONTAINER_APPS_ENV_NAME" `
    --resource-group "$RESOURCE_GROUP" `
    --storage-name "$FILE_SHARE_NAME" `
    --azure-file-account-name "$STORAGE_ACCOUNT_NAME" `
    --azure-file-account-key "$STORAGE_ACCOUNT_KEY" `
    --azure-file-share-name "$FILE_SHARE_NAME" `
    --access-mode ReadOnly `
    --only-show-errors `
    --output none

# ==============================================================================
# Build and Push Docker Images
# ==============================================================================

Write-Host ""
Write-Host "Building and pushing Docker images."

$MODEL_TRAINER_IMAGE = "azure-agentic-ml-model-trainer:latest"
$MODEL_SERVER_IMAGE = "azure-agentic-ml-model-server:latest"

Write-Step "1/2" "Building and Pushing Model Trainer Image"
az acr build `
    --registry "$CONTAINER_REGISTRY_NAME" `
    --image "$MODEL_TRAINER_IMAGE" `
    --no-logs `
    --only-show-errors `
    containers/model-trainer

Write-Step "2/2" "Building and Pushing Model Server Image"
az acr build `
    --registry "$CONTAINER_REGISTRY_NAME" `
    --image "$MODEL_SERVER_IMAGE" `
    --no-logs `
    --only-show-errors `
    containers/model-server

# ==============================================================================
# Generate .env Configuration File
# ==============================================================================

$ENV_CONTENT = @"
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
"@

$ENV_CONTENT | Out-File -FilePath .env -Encoding ascii

# ==============================================================================
# Completion
# ==============================================================================

Write-Host ""
Write-Host "Deployment completed successfully."
Write-Host "Configuration saved to .env."
Write-Host ""
Write-Host "You can now start the Azure AgenticML MCP server."