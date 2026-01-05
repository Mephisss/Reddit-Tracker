#!/usr/bin/env python3
"""
Merge two Reddit Tracker databases into one.

Usage:
    python merge_data.py source.db target.db
    python merge_data.py db1.db db2.db --output merged.db
"""

import sqlite3
import argparse
from pathlib import Path


def merge_databases(source_path: str, target_path: str, output_path: str = None):
    """
    Merge source database into target database.
    If output_path is provided, creates a new merged database.
    Otherwise, merges into target in-place.
    """
    
    source_path = Path(source_path)
    target_path = Path(target_path)
    
    if not source_path.exists():
        print(f"Error: Source database not found: {source_path}")
        return False
    
    if not target_path.exists():
        print(f"Error: Target database not found: {target_path}")
        return False
    
    # If output specified, copy target to output first
    if output_path:
        output_path = Path(output_path)
        import shutil
        shutil.copy(target_path, output_path)
        target_path = output_path
        print(f"Created output database: {output_path}")
    
    # Connect to both databases
    source_conn = sqlite3.connect(source_path)
    target_conn = sqlite3.connect(target_path)
    
    source_conn.row_factory = sqlite3.Row
    target_conn.row_factory = sqlite3.Row
    
    source_cur = source_conn.cursor()
    target_cur = target_conn.cursor()
    
    stats = {
        "account_snapshots": {"added": 0, "skipped": 0},
        "posts": {"added": 0, "updated": 0, "skipped": 0},
        "comments": {"added": 0, "updated": 0, "skipped": 0},
        "score_history": {"added": 0, "skipped": 0},
    }
    

    print("\nMerging account_snapshots...")
    source_cur.execute("SELECT * FROM account_snapshots")
    for row in source_cur.fetchall():
        target_cur.execute(
            "SELECT id FROM account_snapshots WHERE username = ? AND timestamp = ?",
            (row["username"], row["timestamp"])
        )
        if not target_cur.fetchone():
            target_cur.execute("""
                INSERT INTO account_snapshots 
                (username, timestamp, post_karma, comment_karma, total_karma, 
                 account_created, is_gold, is_mod, has_verified_email, raw_data)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                row["username"], row["timestamp"], row["post_karma"], 
                row["comment_karma"], row["total_karma"], row["account_created"],
                row["is_gold"], row["is_mod"], row["has_verified_email"], row["raw_data"]
            ))
            stats["account_snapshots"]["added"] += 1
        else:
            stats["account_snapshots"]["skipped"] += 1

    print("Merging posts...")
    source_cur.execute("SELECT * FROM posts")
    for row in source_cur.fetchall():
        target_cur.execute("SELECT id, last_updated FROM posts WHERE post_id = ?", (row["post_id"],))
        existing = target_cur.fetchone()
        
        if not existing:
            target_cur.execute("""
                INSERT INTO posts 
                (post_id, username, subreddit, title, selftext, url, local_image_path,
                 score, upvote_ratio, num_comments, created_utc, first_seen, 
                 last_updated, is_self, over_18, permalink)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                row["post_id"], row["username"], row["subreddit"], row["title"],
                row["selftext"], row["url"], row["local_image_path"], row["score"],
                row["upvote_ratio"], row["num_comments"], row["created_utc"],
                row["first_seen"], row["last_updated"], row["is_self"], 
                row["over_18"], row["permalink"]
            ))
            stats["posts"]["added"] += 1
        elif row["last_updated"] and existing["last_updated"]:

            if row["last_updated"] > existing["last_updated"]:
                target_cur.execute("""
                    UPDATE posts SET 
                        score = ?, upvote_ratio = ?, num_comments = ?, last_updated = ?
                    WHERE post_id = ?
                """, (row["score"], row["upvote_ratio"], row["num_comments"], 
                      row["last_updated"], row["post_id"]))
                stats["posts"]["updated"] += 1
            else:
                stats["posts"]["skipped"] += 1
        else:
            stats["posts"]["skipped"] += 1
    

    print("Merging comments...")
    source_cur.execute("SELECT * FROM comments")
    for row in source_cur.fetchall():
        target_cur.execute("SELECT id, last_updated FROM comments WHERE comment_id = ?", (row["comment_id"],))
        existing = target_cur.fetchone()
        
        if not existing:
            target_cur.execute("""
                INSERT INTO comments 
                (comment_id, username, subreddit, body, score, created_utc,
                 first_seen, last_updated, parent_id, link_id, permalink)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                row["comment_id"], row["username"], row["subreddit"], row["body"],
                row["score"], row["created_utc"], row["first_seen"], 
                row["last_updated"], row["parent_id"], row["link_id"], row["permalink"]
            ))
            stats["comments"]["added"] += 1
        elif row["last_updated"] and existing["last_updated"]:
            if row["last_updated"] > existing["last_updated"]:
                target_cur.execute("""
                    UPDATE comments SET score = ?, last_updated = ?
                    WHERE comment_id = ?
                """, (row["score"], row["last_updated"], row["comment_id"]))
                stats["comments"]["updated"] += 1
            else:
                stats["comments"]["skipped"] += 1
        else:
            stats["comments"]["skipped"] += 1
    

    print("Merging score_history...")
    source_cur.execute("SELECT * FROM score_history")
    for row in source_cur.fetchall():
        target_cur.execute(
            "SELECT id FROM score_history WHERE item_type = ? AND item_id = ? AND timestamp = ?",
            (row["item_type"], row["item_id"], row["timestamp"])
        )
        if not target_cur.fetchone():
            target_cur.execute("""
                INSERT INTO score_history (item_type, item_id, score, timestamp)
                VALUES (?, ?, ?, ?)
            """, (row["item_type"], row["item_id"], row["score"], row["timestamp"]))
            stats["score_history"]["added"] += 1
        else:
            stats["score_history"]["skipped"] += 1
    

    target_conn.commit()
    source_conn.close()
    target_conn.close()
    

    print("\n" + "=" * 50)
    print("MERGE COMPLETE")
    print("=" * 50)
    for table, counts in stats.items():
        parts = [f"{k}: {v}" for k, v in counts.items() if v > 0]
        if parts:
            print(f"{table}: {', '.join(parts)}")
    
    print(f"\nMerged database: {target_path}")
    return True


def main():
    parser = argparse.ArgumentParser(description="Merge two Reddit Tracker databases")
    parser.add_argument("source", help="Source database to merge from")
    parser.add_argument("target", help="Target database to merge into")
    parser.add_argument("--output", "-o", help="Output to new file instead of modifying target")
    
    args = parser.parse_args()
    
    merge_databases(args.source, args.target, args.output)


if __name__ == "__main__":
    main()
