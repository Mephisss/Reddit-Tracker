# Reddit Tracker

A self-hosted web application for monitoring Reddit accounts. Track karma changes, posts, comments, and visualize activity with beautiful charts.

![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)
![Flask](https://img.shields.io/badge/Flask-3.0+-green.svg)
![License](https://img.shields.io/badge/License-MIT-yellow.svg)

## Features

- **📊 Karma Tracking** - Monitor karma progression over time with interactive charts
- **📝 Post Archiving** - Automatically save and track all posts with local image downloads
- **💬 Comment History** - Keep records of comments and score changes
- **📈 Analytics Dashboard** - Visualize posting patterns and subreddit distribution
- **🖼️ Image Backup** - Downloads and stores post images locally
- **⏰ Scheduled Monitoring** - Configurable monitoring intervals
- **🌐 Web Interface** - Clean, responsive dark-themed UI

## Screenshots

<details>
<summary>Click to view screenshots</summary>

### Dashboard
![Dashboard](docs/screenshots/dashboard.png)

### User Detail Page
![User Detail](docs/screenshots/user-detail.png)

</details>

## Installation

### Prerequisites

- Python 3.10 or higher
- pip (Python package manager)

### Quick Start

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/reddit-tracker.git
   cd reddit-tracker
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Initialize the database**
   ```bash
   python reddit_monitor.py --init
   ```

4. **Start monitoring an account**
   ```bash
   python reddit_monitor.py USERNAME --once
   ```

5. **Launch the web interface**
   ```bash
   python app.py
   ```

6. **Open your browser** to [http://localhost:5000](http://localhost:5000)

## Usage

### Monitor Commands

```bash
# Monitor once and exit
python reddit_monitor.py USERNAME --once

# Monitor continuously (default: every 30 minutes)
python reddit_monitor.py USERNAME

# Custom monitoring interval (every 15 minutes)
python reddit_monitor.py USERNAME --interval 15

# View statistics for a user
python reddit_monitor.py USERNAME --stats

# Initialize database only
python reddit_monitor.py --init
```

### Web Interface

Start the web server:

```bash
# Development mode
python app.py

# Production (with gunicorn)
gunicorn app:app --bind 0.0.0.0:5000 --workers 2
```

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_PATH` | Path to SQLite database | `./reddit_data.db` |
| `REDDIT_USER_AGENT` | User agent for Reddit API | `RedditTracker/1.0` |
| `PORT` | Web server port | `5000` |
| `FLASK_DEBUG` | Enable debug mode | `false` |

Example:
```bash
export DATABASE_PATH=/data/reddit.db
export PORT=8080
python app.py
```

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /api/karma/<username>` | Karma history (params: `days`, `from`, `to`) |
| `GET /api/posts/<username>` | Posts by date |
| `GET /api/subreddits/<username>` | Subreddit breakdown |
| `GET /api/karma_changes/<username>` | Karma changes (params: `days`) |
| `GET /api/activity/<username>` | Activity heatmap data |
| `GET /api/score_history/<type>/<id>` | Score history for post/comment |

## Project Structure

```
reddit-tracker/
├── app.py               # Flask web application
├── reddit_monitor.py    # Reddit monitoring script
├── merge_data.py        # Database merge utility
├── requirements.txt     # Python dependencies
├── Procfile            # Heroku/Railway deployment
├── LICENSE             # MIT License
├── README.md           # This file
├── static/
│   └── images/         # Downloaded post images
└── templates/
    ├── index.html      # Dashboard template
    └── user.html       # User detail template
```

## Database Schema

### `account_snapshots`
Stores periodic karma snapshots for tracking progression.

### `posts`
Archives all posts with metadata and local image paths.

### `comments`
Stores comment history with scores.

### `score_history`
Tracks score changes over time for posts and comments.

## Deployment

### Heroku / Railway

1. Create a new app
2. Connect your GitHub repository
3. Deploy with the included `Procfile`

### Docker (Coming Soon)

```dockerfile
# Dockerfile example
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
EXPOSE 5000
CMD ["gunicorn", "app:app", "--bind", "0.0.0.0:5000"]
```

## Merging Databases

If you have multiple tracking databases, you can merge them:

```bash
# Merge source into target (modifies target)
python merge_data.py source.db target.db

# Create a new merged database
python merge_data.py source.db target.db --output merged.db
```

## Legal & Ethical Considerations

- This tool uses Reddit's public JSON API
- Respect Reddit's [API Terms of Service](https://www.redditinc.com/policies/data-api-terms)
- Only track accounts with the user's knowledge or your own accounts
- Downloaded images remain property of their original creators
- Consider data privacy regulations in your jurisdiction

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- [Flask](https://flask.palletsprojects.com/) - Web framework
- [Chart.js](https://www.chartjs.org/) - Beautiful charts
- [Tailwind CSS](https://tailwindcss.com/) - Styling
- [Space Mono](https://fonts.google.com/specimen/Space+Mono) - Font

---

**Note:** This tool is for personal use and educational purposes. Always respect user privacy and platform terms of service.
