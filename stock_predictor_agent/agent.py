import os
import asyncio
import json
import pandas as pd
from pydantic import BaseModel, Field
from typing import List, Any, Dict
from dotenv import load_dotenv

# Assuming the SDK is installed as 'openai-agents' and has this structure
# If the actual library name/structure differs, these imports will need adjustment
try:
    from agents import Agent, Runner # Assuming these are the core components
    # Need to figure out how tools are integrated - are they passed to Agent? Runner?
    # The example doesn't show custom tool definition/use clearly for the Runner.
    # Let's proceed assuming tools can be made available somehow.
except ImportError:
    print("ERROR: Failed to import 'agents' library. Make sure 'openai-agents' is installed.")
    print("Attempting fallback import structure...")
    try:
         # Try a hypothetical structure if 'agents' root doesn't work
         from openai_agents import Agent, Runner
    except ImportError:
         raise ImportError("Could not find the 'openai-agents' library with expected structure.")


from tools import get_stock_data, execute_python_code # Import our tool functions

# Load environment variables
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not OPENAI_API_KEY:
    # The SDK might handle auth differently, but good practice to check
    print("Warning: OPENAI_API_KEY found in environment, but SDK might use its own auth.")
    # raise ValueError("OPENAI_API_KEY environment variable not set.")

# --- Pydantic Models for Agent Outputs ---

class PredictionOutput(BaseModel):
    """Output structure for each Coder Agent run."""
    approach_name: str = Field(description="Name of the prediction approach used (e.g., 'ARIMA', 'Linear Regression').")
    # Changed to 'str' to ensure schema compatibility. Removed default as it's not allowed by the API schema generator.
    prediction: str = Field(description="The final prediction result as a JSON string (e.g., '{\"prediction_value\": 150.5, \"signal\": \"BUY\"}').") # Removed default='{}'
    report: str = Field(description="A brief report explaining the methodology, findings, and confidence.")
    code: str = Field(description="The Python code generated and executed for the analysis.")
    # Removed defaults as they might be causing schema issues
    tool_stdout: str = Field(description="Captured stdout from the executed code.")
    tool_stderr: str = Field(description="Captured stderr from the executed code.")
    error: str = Field(description="Any error message during tool execution.")


class JudgeInput(BaseModel):
    """Structure for providing results to the Judge Agent."""
    original_request: str
    results: List[PredictionOutput]


class FinalDecision(BaseModel):
    """Output structure for the Judge Agent."""
    best_approach_name: str = Field(description="The name of the selected best approach.")
    # Changed to 'str' for schema compatibility. This will contain the JSON string from the selected PredictionOutput.
    best_prediction: str = Field(description="The prediction from the selected best approach (as a JSON string).")
    best_report: str = Field(description="The report from the selected best approach.")
    best_code: str = Field(description="The code from the selected best approach.")
    judge_reasoning: str = Field(description="The judge's reasoning for selecting this result.")

# --- Tool Integration (Needs verification based on SDK specifics) ---

# How does the SDK make tools available? Let's assume they need to be defined
# in a way the Agent class understands. The example used built-in tools.
# For custom tools, we might need wrappers or a specific registration mechanism.

# Placeholder: Define tool metadata in the format the SDK might expect (similar to OpenAI functions)
# This is a guess based on common patterns.
AGENT_TOOLS_METADATA = [
     {
        "type": "function", # Assuming 'function' type if custom are supported
        "function": {
            "name": "get_stock_data",
            "description": "Fetches historical stock data (OHLCV) for a given symbol. Returns JSON data.",
            "parameters": { # Matches Anthropic/OpenAI schema style
                "type": "object",
                "properties": {
                    "stock_symbol": {"type": "string", "description": "The stock ticker symbol (e.g., AAPL, MSFT)."},
                    "start_date": {"type": "string", "description": "Optional. Start date in YYYY-MM-DD format."},
                    "end_date": {"type": "string", "description": "Optional. End date in YYYY-MM-DD format."},
                    "timeframe": {"type": "string", "description": "Optional. Data frequency (e.g., '1D', '1H'). Defaults '1D'."}
                },
                "required": ["stock_symbol"],
            },
        }
     },
     {
        "type": "function",
        "function": {
            "name": "execute_python_code",
            "description": "Executes Python code for analysis/prediction. Fetched data is available as pandas DataFrame 'df'. Assign result to 'prediction_output'.",
             "parameters": {
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "Python code string to execute."},
                },
                "required": ["code"],
            },
        }
     }
]

