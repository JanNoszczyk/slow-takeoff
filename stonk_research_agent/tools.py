import os
import asyncio
import requests
import yfinance as yf
import json
import sys # Import sys
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Literal
from dotenv import load_dotenv
# Use field_validator from Pydantic v2 for custom validation
from pydantic import BaseModel, Field, HttpUrl, ValidationError, field_validator
# Removed OpenAI client import as it's no longer used for parsing here

# Import Agent SDK components
try:
    from agents import function_tool, RunContextWrapper
except ImportError:
    print("ERROR: Failed to import 'agents' library components. Make sure 'openai-agents' is installed.", file=sys.stderr)
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

# --- Internal Logic Functions (Undecorated) ---

def _internal_get_yahoo_quote(symbol: str) -> Dict[str, Any]:
    """Core logic to fetch Yahoo Finance quote data."""
    print(f"Logic: _internal_get_yahoo_quote called for {symbol}", file=sys.stderr)
    try:
        ticker = yf.Ticker(symbol)
        info = ticker.info
        if not info or info.get('quoteType') == 'MUTUALFUND':
             fast_info = ticker.fast_info
             if not fast_info or fast_info.get('last_price') is None:
                  print(f"Tool: get_yahoo_quote for {symbol} failed or returned no data (ticker.info empty/mutualfund, fast_info empty).", file=sys.stderr)
                  return {"error": f"Could not retrieve valid quote info for symbol {symbol}. It might be delisted or invalid."}
             print(f"Tool: get_yahoo_quote for {symbol} using fast_info fallback.", file=sys.stderr)
             fast_info['timestamp_utc'] = datetime.utcnow().isoformat()
             return {"quote": fast_info}

        info['timestamp_utc'] = datetime.utcnow().isoformat()
        print(f"Tool: get_yahoo_quote for {symbol} successful.", file=sys.stderr)
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
        print(f"Error in _internal_get_yahoo_quote for {symbol}: {e}", file=sys.stderr)
        return {"error": f"Failed to fetch Yahoo Finance quote: {str(e)}"}

def _internal_get_finnhub_news(symbol: str, count: int) -> List[Dict[str, Any]]:
    """Core logic to fetch Finnhub news."""
    print(f"Logic: _internal_get_finnhub_news called for {symbol} (count: {count})", file=sys.stderr)
    if count is None: count = 10
    if not FINNHUB_API_KEY:
        print("Tool: get_finnhub_news failed: FINNHUB_API_KEY not set.", file=sys.stderr)
        return {"error": "FINNHUB_API_KEY is not set."}
    try:
        today = datetime.now().strftime('%Y-%m-%d')
        seven_days_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
        url = f"https://finnhub.io/api/v1/company-news?symbol={symbol}&from={seven_days_ago}&to={today}&token={FINNHUB_API_KEY}"
        response = requests.get(url)
        response.raise_for_status()
        news = response.json()
        if isinstance(news, list):
            print(f"Tool: get_finnhub_news for {symbol} successful.", file=sys.stderr)
            return news[:count]
        else:
             print(f"Tool: get_finnhub_news for {symbol} returned unexpected format: {news}", file=sys.stderr)
             return {"error": "Finnhub returned unexpected news format."}
    except requests.exceptions.RequestException as e:
        print(f"Error fetching Finnhub news for {symbol}: {e}", file=sys.stderr)
        return {"error": f"Failed to fetch Finnhub news: {str(e)}"}
    except Exception as e:
        print(f"Error processing Finnhub news for {symbol}: {e}", file=sys.stderr)
        return {"error": f"Failed to process Finnhub news: {str(e)}"}

