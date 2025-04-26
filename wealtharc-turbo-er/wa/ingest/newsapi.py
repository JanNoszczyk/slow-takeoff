import asyncio
import httpx
import json
import time
import hashlib
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional, Tuple
from urllib.parse import urlparse
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import dateutil.parser # For parsing datetime strings
import duckdb

from wa import config, db

NEWSAPI_URL = "https://newsapi.org/v2/everything"
# Rate limits: Depend on plan. Free plan allows 100 requests per day total.
# Paid plans have higher limits per second/day.
# Max page size is 100 articles.
MAX_PAGE_SIZE = 100
# Free plan limitations: Can only search articles up to 1 month old.

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((httpx.RequestError, httpx.HTTPStatusError)),
    reraise=True
)
async def fetch_news_page(
    query: str,
    page: int,
    page_size: int,
    client: httpx.AsyncClient,
    from_date: Optional[str] = None, # YYYY-MM-DD or ISO 8601
    to_date: Optional[str] = None,   # YYYY-MM-DD or ISO 8601
    language: str = 'en',
    sort_by: str = 'publishedAt' # relevancy, popularity, publishedAt
) -> Optional[Dict[str, Any]]:
    """
    Fetches a single page of news articles from NewsAPI.

    Args:
        query: The search query (keywords or phrases).
        page: The page number to fetch.
        page_size: Number of results per page (max 100).
        client: An httpx.AsyncClient instance.
        from_date: Optional start date for articles.
        to_date: Optional end date for articles.
        language: Language code (e.g., 'en', 'de').
        sort_by: How to sort the articles.

    Returns:
        The JSON response from the API as a dictionary, or None if failed.
    """
    if not config.NEWSAPI_API_KEY:
        logger.error("NEWSAPI_API_KEY not set. Cannot fetch news.")
        return None
    if not query:
        logger.warning("No query provided for NewsAPI.")
        return None

    headers = {"Authorization": f"Bearer {config.NEWSAPI_API_KEY}"}
    params = {
        "q": query,
        "pageSize": min(page_size, MAX_PAGE_SIZE),
        "page": page,
        "language": language,
        "sortBy": sort_by,
    }
    if from_date:
        params["from"] = from_date
    if to_date:
        params["to"] = to_date

    try:
        response = await client.get(NEWSAPI_URL, params=params, headers=headers, timeout=config.HTTPX_TIMEOUT)
        response.raise_for_status()
        news_data = response.json()
        logger.debug(f"NewsAPI response received for query='{query}', page={page}. Status: {news_data.get('status')}, Found: {news_data.get('totalResults')}")
        if news_data.get('status') != 'ok':
            logger.error(f"NewsAPI returned non-ok status: {news_data.get('code')} - {news_data.get('message')}")
            return None
        return news_data

    except httpx.HTTPStatusError as e:
        logger.error(f"NewsAPI request failed for query='{query}', page={page} with status {e.response.status_code}: {e.response.text}")
        # Handle specific errors
        if e.response.status_code == 401: # Invalid API key
             logger.error("NewsAPI API key is invalid or expired.")
        elif e.response.status_code == 429: # Rate limited
            logger.warning("NewsAPI rate limit hit. Consider delays or upgrading plan.")
        elif e.response.status_code == 426: # Upgrade required (e.g., accessing >1 month old news on free plan)
             logger.warning(f"NewsAPI requires upgrade for this request (e.g., older news): {e.response.text}")
             return None # Don't retry if it's a plan limitation
        # Let tenacity handle retries for other relevant status codes
        raise
    except httpx.RequestError as e:
        logger.error(f"Network error contacting NewsAPI for query='{query}', page={page}: {e}")
        raise # Let tenacity handle retries
    except json.JSONDecodeError as e:
        logger.error(f"Failed to decode NewsAPI JSON response for query='{query}', page={page}: {e}")
        return None # Don't retry on decode error
    except Exception as e:
        logger.error(f"Unexpected error during NewsAPI request for query='{query}', page={page}: {e}")
        return None # Don't retry unknown errors


