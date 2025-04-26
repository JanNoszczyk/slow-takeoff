import os
import requests
import yfinance as yf
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from dotenv import load_dotenv

# Import Agent SDK components
try:
    from agents import function_tool, RunContextWrapper
except ImportError:
    print("ERROR: Failed to import 'agents' library components. Make sure 'openai-agents' is installed.")
    # Define dummy decorators/classes if import fails to avoid immediate script crash
    def function_tool(func=None, **kwargs): return func if func else lambda f: f
    class RunContextWrapper: pass

# Load API keys from the wealtharc-turbo-er .env file
# Construct the path relative to this file's location
dotenv_path = os.path.join(os.path.dirname(__file__), '..', 'wealtharc-turbo-er', '.env')
load_dotenv(dotenv_path=dotenv_path)

FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY")
ALPHAVANTAGE_API_KEY = os.getenv("ALPHAVANTAGE_API_KEY")
FRED_API_KEY = os.getenv("FRED_API_KEY")
EIA_API_KEY = os.getenv("EIA_API_KEY")
NEWSAPI_API_KEY = os.getenv("NEWSAPI_API_KEY")

# --- Tool Implementations ---

@function_tool
def get_yahoo_quote(symbol: str) -> Dict[str, Any]:
    """Fetches near real-time quote data for a given stock symbol using Yahoo Finance.

    Provides information like current price, day high/low, volume, market cap, etc.
    Data might have a delay (typically ~15 minutes).

    Args:
        symbol: The stock ticker symbol (e.g., AAPL, MSFT).

    Returns:
        A dictionary containing quote information or an error message.
    """
    print(f"Tool: get_yahoo_quote called for {symbol}")
    try:
        ticker = yf.Ticker(symbol)
        # .info provides a dictionary with various quote and company details
        info = ticker.info
        if not info or info.get('quoteType') == 'MUTUALFUND': # yfinance sometimes returns minimal dict for errors/delisted
             # Check for common error indicator or if it's not an equity/ETF
             fast_info = ticker.fast_info # fast_info might be more reliable for basic checks
             if not fast_info or fast_info.get('last_price') is None:
                  return {"error": f"Could not retrieve valid quote info for symbol {symbol}. It might be delisted or invalid."}
             # If fast_info looks okay, return that instead
             print(f"Tool: get_yahoo_quote for {symbol} using fast_info fallback.")
             # Add timestamp to fast_info
             fast_info['timestamp_utc'] = datetime.utcnow().isoformat()
             return {"quote": fast_info}


        # Add a timestamp to the returned data
        info['timestamp_utc'] = datetime.utcnow().isoformat()
        print(f"Tool: get_yahoo_quote for {symbol} successful.")
        # Return relevant parts of the info dict under a 'quote' key
        # Select some common fields, but the agent can potentially access others if needed
        quote_data = {
            'symbol': info.get('symbol'),
            'shortName': info.get('shortName'),
            'longName': info.get('longName'),
            'currency': info.get('currency'),
            'quoteType': info.get('quoteType'),
            'marketState': info.get('marketState'),
            'regularMarketPrice': info.get('regularMarketPrice'),
            'regularMarketChange': info.get('regularMarketChange'),
            'regularMarketChangePercent': info.get('regularMarketChangePercent'),
            'regularMarketOpen': info.get('regularMarketOpen'),
            'regularMarketDayHigh': info.get('regularMarketDayHigh'),
            'regularMarketDayLow': info.get('regularMarketDayLow'),
            'regularMarketPreviousClose': info.get('regularMarketPreviousClose'),
            'regularMarketVolume': info.get('regularMarketVolume'),
            'marketCap': info.get('marketCap'),
            'fiftyTwoWeekHigh': info.get('fiftyTwoWeekHigh'),
            'fiftyTwoWeekLow': info.get('fiftyTwoWeekLow'),
            'timestamp_utc': info.get('timestamp_utc')
        }
        return {"quote": quote_data}
    except Exception as e:
        print(f"Error in get_yahoo_quote for {symbol}: {e}")
        return {"error": f"Failed to fetch Yahoo Finance quote: {str(e)}"}

@function_tool
def get_finnhub_news(symbol: str, count: int) -> List[Dict[str, Any]]:
    """Fetches recent market news for a given stock symbol from Finnhub.

    Args:
        symbol: The stock ticker symbol (e.g., AAPL, MSFT).
        count: The number of news articles to return.

    Returns:
        A list of news articles or an error message.
    """
    if count is None:
        count = 10
    print(f"Tool: get_finnhub_news called for {symbol} (count: {count})")
    if not FINNHUB_API_KEY:
        return {"error": "FINNHUB_API_KEY is not set."}
    try:
        # Get today's date and date 7 days ago for the news range
        today = datetime.now().strftime('%Y-%m-%d')
        seven_days_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')

        url = f"https://finnhub.io/api/v1/company-news?symbol={symbol}&from={seven_days_ago}&to={today}&token={FINNHUB_API_KEY}"
        response = requests.get(url)
        response.raise_for_status()  # Raise an exception for bad status codes
        news = response.json()

        # Ensure news is a list and limit the count
        if isinstance(news, list):
            print(f"Tool: get_finnhub_news for {symbol} successful.")
            return news[:count]
        else:
             print(f"Tool: get_finnhub_news for {symbol} returned unexpected format: {news}")
             return {"error": "Finnhub returned unexpected news format."}

    except requests.exceptions.RequestException as e:
        print(f"Error fetching Finnhub news for {symbol}: {e}")
        return {"error": f"Failed to fetch Finnhub news: {str(e)}"}
    except Exception as e:
        print(f"Error processing Finnhub news for {symbol}: {e}")
        return {"error": f"Failed to process Finnhub news: {str(e)}"}


