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
Write-Host "Azure AgenticML Agent Infrastructure Provisioning"
Write-Host "================================================================="

$INPUT_PROJECT = Read-Host "Enter project name (default: agentic-ml-agent)"
if ([string]::IsNullOrWhiteSpace($INPUT_PROJECT)) { $INPUT_PROJECT = "agentic-ml-agent" }
$PROJECT_NAME = Format-Name $INPUT_PROJECT

$INPUT_LOCATION = Read-Host "Enter Azure region (ensure model quota and availability) (default: eastus)"
if ([string]::IsNullOrWhiteSpace($INPUT_LOCATION)) { $INPUT_LOCATION = "eastus" }
$LOCATION = $INPUT_LOCATION

$INPUT_RG = Read-Host "Enter resource group name (default: rg-$PROJECT_NAME)"
if ([string]::IsNullOrWhiteSpace($INPUT_RG)) { $INPUT_RG = "rg-$PROJECT_NAME" }
$RESOURCE_GROUP = $INPUT_RG

$INPUT_MCP_URL = Read-Host "Enter MCP URL (default: http://127.0.0.1:7860/gradio_api/mcp/)"
if ([string]::IsNullOrWhiteSpace($INPUT_MCP_URL)) { $INPUT_MCP_URL = "http://127.0.0.1:7860/gradio_api/mcp/" }
$MCP_URL = $INPUT_MCP_URL

# ==============================================================================
# Derived Resource Names
# ==============================================================================

$UNIX_TIME = [DateTimeOffset]::Now.ToUnixTimeSeconds().ToString()
$UNIQUE_SUFFIX = $UNIX_TIME.Substring($UNIX_TIME.Length - 4)

$AI_RESOURCE_NAME = "$(Format-Name $PROJECT_NAME)ai$UNIQUE_SUFFIX"
$AI_PROJECT_NAME = "proj-default"

# ==============================================================================
# Display Deployment Configuration
# ==============================================================================

Write-Host ""
Write-Host "Deployment configuration"
Write-Host "---------------------------------------------------------------"
Write-Host "Project Name           : $PROJECT_NAME"
Write-Host "Resource Group         : $RESOURCE_GROUP"
Write-Host "Region                 : $LOCATION"
Write-Host "AI Resource            : $AI_RESOURCE_NAME"
Write-Host "AI Project             : $AI_PROJECT_NAME"
Write-Host "MCP URL                : $MCP_URL"
Write-Host "---------------------------------------------------------------"

# ==============================================================================
# Infrastructure Provisioning
# ==============================================================================

Write-Host ""
Write-Host "Provisioning Azure infrastructure."

$SUBSCRIPTION_ID = az account show --query "id" --output tsv
$CURRENT_USER_ID = az ad signed-in-user show --query id --output tsv

Write-Step "1/4" "Creating Resource Group"
az group create `
    --name "$RESOURCE_GROUP" `
    --location "$LOCATION" `
    --only-show-errors `
    --output none

Write-Step "2/4" "Creating Foundry Resource"
az cognitiveservices account create `
    --name "$AI_RESOURCE_NAME" `
    --resource-group "$RESOURCE_GROUP" `
    --location "$LOCATION" `
    --kind AIServices `
    --sku S0 `
    --custom-domain "$AI_RESOURCE_NAME" `
    --yes `
    --only-show-errors `
    --output none

Write-Step "3/4" "Creating Foundry Project"
az cognitiveservices account project create `
    --name "$AI_RESOURCE_NAME" `
    --resource-group "$RESOURCE_GROUP" `
    --project-name "$AI_PROJECT_NAME" `
    --location "$LOCATION" `
    --only-show-errors `
    --output none

Write-Step "4/4" "Assigning Azure AI User Role"
az role assignment create `
    --role "Azure AI User" `
    --assignee-object-id "$CURRENT_USER_ID" `
    --scope "/subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RESOURCE_GROUP" `
    --only-show-errors `
    --output none

# ==============================================================================
# Endpoint Generation
# ==============================================================================

$RESOURCE_ENDPOINT = az cognitiveservices account show `
    --name "$AI_RESOURCE_NAME" `
    --resource-group "$RESOURCE_GROUP" `
    --query "properties.endpoint" `
    --output tsv

$PROJECT_ENDPOINT = "${RESOURCE_ENDPOINT}api/projects/${AI_PROJECT_NAME}"

$DEPLOYMENT_PORTAL_URL = "https://ai.azure.com/resource/deployments?wsid=/subscriptions/${SUBSCRIPTION_ID}/resourceGroups/${RESOURCE_GROUP}/providers/Microsoft.CognitiveServices/accounts/${AI_RESOURCE_NAME}/projects/${AI_PROJECT_NAME}"

# ==============================================================================
# Generate .env Configuration File
# ==============================================================================

$ENV_CONTENT = @"
AZURE_AGENTICML_AGENT_PROJECT_ENDPOINT="$PROJECT_ENDPOINT"
AZURE_AGENTICML_AGENT_MODEL_DEPLOYMENT_NAME=""

AZURE_AGENTICML_AGENT_MCP_URL="$MCP_URL"
"@

$ENV_CONTENT | Out-File -FilePath .env -Encoding ascii

# ==============================================================================
# Completion
# ==============================================================================

Write-Host ""
Write-Host "Deployment completed successfully."
Write-Host "Configuration saved to .env."
Write-Host ""
Write-Host "Next steps:"
Write-Host "1. Deploy your model at the Microsoft Foundry portal:"
Write-Host "$DEPLOYMENT_PORTAL_URL"
Write-Host ""
Write-Host "2. Update the following variable in the .env file with the new deployment name:"
Write-Host "AZURE_AGENTICML_AGENT_MODEL_DEPLOYMENT_NAME"
Write-Host ""
Write-Host "Important:"
Write-Host "Ensure the model is deployed directly in this resource and not in a connected one."
Write-Host "Also ensure that your chosen region ($LOCATION) has sufficient quota for the model."
Write-Host ""
Write-Host "You can now start the Azure AgenticML Agent."