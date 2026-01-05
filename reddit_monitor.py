#!/usr/bin/env python3
"""
Reddit Account Monitor
Tracks a Reddit user's posts, comments, and karma at configurable intervals.
Stores all data in SQLite database and downloads images locally.
"""

import os
import sqlite3
import requests
import time
import json
import argparse
import schedule
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).parent
DB_PATH = Path(os.environ.get("DATABASE_PATH", BASE_DIR / "reddit_data.db"))
IMAGES_DIR = BASE_DIR / "static" / "images"
USER_AGENT = os.environ.get("REDDIT_USER_AGENT", "RedditTracker/1.0 (https://github.com/yourusername/reddit-tracker)")


def init_database():
    """Initialize SQLite database with required tables."""
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Account snapshots - hourly karma/stats captures
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS account_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            post_karma INTEGER,
            comment_karma INTEGER,
            total_karma INTEGER,
            account_created DATETIME,
            is_gold BOOLEAN,
            is_mod BOOLEAN,
            has_verified_email BOOLEAN,
            raw_data TEXT
        )
    """)
    
    # Posts table - with local_image_path for downloaded images
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            post_id TEXT UNIQUE NOT NULL,
            username TEXT NOT NULL,
            subreddit TEXT,
            title TEXT,
            selftext TEXT,
            url TEXT,
            local_image_path TEXT,
            score INTEGER,
            upvote_ratio REAL,
            num_comments INTEGER,
            created_utc DATETIME,
            first_seen DATETIME DEFAULT CURRENT_TIMESTAMP,
            last_updated DATETIME DEFAULT CURRENT_TIMESTAMP,
            is_self BOOLEAN,
            over_18 BOOLEAN,
            permalink TEXT
        )
    """)
    
    # Comments table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            comment_id TEXT UNIQUE NOT NULL,
            username TEXT NOT NULL,
            subreddit TEXT,
            body TEXT,
            score INTEGER,
            created_utc DATETIME,
            first_seen DATETIME DEFAULT CURRENT_TIMESTAMP,
            last_updated DATETIME DEFAULT CURRENT_TIMESTAMP,
            parent_id TEXT,
            link_id TEXT,
            permalink TEXT
        )
    """)
    
    # Score history - track how post/comment scores change over time
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS score_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_type TEXT NOT NULL,
            item_id TEXT NOT NULL,
            score INTEGER,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Create indexes for faster queries
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_snapshots_user ON account_snapshots(username)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_snapshots_time ON account_snapshots(timestamp)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_posts_user ON posts(username)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_comments_user ON comments(username)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_score_history ON score_history(item_type, item_id)")
    
    conn.commit()
    conn.close()
    print(f"[{now()}] Database initialized at {DB_PATH}")


def now():
    """Return current timestamp string."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def download_image(url: str, post_id: str) -> str | None:
    """Download image from URL and save locally. Returns local path or None."""
    if not url or url in ['self', 'default', 'nsfw', 'spoiler']:
        return None
    
    # Check if it's an image URL
    image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp']
    is_image = any(ext in url.lower() for ext in image_extensions) or 'i.redd.it' in url or 'i.imgur' in url
    
    if not is_image:
        return None
    
    try:
        headers = {"User-Agent": USER_AGENT}
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        
        # Determine extension from content-type or URL
        content_type = resp.headers.get('content-type', '')
        if 'jpeg' in content_type or 'jpg' in content_type:
            ext = '.jpg'
        elif 'png' in content_type:
            ext = '.png'
        elif 'gif' in content_type:
            ext = '.gif'
        elif 'webp' in content_type:
            ext = '.webp'
        else:
            # Try to get from URL
            for e in image_extensions:
                if e in url.lower():
                    ext = e
                    break
            else:
                ext = '.jpg'
        
        filename = f"{post_id}{ext}"
        filepath = IMAGES_DIR / filename
        
        with open(filepath, 'wb') as f:
            f.write(resp.content)
        
        return f"images/{filename}"  # Relative path for web serving
        
    except Exception as e:
        print(f"  Could not download image: {e}")
        return None


def fetch_user_about(username: str) -> dict | None:
    """Fetch user profile data from Reddit API."""
    url = f"https://www.reddit.com/user/{username}/about.json"
    headers = {"User-Agent": USER_AGENT}
    
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        return resp.json().get("data", {})
    except requests.RequestException as e:
        print(f"[{now()}] Error fetching user about: {e}")
        return None