@function_tool
def get_alphavantage_overview(symbol: str) -> Dict[str, Any]:
    """Fetches company overview information (sector, industry, description, etc.) from AlphaVantage.

    Args:
        symbol: The stock ticker symbol (e.g., AAPL, MSFT).

    Returns:
        A dictionary containing company overview data or an error message.
    """
    print(f"Tool: get_alphavantage_overview called for {symbol}")
    if not ALPHAVANTAGE_API_KEY:
        return {"error": "ALPHAVANTAGE_API_KEY is not set."}
    try:
        url = f"https://www.alphavantage.co/query?function=OVERVIEW&symbol={symbol}&apikey={ALPHAVANTAGE_API_KEY}"
        response = requests.get(url)
        response.raise_for_status()
        overview = response.json()
        # Check if AlphaVantage returned an empty dict (common for invalid symbols) or error message
        if not overview or "Error Message" in overview or "Information" in overview:
            error_msg = overview.get("Error Message", overview.get("Information", f"No overview data found for {symbol}."))
            print(f"Tool: get_alphavantage_overview for {symbol} failed or returned no data: {error_msg}")
            return {"error": error_msg}

        print(f"Tool: get_alphavantage_overview for {symbol} successful.")
        return {"overview": overview} # Nest under 'overview' key
    except requests.exceptions.RequestException as e:
        print(f"Error fetching AlphaVantage overview for {symbol}: {e}")
        return {"error": f"Failed to fetch AlphaVantage overview: {str(e)}"}
    except Exception as e:
        print(f"Error processing AlphaVantage overview for {symbol}: {e}")
        return {"error": f"Failed to process AlphaVantage overview: {str(e)}"}

@function_tool
def get_fred_series(series_id: str, limit: int) -> Dict[str, Any]:
    """Fetches recent observations for a specific economic data series from FRED (Federal Reserve Economic Data).

    Args:
        series_id: The FRED series ID (e.g., 'GDP', 'UNRATE', 'DGS10' for 10-year Treasury).
        limit: The maximum number of recent observations to return.

    Returns:
        A dictionary containing series observations or an error message.
    """
    if limit is None:
        limit = 10
    print(f"Tool: get_fred_series called for {series_id} (limit: {limit})")
    if not FRED_API_KEY:
        return {"error": "FRED_API_KEY is not set."}
    try:
        url = f"https://api.stlouisfed.org/fred/series/observations?series_id={series_id}&api_key={FRED_API_KEY}&file_type=json&limit={limit}&sort_order=desc"
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        if "observations" not in data or not data["observations"]:
             error_msg = data.get("error_message", f"No FRED observations found for series {series_id}.")
             print(f"Tool: get_fred_series for {series_id} failed or returned no data: {error_msg}")
             return {"error": error_msg}

        print(f"Tool: get_fred_series for {series_id} successful.")
        # Return observations directly, potentially adding series_id for context
        return {"series_id": series_id, "observations": data["observations"]}
    except requests.exceptions.RequestException as e:
        print(f"Error fetching FRED series {series_id}: {e}")
        return {"error": f"Failed to fetch FRED series {series_id}: {str(e)}"}
    except Exception as e:
        print(f"Error processing FRED series {series_id}: {e}")
        return {"error": f"Failed to process FRED series {series_id}: {str(e)}"}


