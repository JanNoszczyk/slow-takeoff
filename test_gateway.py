import pytest
import httpx
import os
from dotenv import load_dotenv
import asyncio
from pydantic import ValidationError

# --- Import Pydantic models from app.py ---
# Assuming app.py is in the same directory or accessible via PYTHONPATH
# If not, adjust the import path accordingly
try:
    from app import (
        AssetODataCollectionResponse, AssetODataResponse,
        CashAccountODataCollectionResponse, InstrumentODataCollectionResponse,
        PortfolioODataCollectionResponse, PortfolioODataResponse,
        PositionODataCollectionResponse, PositionODataResponse,
        TransactionODataCollectionResponse, TransactionODataResponse,
        PortfolioDailyMetricsODataCollectionResponse, PortfolioDailyMetricsODataResponse,
        # Add other necessary models if needed
    )
except ImportError as e:
    pytest.fail(f"Failed to import models from app.py: {e}. Ensure app.py is accessible.")


# Load environment variables from .env file
load_dotenv()

# Get Vidar API details from environment
VIDAR_BASE_URL = os.getenv("VIDAR_BASE_URL")
VIDAR_API_KEY = os.getenv("VIDAR_API_KEY")

# Base URL of the running service (adjust if your docker-compose exposes a different port)
SERVICE_BASE_URL = "http://localhost:24006"

# Check if required environment variables are set for REAL API tests
gateway_env_vars_set = VIDAR_BASE_URL and VIDAR_API_KEY

# Define a pytest marker to skip tests if environment variables are not set
requires_gateway_env = pytest.mark.skipif(
    not gateway_env_vars_set,
    reason="VIDAR_BASE_URL and VIDAR_API_KEY must be set in .env for gateway forwarding tests"
)

# === Test for Gateway Forwarding to Real API ===

@requires_gateway_env
@pytest.mark.asyncio
async def test_gateway_forwarding_real_api(): # Renamed test
    """
    Tests the GET /gateway/myodata/Assets endpoint, which should forward
    the request to the real Vidar API specified in .env.
    """
    assets_url = f"{SERVICE_BASE_URL}/gateway/myodata/Assets"
    headers = {"Accept": "application/json"} # Mimic a typical client request

    async with httpx.AsyncClient() as client:
        try:
            print(f"\n[Test] Requesting: GET {assets_url}")
            response = await client.get(assets_url, headers=headers, timeout=30.0) # Increased timeout for real API call

            print(f"[Test] Response Status Code: {response.status_code}")
            # Try to print first 500 chars of response for debugging if not 200
            if response.status_code != 200:
                 try:
                     print(f"[Test] Response Body (first 500 chars): {response.text[:500]}")
                 except Exception:
                     print("[Test] Could not decode response body.")

            # --- Assertions ---
            assert response.status_code == 200, f"Expected status code 200, but got {response.status_code}"

            # Check if the response body is valid JSON
            try:
                response_data = response.json()
            except ValueError:
                pytest.fail("Response body is not valid JSON.")

            # Check for basic OData structure
            assert "@odata.context" in response_data, "Response JSON should contain '@odata.context'"
            assert "value" in response_data, "Response JSON should contain 'value'"
            assert isinstance(response_data["value"], list), "'value' should be a list"

            print(f"[Test] Received {len(response_data['value'])} assets.")
            # Optionally, add more specific assertions about the asset data structure if known
            # For example, check if the first asset has an 'id' and 'name'
            if response_data["value"]:
                first_asset = response_data["value"][0]
                assert "id" in first_asset, "First asset in 'value' should have an 'id'"
                # Add more checks as needed based on expected Asset structure
                print(f"[Test] First asset ID: {first_asset.get('id')}")


        except httpx.ConnectError as e:
            pytest.fail(f"Connection to the service failed. Is the service running at {SERVICE_BASE_URL}? Error: {e}")
        except httpx.TimeoutException as e:
            pytest.fail(f"Request timed out. The real API might be slow or the service unavailable. Error: {e}")
        except Exception as e:
            pytest.fail(f"An unexpected error occurred: {e}")