# How context (like the fetched 'df') is passed during tool execution by the SDK's Runner
# is unclear from the example. We might need to manage this externally or hope
# the SDK provides a mechanism (e.g., via ctx.context passed to runner).


# --- Agent Definitions ---

# Base instructions for coder agents
CODER_BASE_INSTRUCTIONS = """
You are a Quantitative Analyst Agent. Your task is to analyze historical stock data for {stock_symbol} and generate Python code to predict its future price movement based on the '{approach_name}' approach.

1. You will be provided with historical stock data in a pandas DataFrame named 'df'.
2. Use the '{approach_name}' methodology. Be creative if the name is generic (e.g., 'Trend Following').
3. Generate Python code using pandas and numpy (available as 'pd' and 'numpy'). You can request 'sklearn' or 'statsmodels' if needed for the specific approach.
4. The code MUST assign its final prediction result (which should be a dictionary, e.g., {{{{ 'prediction_value': 150.5, 'signal': 'BUY' }}}}) to a variable named `prediction_output`.
5. The code should focus ONLY on calculation and assigning `prediction_output`. Avoid plotting or file I/O.
6. After generating the code, explain your methodology clearly in a brief report.
7. Structure your final output according to the required PredictionOutput format. IMPORTANT: The 'prediction' field in your final output MUST be a JSON STRING representation of the dictionary result from your code (e.g., prediction='{{\\"prediction_value\\": 150.5, \\"signal\\": \\"BUY\\"}}').
"""

# Judge agent instructions
JUDGE_INSTRUCTIONS = """
You are a Chief Investment Officer Agent. You have received multiple stock prediction analyses for the same request from different Quantitative Analyst Agents, each using a different approach.
Your task is to evaluate these analyses based on the provided prediction (which is a JSON string), report, code, and any execution output/errors.

Input: A list of PredictionOutput objects, where the 'prediction' field contains a JSON string.

Evaluation Criteria:
1.  **Clarity and Soundness of Methodology:** Does the report clearly explain a reasonable approach?
2.  **Code Quality:** Is the provided Python code relevant, correct for the described approach, and safe (no obvious malicious patterns)?
3.  **Prediction Plausibility:** Does the prediction seem reasonable given the data and approach (without guaranteeing accuracy)?
4.  **Execution Success:** Did the code run successfully (check stderr/error fields)? Penalize runs with significant errors.
5.  **Consistency:** Do the report, code, and the content of the prediction JSON string align?

Output: Select the *single best* analysis and provide your reasoning, adhering to the FinalDecision format. Copy the selected JSON string prediction into the 'best_prediction' field. If no analysis is satisfactory, explain why.
"""

# Define Agent instances (assuming Agent() takes instructions and tool metadata)
# Note: Tool usage might be handled by the Runner, not defined per agent. This needs clarification from SDK docs.
judge_agent = Agent(
    name="JudgeAgent",
    instructions=JUDGE_INSTRUCTIONS,
    output_type=FinalDecision, # Specify Pydantic model for output validation
    # tools = [], # Judge might not need tools directly
)

# Coder agents will be created dynamically in the main loop

# --- Main Orchestration Logic ---

