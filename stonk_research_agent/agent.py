import os
import asyncio
import json
from dotenv import load_dotenv

# Import Agent SDK components
try:
    from agents import Agent, Runner, WebSearchTool
except ImportError:
    print("ERROR: Failed to import 'agents' library components. Make sure 'openai-agents' is installed.")
    # Define dummy classes if import fails
    class Agent:
        pass
    class Runner:
        pass
    class WebSearchTool:
        def __init__(self, **kwargs):
            pass

# Import the newly created tools
try:
    from .tools import (
        get_yahoo_quote,
        get_finnhub_news,
        get_alphavantage_overview,
        get_fred_series,
        get_eia_series,
        get_newsapi_headlines
    )
except ImportError:
     print("ERROR: Failed to import tools from stonk_research_agent.tools. Make sure the file exists and is correct.")
     # Define dummy functions
     def get_yahoo_quote(**kwargs): return {"error": "Tool import failed"}
     def get_finnhub_news(**kwargs): return {"error": "Tool import failed"}
     def get_alphavantage_overview(**kwargs): return {"error": "Tool import failed"}
     def get_fred_series(**kwargs): return {"error": "Tool import failed"}
     def get_eia_series(**kwargs): return {"error": "Tool import failed"}
     def get_newsapi_headlines(**kwargs): return {"error": "Tool import failed"}


# Load environment variables (primarily for OPENAI_API_KEY, tools load their own)
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL_ID = os.getenv("OPENAI_MODEL_ID")

# --- Agent Definition ---

STONK_RESEARCH_INSTRUCTIONS = """
You are the Stonk Research Agent, a specialized financial research assistant.
Your goal is to provide comprehensive information about a given stock symbol or company by utilizing the available tools.

Available Tools:
- `get_yahoo_quote`: Fetches near real-time stock quote data (price, volume, market cap, etc.).
- `get_finnhub_news`: Retrieves recent company-specific news articles from Finnhub.
- `get_alphavantage_overview`: Provides company overview details (sector, industry, description).
- `get_fred_series`: Fetches data for specific US economic indicators from FRED (e.g., 'UNRATE' for unemployment, 'GDP').
- `get_eia_series`: Fetches data for specific US energy indicators from EIA (e.g., oil prices).
- `get_newsapi_headlines`: Searches for recent general news headlines related to a query.
- `WebSearchTool`: Performs a web search for any information not covered by other tools.

Workflow:
1.  Understand the user's request (e.g., "Research Apple", "Get latest AAPL quote and news", "Find unemployment rate and WTI oil price").
2.  Identify the most relevant tool(s) to answer the request. You may need to call multiple tools.
3.  Call the necessary tools with appropriate arguments (stock symbols, series IDs, search queries).
4.  Synthesize the information gathered from the tools into a concise and informative summary for the user.
5.  If a tool returns an error, report the error clearly to the user but try to continue with other tools if possible.
6.  Use the `WebSearchTool` for broader context or information not available through the specialized tools.
"""

# Instantiate the agent
try:
    # Define the list of tools
    stonk_tools = [
        get_yahoo_quote,
        get_finnhub_news,
        get_alphavantage_overview,
        get_fred_series,
        get_eia_series,
        get_newsapi_headlines
    ]

    stonk_research_agent = Agent(
        name="StonkResearchAgent",
        instructions=STONK_RESEARCH_INSTRUCTIONS,
        # output_type=None, # Default output is string, suitable for summaries
        tools=stonk_tools,
        model=OPENAI_MODEL_ID
    )
    print("StonkResearchAgent initialized successfully.")

except Exception as e:
    print(f"Error initializing StonkResearchAgent: {e}")
    stonk_research_agent = None # Ensure agent is None if init fails

# --- Main Execution Logic (Example) ---

async def main(user_query: str):
    """Runs the Stonk Research Agent with a user query."""
    if not stonk_research_agent:
        print("Agent failed to initialize. Exiting.")
        return

    print(f"\n--- Running Stonk Research Agent for query: '{user_query}' ---")

    try:
        # Use Runner.run to execute the agent
        result = await Runner.run(stonk_research_agent, user_query)

        print("\n--- Agent Final Output ---")
        print(result.final_output)

        # Optional: Print intermediate steps/tool calls for debugging
        # print("\n--- Agent Run Trace ---")
        # for item in result.new_items:
        #     print(item) # Adjust printing based on item type

    except Exception as e:
        print(f"\n--- Agent Run Error ---")
        print(f"An unexpected error occurred: {e}")


if __name__ == "__main__":
    # Example queries to test the agent
    # query1 = "Give me the latest quote and recent news for Microsoft (MSFT)."
    # query2 = "What is the current US unemployment rate (UNRATE) and WTI spot price (PET.W_EPC0_FPF_Y48SE_DPG.W)?"
    query3 = "Research NVIDIA (NVDA), include company overview, recent news, and current stock price."

    asyncio.run(main(user_query=query3))
    print("\nStonk Research Agent run finished.")
