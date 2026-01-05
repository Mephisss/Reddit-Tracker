#!/usr/bin/env python3
"""
Reddit Tracker Web Interface
Flask app to display tracked Reddit accounts with cards and analytics.
"""

import os
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from flask import Flask, render_template, jsonify, request, send_from_directory

BASE_DIR = Path(__file__).parent
DB_PATH = Path(os.environ.get("DATABASE_PATH", BASE_DIR / "reddit_data.db"))
STATIC_DIR = BASE_DIR / "static"

app = Flask(__name__, static_folder=str(STATIC_DIR), template_folder=str(BASE_DIR / "templates"))


def get_db():
    """Get database connection."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


@app.route('/')
def index():
    """Main dashboard - list all tracked users."""
    conn = get_db()
    cursor = conn.cursor()
    

    cursor.execute("""
        SELECT 
            username,
            MAX(timestamp) as last_updated,
            (SELECT total_karma FROM account_snapshots a2 
             WHERE a2.username = a1.username 
             ORDER BY timestamp DESC LIMIT 1) as total_karma,
            (SELECT post_karma FROM account_snapshots a2 
             WHERE a2.username = a1.username 
             ORDER BY timestamp DESC LIMIT 1) as post_karma,
            (SELECT comment_karma FROM account_snapshots a2 
             WHERE a2.username = a1.username 
             ORDER BY timestamp DESC LIMIT 1) as comment_karma,
            (SELECT COUNT(*) FROM posts WHERE posts.username = a1.username) as post_count,
            (SELECT COUNT(*) FROM comments WHERE comments.username = a1.username) as comment_count
        FROM account_snapshots a1
        GROUP BY username
        ORDER BY total_karma DESC
    """)
    
    users = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    return render_template('index.html', users=users)


@app.route('/user/<username>')
def user_detail(username):
    """User detail page with cards and graphs."""
    conn = get_db()
    cursor = conn.cursor()
    

    cursor.execute("""
        SELECT * FROM account_snapshots 
        WHERE username = ? 
        ORDER BY timestamp DESC LIMIT 1
    """, (username,))
    latest = cursor.fetchone()
    
    if not latest:
        return "User not found", 404
    

    cursor.execute("""
        SELECT * FROM posts 
        WHERE username = ? 
        ORDER BY created_utc DESC
    """, (username,))
    posts = [dict(row) for row in cursor.fetchall()]
 
    cursor.execute("SELECT COUNT(*) as count FROM account_snapshots WHERE username = ?", (username,))
    snapshot_count = cursor.fetchone()['count']
    
    conn.close()
    
    return render_template('user.html', 
                          user=dict(latest), 
                          posts=posts, 
                          snapshot_count=snapshot_count)


@app.route('/api/karma/<username>')
def api_karma_history(username):
    """API endpoint for karma history (for charts)."""
    conn = get_db()
    cursor = conn.cursor()
    

    from_date = request.args.get('from', None)
    to_date = request.args.get('to', None)
    
    if from_date and to_date:
 
        cursor.execute("""
            SELECT timestamp, post_karma, comment_karma, total_karma
            FROM account_snapshots 
            WHERE username = ? AND timestamp BETWEEN ? AND ?
            ORDER BY timestamp ASC
        """, (username, from_date, to_date))
    else:

        days = request.args.get('days', 30, type=float)
  
        hours = int(days * 24)
        
        cursor.execute("""
            SELECT timestamp, post_karma, comment_karma, total_karma
            FROM account_snapshots 
            WHERE username = ? AND timestamp >= datetime('now', ?)
            ORDER BY timestamp ASC
        """, (username, f'-{hours} hours'))
    
    rows = cursor.fetchall()
    conn.close()
    
    data = {
        'labels': [row['timestamp'] for row in rows],
        'post_karma': [row['post_karma'] for row in rows],
        'comment_karma': [row['comment_karma'] for row in rows],
        'total_karma': [row['total_karma'] for row in rows]
    }
    
    return jsonify(data)


@app.route('/api/posts/<username>')
def api_posts_history(username):
    """API endpoint for posts over time."""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT DATE(created_utc) as date, COUNT(*) as count
        FROM posts 
        WHERE username = ?
        GROUP BY DATE(created_utc)
        ORDER BY date ASC
    """, (username,))
    
    rows = cursor.fetchall()
    conn.close()
    
    data = {
        'labels': [row['date'] for row in rows],
        'counts': [row['count'] for row in rows]
    }
    
    return jsonify(data)