def _internal_get_alphavantage_overview(symbol: str) -> Dict[str, Any]:
    """Core logic to fetch AlphaVantage overview."""
    print(f"Logic: _internal_get_alphavantage_overview called for {symbol}", file=sys.stderr)
    if not ALPHAVANTAGE_API_KEY:
        print("Tool: get_alphavantage_overview failed: ALPHAVANTAGE_API_KEY not set.", file=sys.stderr)
        return {"error": "ALPHAVANTAGE_API_KEY is not set."}
    try:
        url = f"https://www.alphavantage.co/query?function=OVERVIEW&symbol={symbol}&apikey={ALPHAVANTAGE_API_KEY}"
        response = requests.get(url)
        response.raise_for_status()
        overview = response.json()
        if not overview or "Error Message" in overview or "Information" in overview:
            error_msg = overview.get("Error Message", overview.get("Information", f"No overview data found for {symbol}."))
            print(f"Tool: get_alphavantage_overview for {symbol} failed or returned no data: {error_msg}", file=sys.stderr)
            return {"error": error_msg}
        print(f"Tool: get_alphavantage_overview for {symbol} successful.", file=sys.stderr)
        return {"overview": overview}
    except requests.exceptions.RequestException as e:
        print(f"Error fetching AlphaVantage overview for {symbol}: {e}", file=sys.stderr)
        return {"error": f"Failed to fetch AlphaVantage overview: {str(e)}"}
    except Exception as e:
        print(f"Error processing AlphaVantage overview for {symbol}: {e}", file=sys.stderr)
        return {"error": f"Failed to process AlphaVantage overview: {str(e)}"}

def _internal_get_fred_series(series_id: str, limit: int) -> Dict[str, Any]:
    """Core logic to fetch FRED series data."""
    print(f"Logic: _internal_get_fred_series called for {series_id} (limit: {limit})", file=sys.stderr)
    if limit is None: limit = 10
    if not FRED_API_KEY:
        print("Tool: get_fred_series failed: FRED_API_KEY not set.", file=sys.stderr)
        return {"error": "FRED_API_KEY is not set."}
    try:
        url = f"https://api.stlouisfed.org/fred/series/observations?series_id={series_id}&api_key={FRED_API_KEY}&file_type=json&limit={limit}&sort_order=desc"
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        if "observations" not in data or not data["observations"]:
             error_msg = data.get("error_message", f"No FRED observations found for series {series_id}.")
             print(f"Tool: get_fred_series for {series_id} failed or returned no data: {error_msg}", file=sys.stderr)
             return {"error": error_msg}
        print(f"Tool: get_fred_series for {series_id} successful.", file=sys.stderr)
        return {"series_id": series_id, "observations": data["observations"]}
    except requests.exceptions.RequestException as e:
        print(f"Error fetching FRED series {series_id}: {e}", file=sys.stderr)
        return {"error": f"Failed to fetch FRED series {series_id}: {str(e)}"}
    except Exception as e:
        print(f"Error processing FRED series {series_id}: {e}", file=sys.stderr)
        return {"error": f"Failed to process FRED series {series_id}: {str(e)}"}

def _internal_get_eia_series(series_id: str, limit: int) -> Dict[str, Any]:
    """Core logic to fetch EIA series data."""
    print(f"Logic: _internal_get_eia_series called for {series_id} (limit: {limit})", file=sys.stderr)
    if limit is None: limit = 10
    if not EIA_API_KEY:
        print("Tool: get_eia_series failed: EIA_API_KEY not set.", file=sys.stderr)
        return {"error": "EIA_API_KEY is not set."}
    try:
        base_url = "https://api.eia.gov/v2"
        url = f"{base_url}/seriesid/{series_id}?api_key={EIA_API_KEY}&out=json&num={limit}"
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        if "response" not in data or "data" not in data["response"] or not data["response"]["data"]:
            error_msg = "No EIA data found or error occurred."
            if "error" in data: error_msg = data["error"]
            elif "data" in data and "error" in data["data"]: error_msg = data["data"]["error"]
            print(f"Tool: get_eia_series for {series_id} failed or returned no data: {error_msg}", file=sys.stderr)
            return {"error": error_msg}
        print(f"Tool: get_eia_series for {series_id} successful.", file=sys.stderr)
        return {"series_id": series_id, "data": data["response"]["data"]}
    except requests.exceptions.RequestException as e:
        print(f"Error fetching EIA series {series_id}: {e}", file=sys.stderr)
        return {"error": f"Failed to fetch EIA series {series_id}: {str(e)}"}
    except Exception as e:
        print(f"Error processing EIA series {series_id}: {e}", file=sys.stderr)
        return {"error": f"Failed to process EIA series {series_id}: {str(e)}"}

