import os
import asyncio
import json
from dotenv import load_dotenv

# Import Agent SDK components
try:
    # Try importing specific item types first
    from agents.items import ToolCallOutputItem
    from agents import Agent, Runner, WebSearchTool
    print("DEBUG: Successfully imported Agent SDK components including ToolCallOutputItem.")
except ImportError:
    # Fallback if ToolCallOutputItem is not directly available (older version?)
    print("WARNING: Could not import ToolCallOutputItem directly. Will rely on generic item checking.")
    try:
        from agents import Agent, Runner, WebSearchTool, FunctionToolResult
        ToolCallOutputItem = None # Indicate it's not available
        print("DEBUG: Imported Agent SDK components using FunctionToolResult fallback.")
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
        # Define dummy types/vars used later
        ToolCallOutputItem = None
        FunctionToolResult = None

# Import the newly created tools
try:
    from .tools import (
        get_yahoo_quote,
        get_finnhub_news,
        get_alphavantage_overview,
        get_fred_series,
        get_eia_series,
        get_newsapi_headlines,
        run_full_research
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
     def run_full_research(**kwargs): return '{"error": "Tool import failed"}'


# Load environment variables (primarily for OPENAI_API_KEY, tools load their own)
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL_ID = os.getenv("OPENAI_MODEL_ID")

# --- Agent Definition ---

STONK_RESEARCH_INSTRUCTIONS = """
You are the Stonk Research Agent, a specialized financial research assistant. Your goal is to synthesize comprehensive information efficiently using structured data tools and web search.

**Core Principles:**
1.  **Structured Data First:** For ANY request mentioning a specific company name or ticker symbol (e.g., "Apple", "MSFT", "NVIDIA", "NVDA"), you **MUST** use the `run_full_research` tool as your FIRST step to gather core quote, news, and overview data. No exceptions.
2.  **Web Search for Context:** AFTER using `run_full_research`, you **MUST** also use the `WebSearchTool` to supplement the structured data. Search for recent events, analysis, sentiment, market context, or qualitative information not captured by the specific APIs.
3.  **Synthesize:** Combine insights from both `run_full_research` (structured JSON) and `WebSearchTool` (web results) into a cohesive final answer.
4.  **Label Sources:** Clearly indicate the source for each piece of information (e.g., "Quote (via run_full_research/Yahoo)", "Recent Analysis (via WebSearchTool)").

**Available Tools:**
- `run_full_research`: **(Primary for Structured Company Data)** Gathers quote, news (Finnhub, NewsAPI), and overview data for a stock symbol. Returns structured JSON. Use this FIRST for any company-specific query. Can optionally include FRED/EIA series.
- `WebSearchTool`: **(Primary for Context & Recent Events)** Performs a web search. Use this alongside `run_full_research` for company queries to find recent analysis, broader market context, sentiment, or information not in the structured APIs. Also use for general financial topic queries.
- `get_fred_series`: Fetches specific US economic indicators from FRED (e.g., 'UNRATE'). Use directly *only* if this is the sole data requested.
- `get_eia_series`: Fetches specific US energy indicators from EIA (e.g., oil prices). Use directly *only* if this is the sole data requested.
- `get_newsapi_headlines`: Fetches general news headlines for non-company queries (e.g., "semiconductor industry news"). Use directly *only* if this is the sole data requested.

**Workflow:**
1.  **Analyze Request:** Determine if the query mentions a specific company name or symbol.
2.  **Company Research (Mandatory First Step):**
    a.  If a company name/symbol IS mentioned: Execute `run_full_research` **IMMEDIATELY**. Use the identified symbol(s). **Default `news_count` to 5 if not specified by the user.** Include any requested FRED/EIA series. This step is **NON-NEGOTIABLE** for company queries.
    b.  After `run_full_research` completes: Execute `WebSearchTool` with relevant queries (e.g., "[Company Name] recent news", "[Symbol] stock analysis", "[Company Name] market sentiment") to gather context and recent qualitative insights. This step is also **MANDATORY** for company queries.
    c.  Synthesize the structured JSON output from `run_full_research` and the text results from `WebSearchTool` into a comprehensive report. Label all sources clearly.
3.  **Specific Economic/Energy Data:** If the user *only* asks for FRED or EIA data (and NO company is mentioned), use `get_fred_series` or `get_eia_series` respectively.
4.  **General Topic/News:** If the user asks about a general topic or non-company news (and NO company is mentioned), use `WebSearchTool` and/or `get_newsapi_headlines`.
5.  **Failure Handling:** If `run_full_research` is attempted and fails, clearly state this, then proceed with `WebSearchTool` for alternative information gathering.
6.  **Output:** Provide a well-structured, synthesized answer combining insights from all tools used, with clear source attribution for each section.
"""

# Instantiate the agent
try:
    # Define the list of tools, including WebSearchTool
    stonk_tools = [
        run_full_research,         # Primary structured data tool
        WebSearchTool(),           # Primary context/web tool
        get_fred_series,           # Specific use tool
        get_eia_series,            # Specific use tool
        get_newsapi_headlines,     # Specific use tool
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

        # --- Save run_full_research output if found ---
        saved_output = False
        print(f"DEBUG: Checking result.new_items (type: {type(result.new_items)}, length: {len(result.new_items) if hasattr(result.new_items, '__len__') else 'N/A'})")

        # Determine which item type holds the tool output (ToolCallOutputItem preferred)
        valid_output_item_type = ToolCallOutputItem # From import at top

        if valid_output_item_type:
            print(f"DEBUG: Will check for items of type {valid_output_item_type.__name__}")
            for i, item in enumerate(result.new_items):
                print(f"DEBUG: Item {i}: type={type(item)}")
                is_tool_output_item = isinstance(item, valid_output_item_type)

                if is_tool_output_item:
                    # Get output and associated tool call ID (if available)
                    tool_call_id = getattr(item, 'tool_call_id', 'N/A')
                    item_output_obj = getattr(item, 'output', None)
                    item_output_str = str(item_output_obj) if item_output_obj is not None else ""

                    print(f"DEBUG: Item {i}: Is {valid_output_item_type.__name__}? {is_tool_output_item}, tool_call_id='{tool_call_id}', output_snippet='{item_output_str[:50]}...'")

                    # Heuristic check: Does the output *look* like the JSON from run_full_research?
                    # This is brittle but necessary without a definitive tool_name on ToolCallOutputItem.
                    # A better approach might involve finding the corresponding ToolCallItem via tool_call_id.
                    looks_like_research_output = isinstance(item_output_obj, str) and item_output_str.strip().startswith('{\n  "report": [')

                    if looks_like_research_output:
                        print(f"DEBUG: Found item {i} that looks like 'run_full_research' output based on content.")
                        try:
                            json_output_str = item_output_obj # Already confirmed it's a string
                            # Attempt to pretty-print
                            try:
                                parsed_json = json.loads(json_output_str)
                                pretty_json = json.dumps(parsed_json, indent=2)
                            except json.JSONDecodeError:
                                print("\n--- Warning: run_full_research output was not valid JSON, saving raw string. ---")
                                pretty_json = json_output_str # Save the raw string

                            # Save the file
                            output_filename = "stonk_research_output.json"
                            with open(output_filename, "w") as f:
                                f.write(pretty_json)
                            print(f"\n--- Saved run_full_research output to {output_filename} ---")
                            saved_output = True
                            break # Save only the first occurrence

                        except Exception as write_e:
                            print(f"\n--- Error saving run_full_research output: {write_e} ---")
                            # Optionally print the raw output that failed to save
                            # print(f"Raw output was: {item_output_obj}")
                    else:
                        print(f"DEBUG: Item {i} did not match expected start of run_full_research JSON.")
                else:
                     print(f"DEBUG: Item {i} is not of type {valid_output_item_type.__name__}.")

        else:
             print("DEBUG: Cannot check for tool output items because ToolCallOutputItem type is not available.")

        if not saved_output:
             print("\n--- Note: run_full_research tool output not found or not saved. ---")


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
