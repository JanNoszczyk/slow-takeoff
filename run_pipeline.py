import asyncio
import json
import os
import sys
import argparse
from typing import Optional

# Import agent runners
try:
    # Stonk Research Agent
    from stonk_research_agent.agent import main as run_stonk_research
    from stonk_research_agent.agent import find_tool_output # Need this helper
    from stonk_research_agent.tools import FullResearchReport, SymbolResearchData, WebSearchOutput, HttpUrl, WebSearchNewsArticle # Import necessary models
    from pydantic import ValidationError
    # Dashboard Generator Agent - NEW IMPORT
    from project_agents.dashboard_agent.agent import run_tsx_generation
    print("DEBUG: Successfully imported agent runners and models.", file=sys.stderr) # Redirect to stderr
except ImportError as e:
    print(f"ERROR: Failed to import agent runners or models: {e}", file=sys.stderr) # Also redirect error fallback message
    # Define fallbacks for script execution
    async def run_stonk_research(query: str):
        print(f"ERROR: Fallback run_stonk_research called for query: {query}")
        # Simulate the structure expected by find_tool_output and downstream logic
        # Need to return an object that looks like RunResult with new_items
        class MockItem:
            def __init__(self, tool_name, output):
                self.tool_name = tool_name
                self.output = output
        class MockRunResult:
            def __init__(self):
                error_report = FullResearchReport(report=[SymbolResearchData(symbol="ERROR", web_search=WebSearchOutput(error="Stonk agent import failed"))])
                self.new_items = [MockItem("run_full_research", error_report.model_dump_json(indent=2))]
                self.final_output = None # Or some error text

            def final_output_as(self, type):
                 if type == WebAnalysisOutput: # Need WebAnalysisOutput from stonk agent for this... tricky fallback
                     # Returning a dummy structure matching WebAnalysisOutput
                     class DummyWebAnalysis:
                        overall_summary = "Error: Stonk agent import failed"
                        relevant_news = []
                        key_source_urls = []
                        error = "Stonk agent import failed"
                     return DummyWebAnalysis()
                 return None
        return MockRunResult()

    # Fallback for missing run_tsx_generation
    def run_tsx_generation(json_str: str) -> str:
        print("ERROR: Fallback run_tsx_generation called.", file=sys.stderr)
        return f'<p class="text-red-500">Error: Dashboard agent import failed.</p>'
    FullResearchReport = None
    ValidationError = Exception