def generate_article_id(article: Dict[str, Any]) -> str:
    """Generates a unique ID for a news article, preferably using the URL."""
    url = article.get('url')
    if url:
        # Hash the URL for a consistent ID
        return hashlib.sha256(url.encode('utf-8')).hexdigest()
    else:
        # Fallback: hash title + published time (less reliable)
        title = article.get('title', '')
        published_at = article.get('publishedAt', '')
        fallback_str = f"{title}-{published_at}-{article.get('source',{}).get('name','')}"
        return hashlib.sha256(fallback_str.encode('utf-8')).hexdigest()

def parse_datetime(datetime_str: Optional[str]) -> Optional[datetime]:
    """Safely parse various ISO 8601 formats into timezone-aware datetime objects."""
    if not datetime_str:
        return None
    try:
        dt = dateutil.parser.isoparse(datetime_str)
        # Ensure timezone awareness (assume UTC if not specified)
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError) as e:
        logger.warning(f"Could not parse datetime string '{datetime_str}': {e}")
        return None


def store_raw_news_data(articles: List[Dict[str, Any]], con: duckdb.DuckDBPyConnection):
    """Stores the raw article data in the raw_newsapi table."""
    if not articles:
        return 0

    now_ts = datetime.now(timezone.utc)
    insert_sql = """
        INSERT INTO raw_newsapi (id, fetched_at, payload)
        VALUES (?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            fetched_at = excluded.fetched_at,
            payload = excluded.payload;
    """
    data_to_insert = []
    for article in articles:
        raw_id = generate_article_id(article)
        data_to_insert.append((raw_id, now_ts, json.dumps(article)))

    if data_to_insert:
        try:
            con.executemany(insert_sql, data_to_insert)
            logger.info(f"Stored {len(data_to_insert)} raw NewsAPI articles.")
            return len(data_to_insert)
        except Exception as e:
            logger.error(f"Failed to store raw NewsAPI data: {e}")
            return 0
    return 0

def store_clean_news_data(articles: List[Dict[str, Any]], con: duckdb.DuckDBPyConnection):
    """Stores cleaned/parsed article data in the 'news_raw' table."""
    if not articles:
        return 0

    now_ts = datetime.now(timezone.utc)
    insert_sql = """
        INSERT INTO news_raw (news_id, asset_id, source_name, author, title, description, url, url_to_image, published_at, content, fetched_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT (news_id) DO UPDATE SET
            asset_id = excluded.asset_id,
            source_name = excluded.source_name,
            author = excluded.author,
            published_at = excluded.published_at,
            fetched_at = excluded.fetched_at,
            title = excluded.title,
            description = excluded.description,
            url = excluded.url,
            url_to_image = excluded.url_to_image,
            content = excluded.content;
        -- Optionally add sentiment fields if computed here
    """
    data_to_insert = []
    processed_count = 0
    for article in articles:
        news_id = generate_article_id(article)
        source_name = article.get('source', {}).get('name', 'Unknown')
        published_dt = parse_datetime(article.get('publishedAt'))
        title = article.get('title')
        description = article.get('description') # Use description field for snippet
        url = article.get('url')
        url_to_image = article.get('urlToImage') # Get urlToImage
        content = article.get('content') # NewsAPI often truncates content
        author = article.get('author') # Get author

        # Basic validation
        if not news_id or not url or not published_dt:
             logger.warning(f"Skipping article due to missing ID, URL, or invalid date: {title}")
             continue

        data_to_insert.append((
            news_id,
            None, # asset_id - to be filled later by ER if needed
            f"newsapi:{source_name}", # Prefix source for clarity
            author,
            title,
            description,
            url,
            url_to_image,
            published_dt,
            content,
            now_ts
        ))
        processed_count += 1

    if data_to_insert:
        try:
            con.executemany(insert_sql, data_to_insert)
            logger.info(f"Stored {processed_count} clean NewsAPI articles in news_raw.")
            return processed_count
        except Exception as e:
            logger.error(f"Failed to store clean NewsAPI data: {e}")
            return 0
    return 0


