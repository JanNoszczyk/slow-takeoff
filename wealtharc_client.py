# --- wealtharc_client.py ---
import os
import requests
import logging
from typing import Optional, Dict, Any
from dotenv import load_dotenv
from urllib.parse import urljoin

# Import Pydantic Models for type hinting
from wealtharc_models.models import (
    AssetODataCollectionResponse,
    PortfolioODataCollectionResponse,
    PositionODataCollectionResponse,
    TransactionODataCollectionResponse,
    PortfolioDailyMetricsODataCollectionResponse
)

# --- Setup ---
load_dotenv()

# Basic logging for the client
logger = logging.getLogger("wealtharc_client")
if not logger.hasHandlers():
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

# --- Configuration ---
BASE_URL = os.getenv("VIDAR_BASE_URL")
# API_KEY = os.getenv("VIDAR_API_KEY") # Use the correct key variable
API_KEY = os.getenv("WEALTH_ARC_API_KEY") # Corrected variable name

if not BASE_URL or not API_KEY:
    # logger.error("VIDAR_BASE_URL or VIDAR_API_KEY not found in .env file. API calls will fail.")
    logger.error("VIDAR_BASE_URL or WEALTH_ARC_API_KEY not found in .env file. API calls will fail.") # Updated error message
    # Optionally raise an exception or exit, depending on desired strictness
    # raise ValueError("VIDAR_BASE_URL or VIDAR_API_KEY missing in .env")

# Ensure base URL ends with a slash for urljoin
if BASE_URL and not BASE_URL.endswith('/'):
    BASE_URL += '/'

# --- API Call Helper ---
def _make_request(
    endpoint: str,
    top: Optional[int] = None,
    skip: Optional[int] = None,
    filter_: Optional[str] = None, # Using filter_ to avoid keyword conflict
    select: Optional[str] = None,
    orderby: Optional[str] = None,
    expand: Optional[str] = None,
    additional_params: Optional[Dict[str, Any]] = None
) -> Optional[Dict[str, Any]]: # Return type is generic dict for now, parsing happens later if needed
    """
    Helper function to make GET requests to the WealthArc API,
    incorporating common OData parameters.
    """
    if not BASE_URL or not API_KEY:
        logger.error(f"Cannot make request to {endpoint}: API URL (VIDAR_BASE_URL) or Key (WEALTH_ARC_API_KEY) is not configured.")
        return None # Indicate configuration error

    # Construct the full URL relative to the base API version (assuming v1)
    # Example: https://api.wealthdatabox.com/v1/ + Assets -> https://api.wealthdatabox.com/v1/Assets
    full_url = urljoin(BASE_URL, endpoint) # BASE_URL should include /v1/

    headers = {
        "x-api-key": API_KEY,
        "Accept": "application/json"
    }

    # Build OData params
    odata_params = {}
    if top is not None:
        odata_params["$top"] = top
    if skip is not None:
        odata_params["$skip"] = skip
    if filter_ is not None:
        odata_params["$filter"] = filter_
    if select is not None:
        odata_params["$select"] = select
    if orderby is not None:
        odata_params["$orderby"] = orderby
    if expand is not None:
        odata_params["$expand"] = expand

    # Merge with any additional params provided
    if additional_params:
        odata_params.update(additional_params)

    # Ensure params is None if empty, otherwise requests might send '?'
    final_params = odata_params if odata_params else None

    try:
        # Log details just before sending
        masked_key = f"{API_KEY[:5]}...{API_KEY[-5:]}" if API_KEY and len(API_KEY) > 10 else "Invalid/Short Key"
        logger.info(f"Attempting GET: URL={full_url}")
        logger.info(f"Attempting GET: Headers={{'x-api-key': '{masked_key}', 'Accept': 'application/json'}}")
        logger.info(f"Attempting GET: Params={final_params}")

        response = requests.get(full_url, headers=headers, params=final_params, timeout=60)
        logger.info(f"Response Status Code: {response.status_code}") # Log status immediately
        response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
        return response.json()
    except requests.exceptions.HTTPError as http_err:
        # Log the error, status code, and response text if available
        logger.error(f"HTTP error occurred: {http_err}")
    except requests.exceptions.ConnectionError as conn_err:
        logger.error(f"Connection error occurred: {conn_err}")
    except requests.exceptions.Timeout as timeout_err:
        logger.error(f"Timeout error occurred: {timeout_err}")
    except requests.exceptions.RequestException as req_err:
        logger.error(f"An unexpected request error occurred: {req_err}")
    except Exception as e:
        logger.error(f"An unexpected error occurred during API call: {e}")

    return None # Indicate failure

# --- Client Functions ---
# Note: We are returning the raw dict from the JSON response.
# Pydantic parsing can be added here or done by the caller.
# For simplicity and flexibility, returning the dict for now.
# Type hints reflect the *expected* structure using Pydantic models.

def get_assets(
    top: Optional[int] = None,
    skip: Optional[int] = None,
    filter_: Optional[str] = None,
    select: Optional[str] = None,
    orderby: Optional[str] = None,
    expand: Optional[str] = None,
    additional_params: Optional[Dict[str, Any]] = None
) -> Optional[Dict[str, Any]]: # Hinting with expected structure: Optional[AssetODataCollectionResponse]
    """
    Fetches the Assets collection. Supports OData query parameters.

    Args:
        top: Limit the number of items returned.
        skip: Skip the specified number of items.
        filter_: Filter results based on a specified condition.
        select: Select specific properties to return.
        orderby: Order results by specified properties.
        expand: Include related entities.
        additional_params: Dictionary of any other query parameters.

    Returns:
        A dictionary representing the JSON response, expected to match AssetODataCollectionResponse, or None on failure.
    """
    logger.info("Fetching Assets...")
    return _make_request(
        "Assets",
        top=top, skip=skip, filter_=filter_, select=select, orderby=orderby, expand=expand,
        additional_params=additional_params
    )

