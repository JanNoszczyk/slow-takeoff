# wealtharc-turbo-er/wa/ingest/companies_house.py

import asyncio
import httpx
import pandas as pd
from datetime import datetime, timezone
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_fixed
import duckdb
import json

from ..config import UK_COMPANIES_HOUSE_API_KEY # Import specific variable
from ..db import (
    get_db_connection, COMPANIES_HOUSE_COMPANIES_TABLE,
    COMPANIES_HOUSE_OFFICERS_TABLE, COMPANIES_HOUSE_FILINGS_TABLE # Import constants
)

# UK Companies House API Base URL
COMPANIES_HOUSE_API_BASE_URL = "https://api.company-information.service.gov.uk/"

# API Key
API_KEY = UK_COMPANIES_HOUSE_API_KEY # Use imported variable

# Define table names (now imported from db.py)
RAW_COMPANIES_HOUSE_TABLE = "raw_companies_house" # Generic raw table if needed
# COMPANIES_HOUSE_COMPANIES_TABLE = "companies_house_companies"
# COMPANIES_HOUSE_OFFICERS_TABLE = "companies_house_officers"
# COMPANIES_HOUSE_FILINGS_TABLE = "companies_house_filings"


# --- API Client Setup ---
def get_ch_auth():
    """Returns the authentication tuple for Companies House API."""
    if not API_KEY:
        logger.error("UK_COMPANIES_HOUSE_API_KEY is not configured.")
        raise ValueError("UK Companies House API Key not configured.")
    # Basic Auth: API key as username, blank password
    return (API_KEY, "")

async def make_ch_request(endpoint: str, params: dict | None = None) -> dict | None:
    """Makes an authenticated request to the Companies House API."""
    url = f"{COMPANIES_HOUSE_API_BASE_URL}{endpoint.lstrip('/')}"
    auth = get_ch_auth()

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, params=params, auth=auth, timeout=30.0)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error fetching Companies House data {url}: {e.response.status_code} - {e.request.url}")
            # Handle specific errors like 401 (Unauthorized), 404 (Not Found), 429 (Rate Limit)
            if e.response.status_code == 429:
                logger.warning("Companies House rate limit hit.")
                # Consider adding specific retry logic here or rely on a global rate limiter if implemented
            return None
        except Exception as e:
            logger.error(f"Unexpected error fetching Companies House data {url}: {e}")
            return None

# --- API Fetching Functions ---

@retry(stop=stop_after_attempt(3), wait=wait_fixed(3))
async def search_ch_companies(query: str, items_per_page: int = 20) -> list[dict]:
    """Searches for companies on Companies House."""
    logger.info(f"Searching Companies House for query: '{query}'")
    data = await make_ch_request("search/companies", params={"q": query, "items_per_page": items_per_page})
    if data and data.get("items"):
        logger.success(f"Found {data.get('total_results', 0)} potential company matches for '{query}'. Returning first {len(data['items'])}.")
        return data["items"]
    else:
        logger.warning(f"No companies found for query '{query}'.")
        return []

@retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
async def get_ch_company_profile(company_number: str) -> dict | None:
    """Gets the profile for a specific company number."""
    logger.info(f"Fetching profile for company number: {company_number}")
    return await make_ch_request(f"company/{company_number}")

@retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
async def get_ch_company_officers(company_number: str, items_per_page: int = 50) -> list[dict]:
    """Gets the list of officers for a specific company number."""
    logger.info(f"Fetching officers for company number: {company_number}")
    # TODO: Implement pagination if needed
    data = await make_ch_request(f"company/{company_number}/officers", params={"items_per_page": items_per_page})
    return data.get("items", []) if data else []

@retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
async def get_ch_filing_history(company_number: str, items_per_page: int = 50) -> list[dict]:
    """Gets the filing history for a specific company number."""
    logger.info(f"Fetching filing history for company number: {company_number}")
    # TODO: Implement pagination if needed
    data = await make_ch_request(f"company/{company_number}/filing-history", params={"items_per_page": items_per_page})
    return data.get("items", []) if data else []


# --- Database Storage Functions ---

async def store_ch_company_data(company_data: dict, con: duckdb.DuckDBPyConnection):
    """Stores cleaned company profile data."""
    if not company_data: return

    logger.info(f"Storing company data for {company_data.get('company_number')}")
    fetched_at = datetime.now(timezone.utc)
    record = (
        company_data.get('company_number'),
        company_data.get('company_name'),
        company_data.get('company_status'),
        company_data.get('type'),
        pd.to_datetime(company_data.get('date_of_creation'), errors='coerce').date(),
        json.dumps(company_data.get('registered_office_address')),
        json.dumps(company_data.get('sic_codes')),
        fetched_at
    )

    try:
        con.execute(
            f"""
            INSERT INTO {COMPANIES_HOUSE_COMPANIES_TABLE} (
                company_number, company_name, company_status, company_type, date_of_creation,
                registered_office_address, sic_codes, fetched_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(company_number) DO UPDATE SET
                company_name = excluded.company_name,
                company_status = excluded.company_status,
                company_type = excluded.company_type,
                date_of_creation = excluded.date_of_creation,
                registered_office_address = excluded.registered_office_address,
                sic_codes = excluded.sic_codes,
                fetched_at = excluded.fetched_at;
            """,
            record
        )
    except Exception as e:
        logger.error(f"Error storing company data for {record[0]}: {e}")

