import json
import logging
import mimetypes
from uuid import uuid4

import requests
from azure.identity import DefaultAzureCredential
from azure.mgmt.appcontainers import ContainerAppsAPIClient
from azure.mgmt.containerinstance import ContainerInstanceManagementClient
from azure.mgmt.containerinstance.models import (
    AzureFileVolume,
    Container,
    ContainerGroup,
    ContainerGroupRestartPolicy,
    ImageRegistryCredential,
    OperatingSystemTypes,
    ResourceRequests,
    ResourceRequirements,
    Volume,
    VolumeMount,
)
from azure.storage.fileshare import ShareServiceClient

from .config import settings
from .schemas import ModelTrainingConfig

logger = logging.getLogger(__name__)

# =============================================================================
# AZURE INFRASTRUCTURE SETTINGS
# =============================================================================
SUBSCRIPTION_ID = settings.subscription_id
RESOURCE_GROUP = settings.resource_group
LOCATION = settings.location

STORAGE_ACCOUNT_NAME = settings.storage_account_name
STORAGE_ACCOUNT_KEY = settings.storage_account_key
FILE_SHARE_NAME = settings.file_share_name

CONTAINER_REGISTRY_SERVER = settings.container_registry_server
CONTAINER_REGISTRY_USERNAME = settings.container_registry_username
CONTAINER_REGISTRY_PASSWORD = settings.container_registry_password

CONTAINER_APP_ENVIRONMENT_ID = settings.container_app_environment_id

# =============================================================================
# CONTAINER IMAGES & RESOURCE CONFIGURATION
# =============================================================================
MODEL_TRAINER_IMAGE = settings.model_trainer_image
MODEL_SERVER_IMAGE = settings.model_server_image

TRAINER_MEMORY_GB = settings.trainer_memory_gb
TRAINER_CPU = settings.trainer_cpu

SERVER_MEMORY_GB = settings.server_memory_gb
SERVER_CPU = settings.server_cpu

# =============================================================================
# WORKFLOW CONSTANTS & TIMEOUTS
# =============================================================================
CSV_DOWNLOAD_TIMEOUT_SECONDS = settings.csv_download_timeout_seconds
CSV_UPLOAD_TIMEOUT_SECONDS = settings.csv_upload_timeout_seconds
CSV_PROFILE_TIMEOUT_SECONDS = settings.csv_profile_timeout_seconds
MODEL_TRAINING_TIMEOUT_SECONDS = settings.model_training_timeout_seconds
MODEL_DEPLOYMENT_TIMEOUT_SECONDS = settings.model_deployment_timeout_seconds

CSV_FILENAME = "dataset.csv"
CSV_PROFILE = "csv_profile.json"

PIPELINE_DIR = "pipeline"
PIPELINE_META = "pipeline_meta.json"
PIPELINE_MODEL = "pipeline.joblib"

CSV_PROFILER_SCRIPT = "csv_profiler.py"
MODEL_TRAINER_SCRIPT = "model_trainer.py"
MODEL_SERVER_SCRIPT = "model_server.py"

# =============================================================================
# AZURE SERVICE CLIENTS
# =============================================================================
credential = DefaultAzureCredential()

container_instance_client = ContainerInstanceManagementClient(
    credential=credential,
    subscription_id=SUBSCRIPTION_ID,
)
container_app_client = ContainerAppsAPIClient(
    credential=credential,
    subscription_id=SUBSCRIPTION_ID,
)
file_share_client = ShareServiceClient(
    account_url=f"https://{STORAGE_ACCOUNT_NAME}.file.core.windows.net",
    credential=STORAGE_ACCOUNT_KEY,
).get_share_client(share=FILE_SHARE_NAME)


def generate_request_id() -> dict:
    """Generate a unique request ID for model training workflow.

    This tool creates a new UUID-based request ID and sets up a dedicated directory
    in the Azure file share for a single ML workflow. The request ID must be passed
    to subsequent operations like uploading CSVs, training models, and deploying models.
    Note that reusing a request ID will overwrite the existing CSV, model, and deployment.

    Returns:
        dict: Response containing:
            - ok (bool): True if successful, False otherwise
            - response: Request ID (str) on success, or error message (str) on failure
    """
    request_id = str(uuid4())

    try:
        request_dir = file_share_client.get_directory_client(request_id)
        request_dir.create_directory()
    except Exception:
        logger.exception("Failed to create request dir")
        return {
            "ok": False,
            "response": "Failed to create request dir",
        }

    return {
        "ok": True,
        "response": request_id,
    }