async def run_full_pipeline(stock_query: str):
    """
    Runs the full pipeline: stonk research -> dashboard generation.
    Prints the final TSX code to stdout.
    """
    print(f"DEBUG: Starting pipeline for query: '{stock_query}'", file=sys.stderr) # Use stderr for logs

    # 1. Run Stonk Research Agent
    stonk_agent_run_result = None
    research_json_str: Optional[str] = None
    web_analysis_obj = None # From stonk agent
    merged_report_obj: Optional[FullResearchReport] = None # Final merged report

    try:
        print("DEBUG: Running Stonk Research Agent...", file=sys.stderr)
        # run_stonk_research needs to return the RunResult object for processing
        stonk_agent_run_result = await run_stonk_research(stock_query)
        print("DEBUG: Stonk Research Agent finished.", file=sys.stderr)

        # Extract WebAnalysisOutput (Primary output of StonkResearchAgent)
        try:
            # Assuming WebAnalysisOutput is defined/imported correctly
            from stonk_research_agent.agent import WebAnalysisOutput # Ensure it's imported
            web_analysis_obj = stonk_agent_run_result.final_output_as(WebAnalysisOutput)
            print("DEBUG: Extracted WebAnalysisOutput from stonk agent.", file=sys.stderr)
        except Exception as e:
            print(f"ERROR: Failed to extract WebAnalysisOutput: {e}", file=sys.stderr)
            web_analysis_obj = None # Or create a dummy error object

        # Extract the JSON output from the 'run_full_research' tool call within the stonk agent run
        research_json_str = find_tool_output(stonk_agent_run_result.new_items, "run_full_research")

        if research_json_str and FullResearchReport:
            try:
                # Load the base report from the tool output
                parsed_data = json.loads(research_json_str)
                base_report_obj = FullResearchReport(**parsed_data)
                print("DEBUG: Successfully parsed 'run_full_research' output.", file=sys.stderr)

                # Merge WebAnalysis into the report
                if base_report_obj.report and web_analysis_obj:
                    target_symbol_data = base_report_obj.report[0]
                    try:
                         key_urls_as_httpurl = [HttpUrl(str(url_str)) for url_str in web_analysis_obj.key_source_urls]
                    except ValidationError as url_val_error:
                         print(f"WARN: Error converting key_source_urls back to HttpUrl: {url_val_error}. Using empty list.", file=sys.stderr)
                         key_urls_as_httpurl = []

                    merged_web_search = WebSearchOutput(
                         query=None,
                         overall_summary=web_analysis_obj.overall_summary,
                         relevant_news=web_analysis_obj.relevant_news,
                         key_source_urls=key_urls_as_httpurl,
                         error=web_analysis_obj.error
                    )
                    target_symbol_data.web_search = merged_web_search
                    merged_report_obj = base_report_obj
                    print(f"DEBUG: Merged WebAnalysisOutput into report for {target_symbol_data.symbol}.", file=sys.stderr)
                else:
                     print("WARN: Could not merge WebAnalysisOutput (missing report data or web analysis obj).", file=sys.stderr)
                     merged_report_obj = base_report_obj # Use base report anyway

                # Use the merged report JSON for the dashboard agent
                research_json_string_for_dashboard = merged_report_obj.model_dump_json(indent=2)

            except (json.JSONDecodeError, ValidationError) as e:
                print(f"ERROR: Failed to process 'run_full_research' output JSON: {e}", file=sys.stderr)
                research_json_string_for_dashboard = json.dumps({"error": f"Failed to process base research: {e}"})
        else:
            print("WARN: 'run_full_research' output not found or FullResearchReport model missing.", file=sys.stderr)
            # Create minimal JSON for dashboard agent indicating error
            research_json_string_for_dashboard = json.dumps({"report": [{"symbol": "ERROR", "web_search": {"error": "Base research data missing."}}]})

    except Exception as e:
        print(f"ERROR: Stonk Research Agent run failed: {e}", file=sys.stderr)
        research_json_string_for_dashboard = json.dumps({"report": [{"symbol": "ERROR", "web_search": {"error": f"Stonk agent run failed: {e}"}}]})
        print("DEBUG: Using error JSON for dashboard generation due to stonk agent failure.", file=sys.stderr)

    # 2. Generate TSX Code using Dashboard Agent
    print("DEBUG: Calling Dashboard Agent (run_tsx_generation)...", file=sys.stderr)
    final_output_string = "" # Initialize
    try:
        # Ensure we always have a valid JSON string, even if it's an error structure
        if not research_json_string_for_dashboard:
             print("CRITICAL: research_json_string_for_dashboard was None before calling dashboard agent. Creating error JSON.", file=sys.stderr)
             research_json_string_for_dashboard = json.dumps({"error": "Pipeline failed before dashboard generation."})

        # Call the dashboard agent function synchronously (adjust if it becomes async)
        final_output_string = run_tsx_generation(research_json_string_for_dashboard)
        print(f"DEBUG: Dashboard Agent finished. Output length: {len(final_output_string)}", file=sys.stderr)

    except Exception as dash_e:
        print(f"ERROR: Dashboard Agent (run_tsx_generation) failed: {dash_e}", file=sys.stderr)
        final_output_string = f'<p class="text-red-500">Error: Dashboard generation step failed: {dash_e}</p>'

    # 3. Print final TSX string (or error message) to stdout (for the API route)
    print(final_output_string, file=sys.stdout)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Stonk Research and Dashboard Generation Pipeline.")
    parser.add_argument("stock_query", help="The stock symbol or company name to research (e.g., 'NVDA', 'NVIDIA Corporation').")
    args = parser.parse_args()

    asyncio.run(run_full_pipeline(args.stock_query))
    print("DEBUG: Pipeline Runner finished.", file=sys.stderr)
