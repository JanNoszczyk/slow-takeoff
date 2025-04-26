# wealtharc-turbo-er/wa/ingest/sec_edgar.py

import asyncio
from sec_edgar_downloader import Downloader
from datetime import datetime, timezone, timedelta
from loguru import logger
import duckdb
from pathlib import Path
import os
import json
import pandas as pd

from ..config import SEC_EDGAR_USER_AGENT, PROJECT_ROOT # Import specific variables
from ..db import get_db_connection, SEC_FILINGS_TABLE # Import the constant

# Define table name (now imported)
# SEC_FILINGS_TABLE = "sec_filings_metadata"

# SEC EDGAR User Agent and Download Path
USER_AGENT = SEC_EDGAR_USER_AGENT # Use imported variable
# Define a dedicated directory within the project for EDGAR downloads
DOWNLOAD_PATH = PROJECT_ROOT / "data" / "sec_edgar_filings"

# Ensure the download directory exists
DOWNLOAD_PATH.mkdir(parents=True, exist_ok=True)

# --- Downloader Initialization ---
def get_edgar_downloader():
    """Initializes and returns an SEC EDGAR Downloader instance."""
    if not USER_AGENT or "Your Name Your Email" in USER_AGENT:
        logger.error("SEC_EDGAR_USER_AGENT is not set properly in config/environment.")
        raise ValueError("SEC EDGAR User Agent not configured correctly. Please provide a valid email address.")

    # Initialize downloader, specifying download path and user agent
    dl = Downloader(company_or_cik=None, email_address=USER_AGENT, download_path=str(DOWNLOAD_PATH))
    logger.info(f"SEC EDGAR Downloader initialized. User Agent: {USER_AGENT}, Download Path: {DOWNLOAD_PATH}")
    return dl

# --- Filing Download Function ---

async def download_sec_filings(
    ticker_or_cik: str,
    filing_type: str,
    start_date: str | None = None, # YYYY-MM-DD
    end_date: str | None = None,   # YYYY-MM-DD
    limit: int | None = None,
    include_amends: bool = False
) -> list[dict]:
    """
    Downloads specified SEC filings using sec-edgar-downloader.

    Args:
        ticker_or_cik: Company ticker or CIK.
        filing_type: Filing type (e.g., "10-K", "10-Q", "8-K", "4").
        start_date: Optional start date (after).
        end_date: Optional end date (before).
        limit: Optional limit on the number of filings.
        include_amends: Whether to include amended filings (e.g., 10-K/A).

    Returns:
        A list of dictionaries containing metadata about downloaded filings.
    """
    logger.info(f"Attempting to download {filing_type} filings for {ticker_or_cik}...")
    dl = get_edgar_downloader()
    downloaded_files_metadata = []

    try:
        # Run the synchronous download method in a separate thread
        await asyncio.to_thread(
            dl.get,
            filing_type,
            ticker_or_cik,
            after=start_date,
            before=end_date,
            limit=limit,
            download_details=True, # Get metadata like filing date, accession number
            include_amends=include_amends
        )
        logger.success(f"SEC EDGAR download request completed for {ticker_or_cik}, type {filing_type}.")

        # --- Locate downloaded files (Heuristic based on library structure) ---
        company_path = DOWNLOAD_PATH / ticker_or_cik.upper() / filing_type.upper().replace("-","")
        if company_path.exists():
            for acc_num_dir in company_path.iterdir():
                 if acc_num_dir.is_dir():
                    primary_docs = list(acc_num_dir.glob("primary-document.*")) + list(acc_num_dir.glob("*.htm")) + list(acc_num_dir.glob("*.txt"))
                    primary_doc_path = next((p for p in primary_docs if "primary-document" in p.name and p.suffix =='.html'), None)
                    if not primary_doc_path and primary_docs:
                        primary_doc_path = primary_docs[0]

                    if primary_doc_path and primary_doc_path.exists():
                         details_path = acc_num_dir / "filing-details.json"
                         filing_date = None
                         if details_path.exists():
                              try:
                                   with open(details_path, 'r') as f:
                                        details = json.load(f)
                                        filing_date = details.get('filingDate')
                              except Exception as e:
                                   logger.warning(f"Could not parse filing details JSON {details_path}: {e}")

                         downloaded_files_metadata.append({
                              "ticker_or_cik": ticker_or_cik,
                              "filing_type": filing_type,
                              "accession_number": acc_num_dir.name,
                              "filing_date": filing_date,
                              "primary_doc_path": str(primary_doc_path.relative_to(PROJECT_ROOT)),
                              "downloaded_at": datetime.now(timezone.utc)
                         })
        else:
             logger.warning(f"Expected download directory not found: {company_path}")

    except ValueError as ve:
         logger.error(f"Configuration error downloading filings: {ve}")
         raise
    except Exception as e:
        logger.error(f"Error downloading filings for {ticker_or_cik} ({filing_type}): {e}")

    logger.info(f"Found metadata for {len(downloaded_files_metadata)} downloaded filings for {ticker_or_cik}.")
    return downloaded_files_metadata


