import os
import asyncio
import json
import sys # Import sys for stderr redirection
from typing import Optional, Any, Dict
from dotenv import load_dotenv

# Import Agent SDK components
try:
    import agents # Try base import first
    print("DEBUG: Successfully imported base 'agents' package.", file=sys.stderr)
    from agents.items import ToolCallOutputItem, MessageOutputItem
    from agents import Agent, Runner, WebSearchTool, FunctionToolResult, ItemHelpers # Added ItemHelpers
    print("DEBUG: Successfully imported specific Agent SDK components.", file=sys.stderr)
except ImportError as e:
    print(f"ERROR: Failed to import 'agents' library components: {e}", file=sys.stderr)
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
    from .tools import (
        get_yahoo_quote, get_finnhub_news, get_alphavantage_overview,
        get_fred_series, get_eia_series, get_newsapi_headlines, run_full_research
    )
    # Import the main report structure and the new analysis-specific structure
    from .tools import FullResearchReport, SymbolResearchData, WebSearchOutput, WebSearchNewsArticle, WebAnalysisOutput
    from pydantic import ValidationError, Field, HttpUrl
    print("DEBUG: Tools and Pydantic models imported successfully.", file=sys.stderr)
except ImportError:
     print("ERROR: Failed to import tools or Pydantic models from tools.py.", file=sys.stderr)
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
1.  **Structured Data First:** For ANY request mentioning a specific company name or ticker symbol (e.g., "Apple", "MSFT", "NVIDIA", "NVDA"), you **MUST** use the `run_full_research` tool as your FIRST step. This tool gathers various data including news from NewsAPI and Finnhub. NewsAPI articles often contain an `urlToImage` field. Finnhub articles might also contain image URLs.
2.  **Web Search for Price Impact:** AFTER `run_full_research` completes, you **MUST** use the `WebSearchTool`. Focus on finding **recent news, events, or analysis that could potentially impact the stock price**.
3.  **Analyze and Populate `WebAnalysisOutput`:**
    *   Analyze the results from `WebSearchTool`. Your primary goal is to identify **up to 3 highly relevant and *extremely recent*** web sources.
    *   **Determine Current Date and Strict Recency Filter:**
        1.  You will be provided with the current date (e.g., via system information). Let's assume for this instruction the current date is **May 6, 2025**.
        2.  You **MUST ONLY** select articles published on **May 6, 2025, May 5, 2025, May 4, 2025, or May 3, 2025** (i.e., today or within the previous 3 full days). This is an absolute requirement.
        3.  If `WebSearchTool` does not allow explicit date filtering in its query, you must still manually filter its results to adhere to this strict 3-day window based on the publication dates you can discern for each article.
        4.  If you cannot find at least 1-2 impactful articles within this strict 3-day window, you **MUST** explicitly state this limitation in your `overall_summary` (e.g., "No significant news found for [Company] between May 3-6, 2025.") and may return fewer than 3 articles, or an empty `relevant_news` list. **Under no circumstances should you include articles older than this 3-day window.**
    *   **Selection Criteria (for articles *within* the strict recency filter):**
        1.  **Stock Price Impact:** The article's content must have a clear, direct, and significant potential to impact the stock price.
        2.  **Significance:** The information must be substantial and not minor updates or rehashed old news (even if recent).
        The availability of an image URL should NOT influence your selection of these articles.
    *   For each of the selected articles (0 to 3, depending on what meets the strict recency and impact criteria), create a `WebSearchNewsArticle` object. Populate its `headline`, `reason` (why it might affect stock price), `transcript` (relevant excerpt), `sentiment_score`, `publish_date` (ensure this is accurate and reflects the article's true publication date if available from WebSearchTool, and that it falls within your calculated 3-day window), and `source_url`.
    *   **Image URL Population Strategy (Applied *after* article selection):**
        1.  **Primary (WebSearchTool Data for Selected Article):** For each of your 3 chosen articles, examine the `WebSearchTool`'s output corresponding to *that specific article*. If the `WebSearchTool` data for that article contains a direct image URL or provides enough information (e.g., metadata, HTML snippets) for you to reliably infer/extract a primary image URL for it, use that image URL for the `image_url` field.
        2.  **Fallback (Leave as None for Python logic):** If, for a selected article, you cannot find or infer a suitable image URL from its `WebSearchTool` data, leave its `image_url` field as `None`. A separate Python-based fallback mechanism will then attempt to find a matching image URL from the `run_full_research` data based on the `source_url`.
4.  **Return ONLY `WebAnalysisOutput`:** Your SOLE task after running the tools and performing analysis is to construct and return a `WebAnalysisOutput` object. This object should contain:
    *   `overall_summary`: Your synthesized text summary of the web search findings. **Crucially, if you applied a recency filter (e.g., "news from May 3-6, 2025"), mention this date range in your summary.** If no relevant recent news was found, state that clearly.
    *   `relevant_news`: A list of `WebSearchNewsArticle` objects for the selected articles (0 to 3) that meet the strict recency and impact criteria, with `image_url` populated according to the strategy above.
    *   `key_source_urls`: A list of the source URLs from the selected articles.
    *   `error`: Any error message if the web search or analysis failed.
You MUST return ONLY this `WebAnalysisOutput` object. Do NOT return the full `FullResearchReport`.

**Available Tools:**
- `run_full_research`: **(MANDATORY FIRST STEP for Company Queries)** Gathers base quote, news (including potential image URLs from NewsAPI's `urlToImage`), overview data. Its output is used implicitly and by the Python fallback for `image_url`.
- `WebSearchTool`: **(MANDATORY SECOND STEP for Company Queries)** Performs web search. You must try to make your queries specific to recent news if possible (e.g., "NVIDIA news May 2025"). You must then manually filter results by publish date.
- `get_fred_series`, `get_eia_series`, `get_newsapi_headlines`: Use *only* for non-company specific queries (these will likely result in a text response, not `WebAnalysisOutput`).

**Workflow:**
1.  **Analyze Request:** Identify company symbol(s) and note the current date (e.g., May 6, 2025). Calculate the 3-day recency window (e.g., May 3-6, 2025).
2.  **Company Research:**
    a.  Execute `run_full_research` (default `news_count=5`).
    b.  Execute `WebSearchTool` focusing on price impact queries. Try to include date-related terms in your query if you think it helps the tool (e.g., "NVIDIA stock news May 2025").
    c.  Analyze `WebSearchTool` results. **Filter these results to include ONLY articles published within your calculated 3-day recency window.** From these filtered recent articles, select up to 3 that are most impactful to stock price.
    d.  If no articles (or very few) meet both the strict recency and impact criteria, prepare to state this in your `overall_summary` and return fewer (or zero) articles in `relevant_news`.
    e.  For each chosen `WebSearchNewsArticle` object, populate all fields (including `publish_date` accurately). For `image_url`, first attempt to find an image URL from the `WebSearchTool`'s data for that specific article. If found, use it. If not found via `WebSearchTool` for that article, set `image_url` to `None`.
    f.  Construct the `WebAnalysisOutput` object. Ensure the `overall_summary` mentions the date range used for filtering if articles were found, or explains if no recent impactful news was found.
    g.  Return ONLY the `WebAnalysisOutput` object.
3.  **Other Queries:** Use appropriate tools or `WebSearchTool` and return a text response.
4.  **Failure Handling:** If `WebSearchTool` fails, populate the `error` field in the `WebAnalysisOutput` object. If `run_full_research` fails, still try `WebSearchTool` and return the `WebAnalysisOutput`. If image URL extraction fails for an article, `image_url` should be `None` for that article; do not let this block the process.
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
    print("StonkResearchAgent initialized successfully with output_type=WebAnalysisOutput.", file=sys.stderr)
except Exception as e:
    print(f"Error initializing StonkResearchAgent: {e}", file=sys.stderr)
    stonk_research_agent = None

# --- Helper Function to Extract Image URLs from Raw Research ---
def _extract_image_urls_from_raw_research(raw_research_report: Optional[FullResearchReport]) -> Dict[str, str]:
    """
    Parses the FullResearchReport and extracts a mapping of source_url to image_url.
    """
    image_url_map: Dict[str, str] = {}
    if not raw_research_report or not raw_research_report.report:
        print("DEBUG (_extract_image_urls): Raw research report is None or empty.", file=sys.stderr)
        return image_url_map

    print(f"DEBUG (_extract_image_urls): Processing {len(raw_research_report.report)} symbol(s) in raw report.", file=sys.stderr)
    for i, symbol_data in enumerate(raw_research_report.report):
        print(f"DEBUG (_extract_image_urls): Processing symbol {i+1}: {symbol_data.symbol}", file=sys.stderr)
        # Process NewsAPI headlines
        if symbol_data.newsapi_headlines and symbol_data.newsapi_headlines.articles:
            print(f"DEBUG (_extract_image_urls): Found {len(symbol_data.newsapi_headlines.articles)} NewsAPI articles for {symbol_data.symbol}.", file=sys.stderr)
            for article_idx, article_dict in enumerate(symbol_data.newsapi_headlines.articles):
                source_url = article_dict.get("url")
                image_url = article_dict.get("urlToImage")
                print(f"DEBUG (_extract_image_urls): NewsAPI Article {article_idx+1} for {symbol_data.symbol}: source_url='{source_url}', image_url='{image_url}'", file=sys.stderr)
                if source_url and image_url and source_url not in image_url_map:
                    image_url_map[source_url] = image_url
                    print(f"DEBUG (_extract_image_urls): Added to map: '{source_url}' -> '{image_url}'", file=sys.stderr)
        else:
            print(f"DEBUG (_extract_image_urls): No NewsAPI articles for {symbol_data.symbol}.", file=sys.stderr)
        
        # Process Finnhub news
        if symbol_data.finnhub_news and symbol_data.finnhub_news.news:
            print(f"DEBUG (_extract_image_urls): Found {len(symbol_data.finnhub_news.news)} Finnhub articles for {symbol_data.symbol}.", file=sys.stderr)
            for article_idx, article_dict in enumerate(symbol_data.finnhub_news.news):
                source_url = article_dict.get("url")
                image_url = article_dict.get("image") # Finnhub might use 'image' field
                print(f"DEBUG (_extract_image_urls): Finnhub Article {article_idx+1} for {symbol_data.symbol}: source_url='{source_url}', image_url='{image_url}'", file=sys.stderr)
                if source_url and image_url and source_url not in image_url_map:
                    image_url_map[source_url] = image_url
                    print(f"DEBUG (_extract_image_urls): Added to map: '{source_url}' -> '{image_url}'", file=sys.stderr)
        else:
            print(f"DEBUG (_extract_image_urls): No Finnhub articles for {symbol_data.symbol}.", file=sys.stderr)
    
    print(f"DEBUG (_extract_image_urls): Built image URL map with {len(image_url_map)} entries: {json.dumps(image_url_map, indent=2)}", file=sys.stderr)
    return image_url_map

# --- Helper Function to Find Tool Output ---
def find_tool_output(items: list[Any], tool_name: str) -> Optional[str]:
    """Finds the output string of a specific tool call in the agent results."""
    # Determine the correct output item type based on availability
    output_item_type = ToolCallOutputItem if ToolCallOutputItem else FunctionToolResult
    if not output_item_type:
        print("DEBUG: Neither ToolCallOutputItem nor FunctionToolResult available for tool output searching.", file=sys.stderr)
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
                    print(f"DEBUG: Found output string for '{tool_name}' at index {i}.", file=sys.stderr)
                    return output_obj
                else:
                    # Handle cases where output might be pre-parsed (less common for raw tool output)
                    try:
                        output_str = json.dumps(output_obj)
                        print(f"DEBUG: Found non-string output for '{tool_name}' at index {i}, converting to JSON.", file=sys.stderr)
                        return output_str
                    except Exception as json_e:
                        print(f"WARN: Could not convert output for '{tool_name}' at index {i} to JSON: {json_e}", file=sys.stderr)
                        return None

    print(f"DEBUG: Output string for '{tool_name}' not found.", file=sys.stderr)
    return None


# --- Main Execution Logic (Refactored for Manual Merging) ---
async def main(user_query: str):
    """
    Runs the Stonk Research Agent, gets WebAnalysisOutput, finds run_full_research output,
    merges them into FullResearchReport, and saves JSON.
    """
    if not all([stonk_research_agent, FullResearchReport, SymbolResearchData, WebSearchOutput, WebAnalysisOutput, ValidationError, Field, HttpUrl]):
        print("Agent or Pydantic models failed to initialize. Exiting.", file=sys.stderr)
        return

    print(f"\n--- Running Stonk Research Agent for query: '{user_query}' ---", file=sys.stderr)
    output_filename = "stonk_research_output.json"
    final_report_obj: Optional[FullResearchReport] = None
    web_analysis_obj: Optional[WebAnalysisOutput] = None
    final_text_output: Optional[str] = None

    try:
        # Run the agent
        agent_run_result = await Runner.run(stonk_research_agent, user_query)
        print(f"DEBUG: Agent run completed. Processing {len(agent_run_result.new_items)} new items.", file=sys.stderr)

        # 1. Attempt to get the structured WebAnalysisOutput from the agent
        try:
            web_analysis_obj = agent_run_result.final_output_as(WebAnalysisOutput)
            print("DEBUG: Successfully retrieved structured WebAnalysisOutput from agent result.", file=sys.stderr)
        except (ValidationError, TypeError, AttributeError) as e:
            print(f"ERROR: Agent did not return a valid WebAnalysisOutput object: {e}", file=sys.stderr)
            web_analysis_obj = WebAnalysisOutput(error=f"Agent failed to return valid web analysis: {e}")
            # Try to get raw text output as a fallback for supplementary info
            final_text_output = agent_run_result.final_output if isinstance(agent_run_result.final_output, str) else "Error: Agent output was not text or valid structure."

        # 2. Find the output from the 'run_full_research' tool call
        research_json_str = find_tool_output(agent_run_result.new_items, "run_full_research")

        # 3. Load or initialize the FullResearchReport object from the tool output
        if research_json_str:
            try:
                parsed_data = json.loads(research_json_str)
                final_report_obj = FullResearchReport(**parsed_data) # This is the raw_research_report
                print("DEBUG: Successfully loaded base research data from 'run_full_research' tool output.", file=sys.stderr)
                if not final_report_obj.report:
                     print("WARN: Base report has empty 'report' list. Initializing.", file=sys.stderr)
                     final_report_obj.report.append(SymbolResearchData(symbol="UNKNOWN (Empty Base Report)"))
            except (json.JSONDecodeError, ValidationError) as e:
                print(f"ERROR: Failed to load/validate base structured research data from tool: {e}", file=sys.stderr)
                final_report_obj = FullResearchReport(report=[SymbolResearchData(symbol="UNKNOWN (Base Load/Validation Error)")])
            except Exception as e:
                 print(f"ERROR: Unexpected error processing base structured data: {e}", file=sys.stderr)
                 final_report_obj = FullResearchReport(report=[SymbolResearchData(symbol="UNKNOWN (Base Load Error)")])
        else:
            print("WARN: 'run_full_research' tool output not found in agent results. Creating default report.", file=sys.stderr)
            final_report_obj = FullResearchReport(report=[SymbolResearchData(symbol="UNKNOWN (Base Data Missing)")])

        # NEW STEP: Explicitly populate image_url in web_analysis_obj using raw research data
        if web_analysis_obj and web_analysis_obj.relevant_news and final_report_obj:
            image_url_map = _extract_image_urls_from_raw_research(final_report_obj)
            if image_url_map:
                print(f"DEBUG (main merge): Attempting to merge image URLs into {len(web_analysis_obj.relevant_news)} relevant_news articles.", file=sys.stderr)
                for news_article in web_analysis_obj.relevant_news:
                    if not news_article.image_url and news_article.source_url:
                        source_url_str = str(news_article.source_url) if isinstance(news_article.source_url, HttpUrl) else news_article.source_url
                        print(f"DEBUG (main merge): Checking article '{news_article.headline}', source_url_str='{source_url_str}'", file=sys.stderr)
                        if source_url_str in image_url_map:
                            news_article.image_url = image_url_map[source_url_str]
                            print(f"DEBUG (main merge): SUCCESS - Populated image_url for '{news_article.headline}' with '{image_url_map[source_url_str]}'", file=sys.stderr)
                        else:
                            print(f"DEBUG (main merge): FAILED - No match for '{source_url_str}' in image_url_map.", file=sys.stderr)
                    elif news_article.image_url:
                        print(f"DEBUG (main merge): Article '{news_article.headline}' already has image_url: '{news_article.image_url}'", file=sys.stderr)
                    elif not news_article.source_url:
                        print(f"DEBUG (main merge): Article '{news_article.headline}' has no source_url, cannot map image.", file=sys.stderr)
            else:
                print("DEBUG (main merge): image_url_map is empty, no URLs to merge.", file=sys.stderr)


        # 4. Merge the (now potentially image-enriched) WebAnalysisOutput into the FullResearchReport
        if final_report_obj and final_report_obj.report and web_analysis_obj:
            # Assume the analysis corresponds to the first symbol in the report
            target_symbol_data = final_report_obj.report[0]

            # Create a WebSearchOutput object from the WebAnalysisOutput data
            # Convert key_source_urls from List[str] back to List[HttpUrl] for the final report structure
            try:
                key_urls_as_httpurl = [HttpUrl(url_str) for url_str in web_analysis_obj.key_source_urls]
            except ValidationError as url_val_error:
                 print(f"WARN: Error converting key_source_urls back to HttpUrl during merge: {url_val_error}. Using empty list.", file=sys.stderr)
                 key_urls_as_httpurl = []

            merged_web_search = WebSearchOutput(
                 query=None, # WebAnalysisOutput doesn't contain the query, set to None
                 overall_summary=web_analysis_obj.overall_summary,
                 relevant_news=web_analysis_obj.relevant_news,
                 key_source_urls=key_urls_as_httpurl, # Use the converted list
                 error=web_analysis_obj.error
            )
            target_symbol_data.web_search = merged_web_search
            print(f"DEBUG: Merged WebAnalysisOutput into FullResearchReport for symbol {target_symbol_data.symbol}.", file=sys.stderr)
        elif final_report_obj and final_report_obj.report:
             # Handle case where web analysis failed but base report exists
             target_symbol_data = final_report_obj.report[0]
             target_symbol_data.web_search = WebSearchOutput(error="Web analysis object was not generated or retrieved.")
             print("WARN: WebAnalysisOutput was missing or invalid, updated report with error state.", file=sys.stderr)

        # 5. Save Final Merged JSON
        if final_report_obj:
            try:
                json_output = final_report_obj.model_dump_json(indent=2)
                with open(output_filename, "w") as f:
                    f.write(json_output)
                print(f"\n--- Saved MERGED research output to {output_filename} ---", file=sys.stderr)
            except Exception as write_e:
                print(f"\n--- Error saving merged JSON output: {write_e} ---", file=sys.stderr)
                try: # Save raw dict on error
                    with open(output_filename + ".err", "w") as f_err:
                        json.dump(final_report_obj.model_dump(mode='json'), f_err, indent=2, default=str)
                    print(f"DEBUG: Saved raw dictionary to {output_filename}.err", file=sys.stderr)
                except Exception: pass
        else:
            print("\n--- No final report object generated, nothing saved. ---", file=sys.stderr)

        # Display Final Agent Text Output (Supplementary, if agent provided any)
        # Note: The primary output is the JSON file now.
        if not final_text_output: # Check if we already got fallback text
             for item in reversed(agent_run_result.new_items):
                  if isinstance(item, MessageOutputItem):
                       text_content = ItemHelpers.text_message_output(item) # Use ItemHelpers
                       if text_content:
                           final_text_output = text_content
                           break
        print("\n--- Agent Final Text Output (Supplementary) ---", file=sys.stderr)
        print(final_text_output if final_text_output else "N/A (Agent's primary output is the structured WebAnalysisOutput, merged into JSON)", file=sys.stderr)

        # Return the agent run result so the caller (pipeline) can process it
        return agent_run_result

    except Exception as e:
        print(f"\n--- Agent Run Error ---", file=sys.stderr)
        print(f"An unexpected error occurred during agent run or merging: {e}", file=sys.stderr)
        # Attempt to save error report
        try:
            error_msg = f"Agent Run/Merge Error: {e}"
            error_report = FullResearchReport(report=[SymbolResearchData(symbol="UNKNOWN (Run/Merge Error)", web_search=WebSearchOutput(error=error_msg))])
            with open(output_filename, "w") as f_err:
                 f_err.write(error_report.model_dump_json(indent=2))
            print(f"DEBUG: Saved agent run/merge error report to {output_filename}", file=sys.stderr)
        except Exception: pass


if __name__ == "__main__":
    query = "Research NVIDIA (NVDA), include company overview, recent news, and current stock price."
    asyncio.run(main(user_query=query))
    print("\nStonk Research Agent run finished.", file=sys.stderr)
