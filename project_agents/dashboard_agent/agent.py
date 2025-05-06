import sys
import json
from typing import Dict, Any, Optional

# Add project root to sys.path to allow importing from sibling directories
# Adjust based on actual project structure if necessary
project_root = '../../'
if project_root not in sys.path:
    sys.path.append(project_root)

# Import the UNDECORATED tool logic function
try:
    # Use relative import if possible, otherwise rely on sys.path
    # Import the logic function directly, aliasing it for use here
    from .tools import _generate_news_display_code_logic as generate_news_display_code_func
    print("DEBUG (dashboard_agent.agent): Imported _generate_news_display_code_logic successfully.", file=sys.stderr)
except ImportError as e:
    print(f"ERROR (dashboard_agent.agent): Failed to import tool logic function: {e}. Check path and tool definition.", file=sys.stderr)
    # Define a fallback if import fails
    def generate_news_display_code_func(research_data_json: str) -> str:
        print("ERROR (dashboard_agent.agent): Fallback tool logic called.", file=sys.stderr)
        return '<p class="text-red-500">Error: Dashboard code generation logic failed to load.</p>'

# --- Core Logic for TSX Generation ---

def run_tsx_generation(research_json_str: str) -> str:
    """
    Takes research JSON string, uses the tool to generate TSX for news display.

    Args:
        research_json_str: JSON string containing the full research data.

    Returns:
        A string containing the generated TSX code for the news section,
        or an error message string.
    """
    print("DEBUG (dashboard_agent.agent): Entering run_tsx_generation.", file=sys.stderr)
    if not research_json_str:
        print("ERROR (dashboard_agent.agent): Received empty research_json_str.", file=sys.stderr)
        return '<p class="text-red-500">Error: No research data received.</p>'

    try:
        # Directly call the imported logic function
        tsx_output = generate_news_display_code_func(research_data_json=research_json_str)
        print("DEBUG (dashboard_agent.agent): Tool logic function _generate_news_display_code_logic returned.", file=sys.stderr)
        return tsx_output
    except Exception as e:
        print(f"ERROR (dashboard_agent.agent): Unexpected error calling tool: {e}", file=sys.stderr)
        return f'<p class="text-red-500">Error: Failed during TSX generation process. Type: {type(e).__name__}</p>'

# --- Main execution (if script is called directly) ---
# This part is likely NOT used when called by run_pipeline.py,
# but can be useful for direct testing.
if __name__ == "__main__":
    print("DEBUG (dashboard_agent.agent): Script called directly.", file=sys.stderr)
    # Example: Read JSON from a file or stdin for testing
    example_json = """
    {
      "report": [
        {
          "symbol": "TEST",
          "web_search": {
            "relevant_news": [
              {
                "headline": "Test News 1",
                "source_name": "Test Source",
                "source_url": "https://example.com/1",
                "publish_date": "2025-01-01T12:00:00Z",
                "reason": "Test reason 1.",
                "transcript": "Test transcript 1.",
                "sentiment_score": 0.5
              },
              {
                "headline": "Test News 2 - Bad URL",
                "source_name": "Test Source 2",
                "source_url": "invalid-url",
                "publish_date": "2025-01-02T12:00:00Z",
                "reason": "Test reason 2.",
                "transcript": "Test transcript 2.",
                "sentiment_score": -0.3
              }
            ]
          }
        }
      ]
    }
    """
    if len(sys.argv) > 1:
         input_json_str = sys.argv[1]
         print("DEBUG (dashboard_agent.agent): Received JSON string via argv.", file=sys.stderr)
    else:
         print("DEBUG (dashboard_agent.agent): Using example JSON for testing.", file=sys.stderr)
         input_json_str = example_json

    generated_tsx = run_tsx_generation(input_json_str)
    print("--- Generated TSX ---", file=sys.stderr)
    print(generated_tsx) # Print result to stdout for testing capture
    print("--- End Generated TSX ---", file=sys.stderr)

# Note: Removed the old agent setup using OpenAIAgent as it's not needed
# for this specific task of calling a single tool based on input.
# The `run_pipeline.py` script will import and call `run_tsx_generation`.
