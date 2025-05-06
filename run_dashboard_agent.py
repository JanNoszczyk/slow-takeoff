import asyncio
import json
import os
from typing import Optional

# Import the runner function from the dashboard agent
try:
    from project_agents.dashboard_agent.agent import run_generation
    print("DEBUG: Successfully imported run_generation from project_agents.dashboard_agent.agent")
except ImportError as e:
    print(f"ERROR: Failed to import run_generation: {e}")
    async def run_generation(json_str: str) -> Optional[str]: # Fallback
        print("ERROR: run_generation fallback executed due to import error.")
        return None

async def main():
    """
    Loads research data, runs the dashboard generator agent, and saves the TSX output.
    """
    input_json_path = "stonk_research_output.json"
    output_tsx_path = "dashboard/src/components/GeneratedStockDashboard.tsx"

    # 1. Load the research data JSON
    try:
        with open(input_json_path, 'r') as f:
            research_json_string = f.read()
        print(f"DEBUG: Successfully read research data from {input_json_path}")
    except FileNotFoundError:
        print(f"ERROR: Input file not found: {input_json_path}")
        return
    except Exception as e:
        print(f"ERROR: Failed to read {input_json_path}: {e}")
        return

    # 2. Run the dashboard generator agent
    generated_tsx_code = await run_generation(research_json_string)

    # 3. Save the generated TSX code
    if generated_tsx_code:
        try:
            # Ensure the output directory exists
            os.makedirs(os.path.dirname(output_tsx_path), exist_ok=True)
            with open(output_tsx_path, "w") as f:
                f.write(generated_tsx_code)
            print(f"\n--- Successfully saved generated TSX code to {output_tsx_path} ---")
        except Exception as e:
            print(f"\n--- ERROR: Failed to save generated TSX code to {output_tsx_path}: {e} ---")
            print("\n--- Generated TSX Code (from memory) ---")
            print(generated_tsx_code) # Print code if saving failed
    else:
        print("\n--- Failed to generate TSX code, nothing saved. ---")

if __name__ == "__main__":
    asyncio.run(main())
    print("\nDashboard Generation Runner finished.")
