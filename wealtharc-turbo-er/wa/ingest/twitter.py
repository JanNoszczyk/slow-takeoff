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

# --- Tweepy Client Initialization ---
def get_tweepy_client():
    """Initializes and returns a Tweepy API v2 client."""
    if not BEARER_TOKEN:
        logger.error("TWITTER_BEARER_TOKEN is not set in the environment/config.")
        raise ValueError("Twitter Bearer Token not configured.")

    try:
        client = tweepy.Client(bearer_token=BEARER_TOKEN, wait_on_rate_limit=True)
        # logger.info("Tweepy client initialized.") # Reduce verbosity
        return client
    except Exception as e:
        logger.error(f"Failed to initialize Tweepy client: {e}")
        raise ValueError("Could not initialize Twitter client.") from e

# --- API Fetching Functions ---

@retry(
    stop=stop_after_attempt(3),
    wait=wait_fixed(15),
    retry=retry_if_exception_type((tweepy.errors.TweepyException, ConnectionError)),
    reraise=True
)
async def search_recent_tweets(query: str, max_results: int = 10, start_time: datetime | None = None, end_time: datetime | None = None) -> list[dict]:
    """Searches for recent tweets (past 7 days for standard v2 access) using Twitter API v2."""
    logger.info(f"Searching recent tweets for query: '{query}', max_results: {max_results}")
    try:
        client = get_tweepy_client()
    except ValueError as e:
        logger.error(f"Cannot search tweets: {e}")
        return []

    tweet_data_list = []
    try:
        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(
            None, client.search_recent_tweets, query,
            max_results=max(10, min(100, max_results)),
            start_time=start_time, end_time=end_time,
            tweet_fields=["created_at", "public_metrics", "author_id", "lang", "entities"],
            user_fields=["username"], expansions=["author_id"]
        )

        if response.data:
            logger.success(f"Found {len(response.data)} tweets matching query.")
            users = {user.id: user for user in response.includes.get('users', [])} if response.includes else {}
            for tweet in response.data:
                author = users.get(tweet.author_id)
                tweet_dict = {
                    "tweet_id": str(tweet.id), "text": tweet.text, "created_at": tweet.created_at.isoformat(),
                    "author_id": str(tweet.author_id), "username": author.username if author else "N/A",
                    "lang": tweet.lang, "retweet_count": tweet.public_metrics.get('retweet_count', 0),
                    "reply_count": tweet.public_metrics.get('reply_count', 0), "like_count": tweet.public_metrics.get('like_count', 0),
                    "quote_count": tweet.public_metrics.get('quote_count', 0), "impression_count": tweet.public_metrics.get('impression_count', 0),
                    "entities": tweet.entities
                }
                tweet_data_list.append(tweet_dict)
        else:
            logger.info(f"No recent tweets found for query: '{query}'")

    except tweepy.errors.TweepyException as e:
        logger.error(f"Twitter API error searching tweets for '{query}': {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error searching tweets for '{query}': {e}")

    return tweet_data_list

# --- Database Storage Functions ---

async def store_raw_tweets(tweets: list[dict], db_path: str | None = None):
    """Stores raw tweet JSON payloads."""
    if not tweets: return
    logger.info(f"Storing {len(tweets)} raw tweet payloads...")
    fetched_at = datetime.now(timezone.utc)
    records = [(tweet['tweet_id'], fetched_at, json.dumps(tweet)) for tweet in tweets]

    try:
        def db_operations_in_thread(path: str | None, data: list):
            conn = None
            try:
                conn = get_db_connection(path)
                conn.executemany(
                    f"""
                    INSERT INTO {RAW_TWITTER_TABLE} (id, fetched_at, payload) VALUES (?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET fetched_at=excluded.fetched_at, payload=excluded.payload;
                    """, data
                )
                logger.success(f"Thread stored/updated {len(data)} raw tweet records.")
            except Exception as thread_e:
                logger.error(f"Error in thread storing raw tweet data: {thread_e}")
                raise
            finally:
                if conn: conn.close(); logger.debug("Thread closed raw tweets DB connection.")
        await asyncio.to_thread(db_operations_in_thread, db_path, records)
    except Exception as e:
        logger.error(f"Error storing raw tweet data: {e}"); raise