# === Tests for Gateway Accessing Mock API Endpoints ===

# Define test cases: (entity_set_path, expected_pydantic_model)
mock_endpoint_test_cases = [
    ("Assets", AssetODataCollectionResponse),
    ("Assets/25237", AssetODataResponse), # Example CashAccount key
    ("Assets/25238", AssetODataResponse), # Example Instrument key
    ("Assets/WealthArc.CashAccount", CashAccountODataCollectionResponse),
    ("Assets/WealthArc.Instrument", InstrumentODataCollectionResponse),
    ("Portfolios", PortfolioODataCollectionResponse),
    ("Portfolios/30825", PortfolioODataResponse), # Example key
    ("Positions", PositionODataCollectionResponse),
    ("Positions/601345", PositionODataResponse), # Example key
    ("Transactions", TransactionODataCollectionResponse),
    ("Transactions/701345", TransactionODataResponse), # Example key
    ("PortfoliosDailyMetrics", PortfolioDailyMetricsODataCollectionResponse),
    ("PortfoliosDailyMetrics/301246", PortfolioDailyMetricsODataResponse), # Example key
]

@pytest.mark.parametrize("entity_set, expected_model", mock_endpoint_test_cases)
@pytest.mark.asyncio
async def test_gateway_mock_endpoints(entity_set: str, expected_model):
    """
    Tests the gateway endpoints accessing the *mock* API.
    Validates the response structure against Pydantic models from app.py.
    """
    gateway_url = f"{SERVICE_BASE_URL}/gateway/myodata/{entity_set}"
    headers = {"Accept": "application/json"}

    async with httpx.AsyncClient() as client:
        try:
            print(f"\n[Test Mock] Requesting: GET {gateway_url}")
            # Use the mock URL, no API key needed/sent by gateway for mock
            response = await client.get(gateway_url, headers=headers, timeout=10.0)

            print(f"[Test Mock] Response Status Code: {response.status_code}")
            if response.status_code != 200:
                 try:
                     print(f"[Test Mock] Response Body (first 500 chars): {response.text[:500]}")
                 except Exception:
                     print("[Test Mock] Could not decode response body.")

            # --- Assertions ---
            assert response.status_code == 200, f"Expected status code 200, but got {response.status_code}"
            assert "application/json" in response.headers.get("content-type", ""), "Content-Type should be application/json"

            # Check if the response body is valid JSON
            try:
                response_data = response.json()
                print(f"[Test Mock] Response JSON received.") # Basic confirmation
            except ValueError:
                pytest.fail(f"Response body is not valid JSON for {gateway_url}.")

            # Validate response against the expected Pydantic model
            try:
                validated_data = expected_model.model_validate(response_data)
                print(f"[Test Mock] Response validated successfully against {expected_model.__name__}.")
                # Optionally, add more specific assertions on validated_data if needed
                assert validated_data.value is not None, "'value' field should not be None"

            except ValidationError as e:
                pytest.fail(f"Pydantic validation failed for {gateway_url} against {expected_model.__name__}:\n{e}")
            except Exception as e:
                 pytest.fail(f"Unexpected error during Pydantic validation for {gateway_url}:\n{e}")


        except httpx.ConnectError as e:
            pytest.fail(f"Connection to the service failed. Is the service running at {SERVICE_BASE_URL}? Error: {e}")
        except httpx.TimeoutException as e:
            pytest.fail(f"Request timed out connecting to the service. Error: {e}")
        except Exception as e:
            pytest.fail(f"An unexpected error occurred during mock test for {gateway_url}: {e}")


# Example of how to run this test:
# 1. Ensure the service is running: docker-compose up -d
# 2. Install pytest: pip install pytest pytest-asyncio httpx python-dotenv pydantic
# 3. Run pytest: pytest test_gateway.py -v -s
# The "-s" flag allows print statements to be displayed.
