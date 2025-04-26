import os
import json
import pandas as pd
from datetime import datetime, timedelta
import io
import sys
from contextlib import redirect_stdout, redirect_stderr
import asyncio
import duckdb
from typing import Dict, Any, Optional, List
# Import Agent SDK components
try:
    from agents import function_tool, RunContextWrapper
except ImportError:
    print("ERROR: Failed to import 'agents' library components. Make sure 'openai-agents' is installed.")
    # Define dummy decorators/classes if import fails to avoid immediate script crash
    def function_tool(func=None, **kwargs): return func if func else lambda f: f
    class RunContextWrapper: pass

# Need to adjust path for importing from wealtharc-turbo-er
# This assumes the script is run from the root directory 'slow-takeoff'
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))) # Add slow-takeoff/ to path
try:
    from wealtharc_turbo_er.wa.aggregator import run_all_ingestors
    from wealtharc_turbo_er.wa.config import DB_PATH
    from wealtharc_turbo_er.wa.db import get_db_connection
    # Need to configure logging for the aggregator if not already done elsewhere
    from loguru import logger
    # Basic logging setup if not configured by the main agent script
    # logger.add(sys.stderr, level="INFO") # Example: Log INFO and above to stderr
except ImportError as e:
    print(f"ERROR: Could not import components from wealtharc-turbo-er: {e}")
    # Define dummy functions/variables so the rest of the file doesn't break immediately
    async def run_all_ingestors(*args, **kwargs): raise NotImplementedError("wealtharc-turbo-er import failed")
    DB_PATH = "dummy_db.duckdb"
    def get_db_connection(*args, **kwargs): raise NotImplementedError("wealtharc-turbo-er import failed")
    class LoggerMock:
        def info(self, *args, **kwargs): print("INFO:", *args)
        def success(self, *args, **kwargs): print("SUCCESS:", *args)
        def warning(self, *args, **kwargs): print("WARNING:", *args)
        def error(self, *args, **kwargs): print("ERROR:", *args)
    logger = LoggerMock()

# Potential data sources (choose one or implement switching logic)
# import finnhub # Requires pip install finnhub-python and FINNHUB_API_KEY
import yfinance as yf # Requires pip install yfinance

# --- Configuration ---
# FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY") # Load if using Finnhub
# finnhub_client = finnhub.Client(api_key=FINNHUB_API_KEY) # Initialize if using

# --- Tool Implementations ---