async def store_cleaned_tweets(tweets: list[dict], db_path: str | None = None):
    """Stores cleaned tweet data into the tweets table."""
    if not tweets: return
    logger.info(f"Storing {len(tweets)} cleaned tweet records...")
    fetched_at = datetime.now(timezone.utc)
    records_to_insert = []
    for tweet in tweets:
        created_dt = pd.to_datetime(tweet['created_at']).tz_convert(timezone.utc)
        record = (
            tweet['tweet_id'], 'twitter', created_dt, fetched_at, tweet['author_id'],
            tweet['username'], tweet['text'], None, None # Placeholders for sentiment
        )
        records_to_insert.append(record)

    try:
        def db_operations_in_thread(path: str | None, data: list):
            conn = None
            try:
                conn = get_db_connection(path)
                conn.executemany(
                    f"""
                    INSERT INTO {TWEETS_TABLE} (
                        tweet_id, source, created_at, fetched_at, user_id, username, text,
                        sentiment_score, sentiment_label
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(tweet_id) DO UPDATE SET
                        fetched_at = excluded.fetched_at, user_id = excluded.user_id,
                        username = excluded.username, text = excluded.text;
                    """, data
                )
                logger.success(f"Thread stored/updated {len(data)} cleaned tweet records in {TWEETS_TABLE}.")
            except Exception as thread_e:
                logger.error(f"Error in thread storing cleaned tweet data: {thread_e}")
                raise
            finally:
                if conn: conn.close(); logger.debug("Thread closed cleaned tweets DB connection.")
        await asyncio.to_thread(db_operations_in_thread, db_path, records_to_insert)
    except Exception as e:
        logger.error(f"Error storing cleaned tweet data: {e}"); raise


# --- Main Ingestion Function ---

async def ingest_twitter_search(query: str, max_results: int = 100, days_back: int = 1, db_path: str | None = None):
    """Searches recent tweets, fetches details, and stores them."""
    if not BEARER_TOKEN:
        logger.error("Cannot ingest Twitter data: TWITTER_BEARER_TOKEN not set.")
        return

    logger.info(f"Starting Twitter ingestion for query: '{query}', days_back: {days_back}")
    try:
        now = datetime.now(timezone.utc)
        start_time = now - timedelta(days=days_back) if days_back > 0 else None
        if start_time and (now - start_time).days > 7:
             logger.warning("Standard Twitter API v2 only allows searching up to 7 days back. Adjusting start time.")
             start_time = now - timedelta(days=7)

        tweets_list = await search_recent_tweets(query, max_results=max_results, start_time=start_time, end_time=now)

        if tweets_list:
            try:
                # Run storage operations sequentially but use threading internally
                await store_raw_tweets(tweets_list, db_path=db_path)
                await store_cleaned_tweets(tweets_list, db_path=db_path)
                logger.success(f"Successfully processed {len(tweets_list)} tweets for query '{query}'.")
            except Exception as store_e:
                 logger.error(f"Failed to store Twitter data for query '{query}': {store_e}", exc_info=True)
        else:
            logger.info(f"No tweets found or processed for query '{query}'.")

    except ValueError as ve:
        logger.error(f"Configuration error during Twitter ingestion: {ve}")
    except Exception as e:
        logger.exception(f"Error during Twitter ingestion pipeline for query '{query}': {e}")


# Example Usage
async def main():
    test_query = '"NVIDIA stock" OR $NVDA lang:en -is:retweet'
    test_db_path = "test_twitter.db"
    conn = None
    try:
        conn = get_db_connection(test_db_path)
        from .. import db
        db.create_schema(conn)
        conn.close(); conn = None
        await ingest_twitter_search(test_query, max_results=20, days_back=1, db_path=test_db_path)
    except Exception as e:
         logger.exception(f"Twitter example failed: {e}")
    finally:
        if conn: conn.close()
        import os
        if os.path.exists(test_db_path):
             os.remove(test_db_path); logger.info(f"Cleaned up {test_db_path}")

if __name__ == "__main__":
    if not BEARER_TOKEN:
        print("Please set the TWITTER_BEARER_TOKEN environment variable in your .env file.")
    else:
        asyncio.run(main())