def upload_and_profile_csv(request_id: str, file_url: str) -> dict:
    """Upload a CSV file from a URL and generate a data profile.

    This tool downloads a CSV file from the provided URL, saves it to the Azure file share,
    and runs the CSV profiler to analyze the dataset. The profile includes information
    about columns, data types, missing values, and statistics.

    Args:
        request_id (str): The request ID from generate_request_id()
        file_url (str): HTTP/HTTPS URL pointing to a CSV file

    Returns:
        dict: Response containing:
            - ok (bool): True if successful, False otherwise
            - response: Profile results (dict) on success, or error message (str) on failure
    """
    if not file_url.startswith(("http://", "https://")):
        return {
            "ok": False,
            "response": "Invalid file URL",
        }

    try:
        response = requests.get(file_url, timeout=CSV_DOWNLOAD_TIMEOUT_SECONDS)
        response.raise_for_status()

        mime_guess, _ = mimetypes.guess_type(file_url)
        content_type = response.headers.get("content-type", "").lower()
        if "csv" not in (mime_guess or "") and "csv" not in content_type:
            return {
                "ok": False,
                "response": "URL does not point to a CSV file",
            }

        csv_bytes = response.content
    except Exception:
        logger.exception(f"Failed to download CSV file - {request_id}")
        return {
            "ok": False,
            "response": "Failed to download CSV file",
        }

    try:
        request_dir = file_share_client.get_directory_client(request_id)
        if not request_dir.exists():
            return {
                "ok": False,
                "response": "Invalid request ID",
            }
    except Exception:
        logger.exception(f"Failed to verify request ID - {request_id}")
        return {
            "ok": False,
            "response": "Failed to verify request ID",
        }

    try:
        request_dir.upload_file(
            CSV_FILENAME,
            csv_bytes,
            timeout=CSV_UPLOAD_TIMEOUT_SECONDS,
        )
    except Exception:
        logger.exception(f"Failed to upload CSV file - {request_id}")
        return {
            "ok": False,
            "response": "Failed to upload CSV file",
        }

    try:
        volume = Volume(
            name=f"{FILE_SHARE_NAME}-volume",
            azure_file=AzureFileVolume(
                share_name=FILE_SHARE_NAME,
                storage_account_name=STORAGE_ACCOUNT_NAME,
                storage_account_key=STORAGE_ACCOUNT_KEY,
            ),
        )
        container = Container(
            name="csv-profiler",
            image=f"{CONTAINER_REGISTRY_SERVER}/{MODEL_TRAINER_IMAGE}",
            resources=ResourceRequirements(
                requests=ResourceRequests(
                    memory_in_gb=TRAINER_MEMORY_GB,
                    cpu=TRAINER_CPU,
                )
            ),
            command=[
                "python",
                CSV_PROFILER_SCRIPT,
                "--dataset_path",
                f"/app/{FILE_SHARE_NAME}/{request_id}/{CSV_FILENAME}",
                "--output_dir",
                f"/app/{FILE_SHARE_NAME}/{request_id}",
            ],
            volume_mounts=[
                VolumeMount(
                    name=f"{FILE_SHARE_NAME}-volume",
                    mount_path=f"/app/{FILE_SHARE_NAME}",
                )
            ],
        )
        container_group = ContainerGroup(
            containers=[container],
            os_type=OperatingSystemTypes.LINUX,
            image_registry_credentials=[
                ImageRegistryCredential(
                    server=CONTAINER_REGISTRY_SERVER,
                    username=CONTAINER_REGISTRY_USERNAME,
                    password=CONTAINER_REGISTRY_PASSWORD,
                )
            ],
            restart_policy=ContainerGroupRestartPolicy.NEVER,
            volumes=[volume],
            location=LOCATION,
        )
        poller = container_instance_client.container_groups.begin_create_or_update(
            resource_group_name=RESOURCE_GROUP,
            container_group_name=request_id,
            container_group=container_group,
        )
        result = poller.result(timeout=CSV_PROFILE_TIMEOUT_SECONDS)
        if (
            result
            and result.instance_view
            and result.instance_view.state != "Succeeded"
        ):
            logs = container_instance_client.containers.list_logs(
                resource_group_name=RESOURCE_GROUP,
                container_group_name=request_id,
                container_name="csv-profiler",
            )
            logs_str = (logs.content or "").strip()
            return {
                "ok": False,
                "response": logs_str if logs_str else "Failed to profile CSV",
            }
    except Exception:
        logger.exception(f"Failed to profile CSV - {request_id}")
        return {
            "ok": False,
            "response": "Failed to profile CSV",
        }
    finally:
        try:
            container_instance_client.container_groups.begin_delete(
                resource_group_name=RESOURCE_GROUP,
                container_group_name=request_id,
            )
        except Exception:
            logger.exception(f"Failed to delete container group - {request_id}")

    try:
        profile_result_file = request_dir.get_file_client(CSV_PROFILE)
        profile_result_str = profile_result_file.download_file().readall().decode()
        profile_result = json.loads(profile_result_str)
    except Exception:
        logger.exception(f"Failed to read CSV profiling results - {request_id}")
        return {
            "ok": False,
            "response": "Failed to read CSV profiling results",
        }

    return {
        "ok": True,
        "response": profile_result,
    }


