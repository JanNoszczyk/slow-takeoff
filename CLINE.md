# Cline Agent Documentation (`openai-agents` SDK Usage)

This document explains the structure and execution flow of agents built using the `openai-agents` SDK within this project, using the `stonk_research_agent` as the primary example.

## Core Concepts

1.  **Agent (`Agent` class):**
    *   The primary decision-making entity.
    *   Defined with instructions (prompt), a set of available tools, and optionally specific model settings or output types.
    *   Example: `StonkResearchAgent` in `stonk_research_agent/agent.py`. Its behavior is governed by the `STONK_RESEARCH_INSTRUCTIONS`.

2.  **Tools (`@function_tool`, `WebSearchTool`, etc.):**
    *   Represent actions the agent can take.
    *   Can be Python functions decorated with `@function_tool` (like `run_full_research` in `stonk_research_agent/tools.py`), built-in tools (`WebSearchTool`), or even other agents (`agent.as_tool()`).
    *   The Agent's instructions dictate *when* and *how* these tools should be used.
    *   Function tools execute their own predefined Python logic based on arguments passed by the agent.

3.  **Runner (`Runner` class):**
    *   The orchestrator that manages the interaction loop between the user, the agent, the LLM, and the tools.
    *   Takes the agent and user input (`query`).
    *   Sends the input and agent instructions to the LLM.
    *   Handles the LLM's response:
        *   If it's a final output, returns it.
        *   If it's a tool call, executes the tool function (`on_invoke_tool`).
        *   Sends the tool's result back to the LLM for synthesis.
        *   Repeats until a final output is generated or limits are reached.

## `stonk_research_agent` Example Workflow

1.  **User Query:** A user provides a query (e.g., "Research Apple").
2.  **Runner Invocation:** The code calls `await Runner.run(stonk_research_agent, query)`.
3.  **Agent Decision (LLM Call 1):**
    *   The `Runner` sends the `query` and the `StonkResearchAgent`'s `STONK_RESEARCH_INSTRUCTIONS` to the LLM.
    *   Based on the `CORE DIRECTIVE` in the instructions ("*For ANY request involving a specific company... MUST use `run_full_research`*"), the LLM determines that the `run_full_research` tool should be called.
    *   The LLM generates the necessary arguments for the tool (e.g., `symbol='AAPL'`).
4.  **Tool Execution:**
    *   The `Runner` receives the tool call request.
    *   It invokes the `run_full_research` Python function (defined in `stonk_research_agent/tools.py`) with the arguments provided by the LLM.
    *   The `run_full_research` function executes its logic (internally calling other functions like `get_yahoo_quote`, `get_finnhub_news`, etc.) and returns a consolidated result (e.g., a dictionary or JSON string with quote, news, and overview data).
5.  **Result Synthesis (LLM Call 2):**
    *   The `Runner` sends the result returned by the `run_full_research` function back to the LLM, along with the conversation history.
    *   The LLM synthesizes this data into a user-friendly final response, following any formatting instructions in the agent's prompt.
6.  **Final Output:** The `Runner.run` call returns a `RunResult` object containing the `final_output` string generated in the previous step.

## Recommended SDK Usage Pattern

The standard way to execute an agent is:

```python
import asyncio
from stonk_research_agent.agent import stonk_research_agent # Import your agent instance
from agents import Runner # Import the Runner

async def run_agent_task(query: str):
    if not stonk_research_agent: # Check if agent initialized correctly
        print("Agent not initialized.")
        return

    print(f"Running agent task for: {query}")
    try:
        # Pass the agent instance and user query to Runner.run
        result = await Runner.run(stonk_research_agent, query)

        print("\n--- Final Output ---")
        print(result.final_output)

        # Optional: Inspect intermediate steps
        # for item in result.new_items:
        #     print(item)

    except Exception as e:
        print(f"An error occurred during the agent run: {e}")

# Example usage
if __name__ == "__main__":
    user_query = "Give me a full research report on Microsoft (MSFT)."
    asyncio.run(run_agent_task(user_query))
```

## Additional Context: `openai_docs.md`

For more detailed examples and explanations of various `openai-agents` SDK features (like guardrails, handoffs, streaming, different tool types), please refer to the contents of the `openai_docs.md` file located in the project root. This file contains relevant excerpts from the official OpenAI Agents documentation.
