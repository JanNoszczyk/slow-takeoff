# wealtharc-turbo-er/wa/ingest/twitter.py

import asyncio
import tweepy
import pandas as pd
from datetime import datetime, timezone, timedelta
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_fixed, retry_if_exception_type
import duckdb
import json

from ..config import TWITTER_BEARER_TOKEN # Import specific variable needed
from ..db import get_db_connection, TWEETS_TABLE, RAW_TWITTER_TABLE # Import table constants

# Define table names (now imported)
# RAW_TWITTER_TABLE = "raw_twitter" # Now imported
# TWEETS_TABLE = "tweets_raw"       # Now imported

# Use imported variable directly
BEARER_TOKEN = TWITTER_BEARER_TOKEN
# API_KEY = TWITTER_API_KEY # Example if other keys were needed
# API_SECRET = TWITTER_API_SECRET
# ACCESS_TOKEN = settings.TWITTER_ACCESS_TOKEN
# ACCESS_TOKEN_SECRET = settings.TWITTER_ACCESS_TOKEN_SECRET

# --- Tweepy Client Initialization ---
def get_tweepy_client():
    """Initializes and returns a Tweepy API v2 client."""
    if not BEARER_TOKEN:
        logger.error("TWITTER_BEARER_TOKEN is not set in the environment/config.")
        raise ValueError("Twitter Bearer Token not configured.")

    # Using bearer token for read-only access (v2 search)
    try:
        client = tweepy.Client(bearer_token=BEARER_TOKEN, wait_on_rate_limit=True)
        logger.info("Tweepy client initialized.")
        return client
    except Exception as e:
        logger.error(f"Failed to initialize Tweepy client: {e}")
        raise ValueError("Could not initialize Twitter client.") from e
    # For actions requiring user context (posting, etc.), authentication would be different:
    # client = tweepy.Client(
    #     consumer_key=API_KEY, consumer_secret=API_SECRET,
    #     access_token=ACCESS_TOKEN, access_token_secret=ACCESS_TOKEN_SECRET,
    #     wait_on_rate_limit=True
    # )
    logger.info("Tweepy client initialized.")
    return client

# --- API Fetching Functions ---

# Use tenacity for retries on common Twitter API errors (e.g., rate limits if wait_on_rate_limit fails, temporary server issues)
@retry(
    stop=stop_after_attempt(3),
    wait=wait_fixed(15), # Wait longer between retries for potential rate limits
    retry=retry_if_exception_type((tweepy.errors.TweepyException, ConnectionError)), # Add connection errors
    reraise=True
)
async def search_recent_tweets(query: str, max_results: int = 10, start_time: datetime | None = None, end_time: datetime | None = None) -> list[dict]:
    """
    Searches for recent tweets (past 7 days for standard v2 access) using Twitter API v2.

    Args:
        query: The search query (see Twitter API docs for syntax).
        max_results: Maximum number of tweets to return (10-100).
        start_time: Optional start time (UTC datetime).
        end_time: Optional end time (UTC datetime).

    Returns:
        A list of tweet data dictionaries or an empty list if error/no results.
    """
    logger.info(f"Searching recent tweets for query: '{query}', max_results: {max_results}")
    client = get_tweepy_client() # Get client instance

    tweet_data_list = []
    try:
        # tweepy's methods are synchronous, run in executor
        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(
            None,
            client.search_recent_tweets,
            query,
            max_results=max(10, min(100, max_results)), # Ensure 10 <= max_results <= 100
            start_time=start_time,
            end_time=end_time,
            tweet_fields=["created_at", "public_metrics", "author_id", "lang", "entities"], # Add desired fields
            user_fields=["username"], # Include username
            expansions=["author_id"] # Expand author info
        )

        if response.data:
            logger.success(f"Found {len(response.data)} tweets matching query.")
            users = {user.id: user for user in response.includes.get('users', [])} if response.includes else {}

            for tweet in response.data:
                author = users.get(tweet.author_id)
                tweet_dict = {
                    "tweet_id": str(tweet.id),
                    "text": tweet.text,
                    "created_at": tweet.created_at.isoformat(), # Store as ISO string
                    "author_id": str(tweet.author_id),
                    "username": author.username if author else "N/A",
                    "lang": tweet.lang,
                    "retweet_count": tweet.public_metrics.get('retweet_count', 0),
                    "reply_count": tweet.public_metrics.get('reply_count', 0),
                    "like_count": tweet.public_metrics.get('like_count', 0),
                    "quote_count": tweet.public_metrics.get('quote_count', 0),
                    "impression_count": tweet.public_metrics.get('impression_count', 0),
                    "entities": tweet.entities # Contains hashtags, mentions, urls etc.
                }
                tweet_data_list.append(tweet_dict)
        else:
            logger.info(f"No recent tweets found for query: '{query}'")

    except tweepy.errors.TweepyException as e:
        logger.error(f"Twitter API error searching tweets for '{query}': {e}")
        # Specific handling for rate limits etc. could be added here if needed
        raise # Reraise for tenacity retry
    except Exception as e:
        logger.error(f"Unexpected error searching tweets for '{query}': {e}")
        # Don't retry unexpected errors by default

    return tweet_data_list