def train_model(training_config_str: str) -> dict:
    """Train a machine learning model with the uploaded dataset.

    This tool trains a model using the CSV file that was previously uploaded and profiled.
    It requires a request ID from generate_request_id() and accepts various configuration
    parameters for model training, preprocessing, and evaluation.

    Args:
        training_config_str (str): JSON string containing training configuration parameters

    Returns:
        dict: Response containing:
            - ok (bool): True if successful, False otherwise
            - response: Training results with model metadata (dict) on success, or error message (str) on failure

    JSON Schema:
    {
        "request_id": {
            "title": "Request Id",
            "type": "string"
        },
        "task_type": {
            "description": "Type of machine learning task",
            "enum": [
                "regression",
                "classification"
            ],
            "title": "Task Type",
            "type": "string"
        },
        "target": {
            "description": "Target column name",
            "title": "Target",
            "type": "string"
        },
        "features": {
            "default": "",
            "description": "Comma-separated feature column names",
            "title": "Features",
            "type": "string"
        },
        "model_type": {
            "default": "auto",
            "description": "Type of machine learning model",
            "enum": [
                "auto",
                "random_forest",
                "svm",
                "linear"
            ],
            "title": "Model Type",
            "type": "string"
        },
        "n_estimators": {
            "default": 100,
            "description": "Number of estimators for random forest",
            "exclusiveMinimum": 0,
            "maximum": 1000,
            "title": "N Estimators",
            "type": "integer"
        },
        "svm_kernel": {
            "default": "rbf",
            "description": "Kernel type for SVM",
            "enum": [
                "linear",
                "poly",
                "rbf",
                "sigmoid"
            ],
            "title": "Svm Kernel",
            "type": "string"
        },
        "missing_strategy": {
            "default": "median",
            "description": "Strategy for handling missing values",
            "enum": [
                "drop",
                "mean",
                "median",
                "most_frequent"
            ],
            "title": "Missing Strategy",
            "type": "string"
        },
        "remove_outliers": {
            "default": false,
            "description": "Flag to remove outliers",
            "title": "Remove Outliers",
            "type": "boolean"
        },
        "scaler_type": {
            "default": "none",
            "description": "Type of feature scaler",
            "enum": [
                "none",
                "standard",
                "minmax",
                "robust"
            ],
            "title": "Scaler Type",
            "type": "string"
        },
        "test_size": {
            "default": 0.2,
            "description": "Proportion of dataset for testing",
            "exclusiveMaximum": 0.5,
            "minimum": 0.1,
            "title": "Test Size",
            "type": "number"
        },
        "random_state": {
            "default": 42,
            "description": "Random seed for reproducibility",
            "minimum": 0,
            "title": "Random State",
            "type": "integer"
        },
        "required": [
            "request_id",
            "task_type",
            "target"
        ],
        "type": "object"
    }
    """
    try:
        training_config_dict = json.loads(training_config_str)
        training_config = ModelTrainingConfig(**training_config_dict)
    except json.JSONDecodeError as e:
        return {
            "ok": False,
            "response": f"Invalid JSON format - {str(e)}",
        }
    except Exception as e:
        return {
            "ok": False,
            "response": f"Validation error - {str(e)}",
        }

    request_id = training_config.request_id

    try:
        request_dir = file_share_client.get_directory_client(request_id)
        if not request_dir.exists():
            return {
                "ok": False,
                "response": "Invalid request ID",
            }
    except Exception:
        logger.exception(f"Failed to verify request ID - {request_id}")
        return {
            "ok": False,
            "response": "Failed to verify request ID",
        }

    try:
        csv_file = request_dir.get_file_client(CSV_FILENAME)
        if not csv_file.exists():
            return {
                "ok": False,
                "response": "CSV file not found—please upload the CSV first",
            }
    except Exception:
        logger.exception(f"Failed to access request dir - {request_id}")
        return {
            "ok": False,
            "response": "Failed to access request dir",
        }

    command = [
        "python",
        MODEL_TRAINER_SCRIPT,
        "--dataset_path",
        f"/app/{FILE_SHARE_NAME}/{request_id}/{CSV_FILENAME}",
        "--output_dir",
        f"/app/{FILE_SHARE_NAME}/{request_id}/{PIPELINE_DIR}",
        "--task_type",
        training_config.task_type,
        "--target",
        training_config.target,
        "--model_type",
        training_config.model_type,
        "--n_estimators",
        str(training_config.n_estimators),
        "--svm_kernel",
        training_config.svm_kernel,
        "--missing_strategy",
        training_config.missing_strategy,
        "--scaler_type",
        training_config.scaler_type,
        "--test_size",
        str(training_config.test_size),
        "--random_state",
        str(training_config.random_state),
    ]
    if training_config.features:
        command.extend(["--features", training_config.features])
    if training_config.remove_outliers:
        command.append("--remove_outliers")

    try:
        volume = Volume(
            name=f"{FILE_SHARE_NAME}-volume",
            azure_file=AzureFileVolume(
                share_name=FILE_SHARE_NAME,
                storage_account_name=STORAGE_ACCOUNT_NAME,
                storage_account_key=STORAGE_ACCOUNT_KEY,
            ),
        )
        container = Container(
            name="model-trainer",
            image=f"{CONTAINER_REGISTRY_SERVER}/{MODEL_TRAINER_IMAGE}",
            resources=ResourceRequirements(
                requests=ResourceRequests(
                    memory_in_gb=TRAINER_MEMORY_GB,
                    cpu=TRAINER_CPU,
                )
            ),
            command=command,
            volume_mounts=[
                VolumeMount(
                    name=f"{FILE_SHARE_NAME}-volume",
                    mount_path=f"/app/{FILE_SHARE_NAME}",
                )
            ],
        )
        container_group = ContainerGroup(
            containers=[container],
            os_type=OperatingSystemTypes.LINUX,
            image_registry_credentials=[
                ImageRegistryCredential(
                    server=CONTAINER_REGISTRY_SERVER,
                    username=CONTAINER_REGISTRY_USERNAME,
                    password=CONTAINER_REGISTRY_PASSWORD,
                )
            ],
            restart_policy=ContainerGroupRestartPolicy.NEVER,
            volumes=[volume],
            location=LOCATION,
        )
        poller = container_instance_client.container_groups.begin_create_or_update(
            resource_group_name=RESOURCE_GROUP,
            container_group_name=request_id,
            container_group=container_group,
        )
        result = poller.result(timeout=MODEL_TRAINING_TIMEOUT_SECONDS)
        if (
            result
            and result.instance_view
            and result.instance_view.state != "Succeeded"
        ):
            logs = container_instance_client.containers.list_logs(
                resource_group_name=RESOURCE_GROUP,
                container_group_name=request_id,
                container_name="model-trainer",
            )
            logs_str = (logs.content or "").strip()
            return {
                "ok": False,
                "response": logs_str if logs_str else "Failed to train model",
            }
    except Exception:
        logger.exception(f"Failed to train model - {request_id}")
        return {
            "ok": False,
            "response": "Failed to train model",
        }
    finally:
        try:
            container_instance_client.container_groups.begin_delete(
                resource_group_name=RESOURCE_GROUP,
                container_group_name=request_id,
            )
        except Exception:
            logger.exception(f"Failed to delete container group - {request_id}")

    try:
        pipeline_dir = file_share_client.get_directory_client(
            f"{request_id}/{PIPELINE_DIR}"
        )
        pipeline_meta_file = pipeline_dir.get_file_client(PIPELINE_META)
        pipeline_meta_str = pipeline_meta_file.download_file().readall().decode()
        pipeline_meta = json.loads(pipeline_meta_str)
    except Exception:
        logger.exception(f"Failed to read training results - {request_id}")
        return {
            "ok": False,
            "response": "Failed to read training results",
        }

    return {
        "ok": True,
        "response": pipeline_meta,
    }


