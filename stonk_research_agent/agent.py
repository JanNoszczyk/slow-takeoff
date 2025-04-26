import os
import asyncio
import json
from typing import Optional, Any
from dotenv import load_dotenv

# Import Agent SDK components
try:
    import agents # Try base import first
    print("DEBUG: Successfully imported base 'agents' package.")
    from agents.items import ToolCallOutputItem, MessageOutputItem
    from agents import Agent, Runner, WebSearchTool, FunctionToolResult, ItemHelpers # Added ItemHelpers
    print("DEBUG: Successfully imported specific Agent SDK components.")
except ImportError as e:
    print(f"ERROR: Failed to import 'agents' library components: {e}")
    # Define fallbacks if import fails
    class Agent: pass
    class Runner: pass
    class WebSearchTool:
        def __init__(self, **kwargs): pass
    ToolCallOutputItem = None
    MessageOutputItem = None
    FunctionToolResult = None

# Import tools and Pydantic models
try:
    from tools import (
        get_yahoo_quote, get_finnhub_news, get_alphavantage_overview,
        get_fred_series, get_eia_series, get_newsapi_headlines, run_full_research
    )
    # Import the main report structure and the new analysis-specific structure
    from tools import FullResearchReport, SymbolResearchData, WebSearchOutput, WebSearchNewsArticle, WebAnalysisOutput
    from pydantic import ValidationError, Field, HttpUrl
    print("DEBUG: Tools and Pydantic models imported successfully.")
except ImportError:
     print("ERROR: Failed to import tools or Pydantic models from tools.py.")
     # Define fallbacks
     def get_yahoo_quote(**kwargs): return {"error": "Tool import failed"}
     def get_finnhub_news(**kwargs): return {"error": "Tool import failed"}
     def get_alphavantage_overview(**kwargs): return {"error": "Tool import failed"}
     def get_fred_series(**kwargs): return {"error": "Tool import failed"}
     def get_eia_series(**kwargs): return {"error": "Tool import failed"}
     def get_newsapi_headlines(**kwargs): return {"error": "Tool import failed"}
     def run_full_research(**kwargs): return '{"error": "Tool import failed"}'
     FullResearchReport = None
     SymbolResearchData = None
     WebSearchOutput = None # Still needed for the final merged report structure
     WebSearchNewsArticle = None
     WebAnalysisOutput = None # The agent's direct output type
     ValidationError = None
     Field = None
     HttpUrl = None

# Load environment variables
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL_ID = os.getenv("OPENAI_MODEL_ID")

# --- Agent Definition (Updated Instructions & NEW output_type) ---
STONK_RESEARCH_INSTRUCTIONS = """
You are the Stonk Research Agent, a specialized financial research assistant. Your goal is to use tools to find information and then specifically analyze web search results for stock price impact, returning ONLY a structured `WebAnalysisOutput` object.

**Core Principles:**
1.  **Structured Data First:** For ANY request mentioning a specific company name or ticker symbol (e.g., "Apple", "MSFT", "NVIDIA", "NVDA"), you **MUST** use the `run_full_research` tool as your FIRST step. You will use the data provided by this tool implicitly in your analysis, but you will NOT include it directly in your final output object.
2.  **Web Search for Price Impact:** AFTER `run_full_research` completes, you **MUST** use the `WebSearchTool`. Focus on finding **recent news, events, or analysis that could potentially impact the stock price**.
3.  **Analyze and Populate `WebAnalysisOutput`:** Analyze the results from `WebSearchTool`. For the **top 5 most relevant** web sources found that discuss potential price impact, create a `WebSearchNewsArticle` object containing `headline`, `reason`, `transcript`, `sentiment_score`, and `source_url`.
4.  **Return ONLY `WebAnalysisOutput`:** Your SOLE task after running the tools and performing analysis is to construct and return a `WebAnalysisOutput` object. This object should contain:
    *   `overall_summary`: Your synthesized text summary of the **top 5** web search findings regarding price impact.
    *   `relevant_news`: A list of the `WebSearchNewsArticle` objects you created (limited to the **top 5** most relevant).
    *   `key_source_urls`: A list of the source URLs from the **top 5** relevant news articles.
    *   `error`: Any error message if the web search or analysis failed.
    You MUST return ONLY this `WebAnalysisOutput` object. Do NOT return the full `FullResearchReport`.

**Available Tools:**
- `run_full_research`: **(MANDATORY FIRST STEP for Company Queries)** Gathers base quote, news, overview data. Its output is used implicitly.
- `WebSearchTool`: **(MANDATORY SECOND STEP for Company Queries)** Performs web search. Use results to create the `WebAnalysisOutput`.
- `get_fred_series`, `get_eia_series`, `get_newsapi_headlines`: Use *only* for non-company specific queries (these will likely result in a text response, not `WebAnalysisOutput`).

**Workflow:**
1.  **Analyze Request:** Identify company symbol(s).
2.  **Company Research:**
    a.  Execute `run_full_research` (default `news_count=5`).
    b.  Execute `WebSearchTool` focusing on price impact queries.
    c.  Analyze web search results. For the **top 5** relevant sources, create a `WebSearchNewsArticle` object.
    d.  Construct the `WebAnalysisOutput` object, populating `overall_summary` (based on top 5), `relevant_news` (top 5), and `key_source_urls` (top 5).
    e.  Return ONLY the `WebAnalysisOutput` object.
3.  **Other Queries:** Use appropriate tools or `WebSearchTool` and return a text response.
4.  **Failure Handling:** If `WebSearchTool` fails, populate the `error` field in the `WebAnalysisOutput` object. If `run_full_research` fails, still try `WebSearchTool` and return the `WebAnalysisOutput`.
"""

