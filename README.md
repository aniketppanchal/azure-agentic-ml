<img
  src="https://res.cloudinary.com/djeszvhyx/image/upload/v1773504901/logo_etsph4.png"
  width="100px"
/>

# Azure AgenticML

AI Agent for Building and Deploying Production ML Models on [Azure](https://portal.azure.com)

<p>
  <img
    src="https://img.shields.io/badge/Microsoft%20Agent%20Framework-0369a1?style=for-the-badge&logo=microsoft&logoColor=white"
  />
  <img
    src="https://img.shields.io/badge/Microsoft%20Foundry-0369a1?style=for-the-badge&logo=microsoft&logoColor=white"
  />
  <img
    src="https://img.shields.io/badge/Azure-0369a1?style=for-the-badge&logo=microsoft&logoColor=white"
  />
  <img
    src="https://img.shields.io/badge/license-MIT-0369a1?style=for-the-badge&logoColor=white"
  />
</p>

## 1. Demo Video

[YouTube](https://youtu.be/056zr-k9PJ4)

## 2. Screenshots

| Dataset Profiling                                                                                                | Training Result                                                                                              |
| ---------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------ |
| ![Dataset Profiling](https://res.cloudinary.com/djeszvhyx/image/upload/v1773617337/dataset_profiling_slbr7d.png) | ![Training Result](https://res.cloudinary.com/djeszvhyx/image/upload/v1773617337/training_result_ik4r5m.png) |

| Inference UI                                                                                           | GitHub Copilot Integration                                                                                                         |
| ------------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------- |
| ![Inference UI](https://res.cloudinary.com/djeszvhyx/image/upload/v1773617337/inference_ui_h5hrkr.png) | ![GitHub Copilot Integration](https://res.cloudinary.com/djeszvhyx/image/upload/v1773617338/github_copilot_integration_oyv9hc.png) |

## 3. The Problem: From Dataset to Deployment Is Too Complicated

Building and deploying a machine learning model has always required multiple people and involves several steps. A data scientist explores and profiles the data. An ML engineer decides the model architecture and training configuration. A DevOps engineer provisions infrastructure, containerizes the model, and manages the deployment pipeline. Even for something as simple as a CSV file with a clear prediction target, getting to a live inference endpoint takes days, not because the problem is hard, but because the process is fragmented.

The tools exist. The cloud infrastructure exists. The missing piece has always been intelligence, something that can look at a dataset, understand it, make the right decisions, and see the entire workflow through to deployment without needing a team of specialists at every step. AI agents now provide exactly that intelligence. The only question was whether someone would build the bridge between agentic AI and the machine learning lifecycle. That is what Azure AgenticML is.

Azure AgenticML is built for the data scientist who just wants insights, the ML engineer who just wants a trained model, and the software developer who simply wants a model deployed.

## 4. The Solution: From Dataset to Deployment with an AI Agent

Azure AgenticML is a fully autonomous machine learning system built on Microsoft Agent Framework and Microsoft Foundry. It combines a conversational AI agent with a purpose-built MCP server to take a user from a raw CSV file to a live, production-ready inference endpoint entirely through conversation, entirely on Azure.

The agent is the intelligence. When a user shares a CSV URL, the agent calls the MCP server to upload and profile the dataset. It receives back a rich statistical summary of the data: column types, distributions, missing values, and outliers, which it uses to autonomously determine the training configuration, including the task type, target column, feature set, model architecture, preprocessing strategy, and more. It then instructs the MCP server to train the model. Once training is complete, the agent can trigger deployment.

The MCP server is the execution engine. It handles every interaction with Azure infrastructure, including spinning up Azure Container Instances for ephemeral training jobs, provisioning Azure Container Apps for persistent model serving, managing artifacts through Azure Storage File Share, and pulling container images from Azure Container Registry.

The result is a live HTTPS inference endpoint backed by a schema-aware Gradio UI and a REST API ready for use within minutes of the user sharing their dataset. No ML expertise required. No DevOps expertise required. Just a conversation.

_Agent thinks. Azure AgenticML does the work. Azure runs the work safely and at scale._

## 5. Why Azure AgenticML Matters

AI agents are highly capable of understanding data. Given a dataset, an agent can quickly infer the task type, identify the target column, select useful features, and even decide reasonable hyperparameters. In most of the cases, this reasoning alone is enough to design a machine learning pipeline.

The challenge begins when that reasoning needs to be translated into real systems. Training jobs must run somewhere. Infrastructure must be provisioned. Models must be packaged and deployed. What begins as a simple idea quickly becomes a fragmented workflow involving scripts, containers, cloud resources, and deployment pipelines.

Azure AgenticML bridges this gap.

The project demonstrates that building and deploying a machine learning model can be reduced to a simple natural language interaction. Instead of manually orchestrating infrastructure and training pipelines, a user can simply provide a dataset and ask the agent to handle the rest. The agent analyzes the data, determines the correct training strategy, launches the necessary compute on Azure, trains the model, and deploys a production-ready inference endpoint automatically.

This enables rapid experimentation and prototyping. If a user wants to quickly test which model performs best on a dataset, they no longer need to write training code or configure infrastructure. They can simply ask the agent, and Azure AgenticML executes the full workflow.

The system is also designed to work across different platforms. Because its capabilities are exposed through an MCP server, Azure AgenticML can integrate with agentic environments such as GitHub Copilot Agent Mode. In the future, Azure AgenticML could become a natural extension of Azure AutoML, where intelligent agents handle not only model training but also the entire lifecycle from dataset to deployed service.

Azure AgenticML is intentionally simple. Adding many specialized agents does not automatically improve results. A focused agent with the right tools and infrastructure can often make better decisions and execute workflows more reliably.

## 6. System Architecture

![System Architecture](https://res.cloudinary.com/djeszvhyx/image/upload/v1773615752/architecture_rariwh.svg)

Azure AgenticML is composed of two components: the Azure AgenticML Agent and the Azure AgenticML MCP.

### Azure AgentML Agent

The user interacts with the Azure AgenticML Agent through a Chainlit UI. The agent is powered by Microsoft Agent Framework and Microsoft Foundry. Based on the user's request and the dataset profile it receives, the agent autonomously decides training parameters and orchestrates the full workflow by calling tools exposed by the MCP server.

### Azure AgentML MCP

The Azure AgenticML MCP runs independently and exposes four tools to the agent. It receives tool calls and handles all Azure infrastructure operations on behalf of the agent.

### Workflow

1. The user starts by sharing a CSV file URL with the agent through the Chainlit UI. The agent calls `generate_request_id`, and the MCP Server creates a dedicated workspace directory in Azure Storage File Share for the workflow.

2. The agent calls `upload_and_profile_csv`, and the MCP Server downloads the CSV and uploads it to Azure Storage File Share. It then provisions an Azure Container Instance using the `model-trainer:latest` image from Azure Container Registry. The container mounts the Azure Storage File Share, reads the dataset, profiles it, and writes the profile output back to the File Share. Once complete, the container is automatically destroyed. The profile is returned to the agent.

3. Using the profile, the agent decides the training configuration, such as task type, target column, feature set, preprocessing strategy, and model architecture, then calls `train_model`. The MCP Server provisions a new Azure Container Instance again using the `model-trainer:latest` image. The container mounts the File Share, reads the dataset CSV, trains the model, and saves the trained pipeline and metadata back to the File Share. The container is then destroyed, and the training results are returned to the agent.

4. The agent then calls `deploy_model`. The MCP Server provisions an Azure Container App using the `model-server:latest` image from Azure Container Registry. The Container App mounts the same Azure Storage File Share, reads the trained model and metadata, and launches the Gradio inference server. A live public HTTPS inference URL is returned to the user.

### Shared Storage

All containers share a common Azure Storage File Share, which acts as the artifact bus across the entire workflow:

| Path                                        | Contents                                    |
| ------------------------------------------- | ------------------------------------------- |
| `/<request_id>/dataset.csv`                 | Uploaded CSV dataset                        |
| `/<request_id>/csv_profile.json`            | Dataset profile from the CSV profiler       |
| `/<request_id>/pipeline/pipeline.joblib`    | Trained model from the model trainer        |
| `/<request_id>/pipeline/pipeline_meta.json` | Trained model metadata for the inference UI |

### Container Images

1. `model-trainer:latest`: Used for both CSV profiling and model training. When provisioned for profiling, it runs the CSV profiler script, which reads the dataset from the file share, computes statistical insights, and writes `csv_profile.json` back to the file share. When provisioned for training, it runs the model trainer script, which reads the dataset, applies the agent-specified preprocessing and training configuration, trains the model, and saves the `pipeline.joblib` and `pipeline_meta.json` to the File Share. In both cases the container is destroyed after the job completes.

2. `model-server:latest`: Used for model serving. When provisioned as an Azure Container App, it reads the trained `pipeline.joblib` and `pipeline_meta.json` from the file share and launches a Gradio inference server. The metadata drives the UI column types; valid categorical values and numeric ranges are used to automatically generate the appropriate input fields. The server remains live and accessible.

## 7. Core Capabilities

1. **Automated ML Workflow**: Azure AgenticML handles everything except the agent's reasoning. Once the agent decides what needs to be done, Azure AgenticML takes over the entire workflow from profiling the CSV, training the model, managing Azure infrastructure, and deploying the model automatically. Each deployed model runs inside its own isolated Azure Container App, ensuring strong security and clean separation.

2. **Powerful Dataset Profiler**: Azure AgenticML includes a dedicated CSV profiler that provides rich statistical insights, distributions, missing-value reports, outlier detection reports, and schema summaries. These insights give the agent the precise context it needs to choose the most effective training strategy.

3. **Flexible Model Trainer**: Azure AgenticML includes a dedicated model trainer that supports Random Forest, SVM, and linear models for both regression and classification tasks. Agents define the task type, target column, feature set, and additional configuration options related to preprocessing, dataset splitting, and model-specific settings.

4. **Automatic Model Deployment**: Azure AgenticML doesn't just train models; it deploys them on demand. When the agent requests a deployment, Azure AgenticML provisions a fresh, isolated Azure Container App; mounts the trained model artifacts from Azure Storage File Share; launches an inference server; and returns a live public HTTPS URL to the user.

5. **Schema-Aware Gradio Inference UI**: Azure AgenticML's inference UI is fully type-aware and schema-driven and is exposed through both an interactive Gradio UI and a REST API. When a model is trained, Azure AgenticML saves metadata for every feature's data types, valid categorical values, numeric ranges, and smart imputed defaults, which allows the deployed Gradio interface to automatically adapt; for example, if your CSV had a gender column with values male and female, the UI automatically renders a dropdown instead of a text box. Numeric fields display their observed training ranges, ideal for production use. The result is a self-adapting, intelligent inference UI with no manual setup required.

6. **Optimized for Speed**: You might think provisioning Azure infrastructure, profiling a CSV, training a model, and spinning up an inference server would take a lot of time, but it doesn't. Azure Container Instances are lightweight environments that start up extremely fast, and both the profiler and trainer are built to run quickly. The whole Azure AgenticML workflow feels surprisingly snappy from start to finish.

## 8. Microsoft & Azure Technologies

Azure AgenticML is built entirely on Microsoft and Azure services. The AI value is concentrated in the agent layer; it is the agent's reasoning capability, powered by Microsoft Agent Framework and Microsoft Foundry, that replaces the need for an ML engineer to manually analyze data and decide training parameters. Every other service in the stack exists to give that agent real execution power on Azure infrastructure, making the solution production-ready from conversation to deployment.

1. **Microsoft Agent Framework**<br>Powers the Azure AgenticML Agent, enables the agent to reason over dataset profiles, and autonomously orchestrates the full ML workflow by calling MCP tools.

2. **Microsoft Foundry**<br>Provides the underlying model that powers the Azure AgenticML Agent.

3. **Azure Container Apps**<br>Hosts the model inference server per deployment with public HTTPS ingress and persistent availability.

4. **Azure Container Instances**<br>Provisions ephemeral containers on demand for CSV profiling and model training, automatically destroyed after each job completes to minimize cost.

5. **Azure Container Registry**<br>Stores and serves the `model-trainer:latest` and `model-server:latest` container images.

6. **Azure Storage File Share**<br>Acts as the shared artifact bus across all containers, storing the dataset, profile, trained model, and metadata.

7. **Visual Studio Code**<br>Primary IDE for developing the entire project codebase.

8. **GitHub Copilot**<br>Assisted throughout development with code completion, suggestions, and accelerating implementation.

9. **GitHub**<br>Hosts the public repository for source code, version control, and project submissions.

## 9. Getting Started

### Prerequisites

- [Azure CLI](https://learn.microsoft.com/en-us/cli/azure/install-azure-cli)
- Python 3.11+

### Step 0: Authenticate with Azure

```bash
az login
```

### Step 1: Clone the Repository

```bash
git clone https://github.com/aniketppanchal/azure-agentic-ml
cd azure-agentic-ml
```

### Step 2: Provision MCP Server Resources

```bash
cd azure-agentic-ml-mcp
python3 -m venv .venv
```

**Linux/macOS:**

```bash
source .venv/bin/activate
pip install -r requirements.txt
chmod +x setup.sh && ./setup.sh
cd ..
```

**Windows:**

```powershell
.venv\Scripts\activate
pip install -r requirements.txt
powershell.exe -ExecutionPolicy Bypass -File .\setup.ps1
cd ..
```

### Step 3: Provision Agent Resources

```bash
cd azure-agentic-ml-agent
python3 -m venv .venv
```

**Linux/macOS:**

```bash
source .venv/bin/activate
pip install -r requirements.txt
chmod +x setup.sh && ./setup.sh
```

**Windows:**

```powershell
.venv\Scripts\activate
pip install -r requirements.txt
powershell.exe -ExecutionPolicy Bypass -File .\setup.ps1
```

> **Note:** Open the Microsoft Foundry portal URL printed by the script, deploy your model, and set `AZURE_AGENTICML_AGENT_MODEL_DEPLOYMENT_NAME` in the generated `.env` file.

### Step 4: Run the MCP Server and Agent

Both components need to run simultaneously, so open two separate terminals.

**Start the MCP Server**

```bash
cd azure-agentic-ml-mcp
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
python -m azure_agentic_ml_mcp.main
```

**Start the Agent**

```bash
cd azure-agentic-ml-agent
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
chainlit run azure_agentic_ml_agent/main.py
```

## 10. License

[MIT License](https://github.com/aniketppanchal/azure-agentic-ml/blob/main/LICENSE)

---

**Aniket Panchal** | aniket.prakash.panchal@gmail.com | [Microsoft Learn](https://learn.microsoft.com/en-us/users/aniketppanchal)<br>
**Akash Chaudhary** | akash.chaudhary@live.in | [Microsoft Learn](https://learn.microsoft.com/en-us/users/chaudharyakash)
