// this is the node.js version of the python script

const axios = require('axios');
const { URL } = require('url');
const { parse } = require('querystring');
const clipboardy = require('clipboardy');
const fs = require('fs');
const { JSDOM } = require('jsdom');
const snoowrap = require('snoowrap');
const YouTubeTranscript = require('youtube-transcript');
const textwrap = require('textwrap');
const ini = require('ini');

// --- Configuration File Handling ---
const config = ini.parse(fs.readFileSync('secrets.ini', 'utf-8'));

if (!config.REDDIT || !config.REDDIT.client_id || !config.REDDIT.client_secret || !config.REDDIT.user_agent) {
    console.error("Error reading Reddit credentials from secrets.ini. Please check your configuration file.");
    process.exit(1);
}

const reddit = new snoowrap({
    userAgent: config.REDDIT.user_agent,
    clientId: config.REDDIT.client_id,
    clientSecret: config.REDDIT.client_secret,
});


async function getRedirectedUrl(url) {
    try {
        const response = await axios.get(url, { maxRedirects: 5, timeout: 5000 });
        return response.request.res.responseUrl; // Get the final redirected URL
    } catch (error) {
        console.error(`Error getting redirected URL: ${error}`);
        return url;
    }
}

// Function to extract article content using Cheerio (replace Newspaper3k)
async function scrapeArticle(url) {
    try {
      const response = await axios.get(url);
      const dom = new JSDOM(response.data);
      const { document } = dom.window;
  
      const title = document.querySelector('title')?.textContent || 'Untitled Article';
      const articleText = [...document.querySelectorAll('p')] // Select all <p> elements (adjust selectors as needed)
        .map(p => p.textContent)
        .join('\n\n'); 
  
      return `Title: ${title}\nURL: ${url}\nContent:\n${articleText}`;
    } catch (error) {
      return `Error scraping article: ${error}`;
    }
  }

async function scrapeRedditThread(url) {
    try {
        const submission = await reddit.submission(url);
        let content = `Title: ${submission.title}\nURL: ${url}\nContent:\n`;
        content += `Post content: ${submission.selftext}\n`;
        content += `Posted by: ${submission.author.name}\n`; // Use author.name

        const comments = await submission.expandReplies({ limit: Infinity, depth: Infinity });

        function printComments(comments, level = 0) {
            comments.forEach(comment => {
                const commentBodyWrapped = textwrap.fill(comment.body, { width: 80 });
                content += '  '.repeat(level) + `Comment by ${comment.author?.name || '[deleted]'}: ${commentBodyWrapped}\n`; // Handle deleted comments
                if (comment.replies && comment.replies.length > 0) {
                    printComments(comment.replies, level + 1);
                }
            });
        }

        printComments(comments);
        return content;
    } catch (error) {
        return `Error scraping Reddit thread: ${error}`;
    }
}


function getVideoId(url) {
    try {
        const parsedUrl = new URL(url);
        if (parsedUrl.hostname === 'youtu.be') {
            return parsedUrl.pathname.slice(1);
        } else if (parsedUrl.hostname === 'www.youtube.com' || parsedUrl.hostname === 'youtube.com') {
            const queryParams = parse(parsedUrl.search.substring(1));
            if (queryParams.v) {
                return queryParams.v;
            }
        }
        return null;
    } catch (error) {
        console.error(`Error extracting video ID: ${error}`);
        return null;
    }
}


async function fetchYoutubeTranscript(videoUrl) {
    const videoId = getVideoId(videoUrl);
    if (!videoId) {
        return "Invalid YouTube URL or unable to extract video ID.";
    }

    try {
      const transcript = await YouTubeTranscript.fetchTranscript(videoId, {
        lang: 'en', // Specify English or any other supported language
      });
      const transcriptText = transcript.map(entry => entry.text).join(' '); // Join transcript parts
      return transcriptText;
    } catch (error) {
      return `Error fetching transcript: ${error}`; 
    }
}



async function getYoutubeTitle(url) {
  try {
      const response = await axios.get(url);
      const dom = new JSDOM(response.data);
      const title = dom.window.document.querySelector('meta[property="og:title"]')?.content;
      return title;
  } catch (error) {
      console.error(`Error getting YouTube title: ${error}`);
      return null;
  }
}


async function scrapeYoutubeTranscript(url) {
    const transcript = await fetchYoutubeTranscript(url);
    const title = await getYoutubeTitle(url);

    if (title) {
        if (transcript.startsWith("Error fetching transcript")) {
            return transcript; 
        }
        return `Title: ${title}\nURL: ${url}\nContent:\n${transcript}`;
    } else {
        return `Error: Could not retrieve YouTube video title from ${url}`;
    }
}




async function main() {
    const url = clipboardy.readSync();
    console.log(`Fetched URL from clipboard: ${url}`);

    const redirectedUrl = await getRedirectedUrl(url);


    let content;
    if (redirectedUrl.includes("reddit.com")) {
      content = await scrapeRedditThread(redirectedUrl);
    } else if (redirectedUrl.includes("youtube.com") || redirectedUrl.includes("youtu.be")) {
      content = await scrapeYoutubeTranscript(redirectedUrl);
    } else {
      content = await scrapeArticle(redirectedUrl); // Use the new scrapeArticle function
    }

    const title = content.split('\n')[0].replace("Title: ", "").trim() || "output";
    const filename = "output.txt";
    fs.writeFileSync(filename, content, 'utf-8');
    console.log(`Content saved to ${filename}`);

}


main().catch(error => {
    console.error(`An error occurred: ${error}`);
});