# Instantiate the agent with the NEW output_type
try:
    # Check if necessary models are available before initializing
    if not all([FullResearchReport, WebAnalysisOutput]):
         raise ImportError("Required Pydantic models (FullResearchReport, WebAnalysisOutput) not loaded.")

    stonk_tools = [run_full_research, WebSearchTool(), get_fred_series, get_eia_series, get_newsapi_headlines]
    stonk_research_agent = Agent(
        name="StonkResearchAgent",
        instructions=STONK_RESEARCH_INSTRUCTIONS,
        tools=stonk_tools,
        output_type=WebAnalysisOutput, # Specify the NEW structured output type
        model=OPENAI_MODEL_ID
    )
    print("StonkResearchAgent initialized successfully with output_type=WebAnalysisOutput.")
except Exception as e:
    print(f"Error initializing StonkResearchAgent: {e}")
    stonk_research_agent = None


# --- Helper Function to Find Tool Output ---
def find_tool_output(items: list[Any], tool_name: str) -> Optional[str]:
    """Finds the output string of a specific tool call in the agent results."""
    # Determine the correct output item type based on availability
    output_item_type = ToolCallOutputItem if ToolCallOutputItem else FunctionToolResult
    if not output_item_type:
        print("DEBUG: Neither ToolCallOutputItem nor FunctionToolResult available for tool output searching.")
        return None

    for i, item in enumerate(items):
        if isinstance(item, output_item_type):
            item_tool_name = getattr(item, 'tool_name', None)
            # Specific check for run_full_research, as its name might be different in older SDK versions
            is_research_tool = (item_tool_name == tool_name) or \
                               (tool_name == "run_full_research" and isinstance(getattr(item, 'output', None), str) and getattr(item, 'output', '').strip().startswith('{\n  "report": ['))

            if is_research_tool:
                output_obj = getattr(item, 'output', None)
                if isinstance(output_obj, str):
                    print(f"DEBUG: Found output string for '{tool_name}' at index {i}.")
                    return output_obj
                else:
                    # Handle cases where output might be pre-parsed (less common for raw tool output)
                    try:
                        output_str = json.dumps(output_obj)
                        print(f"DEBUG: Found non-string output for '{tool_name}' at index {i}, converting to JSON.")
                        return output_str
                    except Exception as json_e:
                        print(f"WARN: Could not convert output for '{tool_name}' at index {i} to JSON: {json_e}")
                        return None

    print(f"DEBUG: Output string for '{tool_name}' not found.")
    return None