@app.route('/api/subreddits/<username>')
def api_subreddit_breakdown(username):
    """API endpoint for subreddit breakdown."""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT subreddit, COUNT(*) as count, SUM(score) as total_score
        FROM posts 
        WHERE username = ?
        GROUP BY subreddit
        ORDER BY count DESC
        LIMIT 10
    """, (username,))
    
    rows = cursor.fetchall()
    conn.close()
    
    data = {
        'labels': [row['subreddit'] for row in rows],
        'counts': [row['count'] for row in rows],
        'scores': [row['total_score'] or 0 for row in rows]
    }
    
    return jsonify(data)


@app.route('/api/score_history/<item_type>/<item_id>')
def api_score_history(item_type, item_id):
    """API endpoint for individual post/comment score history."""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT timestamp, score
        FROM score_history 
        WHERE item_type = ? AND item_id = ?
        ORDER BY timestamp ASC
    """, (item_type, item_id))
    
    rows = cursor.fetchall()
    conn.close()
    
    data = {
        'labels': [row['timestamp'] for row in rows],
        'scores': [row['score'] for row in rows]
    }
    
    return jsonify(data)


@app.route('/api/activity/<username>')
def api_activity_heatmap(username):
    """API endpoint for activity heatmap data."""
    conn = get_db()
    cursor = conn.cursor()
    

    cursor.execute("""
        SELECT 
            CAST(strftime('%w', created_utc) AS INTEGER) as day_of_week,
            CAST(strftime('%H', created_utc) AS INTEGER) as hour,
            COUNT(*) as count
        FROM posts 
        WHERE username = ?
        GROUP BY day_of_week, hour
    """, (username,))
    
    post_activity = [dict(row) for row in cursor.fetchall()]

    cursor.execute("""
        SELECT 
            CAST(strftime('%w', created_utc) AS INTEGER) as day_of_week,
            CAST(strftime('%H', created_utc) AS INTEGER) as hour,
            COUNT(*) as count
        FROM comments 
        WHERE username = ?
        GROUP BY day_of_week, hour
    """, (username,))
    
    comment_activity = [dict(row) for row in cursor.fetchall()]
    
    conn.close()
    
    return jsonify({
        'posts': post_activity,
        'comments': comment_activity
    })


@app.route('/api/karma_changes/<username>')
def api_karma_changes(username):
    """API endpoint for karma changes between snapshots."""
    conn = get_db()
    cursor = conn.cursor()
    
    days = request.args.get('days', 7, type=float)
    hours = int(days * 24)
    
    cursor.execute("""
        SELECT timestamp, total_karma,
               total_karma - LAG(total_karma) OVER (ORDER BY timestamp) as karma_change
        FROM account_snapshots 
        WHERE username = ? AND timestamp >= datetime('now', ?)
        ORDER BY timestamp ASC
    """, (username, f'-{hours} hours'))
    
    rows = cursor.fetchall()
    conn.close()
    
    data = {
        'labels': [row['timestamp'] for row in rows],
        'total_karma': [row['total_karma'] for row in rows],
        'changes': [row['karma_change'] or 0 for row in rows]
    }
    
    return jsonify(data)


@app.route('/images/<path:filename>')
def serve_image(filename):
    """Serve downloaded images."""
    return send_from_directory(STATIC_DIR / 'images', filename)


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    app.run(debug=debug, host='0.0.0.0', port=port)