# --- Database Storage Function ---

async def store_sec_filings_metadata(filings_metadata: list[dict], con: duckdb.DuckDBPyConnection):
    """Stores metadata about downloaded SEC filings into the database."""
    if not filings_metadata:
        return

    logger.info(f"Storing metadata for {len(filings_metadata)} SEC filings...")
    records_to_insert = []

    for meta in filings_metadata:
        filing_dt = pd.to_datetime(meta['filing_date'], errors='coerce').date() if meta['filing_date'] else None
        record = (
            meta['accession_number'],
            meta['ticker_or_cik'].upper(),
            meta['filing_type'].upper(),
            filing_dt,
            meta['primary_doc_path'],
            meta['downloaded_at']
        )
        records_to_insert.append(record)

    try:
        con.executemany(
            f"""
            INSERT INTO {SEC_FILINGS_TABLE} (
                accession_number, ticker_cik, filing_type, filing_date, primary_doc_path, downloaded_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(accession_number) DO UPDATE SET
                downloaded_at = excluded.downloaded_at,
                primary_doc_path = excluded.primary_doc_path;
            """,
            records_to_insert
        )
        logger.success(f"Successfully stored/updated metadata for {len(records_to_insert)} SEC filings.")
    except Exception as e:
        logger.error(f"Error storing SEC filing metadata: {e}")


# --- Main Ingestion Function ---

async def ingest_sec_filings(
    ticker_or_cik: str,
    filing_type: str,
    start_date: str | None = None,
    end_date: str | None = None,
    limit: int | None = 5,
    include_amends: bool = False,
    con: duckdb.DuckDBPyConnection | None = None
):
    """Downloads SEC filings and stores metadata."""
    if not USER_AGENT or "Your Name Your Email" in USER_AGENT:
         logger.error("Cannot ingest SEC EDGAR data: User Agent not properly configured.")
         return

    logger.info(f"Starting SEC EDGAR ingestion for {ticker_or_cik}, type {filing_type}")
    conn_local = con or get_db_connection()

    try:
        filings_metadata = await download_sec_filings(
            ticker_or_cik=ticker_or_cik,
            filing_type=filing_type,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
            include_amends=include_amends
        )

        if filings_metadata:
            await store_sec_filings_metadata(filings_metadata, con=conn_local)
        else:
            logger.info(f"No new filings downloaded or metadata found for {ticker_or_cik} ({filing_type}).")

    except ValueError as ve:
         logger.error(f"Configuration error during SEC ingestion: {ve}")
    except Exception as e:
        logger.exception(f"Error during SEC EDGAR ingestion pipeline for {ticker_or_cik}: {e}")
    finally:
        if not con and conn_local:
            conn_local.close()


# Example Usage
async def main():
    test_ticker = "AAPL"
    test_filing_type = "10-K"
    start = (datetime.now() - timedelta(days=400)).strftime('%Y-%m-%d')
    end = datetime.now().strftime('%Y-%m-%d')

    conn = get_db_connection()
    try:
        from .. import db
        db.create_schema(conn)
        await ingest_sec_filings(test_ticker, test_filing_type, start_date=start, end_date=end, limit=2, con=conn)
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    if not USER_AGENT or "Your Name Your Email" in USER_AGENT:
        print("Please set the SEC_EDGAR_USER_AGENT environment variable in your .env file (e.g., 'Your Name youremail@example.com').")
    else:
        asyncio.run(main())