def get_portfolios(
    top: Optional[int] = None,
    skip: Optional[int] = None,
    filter_: Optional[str] = None,
    select: Optional[str] = None,
    orderby: Optional[str] = None,
    expand: Optional[str] = None,
    additional_params: Optional[Dict[str, Any]] = None
) -> Optional[Dict[str, Any]]: # Hinting with expected structure: Optional[PortfolioODataCollectionResponse]
    """
    Fetches the Portfolios collection. Supports OData query parameters.

    Args:
        top: Limit the number of items returned.
        skip: Skip the specified number of items.
        filter_: Filter results based on a specified condition.
        select: Select specific properties to return.
        orderby: Order results by specified properties.
        expand: Include related entities.
        additional_params: Dictionary of any other query parameters.

    Returns:
        A dictionary representing the JSON response, expected to match PortfolioODataCollectionResponse, or None on failure.
    """
    logger.info("Fetching Portfolios...")
    return _make_request(
        "Portfolios",
        top=top, skip=skip, filter_=filter_, select=select, orderby=orderby, expand=expand,
        additional_params=additional_params
    )

def get_positions(
    top: Optional[int] = None,
    skip: Optional[int] = None,
    filter_: Optional[str] = None,
    select: Optional[str] = None,
    orderby: Optional[str] = None,
    expand: Optional[str] = None,
    additional_params: Optional[Dict[str, Any]] = None
) -> Optional[Dict[str, Any]]: # Hinting with expected structure: Optional[PositionODataCollectionResponse]
    """
    Fetches the Positions collection. Supports OData query parameters.

    Args:
        top: Limit the number of items returned.
        skip: Skip the specified number of items.
        filter_: Filter results based on a specified condition.
        select: Select specific properties to return.
        orderby: Order results by specified properties.
        expand: Include related entities (e.g., 'values', 'pnl', 'performances').
        additional_params: Dictionary of any other query parameters.

    Returns:
        A dictionary representing the JSON response, expected to match PositionODataCollectionResponse, or None on failure.
    """
    logger.info("Fetching Positions...")
    return _make_request(
        "Positions",
        top=top, skip=skip, filter_=filter_, select=select, orderby=orderby, expand=expand,
        additional_params=additional_params
    )

def get_transactions(
    top: Optional[int] = None,
    skip: Optional[int] = None,
    filter_: Optional[str] = None,
    select: Optional[str] = None,
    orderby: Optional[str] = None,
    expand: Optional[str] = None,
    additional_params: Optional[Dict[str, Any]] = None
) -> Optional[Dict[str, Any]]: # Hinting with expected structure: Optional[TransactionODataCollectionResponse]
    """
    Fetches the Transactions collection. Supports OData query parameters.

    Args:
        top: Limit the number of items returned.
        skip: Skip the specified number of items.
        filter_: Filter results based on a specified condition.
        select: Select specific properties to return.
        orderby: Order results by specified properties.
        expand: Include related entities (e.g., 'values').
        additional_params: Dictionary of any other query parameters.

    Returns:
        A dictionary representing the JSON response, expected to match TransactionODataCollectionResponse, or None on failure.
    """
    logger.info("Fetching Transactions...")
    return _make_request(
        "Transactions",
        top=top, skip=skip, filter_=filter_, select=select, orderby=orderby, expand=expand,
        additional_params=additional_params
    )

def get_portfolios_daily_metrics(
    top: Optional[int] = None,
    skip: Optional[int] = None,
    filter_: Optional[str] = None,
    select: Optional[str] = None,
    orderby: Optional[str] = None,
    expand: Optional[str] = None,
    additional_params: Optional[Dict[str, Any]] = None
) -> Optional[Dict[str, Any]]: # Hinting with expected structure: Optional[PortfolioDailyMetricsODataCollectionResponse]
    """
    Fetches the PortfoliosDailyMetrics collection. Supports OData query parameters.

    Args:
        top: Limit the number of items returned.
        skip: Skip the specified number of items.
        filter_: Filter results based on a specified condition.
        select: Select specific properties to return.
        orderby: Order results by specified properties.
        expand: Include related entities (e.g., 'custodianPerformances', 'aums', 'performances').
        additional_params: Dictionary of any other query parameters.

    Returns:
        A dictionary representing the JSON response, expected to match PortfolioDailyMetricsODataCollectionResponse, or None on failure.
    """
    logger.info("Fetching PortfoliosDailyMetrics...")
    return _make_request(
        "PortfoliosDailyMetrics",
        top=top, skip=skip, filter_=filter_, select=select, orderby=orderby, expand=expand,
        additional_params=additional_params
    )

# Example of fetching a specific entity (adjust as needed)
# def get_portfolio_by_id(portfolio_id: int, params: dict = None):
#     """Fetches a specific Portfolio by its ID."""
#     logger.info(f"Fetching Portfolio with ID: {portfolio_id}...")
#     return _make_request(f"Portfolios({portfolio_id})", params=params)

# Add more functions here for other specific endpoints or entity types if needed.