# --- Database Storage Functions ---

async def store_raw_tweets(tweets: list[dict], con: duckdb.DuckDBPyConnection):
    """Stores raw tweet JSON payloads."""
    if not tweets:
        return

    logger.info(f"Storing {len(tweets)} raw tweet payloads...")
    fetched_at = datetime.now(timezone.utc)
    records = []
    for tweet in tweets:
        # Use tweet_id as the primary key for the raw table
        records.append((tweet['tweet_id'], fetched_at, json.dumps(tweet)))

    try:
        # Use executemany for potentially better performance
        con.executemany(
            f"""
            INSERT INTO {RAW_TWITTER_TABLE} (id, fetched_at, payload) VALUES (?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET fetched_at=excluded.fetched_at, payload=excluded.payload;
            """,
            records
        )
        logger.success(f"Successfully stored/updated {len(records)} raw tweet records.")
    except Exception as e:
        logger.error(f"Error storing raw tweet data: {e}")


async def store_cleaned_tweets(tweets: list[dict], con: duckdb.DuckDBPyConnection):
    """Stores cleaned tweet data into the tweets_raw table."""
    if not tweets:
        return

    logger.info(f"Storing {len(tweets)} cleaned tweet records...")
    fetched_at = datetime.now(timezone.utc)
    records_to_insert = []

    for tweet in tweets:
        # Convert created_at string back to datetime, ensure timezone aware
        created_dt = pd.to_datetime(tweet['created_at']).tz_convert(timezone.utc)

        # Prepare record for tweets_raw table (matching its schema)
        record = (
            tweet['tweet_id'],
            'twitter', # source
            created_dt,
            fetched_at,
            tweet['author_id'],
            tweet['username'],
            tweet['text'],
            None, # sentiment_score (placeholder)
            None  # sentiment_label (placeholder)
            # Add other fields if the tweets_raw schema is expanded
        )
        records_to_insert.append(record)

    try:
        con.executemany(
            f"""
            INSERT INTO {TWEETS_TABLE} (
                tweet_id, source, created_at, fetched_at, user_id, username, text,
                sentiment_score, sentiment_label
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(tweet_id) DO UPDATE SET
                fetched_at = excluded.fetched_at,
                user_id = excluded.user_id,
                username = excluded.username,
                text = excluded.text;
                -- Avoid updating created_at, source, sentiment on conflict
            """,
            records_to_insert
        )
        logger.success(f"Successfully stored/updated {len(records_to_insert)} cleaned tweet records in {TWEETS_TABLE}.")
    except Exception as e:
        logger.error(f"Error storing cleaned tweet data: {e}")


# --- Main Ingestion Function ---

async def ingest_twitter_search(query: str, max_results: int = 100, days_back: int = 1, con: duckdb.DuckDBPyConnection | None = None):
    """Searches recent tweets, fetches details, and stores them."""
    if not BEARER_TOKEN:
        logger.error("Cannot ingest Twitter data: TWITTER_BEARER_TOKEN not set.")
        return

    logger.info(f"Starting Twitter ingestion for query: '{query}', days_back: {days_back}")
    conn_local = con or get_db_connection()

    try:
        # Calculate start/end times
        now = datetime.now(timezone.utc)
        start_time = now - timedelta(days=days_back) if days_back > 0 else None
        # API allows searching up to 7 days back for standard access
        if start_time and (now - start_time).days > 7:
             logger.warning(f"Standard Twitter API v2 only allows searching up to 7 days back. Adjusting start time.")
             start_time = now - timedelta(days=7)

        tweets_list = await search_recent_tweets(query, max_results=max_results, start_time=start_time, end_time=now)

        if tweets_list:
            # Store both raw and cleaned data
            await store_raw_tweets(tweets_list, con=conn_local)
            await store_cleaned_tweets(tweets_list, con=conn_local)
            logger.success(f"Successfully processed {len(tweets_list)} tweets for query '{query}'.")
        else:
            logger.info(f"No tweets found or processed for query '{query}'.")

    except ValueError as ve: # Catch missing token error
        logger.error(f"Configuration error during Twitter ingestion: {ve}")
    except Exception as e:
        logger.exception(f"Error during Twitter ingestion pipeline for query '{query}': {e}")
    finally:
        if not con and conn_local:
            conn_local.close()


# Example Usage
async def main():
    test_query = '"NVIDIA stock" OR $NVDA lang:en -is:retweet' # Example financial query
    conn = get_db_connection()
    try:
        # Ensure schema exists
        from .. import db # Import here for example clarity
        db.create_schema(conn)
        await ingest_twitter_search(test_query, max_results=20, days_back=1, con=conn)
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    # Need to configure TWITTER_BEARER_TOKEN in .env for this to work
    if not BEARER_TOKEN:
        print("Please set the TWITTER_BEARER_TOKEN environment variable in your .env file.")
    else:
        asyncio.run(main())