@function_tool
def get_stock_data(stock_symbol: str, start_date: str = None, end_date: str = None, timeframe: str = '1D') -> dict:
    """Fetches historical stock data (OHLCV) for a given symbol using yfinance.

    Handles date defaults and basic error checking. Returns data as a dictionary suitable for JSON conversion.

    Args:
        stock_symbol: The stock ticker symbol (e.g., AAPL, MSFT).
        start_date: Optional. Start date in YYYY-MM-DD format. Defaults to 90 days ago.
        end_date: Optional. End date in YYYY-MM-DD format. Defaults to today.
        timeframe: Optional. Data frequency (e.g., '1D', '1H', '5m'). Defaults to '1D'.
    """
    print(f"Tool: get_stock_data called for {stock_symbol}")
    try:
        # Default dates
        if end_date is None:
            end_date = datetime.now().strftime('%Y-%m-%d')
        if start_date is None:
            start_date = (datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d')

        # Map timeframe (yfinance uses different notation)
        interval_map = {
            '1D': '1d', '1H': '1h', '5m': '5m', '15m': '15m', '30m': '30m' # Add others as needed
        }
        yf_interval = interval_map.get(timeframe, '1d') # Default to daily

        # Validate timeframe vs date range for yfinance constraints if needed
        # (e.g., intraday data has date range limits)

        print(f"Fetching {stock_symbol} data from {start_date} to {end_date} with interval {yf_interval}")

        # Fetch data using yfinance
        ticker = yf.Ticker(stock_symbol)
        # Note: yfinance interval parameter depends on period/start&end dates
        # For start/end dates, interval is usually sufficient.
        hist = ticker.history(start=start_date, end=end_date, interval=yf_interval)

        if hist.empty:
            return {"error": f"No data found for {stock_symbol} in the specified range/interval."}

        # Reset index to turn the DatetimeIndex into a column
        hist.reset_index(inplace=True)

        # Find the actual datetime column name (case-insensitive, common names: Date, Datetime)
        datetime_col_name = None
        for col in hist.columns:
            if col.lower() in ['date', 'datetime']:
                datetime_col_name = col
                break

        if not datetime_col_name:
            return {"error": "Could not find datetime column in yfinance output after reset_index."}

        # Define standard columns we want
        target_cols_map = {
            datetime_col_name: 'datetime',
            'Open': 'open',
            'High': 'high',
            'Low': 'low',
            'Close': 'close',
            'Volume': 'volume'
        }

        # Rename columns that exist in the DataFrame
        cols_to_rename = {k: v for k, v in target_cols_map.items() if k in hist.columns}
        hist.rename(columns=cols_to_rename, inplace=True)

        # Define the final columns we absolutely need
        final_expected_cols = ['datetime', 'open', 'high', 'low', 'close', 'volume']
        available_cols = [col for col in final_expected_cols if col in hist.columns]

        # Check if essential 'datetime' column is present
        if 'datetime' not in available_cols:
            return {"error": f"Critical 'datetime' column missing after processing yfinance data."}

        # Convert datetime column to string format for JSON serialization
        # Ensure the column is actually datetime type before using .dt accessor
        if pd.api.types.is_datetime64_any_dtype(hist['datetime']):
             hist['datetime'] = hist['datetime'].dt.strftime('%Y-%m-%d %H:%M:%S')
        else:
             # Attempt conversion if it's not already datetime
             try:
                  hist['datetime'] = pd.to_datetime(hist['datetime']).dt.strftime('%Y-%m-%d %H:%M:%S')
             except Exception as dt_err:
                  print(f"Warning: Could not format datetime column: {dt_err}")
                  # Proceeding with original format, might cause issues later
                  hist['datetime'] = hist['datetime'].astype(str)


        # Select available columns and convert to list of dictionaries
        data_list = hist[available_cols].to_dict('records')

        print(f"Successfully fetched and processed {len(data_list)} data points.")
        return {"data": data_list} # Return data in a structured dict

    except Exception as e:
        print(f"Error fetching data for {stock_symbol} with yfinance: {e}")
        return {"error": f"Failed to fetch data: {str(e)}"}

    # --- Finnhub Implementation (Alternative) ---
    # try:
    #     print(f"Fetching {stock_symbol} data using Finnhub...")
    #     # Finnhub uses Unix timestamps
    #     start_ts = int(datetime.strptime(start_date, '%Y-%m-%d').timestamp())
    #     end_ts = int(datetime.strptime(end_date, '%Y-%m-%d').timestamp())
    #     resolution_map = {'1D': 'D', '1H': '60', '30m': '30', '15m': '15', '5m': '5'} # Finnhub resolutions
    #     resolution = resolution_map.get(timeframe, 'D')
    #
    #     # Call Finnhub API
    #     res = finnhub_client.stock_candles(stock_symbol, resolution, start_ts, end_ts)
    #
    #     if res.get('s') != 'ok':
    #          return {"error": f"Finnhub API error for {stock_symbol}: {res.get('s', 'Unknown error')}"}
    #
    #     # Process Finnhub response (it's structured differently)
    #     if not res.get('t'): # Check if timestamp list exists
    #          return {"error": f"No data found via Finnhub for {stock_symbol} in the specified range/interval."}
    #
    #     df = pd.DataFrame({
    #         'datetime': [datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S') for ts in res['t']],
    #         'open': res['o'],
    #         'high': res['h'],
    #         'low': res['l'],
    #         'close': res['c'],
    #         'volume': res['v']
    #     })
    #     data_list = df.to_dict('records')
    #     print(f"Successfully fetched {len(data_list)} data points via Finnhub.")
    #     return {"data": data_list}
    #
    # except Exception as e:
    #     print(f"Error fetching data for {stock_symbol} with Finnhub: {e}")
     #     return {"error": f"Failed to fetch data via Finnhub: {str(e)}"}


@function_tool
def execute_python_code(ctx: RunContextWrapper[Any], code: str) -> dict:
    """Executes a string of Python code in a restricted scope.

    Injects fetched stock data ('df') and aggregated data ('aggregated_data') into the scope from the context.
    Captures stdout, stderr, and the value of the 'prediction_output' variable assigned by the code.
    WARNING: Uses exec(), which has security implications. Sandboxing is recommended for production.

    Args:
        ctx: The agent run context, expected to contain 'stock_data_dict' and 'aggregated_data_dict'.
        code: The Python code string to execute.
    """
    print(f"Tool: execute_python_code called.")
    # print(f"Code to execute:\n---\n{code}\n---") # Optional: Log the code for debugging

    local_scope = {}
    error_occurred = False
    std_err_prep = ""

    # Retrieve data from context
    data_context = ctx.context.get("stock_data_dict", {}) if ctx.context else {}
    aggregated_data_context = ctx.context.get("aggregated_data_dict", {}) if ctx.context else {}

    # Prepare DataFrame from the stock data context
    if data_context and "data" in data_context and data_context["data"]:
        try:
            df = pd.DataFrame(data_context["data"])
            # Attempt to convert relevant columns to numeric, coercing errors
            for col in ['open', 'high', 'low', 'close', 'volume']:
                 if col in df.columns:
                      df[col] = pd.to_numeric(df[col], errors='coerce')
            # Handle datetime conversion if needed (assuming 'datetime' column exists)
            if 'datetime' in df.columns:
                df['datetime'] = pd.to_datetime(df['datetime'], errors='coerce')
                df.set_index('datetime', inplace=True) # Often useful for time series analysis

            print(f"DataFrame with {len(df)} rows prepared for code execution.")
            local_scope['df'] = df
            local_scope['pd'] = pd # Make pandas available
            local_scope['numpy'] = __import__('numpy') # Make numpy available as numpy
            # Add other safe libraries here if needed, e.g.,
            # local_scope['sklearn'] = __import__('sklearn')
            # local_scope['statsmodels'] = __import__('statsmodels')
        except Exception as e:
             print(f"Error preparing stock DataFrame for code execution: {e}")
             std_err_prep += f"Stock data preparation failed: {str(e)}\n"
             error_occurred = True
             # Don't return yet, allow aggregated data prep and potential execution without 'df'
    else:
        print("Warning: No stock data ('df') provided for code execution.")
        std_err_prep += "Warning: No stock data ('df') provided.\n"
        # Allow execution without 'df' if aggregated_data is present


    # Prepare aggregated data context
    if aggregated_data_context and "data" in aggregated_data_context:
         print("Aggregated data context provided, adding 'aggregated_data' to scope.")
         # Use .get() for safety, although we check aggregated_data_context above
         local_scope['aggregated_data'] = aggregated_data_context.get("data", {})
         # Log if there were errors during aggregation fetch
         if "errors" in aggregated_data_context and aggregated_data_context["errors"]:
              agg_errors = "; ".join(aggregated_data_context["errors"])
              print(f"Warning: Aggregated data fetch had errors: {agg_errors}")
              std_err_prep += f"Warning: Aggregated data fetch had errors: {agg_errors}\n"
    else:
        print("Warning: No aggregated data provided for code execution.")
        std_err_prep += "Warning: No aggregated data provided.\n"
        # Allow execution without 'aggregated_data' if 'df' is present

    # If neither data source was successfully prepared or provided, return error
    if 'df' not in local_scope and 'aggregated_data' not in local_scope:
         return {"error": "Neither stock data ('df') nor aggregated data was available for execution.", "stdout": "", "stderr": std_err_prep}

    # Original code expected a return here on error, keeping structure similar
    # but now it only returns if BOTH contexts are unusable.
    # The try...except below handles the actual execution.

    stdout_capture = io.StringIO()
    stderr_capture = io.StringIO()

    # Execute the code within the controlled scope
    # (Removed duplicated data preparation block here)
    try:
        with redirect_stdout(stdout_capture), redirect_stderr(stderr_capture):
            exec(code, {"__builtins__": {}}, local_scope) # Restricted builtins for safety

        # Extract results
        stdout_val = stdout_capture.getvalue()
        stderr_val = stderr_capture.getvalue()
        prediction = local_scope.get('prediction_output', None) # Get the specific variable

        print("Code execution finished.")
        if stderr_val:
            print(f"Execution stderr:\n{stderr_val}")
        if prediction is not None:
             print(f"Prediction output variable found: {prediction}")


        # Format output for the Assistant
        result = {
            "stdout": stdout_val,
            "stderr": stderr_val,
            "prediction_output": prediction # Can be None if not set by the code
        }
        # Convert numpy types if prediction is numpy array/scalar for JSON serialization
        if isinstance(prediction, __import__('numpy').ndarray):
             result["prediction_output"] = prediction.tolist()
        elif isinstance(prediction, __import__('numpy').generic):
             result["prediction_output"] = prediction.item()


        return result

    except Exception as e:
        print(f"Error during code execution: {e}")
        stderr_val = stderr_capture.getvalue()
        return { # Add the missing return statement and correct indentation
            "error": f"Code execution failed: {str(e)}",
            "stdout": stdout_capture.getvalue(),
            "stderr": std_err_prep + stderr_val + f"\nException: {str(e)}" # Prepend prep errors/warnings
        }

# --- New Aggregated Data Tool ---

# Define tables created by the ingestors we expect to query
# Note: Ensure these table names match exactly what aggregator.py creates in the DB.
AGGREGATOR_TABLES = {
    "google_trends": "google_trends_interest",
    "wikimedia": "wikipedia_pages",
    "gdelt": "gdelt_mentions",
    "stocktwits": "stocktwits_messages",
    "newsapi": "news_raw", # <-- Add NewsAPI table
    # Add other tables if aggregator.py uses more ingestors (e.g., reddit, sec_edgar etc. if used)
    "reddit": "reddit_submissions", # Assuming table name
    "sec_edgar": "sec_filings", # Assuming table name
}

@function_tool
async def get_aggregated_data(query_name: str, query_symbol: Optional[str] = None, limit_per_table: int = 20) -> Dict[str, Any]:
    """Runs wealtharc-turbo-er ingestors and queries the database for aggregated data.

    Fetches data from sources like Google Trends, Wikipedia, GDELT, StockTwits, NewsAPI, Reddit, SEC Edgar etc.,
    related to the given company name or symbol.

    Args:
        query_name: The company name or primary keyword to search for (e.g., 'Apple Inc.', 'NVIDIA').
        query_symbol: Optional. The stock ticker symbol (e.g., AAPL, NVDA). If provided, used for symbol-specific sources like StockTwits.
        limit_per_table: Optional. Max number of records to fetch per data source table (default: 20).
    """
    print(f"Tool: get_aggregated_data called for '{query_name}' (Symbol: {query_symbol})")
    results = {"ingestion_summary": {}, "data": {}, "errors": []}
    db_file = DB_PATH # Use the imported path

    try:
        # Step 1: Run the ingestors
        logger.info(f"Running ingestors for query: '{query_name}'...")
        # Assuming run_all_ingestors is available and correctly imported
        # Note: Ensure the called run_all_ingestors handles logging setup or pass logger.
        await run_all_ingestors(
            query_name=query_name,
            query_symbol=query_symbol,
            db_path=db_file,
            limit_per_source=limit_per_table * 2, # Fetch slightly more initially
            create_db_schema=True # Ensure schema exists
        )
        logger.success(f"Ingestion process completed for query: '{query_name}'.")
        results["ingestion_summary"]["status"] = "Completed" # Basic summary

    except Exception as e:
        logger.error(f"Aggregator run failed for '{query_name}': {e}", exc_info=True)
        results["errors"].append(f"Aggregator run failed: {str(e)}")
        # Continue to try reading existing data if any

    # Step 2: Query the database
    conn = None
    try:
        logger.info(f"Connecting to database '{db_file}' to fetch aggregated data.")
        conn = get_db_connection(db_file, read_only=True) # Read-only connection

        # Check available tables
        try:
             existing_tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall()
             existing_table_names = {row[0] for row in existing_tables}
             logger.info(f"Tables found in DB: {existing_table_names}")
        except Exception as db_err: # Catch potential DuckDB errors during introspection
            logger.error(f"Failed to list tables in database: {db_err}")
            results["errors"].append(f"DB table check failed: {str(db_err)}")
            existing_table_names = set() # Assume no tables if check fails

        for key, table_name in AGGREGATOR_TABLES.items():
            if table_name not in existing_table_names:
                 logger.warning(f"Table '{table_name}' not found in database. Skipping query for '{key}'.")
                 results["data"][key] = {"error": f"Table '{table_name}' not found."}
                 continue # Skip to next table

            try:
                # Basic query - selecting all columns, ordering by a potential timestamp, limiting results
                # We need to guess common timestamp column names or make queries more specific later
                # Common timestamp columns: 'timestamp', 'date', 'publishedAt', 'created_at'
                # This is a simplified approach; robust querying requires knowing exact schemas
                query = f"SELECT * FROM {table_name} ORDER BY timestamp DESC LIMIT {limit_per_table};" # Example query
                try:
                    logger.info(f"Querying table '{table_name}'...")
                    data_df = conn.execute(query).fetchdf()
                except (duckdb.CatalogException, duckdb.BinderException) as col_err:
                    # If 'timestamp' column doesn't exist, try a simpler query
                    logger.warning(f"Column 'timestamp' likely missing in '{table_name}', trying basic query: {col_err}")
                    query = f"SELECT * FROM {table_name} LIMIT {limit_per_table};"
                    try:
                         data_df = conn.execute(query).fetchdf()
                    except Exception as fallback_err:
                         logger.error(f"Fallback query failed for table '{table_name}': {fallback_err}")
                         results["data"][key] = {"error": f"Query failed: {fallback_err}"}
                         continue # Skip to next table

                if not data_df.empty:
                    # Convert DataFrame to list of dicts for JSON serialization
                    # Handle potential Timestamp objects
                    for col in data_df.select_dtypes(include=['datetime64[ns]']).columns:
                        data_df[col] = data_df[col].astype(str)
                    results["data"][key] = data_df.to_dict('records')
                    logger.success(f"Fetched {len(data_df)} records from '{table_name}'.")
                else:
                    logger.info(f"No records found in '{table_name}'.")
                    results["data"][key] = [] # Empty list if no data

            except Exception as e:
                logger.error(f"Failed to query table '{table_name}': {e}", exc_info=True)
                results["data"][key] = {"error": f"Query failed: {str(e)}"}
                results["errors"].append(f"Query failed for {table_name}: {str(e)}")

    except Exception as e:
        logger.error(f"Database connection/query failed: {e}", exc_info=True)
        results["errors"].append(f"Database connection/query failed: {str(e)}")
    finally:
        if conn:
            conn.close()
            logger.info("Database connection closed.")


# Example usage (for testing tools directly)
if __name__ == '__main__':

    async def test_async_tools():
        # --- Test get_stock_data ---
        print("Testing get_stock_data...")
        # stock_data = get_stock_data("AAPL", start_date="2024-01-01", end_date="2024-01-10")
        stock_data = get_stock_data("MSFT") # Test default dates
        if "error" in stock_data:
            print(f"Error fetching data: {stock_data['error']}")
        elif "data" in stock_data:
            print(f"Fetched {len(stock_data['data'])} records.")
            print("Sample:", stock_data['data'][:2]) # Print first 2 records
            df_test = pd.DataFrame(stock_data['data'])
            print("\nDataFrame Info:")
            df_test.info()

        # --- Test execute_python_code ---
        # Requires manual context creation for direct testing
        print("\nTesting execute_python_code...")
        if "data" in stock_data and stock_data["data"]:
            mock_ctx = type('obj', (object,), {
                'context': {
                    'stock_data_dict': stock_data,
                    'aggregated_data_dict': {'data': {'news_raw': [{'title': 'mock news'}]}} # Mock aggregated
                }
            })()

            # Example 1: Simple calculation
            test_code_1 = """
import pandas as pd
print("Calculating mean closing price...")
mean_price = df['close'].mean()
prediction_output = {'mean_close': mean_price}
print(f"Mean calculated: {mean_price}")
"""
            print("\nExecuting Test Code 1 (Mean Calculation):")
            exec_result_1 = execute_python_code(mock_ctx, test_code_1)
            print("Result 1:", json.dumps(exec_result_1, indent=2))

            # Example 2: Code with potential error
            test_code_2 = """
print("Attempting division by zero...")
result = 1 / 0
prediction_output = result
"""
            print("\nExecuting Test Code 2 (Division by Zero):")
            exec_result_2 = execute_python_code(mock_ctx, test_code_2)
            print("Result 2:", json.dumps(exec_result_2, indent=2))

            # Example 3: Code using numpy
            test_code_3 = """
import numpy
print("Calculating standard deviation using numpy...")
std_dev = numpy.std(df['close'])
prediction_output = {'std_dev_close': std_dev}
print(f"Std Dev calculated: {std_dev}")
"""
            print("\nExecuting Test Code 3 (Numpy Std Dev):")
            exec_result_3 = execute_python_code(mock_ctx, test_code_3)
            print("Result 3:", json.dumps(exec_result_3, indent=2))

            # Example 4: Code using aggregated data
            test_code_4 = """
print("Checking aggregated data...")
news_count = len(aggregated_data.get('news_raw', []))
prediction_output = {'news_count': news_count}
print(f"Found {news_count} news items.")
"""
            print("\nExecuting Test Code 4 (Aggregated Data):")
            exec_result_4 = execute_python_code(mock_ctx, test_code_4)
            print("Result 4:", json.dumps(exec_result_4, indent=2))


        else:
            print("Skipping execute_python_code tests as stock data fetching failed.")

        # --- Test get_aggregated_data ---
        print("\nTesting get_aggregated_data...")
        agg_data = await get_aggregated_data(query_name="NVIDIA", query_symbol="NVDA")
        if "error" in agg_data or (isinstance(agg_data.get("errors"), list) and agg_data["errors"]):
            print(f"Error fetching aggregated data: {agg_data.get('error', agg_data.get('errors'))}")
        elif "data" in agg_data:
            print("Aggregated data fetched successfully.")
            for key, items in agg_data["data"].items():
                if isinstance(items, list):
                    print(f"  - {key}: {len(items)} records (Sample: {items[0] if items else 'N/A'})")
                elif isinstance(items, dict) and "error" in items:
                    print(f"  - {key}: Error - {items['error']}")
            # print(json.dumps(agg_data, indent=2)) # Optional: print full result

    # Run the async test function
    asyncio.run(test_async_tools())
