import os
import asyncio
import json
import pandas as pd
# Remove direct openai import if SDK handles client internally
# import openai
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


# Import the decorated tool functions directly
from tools import get_stock_data, execute_python_code, get_aggregated_data

# Load environment variables
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY") # SDK generally uses this automatically
OPENAI_MODEL_ID = os.getenv("OPENAI_MODEL_ID")

# --- Pydantic Models for Agent Outputs ---

class PredictionOutput(BaseModel):
    """Output structure for each Coder Agent run."""
    approach_name: str = Field(description="Name of the prediction approach used (e.g., 'ARIMA', 'Linear Regression').")
    # Use Dict for the prediction output from the executed code
    prediction: Dict[str, Any] = Field(description="The final prediction result dictionary (e.g., {'prediction_value': 150.5, 'signal': 'BUY'}).")
    report: str = Field(description="A brief report explaining the methodology, findings, and confidence.")
    code: str = Field(description="The Python code generated for the analysis.")
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
    # Use Dict to match the type in PredictionOutput
    best_prediction: Dict[str, Any] = Field(description="The prediction dictionary from the selected best approach.")
    best_report: str = Field(description="The report from the selected best approach.")
    best_code: str = Field(description="The code from the selected best approach.")
    judge_reasoning: str = Field(description="The judge's reasoning for selecting this result.")

# --- Tool Integration (Using SDK's @function_tool) ---

# --- Tool Integration (Using SDK's @function_tool) ---
# No need for AGENT_TOOLS_METADATA. The SDK uses the decorated functions directly.
# Context passing will be handled via Runner.run(..., context=...) and ctx argument in tools.


# --- Agent Definitions ---

# Base instructions for coder agents
CODER_BASE_INSTRUCTIONS = """
You are a Quantitative Analyst Agent. Your task is to analyze historical stock data for {stock_symbol} and predict its future price movement based on the '{approach_name}' approach using the tools provided.

1.  **Analyze Data**: You have access to historical stock data ('df') and aggregated news/trends ('aggregated_data') through the context provided to the `execute_python_code` tool.
2.  **Select Methodology**: Apply the '{approach_name}' methodology. Incorporate insights from BOTH the stock data AND the aggregated data where relevant. Be creative if the name is generic (e.g., 'Trend Following', 'Sentiment Analysis').
3.  **Generate Code**: Generate Python code using pandas ('pd') and numpy ('numpy'). The code MUST assign its final prediction result (a Python dictionary, e.g., `{{'prediction_value': 150.5, 'signal': 'BUY', 'confidence_based_on_news': 0.7}}`) to a variable named `prediction_output`. Focus ONLY on calculation; avoid plotting or file I/O.
4.  **Execute Code**: Use the `execute_python_code` tool, passing the generated code string to it. This tool will run the code with the 'df' and 'aggregated_data' context available.
5.  **Generate Report**: Write a brief report explaining your methodology, findings, and confidence.
6.  **Final Output**: Structure your final output according to the `PredictionOutput` format. The `prediction` field should contain the *dictionary* returned by the `execute_python_code` tool's `prediction_output` key. The `tool_stdout`, `tool_stderr`, and `error` fields should be populated from the tool's result if available.
"""

# Judge agent instructions
JUDGE_INSTRUCTIONS = """
You are a Chief Investment Officer Agent. You have received multiple stock prediction analyses for the same request from different Quantitative Analyst Agents, each using a different approach.
Your task is to evaluate these analyses based on the provided prediction (which is a dictionary), report, code, and any execution output/errors.

Input: A list of PredictionOutput objects, where the 'prediction' field contains a Python dictionary.

Evaluation Criteria:
1.  **Clarity and Soundness of Methodology:** Does the report clearly explain a reasonable approach?
2.  **Code Quality:** Is the provided Python code relevant, correct for the described approach, and safe (no obvious malicious patterns)?
3.  **Prediction Plausibility:** Does the prediction dictionary seem reasonable given the data and approach (without guaranteeing accuracy)?
4.  **Execution Success:** Did the code run successfully (check tool_stdout/tool_stderr/error fields)? Penalize runs with significant errors.
5.  **Consistency:** Do the report, code, and the prediction dictionary align?

Output: Select the *single best* analysis and provide your reasoning, adhering to the FinalDecision format. Copy the selected prediction dictionary into the 'best_prediction' field. If no analysis is satisfactory, explain why.
"""

# Define Agent instances (assuming Agent() takes instructions and tool metadata)
# Attempting to pass model and potentially api_key if supported by the Agent class
try:
    judge_agent = Agent(
        name="JudgeAgent",
        instructions=JUDGE_INSTRUCTIONS,
        output_type=FinalDecision, # Specify Pydantic model for output validation
        # tools = [], # Judge doesn't need tools directly
        model=OPENAI_MODEL_ID,
        # api_key=OPENAI_API_KEY # SDK handles API key via environment variable
        # client=client
    )
    # print("Initialized JudgeAgent.") # Simpler log
except TypeError as e:
     # Provide a more informative warning if model arg fails
     print(f"Warning: Could not pass 'model' to JudgeAgent init: {e}. Using SDK default model.")
     judge_agent = Agent(
         name="JudgeAgent",
         instructions=JUDGE_INSTRUCTIONS,
         output_type=FinalDecision
     )


