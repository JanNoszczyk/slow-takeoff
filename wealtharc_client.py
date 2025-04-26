# --- wealtharc_client.py (Async Version) ---
import os
import httpx # Use httpx for async requests
import asyncio
import logging
from typing import Optional, Dict, Any, Tuple
from dotenv import load_dotenv
from urllib.parse import urljoin
import time

# Import Pydantic Models remain the same
# from wealtharc_models.models import ... # Keep existing model imports if any

# --- Setup ---
load_dotenv()

# Basic logging for the client (remains the same)
logger = logging.getLogger("wealtharc_client")
if not logger.hasHandlers():
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

# --- Configuration ---
BASE_URL = os.getenv("VIDAR_BASE_URL")
API_KEY = os.getenv("WEALTH_ARC_API_KEY") # Corrected variable name

if not BASE_URL or not API_KEY:
    logger.error("VIDAR_BASE_URL or WEALTH_ARC_API_KEY not found in .env file. API calls will fail.")
    # Decide on error handling: raise error or allow failing calls
    # raise ValueError("VIDAR_BASE_URL or WEALTH_ARC_API_KEY missing in .env")

# Ensure base URL ends with a slash for urljoin
if BASE_URL and not BASE_URL.endswith('/'):
    BASE_URL += '/'

# --- Async API Call Helper ---
# Use a semaphore to limit concurrent requests globally for this client
# Adjust the limit based on API rate limits and testing
CONCURRENCY_LIMIT = 1 # Reduced to 1 for sequential processing to avoid rate limits
semaphore = asyncio.Semaphore(CONCURRENCY_LIMIT)

# Global AsyncClient instance for connection pooling
# Set timeouts: connect=10s, read=180s (adjust as needed)
# Follow redirects, set limits for connections
http_client = httpx.AsyncClient(
    timeout=httpx.Timeout(180.0, connect=10.0),
    limits=httpx.Limits(max_connections=100, max_keepalive_connections=20),
    follow_redirects=True
)

async def _make_request(
    endpoint: str,
    top: Optional[int] = None,
    skip: Optional[int] = None,
    filter_: Optional[str] = None,
    select: Optional[str] = None,
    orderby: Optional[str] = None,
    expand: Optional[str] = None,
    additional_params: Optional[Dict[str, Any]] = None,
    retry_attempts: int = 5, # Increased retries
    initial_delay: float = 2.0 # Increased initial delay
) -> Optional[Dict[str, Any]]:
    """
    Asynchronous helper function to make GET requests using httpx.AsyncClient,
    incorporating OData parameters, concurrency limiting, and basic retries.
    """
    if not BASE_URL or not API_KEY:
        logger.error(f"Cannot make request to {endpoint}: API config missing.")
        return None

    full_url = urljoin(BASE_URL, endpoint)
    headers = {"x-api-key": API_KEY, "Accept": "application/json"}

    odata_params = {}
    if top is not None: odata_params["$top"] = top
    if skip is not None: odata_params["$skip"] = skip
    if filter_ is not None: odata_params["$filter"] = filter_
    if select is not None: odata_params["$select"] = select
    if orderby is not None: odata_params["$orderby"] = orderby
    if expand is not None: odata_params["$expand"] = expand
    if additional_params: odata_params.update(additional_params)

    final_params = odata_params if odata_params else None
    current_attempt = 0
    delay = initial_delay

    async with semaphore: # Acquire semaphore before making the request
        while current_attempt < retry_attempts:
            current_attempt += 1
            try:
                masked_key = f"{API_KEY[:5]}...{API_KEY[-5:]}" if API_KEY and len(API_KEY) > 10 else "Invalid"
                logger.debug(f"Attempt {current_attempt}: GET {full_url} | Params: {final_params} | Headers: {{'x-api-key': '{masked_key}', ...}}")

                response = await http_client.get(full_url, headers=headers, params=final_params)
                logger.debug(f"Response Status: {response.status_code} for {full_url} (Skip={skip})")

                # Specific check for 429 Too Many Requests or 5xx Server Errors for retries
                if response.status_code == 429 or response.status_code >= 500:
                    response.raise_for_status() # Raise specific HTTPError to trigger retry logic

                response.raise_for_status() # Raise for other 4xx errors immediately
                return response.json()

            except httpx.HTTPStatusError as http_err:
                # Retry on 429 or 5xx errors
                if http_err.response.status_code == 429 or http_err.response.status_code >= 500:
                    if current_attempt < retry_attempts:
                        logger.warning(f"Attempt {current_attempt} failed ({http_err.response.status_code}). Retrying in {delay:.2f}s... URL: {full_url}")
                        await asyncio.sleep(delay)
                        delay *= 2 # Exponential backoff
                        continue # Go to next retry iteration
                    else:
                        logger.error(f"HTTP error after {retry_attempts} attempts: {http_err} | URL: {full_url}")
                        return None # Max retries reached for retryable errors
                else:
                    logger.error(f"HTTP error (non-retryable): {http_err} | URL: {full_url}")
                    return None # Non-retryable client/server error
            except httpx.RequestError as req_err:
                # Network errors, timeouts etc. - potentially retryable
                 if current_attempt < retry_attempts:
                    logger.warning(f"Request error on attempt {current_attempt}: {req_err}. Retrying in {delay:.2f}s... URL: {full_url}")
                    await asyncio.sleep(delay)
                    delay *= 2
                    continue
                 else:
                    logger.error(f"Request error after {retry_attempts} attempts: {req_err} | URL: {full_url}")
                    return None # Max retries reached
            except Exception as e:
                logger.error(f"Unexpected error during API call (Attempt {current_attempt}): {e} | URL: {full_url}")
                # Decide if general exceptions should be retried or fail immediately
                # For now, fail immediately on unexpected errors
                return None

    # Should only be reached if all retry attempts failed for retryable errors
    logger.error(f"All {retry_attempts} retry attempts failed for {full_url}")
    return None


