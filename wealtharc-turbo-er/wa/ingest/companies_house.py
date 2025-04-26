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

# --- API Client Setup ---
def get_ch_auth():
    """Returns the authentication tuple for Companies House API."""
    if not API_KEY:
        logger.error("UK_COMPANIES_HOUSE_API_KEY is not configured.")
        raise ValueError("UK Companies House API Key not configured.")
    return (API_KEY, "")

async def make_ch_request(endpoint: str, params: dict | None = None) -> dict | None:
    """Makes an authenticated request to the Companies House API."""
    url = f"{COMPANIES_HOUSE_API_BASE_URL}{endpoint.lstrip('/')}"
    try:
        auth = get_ch_auth() # Get auth, may raise ValueError
    except ValueError as e:
        logger.error(f"Cannot make CH request: {e}")
        return None # Don't proceed without auth

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, params=params, auth=auth, timeout=30.0)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error fetching Companies House data {url}: {e.response.status_code} - {e.request.url}")
            if e.response.status_code == 429: logger.warning("Companies House rate limit hit.")
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
    data = await make_ch_request(f"company/{company_number}/officers", params={"items_per_page": items_per_page})
    return data.get("items", []) if data else []

@retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
async def get_ch_filing_history(company_number: str, items_per_page: int = 50) -> list[dict]:
    """Gets the filing history for a specific company number."""
    logger.info(f"Fetching filing history for company number: {company_number}")
    data = await make_ch_request(f"company/{company_number}/filing-history", params={"items_per_page": items_per_page})
    return data.get("items", []) if data else []


# --- Database Storage Functions ---

async def store_ch_company_data(company_data: dict, db_path: str | None = None):
    """Stores cleaned company profile data."""
    if not company_data: return
    co_num = company_data.get('company_number')
    logger.info(f"Storing company data for {co_num}")
    record = (
        co_num, company_data.get('company_name'), company_data.get('company_status'),
        company_data.get('type'), pd.to_datetime(company_data.get('date_of_creation'), errors='coerce').date(),
        json.dumps(company_data.get('registered_office_address')), json.dumps(company_data.get('sic_codes')),
        datetime.now(timezone.utc)
    )
    try:
        def db_operations_in_thread(path: str | None, data: tuple):
            conn = None
            try:
                conn = get_db_connection(path)
                conn.execute(
                    f"""
                    INSERT INTO {COMPANIES_HOUSE_COMPANIES_TABLE} (
                        company_number, company_name, company_status, company_type, date_of_creation,
                        registered_office_address, sic_codes, fetched_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(company_number) DO UPDATE SET
                        company_name=excluded.company_name, company_status=excluded.company_status,
                        company_type=excluded.company_type, date_of_creation=excluded.date_of_creation,
                        registered_office_address=excluded.registered_office_address, sic_codes=excluded.sic_codes,
                        fetched_at=excluded.fetched_at;
                    """, data
                )
                logger.success(f"Thread stored/updated company data for {data[0]}.")
            except Exception as thread_e: logger.error(f"Error in thread storing company data for {data[0]}: {thread_e}"); raise
            finally:
                if conn: conn.close(); logger.debug(f"Thread closed company data DB connection for {data[0]}.")
        await asyncio.to_thread(db_operations_in_thread, db_path, record)
    except Exception as e: logger.error(f"Error storing company data for {co_num}: {e}"); raise

async def store_ch_officer_data(company_number: str, officers: list[dict], db_path: str | None = None):
    """Stores officer data, linking back to the company."""
    if not officers: return
    logger.info(f"Storing {len(officers)} officer records for company {company_number}")
    fetched_at = datetime.now(timezone.utc)
    records = []
    for officer in officers:
        record = (
            company_number, officer.get('links', {}).get('officer', {}).get('appointments', '').split('/')[2],
            officer.get('name'), officer.get('officer_role'), officer.get('nationality'), officer.get('occupation'),
            pd.to_datetime(officer.get('appointed_on'), errors='coerce').date(),
            pd.to_datetime(officer.get('resigned_on'), errors='coerce').date(),
            json.dumps(officer.get('address')), fetched_at
        )
        records.append(record)
    try:
        def db_operations_in_thread(path: str | None, data: list, co_num: str):
            conn = None
            try:
                conn = get_db_connection(path)
                conn.executemany(
                    f"""
                    INSERT INTO {COMPANIES_HOUSE_OFFICERS_TABLE} (
                        company_number, officer_id, name, officer_role, nationality, occupation,
                        appointed_on, resigned_on, address, fetched_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(company_number, officer_id) DO UPDATE SET
                        name=excluded.name, officer_role=excluded.officer_role, nationality=excluded.nationality,
                        occupation=excluded.occupation, appointed_on=excluded.appointed_on, resigned_on=excluded.resigned_on,
                        address=excluded.address, fetched_at=excluded.fetched_at;
                    """, data
                )
                logger.success(f"Thread stored/updated {len(data)} officer records for company {co_num}.")
            except Exception as thread_e: logger.error(f"Error in thread storing officer data for company {co_num}: {thread_e}"); raise
            finally:
                if conn: conn.close(); logger.debug(f"Thread closed officer data DB connection for {co_num}.")
        await asyncio.to_thread(db_operations_in_thread, db_path, records, company_number)
    except Exception as e: logger.error(f"Error storing officer data for company {company_number}: {e}"); raise