# Coder agents will be created dynamically in the main loop

# --- Main Orchestration Logic ---

async def run_analysis_approach(approach_name: str, stock_symbol: str, stock_data_context: Dict, aggregated_data_context: Dict) -> PredictionOutput:
    """
    Runs a single coder agent for a specific approach, providing both
    stock price data ('df') and aggregated news/trends data ('aggregated_data').
    """
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

    # Attempt to pass model and API key to Coder Agent
    try:
        coder_agent = Agent(
            name=f"CoderAgent_{approach_name.replace(' ', '_')}",
            instructions=coder_instructions,
            output_type=PredictionOutput,
            model=OPENAI_MODEL_ID,
            # api_key=OPENAI_API_KEY, # Remove API key param
            # client=client,
            tools=[get_stock_data, execute_python_code, get_aggregated_data], # Pass decorated tools
        )
        # print(f"Initialized CoderAgent {approach_name}.") # Simpler log
    except TypeError as e:
        print(f"Warning: Could not pass 'model' or 'tools' to CoderAgent init: {e}. Using SDK defaults.")
        coder_agent = Agent(
            name=f"CoderAgent_{approach_name.replace(' ', '_')}",
            instructions=coder_instructions,
            output_type=PredictionOutput,
            tools=[get_stock_data, execute_python_code, get_aggregated_data] # Pass tools here too
        )

    # How to pass context (stock_data_context) to the execution?
    # This is the biggest uncertainty with the SDK example.
    # Option 1: Runner takes context? `Runner.run(..., context=stock_data_context)`
    # Option 2: Inject data description into the prompt? (Less ideal)
    # Option 3: A special tool to load context?
    # The initial prompt for the coder agent, guiding it to use the tool
    coder_prompt = f"Analyze the stock data for {stock_symbol} using the {approach_name} approach. Generate the Python code, then use the 'execute_python_code' tool to run it, and finally formulate the report and final output structure."

    try:
        # Context for the Runner only needs the data; tools are linked via the Agent.
        runner_context = {
            "stock_data_dict": stock_data_context,
            "aggregated_data_dict": aggregated_data_context
        }

        # The Runner will now execute the tools passed to the Agent.
        # The agent needs to be instructed to call the `execute_python_code` tool.
        # The tool will receive the context via its `ctx` parameter.
        result = await Runner.run(
            coder_agent,
            coder_prompt,
            context=runner_context # Pass data and tool functions via context
        )

        # Assuming result.final_output contains the structured output
        # The SDK's Runner should have handled the tool call (`execute_python_code`)
        # and the agent should have used the tool's output to populate the PredictionOutput.
        prediction_result = result.final_output_as(PredictionOutput)

        # *** Manual execution logic is removed ***

        print(f"<--- Finished analysis for approach: {approach_name}")
        # Ensure approach_name is set, sometimes models forget
        prediction_result.approach_name = approach_name
        return prediction_result

    except Exception as e:
        print(f"XXXX ERROR running approach {approach_name}: {e}")
        # Return a simplified error-filled PredictionOutput
        return PredictionOutput(
            approach_name=approach_name,
            prediction={}, # Default to empty dict
            report=f"Failed to run agent or process result for this approach. Error: {str(e)}",
            code="",
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

    print(f"Stock data fetched successfully ({len(stock_data_context['data'])} records).")

    # 1b. Fetch aggregated data
    print("Fetching aggregated news/trends data...")
    # Use stock_symbol as query_name and query_symbol for simplicity
    # A more robust approach might involve getting the company name separately
    # Await the async tool function call
    aggregated_data_context = await get_aggregated_data(query_name=stock_symbol, query_symbol=stock_symbol)
    # Check for errors in the returned dictionary
    if aggregated_data_context.get("error") or (isinstance(aggregated_data_context.get("errors"), list) and aggregated_data_context["errors"]):
        print(f"Warning: Failed to fetch or encountered errors during aggregated data fetch: {aggregated_data_context.get('error', aggregated_data_context.get('errors'))}")
        # Proceed without aggregated data if fetching failed
        aggregated_data_context = {"data": {}, "errors": ["Fetching failed or returned errors"]}
    else:
        print("Aggregated data fetched successfully.")
        # Optional: Log summary of fetched aggregated data
        for key, data in aggregated_data_context.get("data", {}).items():
             if isinstance(data, list):
                  print(f"  - {key}: {len(data)} records")
             elif isinstance(data, dict) and "error" in data:
                  print(f"  - {key}: Error - {data['error']}")


    print("Running coder agents in parallel...")
    # 2. Run Coder Agents in Parallel, passing both data contexts
    tasks = [run_analysis_approach(name, stock_symbol, stock_data_context, aggregated_data_context) for name in approaches]
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
        # Print the prediction dictionary directly
        print("\n--- Best Prediction (Dictionary) ---")
        try:
            # Ensure the prediction is not None/empty dict before printing
            if final_decision.best_prediction:
                 print(json.dumps(final_decision.best_prediction, indent=2))
            else:
                 print("(Empty prediction dictionary received)")
        except Exception as print_err: # Catch potential errors during printing/serialization
            print(f"(Could not display prediction dictionary: {print_err})")
            print(f"Raw data: {final_decision.best_prediction}")


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