async def run_analysis_approach(approach_name: str, stock_symbol: str, stock_data_context: Dict) -> PredictionOutput:
    """Runs a single coder agent for a specific approach."""
    print(f"---> Starting analysis for approach: {approach_name}")
    # Correctly escape braces for .format()
    try:
        coder_instructions = CODER_BASE_INSTRUCTIONS.format(
            stock_symbol=stock_symbol,
            approach_name=approach_name
        )
    except KeyError as e:
        print(f"XXXX FORMATTING ERROR in CODER_BASE_INSTRUCTIONS: {e}")
        print("Ensure all curly braces intended for literal output are doubled (e.g., {{ example }} )")
        raise # Re-raise the error after printing context

    coder_agent = Agent(
        name=f"CoderAgent_{approach_name.replace(' ', '_')}",
        instructions=coder_instructions,
        output_type=PredictionOutput,
        # output_schema_strict=False, # Removed: This parameter is not valid for Agent.__init__
        # tools=AGENT_TOOLS_METADATA, # How are tools linked? Assume Runner knows?
    )

    # How to pass context (stock_data_context) to the execution?
    # This is the biggest uncertainty with the SDK example.
    # Option 1: Runner takes context? `Runner.run(..., context=stock_data_context)`
    # Option 2: Inject data description into the prompt? (Less ideal)
    # Option 3: A special tool to load context?
    # Let's assume Option 1 for now.

    # The initial prompt for the coder agent
    coder_prompt = f"Analyze the provided stock data for {stock_symbol} using the {approach_name} approach and generate the prediction, report, and code."

    try:
        # Assume Runner.run needs agent, prompt, and potentially context for tools
        # The context might need to include the actual tool functions if not globally registered
        runner_context = {
            "stock_data_dict": stock_data_context, # Pass raw data dict
            "tools": { # Map names to functions if Runner needs it
                 "get_stock_data": get_stock_data, # Might not be needed by coder if data is pre-fetched
                 "execute_python_code": execute_python_code
            }
             # Add OPENAI_API_KEY if SDK doesn't handle it automatically?
             # "openai_api_key": OPENAI_API_KEY
        }

        # *** THIS IS THE CRITICAL UNKNOWN ***
        # How does the Runner execute tools defined in `tools.py` and pass context?
        # The example only shows built-in tools or simple agent handoffs.
        # We'll proceed with a plausible call signature.
        result = await Runner.run(
            coder_agent,
            coder_prompt,
            # context=runner_context # Pass data and potentially tool functions via context?
        )

        # Assuming result.final_output contains the structured output
        prediction_result = result.final_output_as(PredictionOutput)

        # *** POST-PROCESSING / TOOL EXECUTION HANDLING ***
        # If the agent *generates* code but doesn't *execute* it via a tool call within the run:
        # We might need to manually call `execute_python_code` here using the generated code
        # and the `stock_data_context`, then update the `prediction_result`.

        # Example of manual execution if the SDK doesn't handle it implicitly:
        # Check if code exists AND prediction is the default empty JSON string, indicating it wasn't set by the agent/tool run
        if prediction_result.code and prediction_result.prediction == '{}':
             print(f"Manually executing code for approach: {approach_name}")
             exec_output = execute_python_code(prediction_result.code, stock_data_context)

             # Format the prediction output as JSON string
             pred_dict = exec_output.get("prediction_output")
             final_prediction_str = '{}' # Default to empty JSON string
             if pred_dict is not None:
                 try:
                     # Attempt to serialize the output from the executed code
                     final_prediction_str = json.dumps(pred_dict)
                 except TypeError as json_err:
                      print(f"Warning: Could not JSON serialize prediction output for {approach_name}: {json_err}")
                      # Serialize error info instead
                      final_prediction_str = json.dumps({"error": "Serialization failed", "raw_output": str(pred_dict)})
             prediction_result.prediction = final_prediction_str # Assign the JSON string

             prediction_result.tool_stdout = exec_output.get("stdout", "")
             prediction_result.tool_stderr = exec_output.get("stderr", "")
             prediction_result.error = exec_output.get("error", "") # Overwrite any previous agent error with execution error if any
             # Update the report if execution failed
             if prediction_result.error:
                  # Ensure report is not None before appending
                  if prediction_result.report is None: prediction_result.report = ""
                  prediction_result.report += f"\n\nMANUAL EXECUTION ERROR: {prediction_result.error}"
                  prediction_result.report += f"\nSTDERR:\n{prediction_result.tool_stderr}"


        print(f"<--- Finished analysis for approach: {approach_name}")
        # Ensure approach_name is set, sometimes models forget
        prediction_result.approach_name = approach_name
        return prediction_result

    except Exception as e:
        print(f"XXXX ERROR running approach {approach_name}: {e}")
        # Return an error-filled PredictionOutput
        return PredictionOutput(
            approach_name=approach_name,
            prediction="", # Provide default empty string for prediction field since default was removed
            report=f"Failed to run agent for this approach. Error: {str(e)}",
            code="",
            # Provide default empty strings for fields that no longer have defaults in the model
            tool_stdout="",
            tool_stderr="",
            error=str(e)
        )