async def ingest_newsapi_headlines(
    query: str,
    max_articles: int = 100, # Total articles to fetch (keeping default 100 as it's max per page)
    db_path: str = config.DB_PATH, # Accept db_path, default to config
    days_back: int = 30 # Default to 30 days back to capture last month (max ~30 for free plan)
    # Removed con: duckdb.DuckDBPyConnection = None - manage connection internally based on db_path
):
    """
    High-level function to fetch recent news headlines (last 'days_back' days)
    for a query, store raw and clean data in the specified database.

    Args:
        query: The search query.
        max_articles: The maximum number of articles to fetch across all pages.
        db_path: Path to the DuckDB database file.
        days_back: How many days of history to include in the search.
    """
    if not query:
        logger.info("No query provided for NewsAPI ingestion.")
        return
    if not config.NEWSAPI_API_KEY:
        logger.error("NEWSAPI_API_KEY not set. Aborting NewsAPI ingestion.")
        return

    # Manage connection based on db_path
    con = None
    try:
        logger.debug(f"NewsAPI: Connecting to DB at {db_path}")
        con = db.get_db_connection(db_path=db_path) # Use provided db_path
    except Exception as e:
        logger.error(f"NewsAPI: Failed to connect to database at {db_path}: {e}")
        return # Cannot proceed without DB connection

    total_raw_stored = 0
    total_clean_stored = 0
    fetched_articles_count = 0
    start_time = time.time()
    page = 1
    page_size = min(MAX_PAGE_SIZE, max_articles) # Adjust page size based on max_articles

    # Define date range
    to_dt = datetime.now(timezone.utc)
    from_dt = to_dt - timedelta(days=days_back)
    from_date_str = from_dt.strftime('%Y-%m-%d')
    to_date_str = to_dt.strftime('%Y-%m-%d')
    logger.info(f"Fetching NewsAPI articles for query='{query}' from {from_date_str} to {to_date_str}")

    try:
        async with httpx.AsyncClient() as client:
            while fetched_articles_count < max_articles:
                logger.info(f"Fetching NewsAPI page {page} for query '{query}'...")
                page_data = await fetch_news_page(
                    query=query,
                    page=page,
                    page_size=page_size,
                    client=client,
                    from_date=from_date_str,
                    to_date=to_date_str
                )

                if not page_data or page_data.get('status') != 'ok' or not page_data.get('articles'):
                    logger.warning(f"No more articles found or error occurred for query '{query}' on page {page}.")
                    break # Stop pagination

                articles = page_data['articles']
                num_articles_on_page = len(articles)
                logger.info(f"Received {num_articles_on_page} articles on page {page}.")

                # Store raw data
                raw_stored = store_raw_news_data(articles, con)
                total_raw_stored += raw_stored

                # Store clean data
                clean_stored = store_clean_news_data(articles, con)
                total_clean_stored += clean_stored

                fetched_articles_count += num_articles_on_page

                # Check if we've reached the total requested or the end of results
                total_results = page_data.get('totalResults', 0)
                if fetched_articles_count >= total_results or fetched_articles_count >= max_articles:
                    logger.info("Reached max articles limit or end of results.")
                    break

                page += 1
                # Optional: Add a small delay between pages if needed for rate limits
                await asyncio.sleep(0.5)

    except Exception as e:
        logger.error(f"An unexpected error occurred during NewsAPI ingestion: {e}")
    finally:
        end_time = time.time()
        logger.info(f"NewsAPI ingestion finished for query '{query}' in {end_time - start_time:.2f}s. Fetched: {fetched_articles_count}, Stored: {total_raw_stored} raw, {total_clean_stored} clean.")
        # Close the connection managed within this function
        if con:
            db.close_db_connection(con)


if __name__ == "__main__":
    # Example usage: Fetch news about Tesla
    example_query = "Tesla OR Elon Musk"
    max_results_to_fetch = 20 # Fetch fewer for example run

    # Example requires db_path now
    db_file_path = config.DB_PATH
    # Make sure the DB schema exists first
    temp_conn = None
    try:
        temp_conn = db.get_db_connection(db_path=db_file_path)
        db.create_schema(temp_conn)
        asyncio.run(ingest_newsapi_headlines(example_query, max_articles=max_results_to_fetch, db_path=db_file_path))
    except Exception as e:
        logger.error(f"Main execution error: {e}")
    finally:
        if temp_conn:
            db.close_db_connection(temp_conn) # Close the temp connection