def _internal_get_newsapi_headlines(query: str, count: int) -> List[Dict[str, Any]]:
    """Core logic to fetch NewsAPI headlines."""
    print(f"Logic: _internal_get_newsapi_headlines called for '{query}' (count: {count})", file=sys.stderr)
    if count is None: count = 10
    if not NEWSAPI_API_KEY:
        print("Tool: get_newsapi_headlines failed: NEWSAPI_API_KEY not set.", file=sys.stderr)
        return {"error": "NEWSAPI_API_KEY is not set."}
    try:
        url = f"https://newsapi.org/v2/everything?q={query}&apiKey={NEWSAPI_API_KEY}&pageSize={min(count, 100)}&sortBy=publishedAt"
        response = requests.get(url)
        response.raise_for_status()
        news_data = response.json()
        if news_data.get("status") != "ok":
            error_msg = news_data.get("message", "NewsAPI returned an error.")
            print(f"Tool: get_newsapi_headlines for '{query}' failed: {error_msg}", file=sys.stderr)
            return {"error": error_msg}
        articles = news_data.get("articles", [])
        print(f"Tool: get_newsapi_headlines for '{query}' successful.", file=sys.stderr)
        return articles
    except requests.exceptions.RequestException as e:
        print(f"Error fetching NewsAPI headlines for '{query}': {e}", file=sys.stderr)
        return {"error": f"Failed to fetch NewsAPI headlines: {str(e)}"}
    except Exception as e:
        print(f"Error processing NewsAPI headlines for '{query}': {e}", file=sys.stderr)
        return {"error": f"Failed to process NewsAPI headlines: {str(e)}"}


def _internal_perform_web_search(query: str) -> Dict[str, Any]:
    """
    Simulates performing a web search and manually structures the results.
    NOTE: This is currently a simulation. Replace with actual search logic.
    """
    print(f"Logic: Simulating _internal_perform_web_search for query: '{query}'", file=sys.stderr)
    # Simulate finding some results - replace with actual search/parsing logic
    return {
        "query": query,
        "overall_summary": f"Simulated web search summary for '{query}': Key insights include topic A, trend B, and recent event C.",
        "sentiment": "Neutral",
        "sentiment_reasoning": "Based on simulated analysis of mixed headlines.",
        "relevant_news": [
            {
                "headline": f"Simulated: Major Development Related to {query}",
                "source_name": "Simulated News Source",
                "source_url": f"https://example.com/simulated/{query.replace(' ', '-')}-1",
                "summary": "A simulated event occurred impacting the subject.",
                "publish_date": datetime.utcnow().isoformat(),
            }
        ],
        "key_source_urls": [
            f"https://example.com/simulated/{query.replace(' ', '-')}-1",
        ],
        "error": None # Indicate success
    }


# --- Pydantic Models for Structured Output (Single Definition Block) ---
class YahooQuoteData(BaseModel):
    quote: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

class FinnhubNewsData(BaseModel):
    news: Optional[List[Dict[str, Any]]] = None
    error: Optional[str] = None

class AlphavantageOverviewData(BaseModel):
    overview: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

class FredSeriesData(BaseModel):
    data: Optional[Dict[str, Any]] = None # {'series_id': ..., 'observations': [...]}
    error: Optional[str] = None

class EiaSeriesData(BaseModel):
    data: Optional[Dict[str, Any]] = None # {'series_id': ..., 'data': [...]}
    error: Optional[str] = None

class NewsApiHeadlinesData(BaseModel):
    articles: Optional[List[Dict[str, Any]]] = None
    error: Optional[str] = None