async def main(stock_symbol: str, approaches: List[str]):
    """Main orchestration function."""
    print(f"Starting analysis for {stock_symbol} with approaches: {', '.join(approaches)}")

    # 1. Fetch data once
    print("Fetching initial stock data...")
    # Use default dates/timeframe for now
    stock_data_context = get_stock_data(stock_symbol=stock_symbol)
    if "error" in stock_data_context or not stock_data_context.get("data"):
        print(f"Failed to fetch initial data: {stock_data_context.get('error', 'No data returned')}")
        return

    print(f"Data fetched successfully ({len(stock_data_context['data'])} records). Running coder agents in parallel...")

    # 2. Run Coder Agents in Parallel
    tasks = [run_analysis_approach(name, stock_symbol, stock_data_context) for name in approaches]
    coder_results: List[PredictionOutput] = await asyncio.gather(*tasks)

    # Filter out failed runs if needed, though judge can handle errors
    # Keep results even if they have code execution errors, judge should see them.
    successful_results = [res for res in coder_results if res.report or res.code]
    print(f"\nCollected {len(successful_results)} results from coder agents (including runs with execution errors).")

    if not successful_results:
        print("No valid analysis results obtained from any coder agent.")
        return

    # 3. Run Judge Agent
    print("Running Judge Agent...")
    judge_input_data = JudgeInput(
        original_request=f"Analyze {stock_symbol} using various methods and select the best prediction.",
        results=successful_results
    )

    try:
        # How does Judge Agent receive complex input like judge_input_data?
        # Option A: Pass the Pydantic object directly if supported.
        # Option B: Serialize to JSON/dict and pass as string/dict prompt.
        # Passing the object directly failed. Let's serialize to dict.
        # Use model_dump() for Pydantic v2+ or dict() for v1
        try:
             # Use model_dump_json for direct JSON serialization if available (Pydantic v2)
             judge_prompt_json = judge_input_data.model_dump_json(indent=2)
        except AttributeError:
             # Fallback for Pydantic v1 / simpler serialization
             try:
                 judge_prompt_dict = judge_input_data.model_dump(mode='json') # Serialize nested models correctly
             except AttributeError:
                 # Fallback for Pydantic v1 might need manual serialization of nested objects
                 results_list = [r.dict() for r in judge_input_data.results]
                 judge_prompt_dict = {"original_request": judge_input_data.original_request, "results": results_list}
             judge_prompt_json = json.dumps(judge_prompt_dict, indent=2)


        print(f"\nSending input to Judge Agent:\n{judge_prompt_json[:1000]}...\n") # Log truncated input (increased length)

        judge_run_result = await Runner.run(
            judge_agent,
            judge_prompt_json # Pass the JSON string as input
            # Alternatively, could try passing judge_prompt_dict if JSON string fails
        )

        # It's possible the SDK *might* automatically parse the JSON string back
        # if the agent's input type was defined, but it's safer to assume the
        # agent just gets the string and needs to parse it based on instructions.
        # The Judge instructions describe the input structure.

        final_decision = judge_run_result.final_output_as(FinalDecision)

        # 4. Print Final Result
        print("\n======= JUDGE'S FINAL DECISION =======")
        print(f"Selected Approach: {final_decision.best_approach_name}")
        print(f"Judge's Reasoning: {final_decision.judge_reasoning}")
        print("\n--- Best Prediction (JSON String) ---")
        print(final_decision.best_prediction)
        # Attempt to parse and print the prediction dict prettily
        try:
            # Ensure the prediction is not None or empty before parsing
            if final_decision.best_prediction and final_decision.best_prediction.strip():
                 best_prediction_dict = json.loads(final_decision.best_prediction)
                 print("\n--- Best Prediction (Parsed) ---")
                 print(json.dumps(best_prediction_dict, indent=2))
            else:
                 print("\n--- Best Prediction (Parsed) ---")
                 print("(Empty prediction string received)")
        except json.JSONDecodeError as json_err:
            print(f"(Could not parse prediction JSON string: {json_err})")
            print(f"Raw string: {final_decision.best_prediction}")


        print("\n--- Best Report ---")
        print(final_decision.best_report)
        print("\n--- Best Code ---")
        print(final_decision.best_code)
        print("======================================")

    except Exception as e:
        print(f"XXXX ERROR running Judge Agent: {e}")
        print("\n--- Raw Coder Results ---")
        for i, res in enumerate(successful_results):
             print(f"\nResult {i+1} ({res.approach_name}):")
             print(f"  Prediction: {res.prediction}")
             print(f"  Report: {res.report[:200]}...") # Truncate long reports
             print(f"  Error: {res.error}")
             print(f"  Stderr: {res.tool_stderr[:200]}...")


if __name__ == "__main__":
    # Define the stock and approaches to try
    stock = "AAPL"
    analysis_approaches = [
        "Simple Moving Average Crossover (10-day vs 30-day)",
        "Linear Regression on recent price trend (last 30 days)",
        # "ARIMA model forecast (using statsmodels)", # Commenting out ARIMA which might need explicit library install/import in tool
        "Basic Momentum Indicator (Rate of Change - 14 days)"
    ]

    asyncio.run(main(stock_symbol=stock, approaches=analysis_approaches))
    print("\nAgent run finished.")
