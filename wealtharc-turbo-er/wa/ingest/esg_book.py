import asyncio
import httpx
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_fixed, wait_random_exponential
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, date, timezone
import pandas as pd

from wa.config import settings
from wa.db import get_db_connection

# ESG Book API Endpoint (confirm specific endpoint if different)
ESG_BOOK_API_URL = "https://api.esgbook.com/graphql"

# Example GraphQL Query (adjust based on ESG Book schema and desired fields)
# This query assumes fetching overall ESG score, pillars, and grade for a list of ISINs
# You MUST check ESG Book's documentation for the correct schema and field names.
ESG_SCORES_QUERY_TEMPLATE = """
query EsgScoresByIsin($isins: [String!]!) {
  companies(identifiers: $isins, identifierType: ISIN) {
    isin
    company_name
    esg_score {
      value
      grade
      date # Or relevant timestamp field
    }
    environment_score {
      value
      grade
      date
    }
    social_score {
      value
      grade
      date
    }
    governance_score {
      value
      grade
      date
    }
    # Add other relevant fields like industry, country, etc. if needed
  }
}
"""

@retry(
    stop=stop_after_attempt(3),
    wait=wait_random_exponential(multiplier=1, min=2, max=10),
    retry_error_callback=lambda retry_state: logger.warning(f"Retrying ESG Book fetch after error: {retry_state.outcome.exception()}")
)
async def fetch_esg_book_data(query: str, variables: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    """Fetches data from the ESG Book GraphQL API."""
    if not settings.ESG_BOOK_API_KEY:
        logger.warning("ESG_BOOK_API_KEY not set. Skipping ESG Book fetch.")
        return None

    headers = {
        "Authorization": f"Bearer {settings.ESG_BOOK_API_KEY}", # Or "ApiKey" etc. check docs
        "Content-Type": "application/json",
    }

    payload = {"query": query}
    if variables:
        payload["variables"] = variables

    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            logger.info(f"Posting to ESG Book GraphQL API: {ESG_BOOK_API_URL}")
            # logger.debug(f"Payload: {payload}") # Be careful logging sensitive queries/variables
            response = await client.post(ESG_BOOK_API_URL, headers=headers, json=payload)

            # Handle potential errors (e.g., 401 Unauthorized, 429 Rate Limit)
            if response.status_code == 401:
                 logger.error("ESG Book API Error: Unauthorized (401). Check your API key.")
                 return None # Fatal auth error
            if response.status_code == 429:
                 logger.warning("ESG Book API Error: Too Many Requests (429). Retrying after delay...")
                 raise httpx.HTTPStatusError(message="Rate limit hit", request=response.request, response=response) # Trigger retry


            response.raise_for_status() # Raise for other HTTP errors
            data = response.json()

            # Check for errors within the GraphQL response payload
            if "errors" in data:
                error_messages = [err.get("message", "Unknown GraphQL error") for err in data["errors"]]
                logger.error(f"ESG Book GraphQL Error(s): {'; '.join(error_messages)}")
                # Depending on the error, might still contain partial data in 'data' field
                # For now, treat GraphQL errors as failure to get expected data
                return None # Or return data['data'] if partial results are acceptable

            logger.success("Successfully fetched data from ESG Book GraphQL API.")
            return data.get("data") # Return only the 'data' part of the response

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error fetching ESG Book: Status {e.response.status_code}. Response: {e.response.text[:200]}")
            raise # Let tenacity handle retry for relevant status codes like 429
        except Exception as e:
            logger.error(f"Error posting to ESG Book API: {e}")
            raise # Let tenacity handle retry

async def store_raw_esg_book_data(conn, query_type: str, identifiers: List[str], data: Any):
    """Stores the raw ESG Book GraphQL response."""
    if data:
        # Create a somewhat unique ID
        timestamp_str = str(int(time.time()))
        identifier_hash = str(hash(tuple(sorted(identifiers))))[:8] # Short hash of identifiers
        raw_id = f"esgbook_{query_type}_{identifier_hash}_{timestamp_str}"
        logger.debug(f"Storing raw ESG Book data for query type {query_type}")
        await conn.execute("""
            INSERT INTO raw_esg_book (id, fetched_at, payload)
            VALUES ($1, CURRENT_TIMESTAMP, $2::JSON)
            ON CONFLICT (id) DO UPDATE SET
                fetched_at = excluded.fetched_at,
                payload = excluded.payload;
        """, raw_id, str(data)) # Store response data as JSON string
        logger.success(f"Stored raw ESG Book data for {query_type}")

def parse_esg_book_scores(raw_data: Dict[str, Any]) -> Optional[pd.DataFrame]:
    """
    Parses the ESG Book GraphQL response for company scores.

    Assumes the response structure from the example ESG_SCORES_QUERY_TEMPLATE.

    Returns:
        Pandas DataFrame with columns like 'isin', 'score_type', 'value', 'grade', 'date',
        or None if parsing fails.
    """
    try:
        companies_data = raw_data.get("companies", [])
        if not companies_data:
            logger.warning("No 'companies' data found in ESG Book response.")
            return None

        scores_list = []
        score_types = ["esg_score", "environment_score", "social_score", "governance_score"]

        for company in companies_data:
            isin = company.get("isin")
            if not isin:
                continue # Skip if no identifier

            for score_type in score_types:
                score_data = company.get(score_type)
                if score_data and score_data.get("value") is not None:
                    try:
                        # Attempt to parse date (format might vary, e.g., YYYY-MM-DD or just YYYY)
                        date_str = score_data.get("date")
                        score_date = None
                        if date_str:
                             if len(date_str) == 4: # Assume YYYY
                                 score_date = date(int(date_str), 12, 31) # Use year end
                             elif len(date_str) >= 10: # Assume YYYY-MM-DD
                                 score_date = date.fromisoformat(date_str[:10])

                        if score_date: # Only add score if date is valid
                            scores_list.append({
                                "isin": isin,
                                "score_type": score_type,
                                "value": float(score_data["value"]),
                                "grade": score_data.get("grade"),
                                "date": score_date,
                            })
                    except (ValueError, TypeError) as e:
                        logger.warning(f"Skipping score {score_type} for ISIN {isin} due to parsing error: {e}. Data: {score_data}")

        if not scores_list:
            logger.warning("No valid scores parsed from ESG Book response.")
            return pd.DataFrame(columns=['isin', 'score_type', 'value', 'grade', 'date']) # Return empty DF

        scores_df = pd.DataFrame(scores_list)
        logger.success(f"Parsed {len(scores_df)} ESG score entries.")
        return scores_df

    except Exception as e:
        logger.error(f"Failed to parse ESG Book scores response: {e}")
        return None


async def ingest_esg_book_scores(conn, isins: List[str]):
    """Fetches, parses, and stores ESG scores for a list of ISINs."""
    logger.info(f"Ingesting ESG Book scores for {len(isins)} ISINs...")

    if not isins:
        logger.warning("No ISINs provided for ESG Book ingestion.")
        return False

    variables = {"isins": isins}
    query = ESG_SCORES_QUERY_TEMPLATE

    # Fetch data
    raw_data = await fetch_esg_book_data(query=query, variables=variables)
    if not raw_data:
        logger.error(f"Failed to fetch ESG scores from ESG Book for ISINs: {isins}")
        return False

    # Store raw data
    await store_raw_esg_book_data(conn, "scores_by_isin", isins, raw_data)

    # Parse data
    scores_df = parse_esg_book_scores(raw_data)
    if scores_df is None: # Parsing failed
        logger.error("Failed to parse ESG scores data.")
        return False
    elif scores_df.empty:
         logger.warning("No ESG scores parsed. Nothing to store.")
         return True # Not a failure if parsing worked but yielded no data

    # --- Map ISINs to asset_ids ---
    # Create a mapping from ISIN to asset_id from our assets table
    isin_list_str = ','.join(f"'{isin}'" for isin in isins) # Prepare for SQL IN clause
    try:
        mapping_df = await conn.execute_fetchall(f"SELECT isin, asset_id FROM assets WHERE isin IN ({isin_list_str})")
        isin_to_asset_id = {row[0]: row[1] for row in mapping_df}
        logger.debug(f"Found {len(isin_to_asset_id)} matching assets for ISINs.")
    except Exception as e:
        logger.error(f"Failed to query asset IDs for ISIN mapping: {e}")
        return False # Cannot proceed without mapping

    # Add asset_id to scores_df
    scores_df['asset_id'] = scores_df['isin'].map(isin_to_asset_id)
    # Filter out scores for ISINs not found in our assets table
    scores_to_insert_df = scores_df.dropna(subset=['asset_id'])
    scores_to_insert_df['asset_id'] = scores_to_insert_df['asset_id'].astype(int)

    if scores_to_insert_df.empty:
        logger.warning("No ESG scores remaining after mapping ISINs to known asset IDs.")
        return True


    # --- Store Parsed Scores ---
    rows_to_insert = [
        (row['asset_id'], row['score_type'], row['date'], row['value'], row['grade'])
        for _, row in scores_to_insert_df.iterrows() if pd.notna(row['value']) and pd.notna(row['date'])
    ]

    if not rows_to_insert:
        logger.warning("No valid (non-null) ESG scores with dates to insert.")
        return True

    try:
        await conn.executemany("""
            INSERT INTO esg_scores (asset_id, score_type, date, value, grade, fetched_at)
            VALUES ($1, $2, $3, $4, $5, CURRENT_TIMESTAMP)
            ON CONFLICT (asset_id, score_type, date, source) DO UPDATE SET
                value = excluded.value,
                grade = excluded.grade,
                fetched_at = excluded.fetched_at;
        """, rows_to_insert)
        logger.success(f"Successfully inserted/updated {len(rows_to_insert)} ESG scores.")
        return True
    except Exception as e:
        logger.error(f"Database error inserting ESG scores: {e}")
        return False

async def run_esg_book_ingestion(isins: List[str]):
    """Wrapper function to run ESG Book ingestion for a list of ISINs."""
    logger.info(f"Starting ESG Book ingestion job for {len(isins)} ISINs...")
    conn = None
    try:
        conn = await get_db_connection()
        # Process in batches if needed, API might have limits on identifiers per query
        batch_size = 50 # Example batch size, check API docs
        all_success = True
        for i in range(0, len(isins), batch_size):
            batch_isins = isins[i:i + batch_size]
            logger.info(f"Processing ESG Book batch {i//batch_size + 1} ({len(batch_isins)} ISINs)...")
            success = await ingest_esg_book_scores(conn, batch_isins)
            if not success:
                all_success = False # Mark failure but continue other batches
                logger.error(f"ESG Book batch failed for ISINs starting with {batch_isins[0]}")
            await asyncio.sleep(1) # Small delay between batches

        if all_success:
            logger.success("ESG Book ingestion job completed successfully for all batches.")
        else:
            logger.warning("ESG Book ingestion job completed with one or more batch failures.")

    except Exception as e:
        logger.error(f"General error during ESG Book ingestion job: {e}")
    finally:
        if conn:
            await conn.close()
            logger.info("Database connection closed for ESG Book ingest.")

# Example usage (optional):
# if __name__ == "__main__":
#     async def main():
#         # ISINs for AAPL, MSFT, NVDA (example)
#         test_isins = ["US0378331005", "US5949181045", "US67066G1040"]
#         await run_esg_book_ingestion(test_isins)
#     asyncio.run(main())

```

I'll wait for confirmation that `wealtharc-turbo-er/wa/ingest/esg_book.py` was created successfully. Then, I'll update the Streamlit app.
