import os
from urllib.parse import urlparse

import requests


def is_valid_path(path: str) -> (bool, str):
    """Check if a given path is valid."""
    try:
        # Check if the path is an absolute path
        if not os.path.isabs(path):  # Verify it is an absolute path
            msg = "The path is not an absolute path."
            return False, msg

        # Check if the path exists
        if not os.path.exists(path):  # Verify the path exists
            msg = "The path does not exist."
            return False, msg

        # Check if the path is accessible
        if not os.access(path, os.R_OK):  # Check read permissions
            msg = "The path is not readable."
            return False, msg

        # The path is valid
        msg = "The path is valid."
        return True, msg
    except Exception as e:
        msg = f"Error path: {e}"
        return False, msg


def is_valid_youtube_url(url: str) -> (bool, str):
    """Check if a YouTube URL is valid."""
    try:
        # Check if the URL is valid
        parsed = urlparse(url)
        if not all([parsed.scheme, parsed.netloc]):
            msg = "The URL is not valid."
            return False, msg

        # Check if the URL is viewable
        response = requests.get(url, timeout=5)
        if not response.status_code == 200 or "Video unavailable" in response.text:
            msg = "The YouTube video is not accessible."
            return False, msg

        # The URL is valid
        msg = "The YouTube video is accessible."
        return True, msg
    except Exception as e:
        print(f"Error URL: {e}")
        return False


if __name__ == '__main__':
    # path_to_check = "C:\\SZC\\SZCGithub\\Study\\Other Skills\\Python\\Downloader\\GUI.py"
    # result = is_valid_youtube_url(path_to_check)
    # if result[0]:
    #     print(result[1])
    # else:
    #     print(result[1])

    # url_to_check = "httjdhgj.com"
    url_to_check = "https://www.youtube.com/watch?v=xkzonY4YmKE"
    result = is_valid_youtube_url(url_to_check)
    if result[0]:
        print(result[1])
    else:
        print(result[1])
