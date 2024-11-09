import requests

def get_redirected_url(url):
    """
    Retrieves the final redirected URL after following all redirects.

    Args:
        url: The initial URL to follow.

    Returns:
        The final redirected URL as a string, or the original URL if an error occurs 
        or if there are no redirects.
    """
    try:
        response = requests.get(url, allow_redirects=True, timeout=5)
        response.raise_for_status()  # Raise an exception for bad status codes (4xx or 5xx)
        return response.url
    except requests.exceptions.RequestException as e:
        print(f"Error getting redirected URL for {url}: {e}")
        return url  # Return the original URL on error

if __name__ == "__main__":
    input_url = input("Enter the URL: ")  # Get URL from user input
    redirected_url = get_redirected_url(input_url)
    print(f"Redirected URL: {redirected_url}")