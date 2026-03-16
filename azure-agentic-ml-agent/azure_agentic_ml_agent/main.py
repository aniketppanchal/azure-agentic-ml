import ast
import json
import logging

import chainlit as cl
from agent_framework import Agent, AgentSession, MCPStreamableHTTPTool
from agent_framework.azure import AzureAIAgentClient
from azure.identity.aio import DefaultAzureCredential
from config import settings

logging.getLogger("azure").setLevel(logging.ERROR)
logging.getLogger("httpx").setLevel(logging.ERROR)

# =============================================================================
# AZURE AI AGENT CONFIGURATION
# =============================================================================
PROJECT_ENDPOINT = str(settings.project_endpoint)
MODEL_DEPLOYMENT_NAME = settings.model_deployment_name

# =============================================================================
# MCP TOOL SERVER CONFIGURATION
# =============================================================================
MCP_URL = str(settings.mcp_url)

# =============================================================================
# AGENT SYSTEM PROMPT
# =============================================================================
SYSTEM_PROMPT = """You are the Azure AgenticML assistant.

Your role is to orchestrate machine learning workflows on Azure by
calling tools provided by the Azure AgenticML MCP server.

Typical workflow:
1. Generate a request ID.
2. Upload and profile the dataset.
3. Train the model.
4. Deploy the model.

Guidelines:
1. Use tools to perform all operations.
2. Explain the result clearly after a tool returns a response.
3. Format all responses using clear, well-structured Markdown."""


@cl.on_chat_start
async def on_chat_start() -> None:
    agent = Agent(
        client=AzureAIAgentClient(
            project_endpoint=PROJECT_ENDPOINT,
            model_deployment_name=MODEL_DEPLOYMENT_NAME,
            credential=DefaultAzureCredential(),
        ),
        instructions=SYSTEM_PROMPT,
        name="Azure AgenticML Agent",
    )
    agent_session = AgentSession()
    mcp_server = MCPStreamableHTTPTool(
        name="Azure AgenticML MCP",
        url=MCP_URL,
    )

    cl.user_session.set("agent", agent)
    cl.user_session.set("agent_session", agent_session)
    cl.user_session.set("mcp_server", mcp_server)


@cl.on_message
async def on_message(query: cl.Message) -> None:
    agent: Agent = cl.user_session.get("agent")
    agent_session: AgentSession = cl.user_session.get("agent_session")
    mcp_server: MCPStreamableHTTPTool = cl.user_session.get("mcp_server")

    response = cl.Message(content="")
    steps: dict[str, cl.Step] = {}

    async for chunk in agent.run(
        query.content,
        stream=True,
        session=agent_session,
        tools=mcp_server,
    ):
        for content in chunk.contents:
            if content.type == "text":
                await response.stream_token(content.text)

            elif content.type == "function_call":
                step = cl.Step(name=content.name, type="tool")
                args = content.arguments
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except Exception:
                        pass

                step.input = f"```json\n{json.dumps(args, indent=2, default=str)}\n```"
                await step.send()
                if content.call_id:
                    steps[content.call_id] = step

            elif content.type == "function_result":
                if not (step := steps.get(content.call_id)):
                    continue

                out = content.result
                if isinstance(out, str):
                    try:
                        out = json.loads(out)
                    except Exception:
                        try:
                            out = ast.literal_eval(out)
                        except Exception:
                            pass

                step.output = f"```json\n{json.dumps(out, indent=2, default=str)}\n```"
                await step.update()
                del steps[content.call_id]

    await response.update()