async def store_ch_officer_data(company_number: str, officers: list[dict], con: duckdb.DuckDBPyConnection):
    """Stores officer data, linking back to the company."""
    if not officers: return

    logger.info(f"Storing {len(officers)} officer records for company {company_number}")
    fetched_at = datetime.now(timezone.utc)
    records = []
    for officer in officers:
        appointed_on = pd.to_datetime(officer.get('appointed_on'), errors='coerce').date()
        resigned_on = pd.to_datetime(officer.get('resigned_on'), errors='coerce').date()
        record = (
            company_number,
            officer.get('links', {}).get('officer', {}).get('appointments', '').split('/')[2], # Extract officer ID heuristic
            officer.get('name'),
            officer.get('officer_role'),
            officer.get('nationality'),
            officer.get('occupation'),
            appointed_on,
            resigned_on,
            json.dumps(officer.get('address')),
            fetched_at
        )
        records.append(record)

    try:
        # Upsert based on company_number and officer_id
        con.executemany(
            f"""
            INSERT INTO {COMPANIES_HOUSE_OFFICERS_TABLE} (
                company_number, officer_id, name, officer_role, nationality, occupation,
                appointed_on, resigned_on, address, fetched_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(company_number, officer_id) DO UPDATE SET
                name = excluded.name, officer_role = excluded.officer_role, nationality = excluded.nationality,
                occupation = excluded.occupation, appointed_on = excluded.appointed_on, resigned_on = excluded.resigned_on,
                address = excluded.address, fetched_at = excluded.fetched_at;
            """,
            records
        )
    except Exception as e:
        logger.error(f"Error storing officer data for company {company_number}: {e}")

async def store_ch_filing_data(company_number: str, filings: list[dict], con: duckdb.DuckDBPyConnection):
    """Stores filing history data."""
    if not filings: return

    logger.info(f"Storing {len(filings)} filing records for company {company_number}")
    fetched_at = datetime.now(timezone.utc)
    records = []
    for filing in filings:
        action_date = pd.to_datetime(filing.get('action_date'), errors='coerce').date()
        record = (
            company_number,
            filing.get('transaction_id'), # Usually unique per filing action
            filing.get('category'),
            filing.get('type'),
            action_date,
            filing.get('description'),
            json.dumps(filing.get('links')), # Contains link to document metadata
            fetched_at
        )
        records.append(record)

    try:
        # Upsert based on company_number and transaction_id
        con.executemany(
            f"""
            INSERT INTO {COMPANIES_HOUSE_FILINGS_TABLE} (
                company_number, transaction_id, category, type, action_date, description, links, fetched_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(company_number, transaction_id) DO UPDATE SET
                 category=excluded.category, type=excluded.type, action_date=excluded.action_date,
                 description=excluded.description, links=excluded.links, fetched_at=excluded.fetched_at;
            """,
            records
        )
    except Exception as e:
        logger.error(f"Error storing filing data for company {company_number}: {e}")


# --- Main Ingestion Function ---

async def ingest_companies_house_company(company_number: str, con: duckdb.DuckDBPyConnection | None = None):
    """Fetches profile, officers, and filing history for a company and stores it."""
    if not API_KEY:
        logger.error("Cannot ingest Companies House data: API Key not set.")
        return

    logger.info(f"Starting Companies House ingestion for company: {company_number}")
    conn_local = con or get_db_connection()

    try:
        profile = await get_ch_company_profile(company_number)
        if profile:
            await store_ch_company_data(profile, con=conn_local)

            officers = await get_ch_company_officers(company_number)
            if officers:
                await store_ch_officer_data(company_number, officers, con=conn_local)

            filings = await get_ch_filing_history(company_number)
            if filings:
                await store_ch_filing_data(company_number, filings, con=conn_local)

            logger.success(f"Successfully processed data for company {company_number}.")
        else:
            logger.warning(f"Could not retrieve profile for company {company_number}.")

    except ValueError as ve: # Catch config error
        logger.error(f"Configuration error: {ve}")
    except Exception as e:
        logger.exception(f"Error during Companies House ingestion pipeline for {company_number}: {e}")
    finally:
        if not con and conn_local:
            conn_local.close()


# Example Usage
async def main():
    # Example: Search for 'BLACKROCK' and process the first result
    conn = get_db_connection()
    try:
        from .. import db # Import here for example clarity
        db.create_schema(conn) # Ensure schema exists

        search_term = "BLACKROCK INVESTMENT MANAGEMENT (UK) LIMITED"
        companies = await search_ch_companies(search_term, items_per_page=1)
        if companies:
            first_company_number = companies[0].get('company_number')
            if first_company_number:
                await ingest_companies_house_company(first_company_number, con=conn)
        else:
            print(f"No companies found for '{search_term}'")

    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    if not API_KEY:
        print("Please set the UK_COMPANIES_HOUSE_API_KEY environment variable.")
    else:
        asyncio.run(main())
