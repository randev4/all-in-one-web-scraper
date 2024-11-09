from flask import Flask, request, jsonify
import requests
from urllib.parse import urlparse, parse_qs
from newspaper import Article
import praw
from youtube_transcript_api import YouTubeTranscriptApi
import textwrap
import configparser
from bs4 import BeautifulSoup
import lxml
import httpx

app = Flask(__name__)

# --- Configuration File Handling ---
config = configparser.ConfigParser()
config.read('secrets.ini')

REDDIT_CLIENT_ID = config.get('REDDIT', 'client_id')
REDDIT_CLIENT_SECRET = config.get('REDDIT', 'client_secret')
REDDIT_USER_AGENT = config.get('REDDIT', 'user_agent')

def get_redirected_url(url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
    }
    try:
        with httpx.Client(headers=headers, follow_redirects=True, timeout=10) as client:
            response = client.get(url)
            response.raise_for_status()
            return str(response.url)
    except httpx.RequestError as e:
        print(f"Error getting redirected URL for {url}: {e}")
        return url


def scrape_article(url):
    article = Article(url)
    try:
        article.download()
        article.parse()
        return {
            "title": article.title,
            "url": url,
            "content": article.text
        }
    except Exception as e:
        return {"error": f"Error scraping article: {e}"}


def scrape_reddit_thread(url):
    reddit = praw.Reddit(
        client_id=REDDIT_CLIENT_ID,
        client_secret=REDDIT_CLIENT_SECRET,
        user_agent=REDDIT_USER_AGENT
    )
    try:
        submission = reddit.submission(url=url)

        # Collect the title, url, and content
        title = submission.title
        url = url
        content = f"Post content: {submission.selftext}\nPosted by: {submission.author}\n"

        # Collect comments
        submission.comments.replace_more(limit=None)

        def collect_comments(comments, collected_comments):
            for comment in comments:
                comment_body = ' '.join(line.strip() for line in comment.body.split('\n') if line.strip())
                comment_body = textwrap.fill(comment_body, width=80)
                collected_comments.append(f'Comment by {comment.author}: {comment_body}\n')
                if comment.replies:
                    collect_comments(comment.replies, collected_comments)

        collected_comments = []
        collect_comments(submission.comments, collected_comments)

        # Add comments to the content
        content += '\n'.join(collected_comments)

        return {
            "title": title,
            "url": url,
            "content": content
        }

    except praw.exceptions.PRAWException as e:  # Catch Reddit-specific errors
        return {"error": f"Error scraping Reddit thread: {e}"}
    except Exception as e:  # Catch any other unexpected errors
        return {"error": f"An unexpected error occurred during Reddit scraping: {e}"}

def get_video_id(url):  # Helper function (you might already have this)
    try:
        parsed_url = urlparse(url)
        if parsed_url.netloc == 'youtu.be':
            return parsed_url.path[1:]  # Extract ID from short URL
        elif parsed_url.netloc in ('www.youtube.com', 'youtube.com'):
            query_params = parse_qs(parsed_url.query)
            if 'v' in query_params:
                return query_params['v'][0]
        return None  # Invalid URL format
    except Exception as e:
        print(f"There was an error extracting video id from the youtube url: {e}")
        return None

def fetch_youtube_transcript(video_url):
    video_id = get_video_id(video_url)
    if not video_id:
        return "Invalid YouTube URL or unable to extract video ID."

    try:
        transcript = YouTubeTranscriptApi.get_transcript(video_id)
        transcript_text = " ".join([entry['text'] for entry in transcript])  # Combine text into one string
        return transcript_text
    except Exception as e:
        return f"Error fetching transcript: {e}"

def get_youtube_title(url):  # New function to get the title using requests and BeautifulSoup
    try:
        response = requests.get(url)
        response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)
        soup = BeautifulSoup(response.content, 'html.parser')
        title = soup.find('meta', property='og:title')['content']
        return title
    except requests.exceptions.RequestException as e:
        print(f"Error getting YouTube title: {e}")
        return "Unable to retrieve title"

def get_youtube_data(url):
    title = get_youtube_title(url)
    content = fetch_youtube_transcript(url)

    if title is None or content.startswith("Error"):
        return {"error": "Error fetching YouTube data"}

    return {
        "title": title,
        "url": url,
        "content": content
    }

@app.route('/scrape', methods=['POST'])
def scrape():
    url = request.form.get('url')
    if not url:
        return jsonify({'error': 'URL is required'}), 400

    redirected_url = get_redirected_url(url)

    try:
        if "reddit.com" in redirected_url:
            scraped_data = scrape_reddit_thread(redirected_url) # Use redirected_url here
        elif "youtube.com" in redirected_url or "youtu.be" in redirected_url:
            scraped_data = get_youtube_data(redirected_url) # Use redirected_url here
        else:
            scraped_data = scrape_article(redirected_url) # Use redirected_url here

        if "error" in scraped_data:  # Check for errors from scraping functions
            return jsonify(scraped_data), 500 # Return the error

        # Extract title, url, content (Handles dict and string cases)
        title = scraped_data.get("title", "Scraped Content") # Use .get() for dicts
        content = scraped_data.get("content", "") # Default to empty string if no content

        return jsonify({'title': title, 'url': redirected_url, 'content': content.strip()})

    except Exception as e:
        return jsonify({'error': str(e)}), 500  # Handle other potential errors


if __name__ == '__main__':
    app.run(debug=True)