# --- Async Client Functions ---
# Functions now need to be async and use await

async def get_assets(
    top: Optional[int] = None, skip: Optional[int] = None, filter_: Optional[str] = None,
    select: Optional[str] = None, orderby: Optional[str] = None, expand: Optional[str] = None,
    additional_params: Optional[Dict[str, Any]] = None
) -> Optional[Dict[str, Any]]:
    """Async fetch Assets."""
    logger.debug(f"Queueing fetch Assets (skip={skip}, top={top})...")
    return await _make_request(
        "Assets", top=top, skip=skip, filter_=filter_, select=select, orderby=orderby, expand=expand,
        additional_params=additional_params
    )

async def get_portfolios(
    top: Optional[int] = None, skip: Optional[int] = None, filter_: Optional[str] = None,
    select: Optional[str] = None, orderby: Optional[str] = None, expand: Optional[str] = None,
    additional_params: Optional[Dict[str, Any]] = None
) -> Optional[Dict[str, Any]]:
    """Async fetch Portfolios."""
    logger.debug(f"Queueing fetch Portfolios (skip={skip}, top={top})...")
    return await _make_request(
        "Portfolios", top=top, skip=skip, filter_=filter_, select=select, orderby=orderby, expand=expand,
        additional_params=additional_params
    )

async def get_positions(
    top: Optional[int] = None, skip: Optional[int] = None, filter_: Optional[str] = None,
    select: Optional[str] = None, orderby: Optional[str] = None, expand: Optional[str] = None,
    additional_params: Optional[Dict[str, Any]] = None
) -> Optional[Dict[str, Any]]:
    """Async fetch Positions."""
    logger.debug(f"Queueing fetch Positions (skip={skip}, top={top})...")
    return await _make_request(
        "Positions", top=top, skip=skip, filter_=filter_, select=select, orderby=orderby, expand=expand,
        additional_params=additional_params
    )

async def get_transactions(
    top: Optional[int] = None, skip: Optional[int] = None, filter_: Optional[str] = None,
    select: Optional[str] = None, orderby: Optional[str] = None, expand: Optional[str] = None,
    additional_params: Optional[Dict[str, Any]] = None
) -> Optional[Dict[str, Any]]:
    """Async fetch Transactions."""
    logger.debug(f"Queueing fetch Transactions (skip={skip}, top={top})...")
    return await _make_request(
        "Transactions", top=top, skip=skip, filter_=filter_, select=select, orderby=orderby, expand=expand,
        additional_params=additional_params
    )

async def get_portfolios_daily_metrics(
    top: Optional[int] = None, skip: Optional[int] = None, filter_: Optional[str] = None,
    select: Optional[str] = None, orderby: Optional[str] = None, expand: Optional[str] = None,
    additional_params: Optional[Dict[str, Any]] = None
) -> Optional[Dict[str, Any]]:
    """Async fetch PortfoliosDailyMetrics."""
    logger.debug(f"Queueing fetch PortfoliosDailyMetrics (skip={skip}, top={top})...")
    return await _make_request(
        "PortfoliosDailyMetrics", top=top, skip=skip, filter_=filter_, select=select, orderby=orderby, expand=expand,
        additional_params=additional_params
    )

# Add a function to gracefully close the client when the application exits
async def close_client():
    """Closes the shared httpx.AsyncClient."""
    await http_client.aclose()
    logger.info("HTTP client closed.")

# Example of how to use the async client (optional, for testing)
async def main_test():
    print("Testing async client...")
    assets_page = await get_assets(top=5)
    if assets_page and 'value' in assets_page:
        print(f"Fetched {len(assets_page['value'])} assets.")
        # print(assets_page['value'])
    else:
        print("Failed to fetch assets.")

    await close_client() # Remember to close the client

if __name__ == "__main__":
    # To run the test: python wealtharc_client.py
    asyncio.run(main_test())