async def store_ch_filing_data(company_number: str, filings: list[dict], db_path: str | None = None):
    """Stores filing history data."""
    if not filings: return
    logger.info(f"Storing {len(filings)} filing records for company {company_number}")
    fetched_at = datetime.now(timezone.utc)
    records = []
    for filing in filings:
        record = (
            company_number, filing.get('transaction_id'), filing.get('category'), filing.get('type'),
            pd.to_datetime(filing.get('action_date'), errors='coerce').date(),
            filing.get('description'), json.dumps(filing.get('links')), fetched_at
        )
        records.append(record)
    try:
        def db_operations_in_thread(path: str | None, data: list, co_num: str):
            conn = None
            try:
                conn = get_db_connection(path)
                conn.executemany(
                    f"""
                    INSERT INTO {COMPANIES_HOUSE_FILINGS_TABLE} (
                        company_number, transaction_id, category, type, action_date, description, links, fetched_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(company_number, transaction_id) DO UPDATE SET
                         category=excluded.category, type=excluded.type, action_date=excluded.action_date,
                         description=excluded.description, links=excluded.links, fetched_at=excluded.fetched_at;
                    """, data
                )
                logger.success(f"Thread stored/updated {len(data)} filing records for company {co_num}.")
            except Exception as thread_e: logger.error(f"Error in thread storing filing data for company {co_num}: {thread_e}"); raise
            finally:
                if conn: conn.close(); logger.debug(f"Thread closed filing data DB connection for {co_num}.")
        await asyncio.to_thread(db_operations_in_thread, db_path, records, company_number)
    except Exception as e: logger.error(f"Error storing filing data for company {company_number}: {e}"); raise


# --- Main Ingestion Function ---

async def ingest_companies_house_company(company_number: str, db_path: str | None = None):
    """Fetches profile, officers, and filing history for a company and stores it."""
    if not API_KEY: logger.error("Cannot ingest Companies House data: API Key not set."); return
    logger.info(f"Starting Companies House ingestion for company: {company_number}")
    try:
        profile = await get_ch_company_profile(company_number)
        if profile:
            tasks = []
            # Schedule storage operations, passing db_path
            tasks.append(store_ch_company_data(profile, db_path=db_path))
            officers = await get_ch_company_officers(company_number)
            if officers: tasks.append(store_ch_officer_data(company_number, officers, db_path=db_path))
            filings = await get_ch_filing_history(company_number)
            if filings: tasks.append(store_ch_filing_data(company_number, filings, db_path=db_path))

            # Await storage tasks concurrently (they handle their own connections/threading)
            results = await asyncio.gather(*tasks, return_exceptions=True)
            success_count = sum(1 for r in results if not isinstance(r, Exception))
            fail_count = len(results) - success_count
            if fail_count == 0:
                 logger.success(f"Successfully processed profile, officers, filings for company {company_number}.")
            else:
                 logger.warning(f"Processed data for company {company_number} with {fail_count} storage errors. Check logs.")
                 # Optionally log specific errors from results list
                 for i, res in enumerate(results):
                      if isinstance(res, Exception):
                           logger.error(f"  - Task {i} failed: {res}")
        else:
            logger.warning(f"Could not retrieve profile for company {company_number}.")

    except ValueError as ve: logger.error(f"Configuration error: {ve}"); raise
    except Exception as e: logger.exception(f"Error during Companies House ingestion pipeline for {company_number}: {e}"); raise


# Example Usage
async def main():
    test_db_path = "test_ch.db"
    conn = None
    try:
        conn = get_db_connection(test_db_path)
        from .. import db
        db.create_schema(conn); conn.close(); conn = None

        search_term = "BLACKROCK INVESTMENT MANAGEMENT (UK) LIMITED"
        companies = await search_ch_companies(search_term, items_per_page=1)
        if companies:
            first_company_number = companies[0].get('company_number')
            if first_company_number:
                await ingest_companies_house_company(first_company_number, db_path=test_db_path)
        else:
            print(f"No companies found for '{search_term}'")
    except Exception as e: logger.exception(f"CH example failed: {e}")
    finally:
        if conn: conn.close()
        import os
        if os.path.exists(test_db_path): os.remove(test_db_path); logger.info(f"Cleaned up {test_db_path}")

if __name__ == "__main__":
    if not API_KEY:
        print("Please set the UK_COMPANIES_HOUSE_API_KEY environment variable.")
    else:
        asyncio.run(main())