# --- Main Execution Logic (Refactored for Manual Merging) ---
async def main(user_query: str):
    """
    Runs the Stonk Research Agent, gets WebAnalysisOutput, finds run_full_research output,
    merges them into FullResearchReport, and saves JSON.
    """
    if not all([stonk_research_agent, FullResearchReport, SymbolResearchData, WebSearchOutput, WebAnalysisOutput, ValidationError, Field, HttpUrl]):
        print("Agent or Pydantic models failed to initialize. Exiting.")
        return

    print(f"\n--- Running Stonk Research Agent for query: '{user_query}' ---")
    output_filename = "stonk_research_output.json"
    final_report_obj: Optional[FullResearchReport] = None
    web_analysis_obj: Optional[WebAnalysisOutput] = None
    final_text_output: Optional[str] = None

    try:
        # Run the agent
        agent_run_result = await Runner.run(stonk_research_agent, user_query)
        print(f"DEBUG: Agent run completed. Processing {len(agent_run_result.new_items)} new items.")

        # 1. Attempt to get the structured WebAnalysisOutput from the agent
        try:
            web_analysis_obj = agent_run_result.final_output_as(WebAnalysisOutput)
            print("DEBUG: Successfully retrieved structured WebAnalysisOutput from agent result.")
        except (ValidationError, TypeError, AttributeError) as e:
            print(f"ERROR: Agent did not return a valid WebAnalysisOutput object: {e}")
            web_analysis_obj = WebAnalysisOutput(error=f"Agent failed to return valid web analysis: {e}")
            # Try to get raw text output as a fallback for supplementary info
            final_text_output = agent_run_result.final_output if isinstance(agent_run_result.final_output, str) else "Error: Agent output was not text or valid structure."

        # 2. Find the output from the 'run_full_research' tool call
        research_json_str = find_tool_output(agent_run_result.new_items, "run_full_research")

        # 3. Load or initialize the FullResearchReport object from the tool output
        if research_json_str:
            try:
                parsed_data = json.loads(research_json_str)
                final_report_obj = FullResearchReport(**parsed_data)
                print("DEBUG: Successfully loaded base research data from 'run_full_research' tool output.")
                if not final_report_obj.report:
                     print("WARN: Base report has empty 'report' list. Initializing.")
                     final_report_obj.report.append(SymbolResearchData(symbol="UNKNOWN (Empty Base Report)"))
            except (json.JSONDecodeError, ValidationError) as e:
                print(f"ERROR: Failed to load/validate base structured research data from tool: {e}")
                final_report_obj = FullResearchReport(report=[SymbolResearchData(symbol="UNKNOWN (Base Load/Validation Error)")])
            except Exception as e:
                 print(f"ERROR: Unexpected error processing base structured data: {e}")
                 final_report_obj = FullResearchReport(report=[SymbolResearchData(symbol="UNKNOWN (Base Load Error)")])
        else:
            print("WARN: 'run_full_research' tool output not found in agent results. Creating default report.")
            final_report_obj = FullResearchReport(report=[SymbolResearchData(symbol="UNKNOWN (Base Data Missing)")])

        # 4. Merge the WebAnalysisOutput into the FullResearchReport
        if final_report_obj and final_report_obj.report and web_analysis_obj:
            # Assume the analysis corresponds to the first symbol in the report
            target_symbol_data = final_report_obj.report[0]

            # Create a WebSearchOutput object from the WebAnalysisOutput data
            # Convert key_source_urls from List[str] back to List[HttpUrl] for the final report structure
            try:
                key_urls_as_httpurl = [HttpUrl(url_str) for url_str in web_analysis_obj.key_source_urls]
            except ValidationError as url_val_error:
                 print(f"WARN: Error converting key_source_urls back to HttpUrl during merge: {url_val_error}. Using empty list.")
                 key_urls_as_httpurl = []

            merged_web_search = WebSearchOutput(
                 query=None, # WebAnalysisOutput doesn't contain the query, set to None
                 overall_summary=web_analysis_obj.overall_summary,
                 relevant_news=web_analysis_obj.relevant_news,
                 key_source_urls=key_urls_as_httpurl, # Use the converted list
                 error=web_analysis_obj.error
            )
            target_symbol_data.web_search = merged_web_search
            print(f"DEBUG: Merged WebAnalysisOutput into FullResearchReport for symbol {target_symbol_data.symbol}.")
        elif final_report_obj and final_report_obj.report:
             # Handle case where web analysis failed but base report exists
             target_symbol_data = final_report_obj.report[0]
             target_symbol_data.web_search = WebSearchOutput(error="Web analysis object was not generated or retrieved.")
             print("WARN: WebAnalysisOutput was missing or invalid, updated report with error state.")

        # 5. Save Final Merged JSON
        if final_report_obj:
            try:
                json_output = final_report_obj.model_dump_json(indent=2)
                with open(output_filename, "w") as f:
                    f.write(json_output)
                print(f"\n--- Saved MERGED research output to {output_filename} ---")
            except Exception as write_e:
                print(f"\n--- Error saving merged JSON output: {write_e} ---")
                try: # Save raw dict on error
                    with open(output_filename + ".err", "w") as f_err:
                        json.dump(final_report_obj.model_dump(mode='json'), f_err, indent=2, default=str)
                    print(f"DEBUG: Saved raw dictionary to {output_filename}.err")
                except Exception: pass
        else:
            print("\n--- No final report object generated, nothing saved. ---")

        # Display Final Agent Text Output (Supplementary, if agent provided any)
        # Note: The primary output is the JSON file now.
        if not final_text_output: # Check if we already got fallback text
             for item in reversed(agent_run_result.new_items):
                  if isinstance(item, MessageOutputItem):
                       text_content = ItemHelpers.text_message_output(item) # Use ItemHelpers
                       if text_content:
                           final_text_output = text_content
                           break
        print("\n--- Agent Final Text Output (Supplementary) ---")
        print(final_text_output if final_text_output else "N/A (Agent's primary output is the structured WebAnalysisOutput, merged into JSON)")

    except Exception as e:
        print(f"\n--- Agent Run Error ---")
        print(f"An unexpected error occurred during agent run or merging: {e}")
        # Attempt to save error report
        try:
            error_msg = f"Agent Run/Merge Error: {e}"
            error_report = FullResearchReport(report=[SymbolResearchData(symbol="UNKNOWN (Run/Merge Error)", web_search=WebSearchOutput(error=error_msg))])
            with open(output_filename, "w") as f_err:
                 f_err.write(error_report.model_dump_json(indent=2))
            print(f"DEBUG: Saved agent run/merge error report to {output_filename}")
        except Exception: pass


if __name__ == "__main__":
    query = "Research NVIDIA (NVDA), include company overview, recent news, and current stock price."
    asyncio.run(main(user_query=query))
    print("\nStonk Research Agent run finished.")
