import requests
from urllib.parse import urlparse, parse_qs
import pyperclip
import re
from newspaper import Article
import praw
from youtube_transcript_api import YouTubeTranscriptApi
import os
import io
import sys
import textwrap
import configparser
from bs4 import BeautifulSoup 

# --- Configuration File Handling ---
config = configparser.ConfigParser()
config.read('secrets.ini')

try:
    REDDIT_CLIENT_ID = config['REDDIT']['client_id']
    REDDIT_CLIENT_SECRET = config['REDDIT']['client_secret']
    REDDIT_USER_AGENT = config['REDDIT']['user_agent']
except KeyError as e:
    print(f"Error reading Reddit credentials from secrets.ini: {e}. Please check your configuration file.")
    exit(1)

def get_redirected_url(url):
    try:
        response = requests.get(url, allow_redirects=True, timeout=5)
        return response.url
    except requests.exceptions.RequestException as e:
        print(f"Error getting redirected URL: {e}")
        return url

def scrape_article(url):
    article = Article(url)
    try:
        article.download()
        article.parse()
        return f"Title: {article.title}\nURL: {url}\nContent:\n{article.text}"
    except Exception as e:
        return f"Error scraping article: {e}"

def scrape_reddit_thread(url):
    reddit = praw.Reddit(
        client_id=REDDIT_CLIENT_ID, 
        client_secret=REDDIT_CLIENT_SECRET,
        user_agent=REDDIT_USER_AGENT
    )
    try:
        submission = reddit.submission(url=url)
        buffer = io.StringIO()
        sys.stdout = buffer

        print(f"Title: {submission.title}\nURL: {url}\nContent:\n")
        print(f"Post content: {submission.selftext}\n")
        print(f"Posted by: {submission.author}\n")

        submission.comments.replace_more(limit=None)

        def print_comments(comments, level=0):
            for comment in comments:
                comment_body = ' '.join(line.strip() for line in comment.body.split('\n') if line.strip())
                comment_body = textwrap.fill(comment_body, width=80)
                print('  ' * level + f'Comment by {comment.author}: {comment_body}\n')
                if comment.replies:
                    print_comments(comment.replies, level + 1)

        print_comments(submission.comments)

        sys.stdout = sys.__stdout__
        return buffer.getvalue()
    except Exception as e:
        return f"Error scraping Reddit thread: {e}"

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
        return None # returns nothing when failing
    
def scrape_youtube_transcript(url):
    transcript = fetch_youtube_transcript(url)

    # Get title using the new get_youtube_title function
    title = get_youtube_title(url)

    if title: # checks if get_youtube_title was successful, if it was proceed
        if "Error fetching transcript" in transcript:
             return transcript # Return the error message from fetch_youtube_transcript
        return f"Title: {title}\nURL: {url}\nContent:\n{transcript}"

    else: # failing to get the title, will return error message below
        return f"Error: Could not retrieve YouTube video title from {url}"

def main():
    # Get URL from clipboard
    url = pyperclip.paste()
    print(f"Fetched URL from clipboard: {url}")
    
    redirected_url = get_redirected_url(url)

    if "reddit.com" in redirected_url:
        content = scrape_reddit_thread(redirected_url)
    elif "youtube.com" in redirected_url or "youtu.be" in redirected_url:
        content = scrape_youtube_transcript(redirected_url)
    else:
        content = scrape_article(redirected_url)

    # Save to text file
    title = content.split('\n')[0].replace("Title: ", "").strip() or "output"
    filename = "output.txt"
    
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(content)

    print(f"Content saved to {filename}")

if __name__ == "__main__":
    main()
