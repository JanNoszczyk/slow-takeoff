# wealtharc-turbo-er/wa/ingest/reddit.py

import asyncio
import praw
import pandas as pd
from datetime import datetime, timezone
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_fixed, retry_if_exception_type
import duckdb
import json

from ..config import REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, REDDIT_USER_AGENT # Import specific variables
from ..db import get_db_connection, REDDIT_POSTS_TABLE # Import the constant

# Define table names
RAW_REDDIT_TABLE = "raw_reddit" # For raw JSON payload if needed
# REDDIT_POSTS_TABLE = "reddit_posts" # Now imported

# Reddit API Credentials from config (using imported variables)
CLIENT_ID = REDDIT_CLIENT_ID
CLIENT_SECRET = REDDIT_CLIENT_SECRET
USER_AGENT = REDDIT_USER_AGENT

# --- PRAW Client Initialization ---
def get_reddit_client():
    """Initializes and returns a PRAW Reddit client instance."""
    if not CLIENT_ID or not CLIENT_SECRET or not USER_AGENT:
        logger.error("Reddit API credentials (CLIENT_ID, CLIENT_SECRET, USER_AGENT) are not fully configured.")
        raise ValueError("Reddit API credentials not configured.")

    # Initialize PRAW in read-only mode
    reddit = praw.Reddit(
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        user_agent=USER_AGENT,
        # Optional: Add check_for_async=False if encountering issues in async context,
        # though we'll run PRAW methods in executor anyway.
    )
    reddit.read_only = True # Ensure read-only mode
    logger.info(f"PRAW Reddit client initialized (User Agent: {USER_AGENT}, Read-Only: {reddit.read_only})")
    return reddit

# --- API Fetching Functions ---

# Add retry logic for potential Reddit API issues (rate limits, temporary errors)
@retry(
    stop=stop_after_attempt(3),
    wait=wait_fixed(10), # Wait a bit between retries
    retry=retry_if_exception_type((praw.exceptions.PRAWException, ConnectionError)), # Retry PRAW errors and connection issues
    reraise=True
)
async def search_subreddit_posts(subreddit_name: str, query: str, time_filter: str = 'week', limit: int = 25) -> list[dict]:
    """
    Searches a specific subreddit for posts matching a query.

    Args:
        subreddit_name: The name of the subreddit (e.g., 'wallstreetbets', 'investing').
        query: The search query.
        time_filter: Time filter ('all', 'year', 'month', 'week', 'day', 'hour').
        limit: Maximum number of posts to return.

    Returns:
        A list of post data dictionaries or an empty list.
    """
    logger.info(f"Searching subreddit 'r/{subreddit_name}' for query: '{query}', time: {time_filter}, limit: {limit}")
    reddit = get_reddit_client() # Get client instance
    post_data_list = []

    try:
        subreddit = await asyncio.to_thread(reddit.subreddit, subreddit_name)
        # PRAW's search is a generator, run iteration in executor
        search_results = await asyncio.to_thread(
            list, # Convert generator to list within the thread
            subreddit.search(query, sort='new', time_filter=time_filter, limit=limit)
        )

        logger.success(f"Found {len(search_results)} posts in 'r/{subreddit_name}' matching query.")

        for post in search_results:
            post_dict = {
                "post_id": post.id,
                "title": post.title,
                "subreddit": subreddit_name,
                "author": str(post.author), # May be None
                "created_utc": post.created_utc,
                "score": post.score,
                "upvote_ratio": post.upvote_ratio,
                "num_comments": post.num_comments,
                "url": post.url, # Link to post
                "permalink": f"https://www.reddit.com{post.permalink}", # Full link
                "selftext": post.selftext, # Body text for self-posts
                "is_self": post.is_self,
                "stickied": post.stickied,
            }
            post_data_list.append(post_dict)

    except praw.exceptions.PRAWException as e:
        logger.error(f"Reddit API error searching 'r/{subreddit_name}': {e}")
        raise # Reraise for tenacity
    except Exception as e:
        logger.error(f"Unexpected error searching 'r/{subreddit_name}': {e}")
        # Don't retry unexpected errors

    return post_data_list

# --- Database Storage Functions ---

# Optional: Store raw JSON if needed
# async def store_raw_reddit_posts(posts: list[dict], con: duckdb.DuckDBPyConnection): ...

async def store_cleaned_reddit_posts(posts: list[dict], con: duckdb.DuckDBPyConnection):
    """Stores cleaned Reddit post data into the database."""
    if not posts:
        return

    logger.info(f"Storing {len(posts)} cleaned Reddit post records...")
    fetched_at = datetime.now(timezone.utc)
    records_to_insert = []

    for post in posts:
        created_dt = datetime.fromtimestamp(post['created_utc'], timezone.utc)

        record = (
            post['post_id'],
            post['subreddit'],
            post['title'],
            post['author'],
            created_dt,
            fetched_at,
            post['score'],
            post['num_comments'],
            post['upvote_ratio'],
            post['permalink'],
            post['selftext'] if post['is_self'] else None, # Only store selftext for self-posts
        )
        records_to_insert.append(record)

    try:
        # Use table name constant once added to db.py
        con.executemany(
            f"""
            INSERT INTO {REDDIT_POSTS_TABLE} (
                post_id, subreddit, title, author, created_utc, fetched_at, score,
                num_comments, upvote_ratio, permalink, selftext
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(post_id) DO UPDATE SET
                fetched_at = excluded.fetched_at,
                score = excluded.score,
                num_comments = excluded.num_comments,
                upvote_ratio = excluded.upvote_ratio,
                selftext = excluded.selftext;
            """,
            records_to_insert
        )
        logger.success(f"Successfully stored/updated {len(records_to_insert)} cleaned Reddit posts.")
    except Exception as e:
        logger.error(f"Error storing cleaned Reddit post data: {e}")


# --- Main Ingestion Function ---

async def ingest_reddit_search(subreddit: str, query: str, time_filter: str = 'week', limit: int = 50, con: duckdb.DuckDBPyConnection | None = None):
    """Searches a subreddit for posts and stores them."""
    if not CLIENT_ID or not CLIENT_SECRET:
        logger.error("Cannot ingest Reddit data: Credentials not fully set.")
        return

    logger.info(f"Starting Reddit ingestion for 'r/{subreddit}', query: '{query}'")
    conn_local = con or get_db_connection()

    try:
        posts_list = await search_subreddit_posts(subreddit, query, time_filter=time_filter, limit=limit)

        if posts_list:
            # Store cleaned data (add raw storage later if needed)
            await store_cleaned_reddit_posts(posts_list, con=conn_local)
            logger.success(f"Successfully processed {len(posts_list)} posts from 'r/{subreddit}'.")
        else:
            logger.info(f"No posts found or processed for query '{query}' in 'r/{subreddit}'.")

    except ValueError as ve: # Catch missing credentials error
        logger.error(f"Configuration error during Reddit ingestion: {ve}")
    except Exception as e:
        logger.exception(f"Error during Reddit ingestion pipeline for 'r/{subreddit}': {e}")
    finally:
        if not con and conn_local:
            conn_local.close()


# Example Usage
async def main():
    test_subreddit = "investing"
    test_query = "interest rates OR inflation"
    conn = get_db_connection()
    try:
        # Ensure schema exists
        from .. import db # Import here for example clarity
        db.create_schema(conn)
        await ingest_reddit_search(test_subreddit, test_query, time_filter='week', limit=20, con=conn)
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    # Requires Reddit credentials in .env
    if not CLIENT_ID or not CLIENT_SECRET:
        print("Please set REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET environment variables.")
    else:
        asyncio.run(main())