def deploy_model(request_id: str) -> dict:
    """Deploy a trained machine learning model to a live server.

    This tool takes the trained model from the Azure file share and deploys it to a
    dedicated container app with a Gradio interface. The model must be trained first
    using train_model(). The deployment creates a web interface for making predictions.

    Args:
        request_id (str): The request ID from generate_request_id()

    Returns:
        dict: Response containing:
            - ok (bool): True if successful, False otherwise
            - response: Preview URL (str) on success, or error message (str) on failure
    """
    try:
        request_dir = file_share_client.get_directory_client(request_id)
        if not request_dir.exists():
            return {
                "ok": False,
                "response": "Invalid request ID",
            }
    except Exception:
        logger.exception(f"Failed to verify request ID - {request_id}")
        return {
            "ok": False,
            "response": "Failed to verify request ID",
        }

    try:
        pipeline_dir = file_share_client.get_directory_client(
            f"{request_id}/{PIPELINE_DIR}"
        )
        pipeline_model_file = pipeline_dir.get_file_client(PIPELINE_MODEL)
        if not pipeline_model_file.exists():
            return {
                "ok": False,
                "response": "Model file not found—please train the model first",
            }
    except Exception:
        logger.exception(f"Failed to access request dir - {request_id}")
        return {
            "ok": False,
            "response": "Failed to access request dir",
        }

    try:
        container_app_definition = {
            "location": LOCATION,
            "environmentId": CONTAINER_APP_ENVIRONMENT_ID,
            "configuration": {
                "ingress": {
                    "external": True,
                    "targetPort": 7860,
                    "transport": "auto",
                },
                "secrets": [
                    {
                        "name": "registry-password",
                        "value": CONTAINER_REGISTRY_PASSWORD,
                    }
                ],
                "registries": [
                    {
                        "server": CONTAINER_REGISTRY_SERVER,
                        "username": CONTAINER_REGISTRY_USERNAME,
                        "passwordSecretRef": "registry-password",
                    }
                ],
            },
            "template": {
                "containers": [
                    {
                        "name": "model-server",
                        "image": f"{CONTAINER_REGISTRY_SERVER}/{MODEL_SERVER_IMAGE}",
                        "resources": {
                            "cpu": SERVER_CPU,
                            "memory": f"{SERVER_MEMORY_GB}Gi",
                        },
                        "command": [
                            "python",
                            MODEL_SERVER_SCRIPT,
                            "--model_dir",
                            f"/app/{FILE_SHARE_NAME}/{request_id}/{PIPELINE_DIR}",
                        ],
                        "volumeMounts": [
                            {
                                "volumeName": f"{FILE_SHARE_NAME}-volume",
                                "mountPath": f"/app/{FILE_SHARE_NAME}",
                            }
                        ],
                    }
                ],
                "volumes": [
                    {
                        "name": f"{FILE_SHARE_NAME}-volume",
                        "storageType": "AzureFile",
                        "storageName": FILE_SHARE_NAME,
                    }
                ],
                "scale": {
                    "minReplicas": 1,
                    "maxReplicas": 1,
                },
            },
        }
        poller = container_app_client.container_apps.begin_create_or_update(
            resource_group_name=RESOURCE_GROUP,
            container_app_name=f"model-{request_id[:20].lower()}",
            container_app_envelope=container_app_definition,
        )
        result = poller.result(timeout=MODEL_DEPLOYMENT_TIMEOUT_SECONDS)
        if result and result.provisioning_state == "Succeeded":
            fqdn = getattr(result.configuration.ingress, "fqdn", None)
            if fqdn:
                return {
                    "ok": True,
                    "response": f"https://{fqdn}",
                }
            else:
                logger.error(f"Deployment succeeded but FQDN is missing - {request_id}")
                return {
                    "ok": False,
                    "response": "Failed to deploy model",
                }
        else:
            state = result.provisioning_state if result else "Unknown"
            logger.error(f"Deployment failed with state: {state} - {request_id}")
            return {
                "ok": False,
                "response": "Failed to deploy model",
            }
    except Exception:
        logger.exception(f"Failed to deploy model - {request_id}")
        return {
            "ok": False,
            "response": "Failed to deploy model",
        }