@function_tool
def get_eia_series(series_id: str, limit: int) -> Dict[str, Any]:
    """Fetches recent data for a specific series from the U.S. Energy Information Administration (EIA).

    Note: EIA API v2 structure can vary. This attempts a common pattern.
    Find series IDs via the EIA website or API documentation.

    Args:
        series_id: The EIA series ID (e.g., 'PET.W_EPC0_FPF_Y48SE_DPG.W' for Cushing OK WTI Spot Price).
        limit: The maximum number of recent data points to return.

    Returns:
        A dictionary containing series data or an error message.
    """
    if limit is None:
        limit = 10
    print(f"Tool: get_eia_series called for {series_id} (limit: {limit})")
    if not EIA_API_KEY:
        return {"error": "EIA_API_KEY is not set."}
    try:
        # Using EIA API v2 - route might vary slightly based on series type (e.g., /petroleum/pri/spt/)
        # This is a generic attempt, might need refinement for specific series paths
        base_url = "https://api.eia.gov/v2"
        # Construct the facet/data parts - this is complex and series-dependent
        # Example for weekly petroleum spot price:
        # /petroleum/pri/spt/data/?frequency=weekly&data[0]=value&facets[series][]=PET.W_EPC0_FPF_Y48SE_DPG.W&sort[0][column]=period&sort[0][direction]=desc&length=10
        # This simplified version might work for some series by ID directly:
        url = f"{base_url}/seriesid/{series_id}?api_key={EIA_API_KEY}&out=json&num={limit}"
        # A more robust V2 call often requires specifying frequency, data columns, facets etc.
        # url = f"{base_url}/petroleum/pri/spt/data/?api_key={EIA_API_KEY}&frequency=weekly&data[0]=value&facets[series][]={series_id}&sort[0][column]=period&sort[0][direction]=desc&length={limit}&out=json"


        response = requests.get(url)
        response.raise_for_status()
        data = response.json()

        # Check for errors or empty data in response structure
        if "response" not in data or "data" not in data["response"] or not data["response"]["data"]:
            # Check for specific error message format
            error_msg = "No EIA data found or error occurred."
            if "error" in data:
                error_msg = data["error"]
            elif "data" in data and "error" in data["data"]: # Some EIA errors are nested
                 error_msg = data["data"]["error"]

            print(f"Tool: get_eia_series for {series_id} failed or returned no data: {error_msg}")
            return {"error": error_msg}

        print(f"Tool: get_eia_series for {series_id} successful.")
        # Return the data part of the response, potentially adding series_id
        return {"series_id": series_id, "data": data["response"]["data"]}

    except requests.exceptions.RequestException as e:
        print(f"Error fetching EIA series {series_id}: {e}")
        return {"error": f"Failed to fetch EIA series {series_id}: {str(e)}"}
    except Exception as e:
        print(f"Error processing EIA series {series_id}: {e}")
        return {"error": f"Failed to process EIA series {series_id}: {str(e)}"}

@function_tool
def get_newsapi_headlines(query: str, count: int) -> List[Dict[str, Any]]:
    """Fetches recent news headlines related to a query from NewsAPI.

    Args:
        query: The search query (e.g., company name, stock symbol, topic).
        count: The number of headlines to return.

    Returns:
        A list of news articles or an error message.
    """
    if count is None:
        count = 10
    print(f"Tool: get_newsapi_headlines called for '{query}' (count: {count})")
    if not NEWSAPI_API_KEY:
        return {"error": "NEWSAPI_API_KEY is not set."}
    try:
        # Use 'everything' endpoint for broader search, sort by relevancy or publishedAt
        url = f"https://newsapi.org/v2/everything?q={query}&apiKey={NEWSAPI_API_KEY}&pageSize={min(count, 100)}&sortBy=publishedAt" # Can change sortBy
        response = requests.get(url)
        response.raise_for_status()
        news_data = response.json()

        if news_data.get("status") != "ok":
            error_msg = news_data.get("message", "NewsAPI returned an error.")
            print(f"Tool: get_newsapi_headlines for '{query}' failed: {error_msg}")
            return {"error": error_msg}

        articles = news_data.get("articles", [])
        print(f"Tool: get_newsapi_headlines for '{query}' successful.")
        return articles # Return the list of articles

    except requests.exceptions.RequestException as e:
        print(f"Error fetching NewsAPI headlines for '{query}': {e}")
        return {"error": f"Failed to fetch NewsAPI headlines: {str(e)}"}
    except Exception as e:
        print(f"Error processing NewsAPI headlines for '{query}': {e}")
        return {"error": f"Failed to process NewsAPI headlines: {str(e)}"}

# Example usage for testing tools directly
if __name__ == '__main__':
    async def test_tools():
        print("--- Testing Stonk Research Tools ---")

        symbol = "AAPL" # Apple
        fred_series = "UNRATE" # Unemployment Rate
        eia_series = "PET.W_EPC0_FPF_Y48SE_DPG.W" # WTI Spot Price
        query = "Apple iPhone semiconductor"

        print(f"\n--- Testing get_yahoo_quote ({symbol}) ---")
        quote = get_yahoo_quote(symbol=symbol)
        print(json.dumps(quote, indent=2))

        print(f"\n--- Testing get_finnhub_news ({symbol}) ---")
        f_news = get_finnhub_news(symbol=symbol, count=3)
        print(json.dumps(f_news, indent=2))

        print(f"\n--- Testing get_alphavantage_overview ({symbol}) ---")
        overview = get_alphavantage_overview(symbol=symbol)
        print(json.dumps(overview, indent=2))

        print(f"\n--- Testing get_fred_series ({fred_series}) ---")
        fred_data = get_fred_series(series_id=fred_series, limit=5)
        print(json.dumps(fred_data, indent=2))

        print(f"\n--- Testing get_eia_series ({eia_series}) ---")
        # Note: EIA series ID might require specific API path knowledge
        eia_data = get_eia_series(series_id=eia_series, limit=5)
        print(json.dumps(eia_data, indent=2))

        print(f"\n--- Testing get_newsapi_headlines ('{query}') ---")
        n_news = get_newsapi_headlines(query=query, count=3)
        print(json.dumps(n_news, indent=2))

    # Run async tests (most tools are sync here, but good practice if adding async ones)
    asyncio.run(test_tools())