def fetch_user_posts(username: str, limit: int = 100) -> list:
    """Fetch user's recent posts."""
    url = f"https://www.reddit.com/user/{username}/submitted.json"
    headers = {"User-Agent": USER_AGENT}
    params = {"limit": limit, "sort": "new"}
    
    try:
        resp = requests.get(url, headers=headers, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        return [child["data"] for child in data.get("data", {}).get("children", [])]
    except requests.RequestException as e:
        print(f"[{now()}] Error fetching posts: {e}")
        return []


def fetch_user_comments(username: str, limit: int = 100) -> list:
    """Fetch user's recent comments."""
    url = f"https://www.reddit.com/user/{username}/comments.json"
    headers = {"User-Agent": USER_AGENT}
    params = {"limit": limit, "sort": "new"}
    
    try:
        resp = requests.get(url, headers=headers, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        return [child["data"] for child in data.get("data", {}).get("children", [])]
    except requests.RequestException as e:
        print(f"[{now()}] Error fetching comments: {e}")
        return []


def save_account_snapshot(username: str, data: dict):
    """Save account karma snapshot to database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT INTO account_snapshots 
        (username, post_karma, comment_karma, total_karma, account_created, 
         is_gold, is_mod, has_verified_email, raw_data)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        username,
        data.get("link_karma", 0),
        data.get("comment_karma", 0),
        data.get("total_karma", 0),
        datetime.fromtimestamp(data.get("created_utc", 0)).isoformat() if data.get("created_utc") else None,
        data.get("is_gold", False),
        data.get("is_mod", False),
        data.get("has_verified_email", False),
        json.dumps(data)
    ))
    
    conn.commit()
    conn.close()


def save_posts(username: str, posts: list):
    """Save or update posts in database, downloading images."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    for post in posts:
        post_id = post.get("id")
        created = datetime.fromtimestamp(post.get("created_utc", 0)).isoformat()
        
        # Check if post exists
        cursor.execute("SELECT id, score, local_image_path FROM posts WHERE post_id = ?", (post_id,))
        existing = cursor.fetchone()
        
        if existing:
            # Update existing post
            old_score = existing[1]
            new_score = post.get("score", 0)
            
            cursor.execute("""
                UPDATE posts SET 
                    score = ?, upvote_ratio = ?, num_comments = ?, last_updated = CURRENT_TIMESTAMP
                WHERE post_id = ?
            """, (new_score, post.get("upvote_ratio"), post.get("num_comments"), post_id))
            
            # Log score change if different
            if old_score != new_score:
                cursor.execute("""
                    INSERT INTO score_history (item_type, item_id, score)
                    VALUES ('post', ?, ?)
                """, (post_id, new_score))
        else:
            # New post - download image
            image_url = post.get("url", "")
            local_image_path = download_image(image_url, post_id)
            
            cursor.execute("""
                INSERT INTO posts 
                (post_id, username, subreddit, title, selftext, url, local_image_path, score, upvote_ratio,
                 num_comments, created_utc, is_self, over_18, permalink)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                post_id, username, post.get("subreddit"),
                post.get("title"), post.get("selftext"), image_url, local_image_path,
                post.get("score"), post.get("upvote_ratio"), post.get("num_comments"),
                created, post.get("is_self"), post.get("over_18"),
                post.get("permalink")
            ))
            
            # Initial score entry
            cursor.execute("""
                INSERT INTO score_history (item_type, item_id, score)
                VALUES ('post', ?, ?)
            """, (post_id, post.get("score", 0)))
            
            if local_image_path:
                print(f"    Downloaded image for: {post.get('title', '')[:40]}...")
    
    conn.commit()
    conn.close()


def save_comments(username: str, comments: list):
    """Save or update comments in database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    for comment in comments:
        comment_id = comment.get("id")
        created = datetime.fromtimestamp(comment.get("created_utc", 0)).isoformat()
        
        # Check if comment exists
        cursor.execute("SELECT id, score FROM comments WHERE comment_id = ?", (comment_id,))
        existing = cursor.fetchone()
        
        if existing:
            old_score = existing[1]
            new_score = comment.get("score", 0)
            
            cursor.execute("""
                UPDATE comments SET score = ?, last_updated = CURRENT_TIMESTAMP
                WHERE comment_id = ?
            """, (new_score, comment_id))
            
            if old_score != new_score:
                cursor.execute("""
                    INSERT INTO score_history (item_type, item_id, score)
                    VALUES ('comment', ?, ?)
                """, (comment_id, new_score))
        else:
            cursor.execute("""
                INSERT INTO comments 
                (comment_id, username, subreddit, body, score, created_utc, 
                 parent_id, link_id, permalink)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                comment_id, username, comment.get("subreddit"),
                comment.get("body"), comment.get("score"), created,
                comment.get("parent_id"), comment.get("link_id"),
                comment.get("permalink")
            ))
            
            cursor.execute("""
                INSERT INTO score_history (item_type, item_id, score)
                VALUES ('comment', ?, ?)
            """, (comment_id, comment.get("score", 0)))
    
    conn.commit()
    conn.close()


def monitor_user(username: str):
    """Run a single monitoring cycle for a user."""
    print(f"\n[{now()}] Monitoring u/{username}...")
    
    # Fetch and save account data
    about = fetch_user_about(username)
    if about:
        save_account_snapshot(username, about)
        print(f"  Post karma: {about.get('link_karma', 0):,}")
        print(f"  Comment karma: {about.get('comment_karma', 0):,}")
        print(f"  Total karma: {about.get('total_karma', 0):,}")
    else:
        print(f"  Failed to fetch account data")
        return
    
    time.sleep(1)  # Rate limiting
    
    # Fetch and save posts
    posts = fetch_user_posts(username)
    if posts:
        save_posts(username, posts)
        print(f"  Tracked {len(posts)} posts")
    
    time.sleep(1)
    
    # Fetch and save comments
    comments = fetch_user_comments(username)
    if comments:
        save_comments(username, comments)
        print(f"  Tracked {len(comments)} comments")
    
    print(f"[{now()}] Monitoring cycle complete")


def get_stats(username: str):
    """Display current statistics for a user."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Latest snapshot
    cursor.execute("""
        SELECT timestamp, post_karma, comment_karma, total_karma
        FROM account_snapshots WHERE username = ?
        ORDER BY timestamp DESC LIMIT 1
    """, (username,))
    snapshot = cursor.fetchone()
    
    # Karma change over last 24h
    cursor.execute("""
        SELECT total_karma FROM account_snapshots 
        WHERE username = ? AND timestamp >= datetime('now', '-24 hours')
        ORDER BY timestamp ASC LIMIT 1
    """, (username,))
    old_karma = cursor.fetchone()
    
    # Post/comment counts
    cursor.execute("SELECT COUNT(*) FROM posts WHERE username = ?", (username,))
    post_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM comments WHERE username = ?", (username,))
    comment_count = cursor.fetchone()[0]
    
    # Snapshot count
    cursor.execute("SELECT COUNT(*) FROM account_snapshots WHERE username = ?", (username,))
    snapshot_count = cursor.fetchone()[0]
    
    # Images downloaded
    cursor.execute("SELECT COUNT(*) FROM posts WHERE username = ? AND local_image_path IS NOT NULL", (username,))
    image_count = cursor.fetchone()[0]
    
    conn.close()
    
    print(f"\n=== Stats for u/{username} ===")
    if snapshot:
        print(f"Last checked: {snapshot[0]}")
        print(f"Post karma: {snapshot[1]:,}")
        print(f"Comment karma: {snapshot[2]:,}")
        print(f"Total karma: {snapshot[3]:,}")
        if old_karma:
            change = snapshot[3] - old_karma[0]
            print(f"24h karma change: {change:+,}")
    print(f"Posts tracked: {post_count}")
    print(f"Comments tracked: {comment_count}")
    print(f"Images downloaded: {image_count}")
    print(f"Total snapshots: {snapshot_count}")


def run_scheduler(username: str, interval_minutes: int = 30):
    """Run the scheduler for periodic monitoring."""
    print(f"[{now()}] Starting Reddit Tracker for u/{username}")
    print(f"[{now()}] Checking every {interval_minutes} minutes")
    print(f"[{now()}] Press Ctrl+C to stop\n")
    
    # Run immediately on start
    monitor_user(username)
    
    # Schedule periodic runs
    schedule.every(interval_minutes).minutes.do(monitor_user, username=username)
    
    try:
        while True:
            schedule.run_pending()
            time.sleep(60)
    except KeyboardInterrupt:
        print(f"\n[{now()}] Monitoring stopped")


def main():
    parser = argparse.ArgumentParser(description="Monitor a Reddit account")
    parser.add_argument("username", nargs="?", help="Reddit username to monitor (without u/)")
    parser.add_argument("--interval", "-i", type=int, default=30,
                        help="Check interval in minutes (default: 30)")
    parser.add_argument("--once", "-o", action="store_true",
                        help="Run once and exit (don't schedule)")
    parser.add_argument("--stats", "-s", action="store_true",
                        help="Show stats for user and exit")
    parser.add_argument("--init", action="store_true",
                        help="Initialize database only")
    
    args = parser.parse_args()
    
    # Initialize database
    init_database()
    
    if args.init:
        print("Database initialized.")
        return
    
    if not args.username:
        parser.print_help()
        return
    
    if args.stats:
        get_stats(args.username)
    elif args.once:
        monitor_user(args.username)
    else:
        run_scheduler(args.username, args.interval)


if __name__ == "__main__":
    main()