# Updated WebSearch Pydantic models for stock impact analysis
class WebSearchNewsArticle(BaseModel):
    headline: Optional[str] = Field(None, description="Title of the news article (if available).")
    source_name: Optional[str] = Field(None, description="Name of the news source.")
    source_url: str = Field(..., description="URL of the news source. Must be a valid URL string.") # Changed from HttpUrl to str
    summary: Optional[str] = Field(None, description="Original brief summary from search result (if available).")
    publish_date: Optional[str] = Field(None, description="Publication date/time (ISO format or human-readable).")
    reason: Optional[str] = Field(None, description="Short (1-2 sentence) explanation of why this news might affect the stock price.")
    transcript: Optional[str] = Field(None, description="Relevant excerpt/transcript from the source supporting the reason.")
    image_url: Optional[str] = Field(None, description="URL of the article's main image (if available).") # ADDED image_url
    # Removed ge=-1.0, le=1.0 constraints
    sentiment_score: Optional[float] = Field(None, description="Sentiment score indicating potential stock price impact (-1.0 negative to +1.0 positive).")

    @field_validator('image_url')
    @classmethod
    def check_image_url(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        if not isinstance(v, str):
            # This should ideally be caught by Pydantic based on type annotation Optional[str]
            # but as a safeguard if raw data isn't a string.
            raise ValueError(f"image_url must be a string or None, received {type(v)}")
        if v == "": # Treat empty string as no image URL provided
            return None
        try:
            HttpUrl(v) # Validate non-empty string as a URL
            return v
        except ValidationError:
            # Allow non-URL strings to pass as None, or raise error if strict URL is required
            # For now, let's be lenient and treat invalid URL strings as None (no image)
            # To be strict, uncomment the line below:
            # raise ValueError(f"Invalid URL format for image_url: {v}")
            print(f"Warning: Invalid image_url format '{v}', treating as no image.", file=sys.stderr)
            return None

    @field_validator('source_url')
    @classmethod
    def check_source_url(cls, v: str) -> str: # source_url is mandatory (str, not Optional[str])
        if not v: # Should be caught by Pydantic if type is str and not Optional
            raise ValueError("source_url cannot be empty")
        try:
            HttpUrl(v)
            return v
        except ValidationError:
            raise ValueError(f"Invalid URL format for source_url: {v}")

    @field_validator('sentiment_score')
    @classmethod
    def check_sentiment_score_range(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and not (-1.0 <= v <= 1.0):
            raise ValueError(f"Sentiment score {v} is outside the valid range [-1.0, 1.0]")
        return v

class WebSearchOutput(BaseModel):
    query: Optional[str] = Field(None, description="The original search query performed (if available).")
    overall_summary: Optional[str] = Field(None, description="Synthesized summary, now potentially derived from parsing agent output.") # Modified description
    # Removed overall sentiment fields, now per-article
    relevant_news: List[WebSearchNewsArticle] = Field(default_factory=list, description="List of relevant news articles analyzed for stock price impact.")
    key_source_urls: List[HttpUrl] = Field(default_factory=list, description="List of important source URLs.") # Keep this for quick reference
    error: Optional[str] = None # To capture potential errors during web search/parsing

# NEW: Simplified model for agent's direct output
class WebAnalysisOutput(BaseModel):
    overall_summary: Optional[str] = Field(None, description="Synthesized summary of web search findings related to price impact.")
    relevant_news: List[WebSearchNewsArticle] = Field(default_factory=list, description="List of relevant news articles analyzed for stock price impact.")
    key_source_urls: List[str] = Field(default_factory=list, description="List of important source URLs (as strings).") # Changed from List[HttpUrl]
    error: Optional[str] = None # To capture potential errors during web search/parsing

    @field_validator('key_source_urls', mode='before') # Validate before Pydantic tries to coerce type
    @classmethod
    def check_key_urls(cls, v: List[str]) -> List[str]:
        if not isinstance(v, list):
             # This case might not be strictly necessary with mode='before' but good practice
             raise ValueError("key_source_urls must be a list")
        validated_urls = []
        for i, url_str in enumerate(v):
            try:
                HttpUrl(url_str) # Validate using HttpUrl internally
                validated_urls.append(url_str)
            except ValidationError:
                raise ValueError(f"Invalid URL format in key_source_urls at index {i}: {url_str}")
        return validated_urls

class SymbolResearchData(BaseModel):
    symbol: str
    yahoo_quote: Optional[YahooQuoteData] = None
    finnhub_news: Optional[FinnhubNewsData] = None
    newsapi_headlines: Optional[NewsApiHeadlinesData] = None
    alphavantage_overview: Optional[AlphavantageOverviewData] = None
    fred_series: Dict[str, FredSeriesData] = Field(default_factory=dict) # Keyed by series_id
    eia_series: Dict[str, EiaSeriesData] = Field(default_factory=dict)   # Keyed by series_id
    # Ensure web_search defaults to an empty WebSearchOutput object instead of None
    web_search: WebSearchOutput = Field(default_factory=WebSearchOutput) # Keep this structure for the final combined report

class FullResearchReport(BaseModel):
    # Removed strict config model_config = {'strict': True}
    report: List[SymbolResearchData] = Field(default_factory=list)

# Remove explicit model_rebuild call, as default_factory should handle initialization correctly.
# print("DEBUG: Attempting SymbolResearchData.model_rebuild() after modifying WebSearchOutput field.")
# try:
#     SymbolResearchData.model_rebuild()
#     print("DEBUG: SymbolResearchData.model_rebuild() successful.")
# except AttributeError:
#     print("DEBUG: model_rebuild not needed or available (likely Pydantic v1 or automatic handling).")
# except Exception as e:
#     print(f"DEBUG: ERROR during SymbolResearchData.model_rebuild(): {e}")

# --- Tool Implementations (Decorated Wrappers) ---

@function_tool
def get_yahoo_quote(symbol: str) -> Dict[str, Any]:
    """Fetches near real-time quote data for a given stock symbol using Yahoo Finance."""
    return _internal_get_yahoo_quote(symbol)

@function_tool
def get_finnhub_news(symbol: str, count: int) -> List[Dict[str, Any]]:
    """Fetches recent market news for a given stock symbol from Finnhub."""
    return _internal_get_finnhub_news(symbol, count)

@function_tool
def get_alphavantage_overview(symbol: str) -> Dict[str, Any]:
    """Fetches company overview information from AlphaVantage."""
    return _internal_get_alphavantage_overview(symbol)

@function_tool
def get_fred_series(series_id: str, limit: int) -> Dict[str, Any]:
    """Fetches recent observations for a specific economic data series from FRED."""
    return _internal_get_fred_series(series_id, limit)

@function_tool
def get_eia_series(series_id: str, limit: int) -> Dict[str, Any]:
    """Fetches recent data for a specific series from the EIA."""
    return _internal_get_eia_series(series_id, limit)

@function_tool
def get_newsapi_headlines(query: str, count: int) -> List[Dict[str, Any]]:
    """Fetches recent news headlines related to a query from NewsAPI."""
    return _internal_get_newsapi_headlines(query, count)


@function_tool
def run_full_research(symbols: List[str], news_count: int, fred_series: Optional[List[str]] = None, eia_series: Optional[List[str]] = None) -> str:
    """
    Runs research jobs for a list of stock symbols. Fetches quote, news (Finnhub, NewsAPI),
    overview, and specified FRED/EIA data. Returns aggregated results as JSON.
    Web search is handled separately by the agent.

    Args:
        symbols: List of stock ticker symbols (e.g., ["AAPL", "MSFT"]).
        news_count: Number of news articles/headlines per source (default: 5).
        fred_series: Optional list of FRED series IDs (e.g., ["GDP", "UNRATE"]).
        eia_series: Optional list of EIA series IDs.

    Returns:
        A JSON string representing a FullResearchReport object.
    """
    print(f"DEBUG: Entering run_full_research with symbols={symbols}, news_count={news_count}, fred={fred_series}, eia={eia_series}", file=sys.stderr) # Redirect to stderr
    report_data = []
    if news_count is None: news_count = 5 # Default news count
    if fred_series is None: fred_series = [] # Ensure lists are not None
    if eia_series is None: eia_series = []

    for symbol in symbols:
        print(f"DEBUG: Processing symbol: {symbol}", file=sys.stderr) # Redirect to stderr
        # Instantiate the Pydantic model
        symbol_data = SymbolResearchData(symbol=symbol)
        print(f"DEBUG: SymbolResearchData instantiated successfully for {symbol}", file=sys.stderr) # Redirect to stderr

        # --- Gather Data ---
        print(f"DEBUG: Calling _internal_get_yahoo_quote for {symbol}", file=sys.stderr) # Redirect to stderr
        quote_result = _internal_get_yahoo_quote(symbol=symbol)
        print(f"DEBUG: _internal_get_yahoo_quote result: {str(quote_result)[:100]}...", file=sys.stderr) # Redirect to stderr

        print(f"DEBUG: Calling _internal_get_finnhub_news for {symbol}", file=sys.stderr) # Redirect to stderr
        fhub_news_result = _internal_get_finnhub_news(symbol=symbol, count=news_count)
        print(f"DEBUG: _internal_get_finnhub_news result: {str(fhub_news_result)[:100]}...", file=sys.stderr) # Redirect to stderr

        print(f"DEBUG: Calling _internal_get_newsapi_headlines for {symbol}", file=sys.stderr) # Redirect to stderr
        napi_news_result = _internal_get_newsapi_headlines(query=symbol, count=news_count)
        print(f"DEBUG: _internal_get_newsapi_headlines result: {str(napi_news_result)[:100]}...", file=sys.stderr) # Redirect to stderr

        print(f"DEBUG: Calling _internal_get_alphavantage_overview for {symbol}", file=sys.stderr) # Redirect to stderr
        overview_result = _internal_get_alphavantage_overview(symbol=symbol)
        print(f"DEBUG: _internal_get_alphavantage_overview result: {str(overview_result)[:100]}...", file=sys.stderr) # Redirect to stderr

        # Call the internal (simulated) web search function
        # print(f"DEBUG: Calling _internal_perform_web_search for {symbol}", file=sys.stderr) # Redirect to stderr - Removed call below
        # Removed call to _internal_perform_web_search

        fred_results = {}
        print(f"DEBUG: Processing FRED series: {fred_series}", file=sys.stderr) # Redirect to stderr
        for series_id in fred_series:
            print(f"DEBUG: Calling _internal_get_fred_series for {series_id}", file=sys.stderr) # Redirect to stderr
            fred_results[series_id] = _internal_get_fred_series(series_id=series_id, limit=5)
            print(f"DEBUG: _internal_get_fred_series result for {series_id}: {str(fred_results[series_id])[:100]}...", file=sys.stderr) # Redirect to stderr

        eia_results = {}
        print(f"DEBUG: Processing EIA series: {eia_series}", file=sys.stderr) # Redirect to stderr
        for series_id in eia_series:
            print(f"DEBUG: Calling _internal_get_eia_series for {series_id}", file=sys.stderr) # Redirect to stderr
            eia_results[series_id] = _internal_get_eia_series(series_id=series_id, limit=5)
            print(f"DEBUG: _internal_get_eia_series result for {series_id}: {str(eia_results[series_id])[:100]}...", file=sys.stderr) # Redirect to stderr

        # --- Populate Pydantic Model ---
        print(f"DEBUG: Populating Pydantic model for {symbol}", file=sys.stderr) # Redirect to stderr
        symbol_data.yahoo_quote = YahooQuoteData(**quote_result)
        if isinstance(fhub_news_result, list): symbol_data.finnhub_news = FinnhubNewsData(news=fhub_news_result)
        else: symbol_data.finnhub_news = FinnhubNewsData(**fhub_news_result)
        if isinstance(napi_news_result, list): symbol_data.newsapi_headlines = NewsApiHeadlinesData(articles=napi_news_result)
        else: symbol_data.newsapi_headlines = NewsApiHeadlinesData(**napi_news_result)
        # Conditionally populate AlphaVantage data
        if overview_result and "error" in overview_result:
            symbol_data.alphavantage_overview = None # Assign None if there's an error
            print(f"DEBUG: AlphaVantage error found for {symbol}, setting overview to None.", file=sys.stderr) # Redirect to stderr
        else:
            symbol_data.alphavantage_overview = AlphavantageOverviewData(**overview_result)
            print(f"DEBUG: AlphaVantage data populated successfully for {symbol}.", file=sys.stderr) # Redirect to stderr

        for series_id, result in fred_results.items():
            if "error" in result: symbol_data.fred_series[series_id] = FredSeriesData(error=result["error"])
            else: symbol_data.fred_series[series_id] = FredSeriesData(data=result)
        for series_id, result in eia_results.items():
            if "error" in result: symbol_data.eia_series[series_id] = EiaSeriesData(error=result["error"])
            else: symbol_data.eia_series[series_id] = EiaSeriesData(data=result)

        # Web search population removed

        report_data.append(symbol_data)

    final_report = FullResearchReport(report=report_data)
    json_output = final_report.model_dump_json(indent=2)
    print(f"DEBUG: run_full_research final JSON output (length: {len(json_output)}):\n{json_output[:500]}...", file=sys.stderr) # Redirect to stderr
    return json_output


# Example usage for testing tools directly
if __name__ == '__main__':
    async def test_internal_logic():
        print("--- Testing Stonk Research Tools (Internal Logic) ---")
        symbol = "MSFT"
        fred_id = "UNRATE"
        eia_id = "PET.W_EPC0_FPF_Y48SE_DPG.W"
        query = "Apple iPhone semiconductor"
        news_api_count = 3
        finnhub_count = 3
        econ_limit = 5

        print(f"\n--- Testing _internal_get_yahoo_quote ({symbol}) ---")
        try: print(json.dumps(_internal_get_yahoo_quote(symbol=symbol), indent=2))
        except Exception as e: print(f"Error: {e}")

        print(f"\n--- Testing _internal_get_finnhub_news ({symbol}) ---")
        try: print(json.dumps(_internal_get_finnhub_news(symbol=symbol, count=finnhub_count), indent=2))
        except Exception as e: print(f"Error: {e}")

        print(f"\n--- Testing _internal_get_alphavantage_overview ({symbol}) ---")
        try: print(json.dumps(_internal_get_alphavantage_overview(symbol=symbol), indent=2))
        except Exception as e: print(f"Error: {e}")

        print(f"\n--- Testing _internal_get_fred_series ({fred_id}) ---")
        try: print(json.dumps(_internal_get_fred_series(series_id=fred_id, limit=econ_limit), indent=2))
        except Exception as e: print(f"Error: {e}")

        print(f"\n--- Testing _internal_get_eia_series ({eia_id}) ---")
        try: print(json.dumps(_internal_get_eia_series(series_id=eia_id, limit=econ_limit), indent=2))
        except Exception as e: print(f"Error: {e}")

        print(f"\n--- Testing _internal_get_newsapi_headlines ('{query}') ---")
        try: print(json.dumps(_internal_get_newsapi_headlines(query=query, count=news_api_count), indent=2))
        except Exception as e: print(f"Error: {e}")

        # Removed web search test section
        print(f"\n--- run_full_research test skipped (requires agent Runner) ---")

    try:
        asyncio.run(test_internal_logic())
    except RuntimeError: # Handle cases where asyncio event loop is already running (e.g., in Jupyter)
         print("\nRunning tests synchronously (likely due to existing event loop)...")
         # Simplified synchronous execution - call functions directly
         symbol = "MSFT"
         print(f"\n--- Testing _internal_get_yahoo_quote ({symbol}) ---")
         print(json.dumps(_internal_get_yahoo_quote(symbol=symbol), indent=2))
         # ... Add other necessary sync tests for internal functions if required ...
         print(f"\n--- run_full_research test skipped (requires agent Runner) ---")
    except TypeError as e:
        print(f"\nTypeError during test execution: {e}")
        # Add fallback synchronous tests if needed, similar to RuntimeError block
