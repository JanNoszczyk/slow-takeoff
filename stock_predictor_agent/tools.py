import os
import json
import pandas as pd
from datetime import datetime, timedelta
import io
import sys
from contextlib import redirect_stdout, redirect_stderr

# Potential data sources (choose one or implement switching logic)
# import finnhub # Requires pip install finnhub-python and FINNHUB_API_KEY
import yfinance as yf # Requires pip install yfinance

# --- Configuration ---
# FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY") # Load if using Finnhub
# finnhub_client = finnhub.Client(api_key=FINNHUB_API_KEY) # Initialize if using

# --- Tool Implementations ---

def get_stock_data(stock_symbol: str, start_date: str = None, end_date: str = None, timeframe: str = '1D') -> dict:
    """
    Fetches historical stock data (OHLCV) for a given symbol using yfinance.
    Handles date defaults and basic error checking.
    Returns data as a dictionary suitable for JSON conversion.
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


def execute_python_code(code: str, data_context: dict = None) -> dict:
    """
    Executes a string of Python code in a restricted scope.
    Injects fetched stock data ('df') into the scope if available.
    Captures stdout, stderr, and the value of 'prediction_output'.
    WARNING: Uses exec(), which has security implications. Sandboxing is recommended for production.
    """
    print(f"Tool: execute_python_code called.")
    # print(f"Code to execute:\n---\n{code}\n---") # Optional: Log the code for debugging

    if data_context is None or "data" not in data_context or not data_context["data"]:
         return {"error": "No stock data available to execute code.", "stdout": "", "stderr": ""}

    local_scope = {}
    try:
        # Prepare DataFrame from the context
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
        print(f"Error preparing data for code execution: {e}")
        return {"error": f"Data preparation failed: {str(e)}", "stdout": "", "stderr": ""}


    stdout_capture = io.StringIO()
    stderr_capture = io.StringIO()

    # Execute the code within the controlled scope
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
        return {
            "error": f"Code execution failed: {str(e)}",
            "stdout": stdout_capture.getvalue(),
            "stderr": stderr_val + f"\nException: {str(e)}" # Append exception to stderr
        }

# Example usage (for testing tools directly)
if __name__ == '__main__':
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
    print("\nTesting execute_python_code...")
    if "data" in stock_data and stock_data["data"]:
        # Example 1: Simple calculation
        test_code_1 = """
import pandas as pd
print("Calculating mean closing price...")
mean_price = df['close'].mean()
prediction_output = {'mean_close': mean_price}
print(f"Mean calculated: {mean_price}")
"""
        print("\nExecuting Test Code 1 (Mean Calculation):")
        exec_result_1 = execute_python_code(test_code_1, stock_data)
        print("Result 1:", json.dumps(exec_result_1, indent=2))

        # Example 2: Code with potential error
        test_code_2 = """
print("Attempting division by zero...")
result = 1 / 0
prediction_output = result
"""
        print("\nExecuting Test Code 2 (Division by Zero):")
        exec_result_2 = execute_python_code(test_code_2, stock_data)
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
        exec_result_3 = execute_python_code(test_code_3, stock_data)
        print("Result 3:", json.dumps(exec_result_3, indent=2))

    else:
        print("Skipping execute_python_code tests as data fetching failed.")
