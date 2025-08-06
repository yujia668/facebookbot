# utils.py

import random
import time
import csv
import re
from urllib.parse import urlparse, parse_qs
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

def get_random_comment(path="data/comments.csv"):
    """
    Loads a random comment from the provided CSV file.
    """
    with open(path, "r", encoding="utf-8") as file:
        reader = csv.reader(file)
        comments = [row[0] for row in reader if row]
    return random.choice(comments) if comments else ""

def scroll_to_load_posts(driver, scroll_times=5):
    """
    Scrolls down the page to load more Facebook posts in the group.
    """
    for _ in range(scroll_times):
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(random.uniform(2, 4))

def click_comment_button(driver, post_container):
    """
    Clicks the 'Leave a comment' button on a Facebook post.
    """
    try:
        comment_area = post_container.find_element(By.CSS_SELECTOR, "div[aria-label='Leave a comment']")
        comment_area.click()
        return True
    except Exception:
        return False

def type_like_human(element, text):
    """
    Types text into an input field with human-like pauses.
    """
    for char in text:
        element.send_keys(char)
        time.sleep(random.uniform(0.05, 0.2))

def submit_comment(driver, text):
    """
    Submits a comment by locating the active comment input box and simulating Enter key.
    """
    try:
        active_box = driver.switch_to.active_element
        type_like_human(active_box, text)
        time.sleep(random.uniform(0.5, 1.2))
        active_box.send_keys(Keys.ENTER)
        return True
    except Exception:
        return False

def get_post_id(post_element):
    """
    Attempts to extract a unique post ID or key from the post's href or data attributes.
    Useful to track which posts have already been commented on.
    """
    try:
        links = post_element.find_elements(By.TAG_NAME, "a")
        for link in links:
            href = link.get_attribute("href")
            if href:
                if "posts" in href:
                    return href.split("posts/")[-1].split("/")[0]
                if "permalink" in href:
                    return href.split("permalink/")[-1].split("/")[0]
                if "story_fbid=" in href:
                    return href.split("story_fbid=")[-1].split("&")[0]
                if "fbid=" in href:
                    return href.split("fbid=")[-1].split("&")[0]
                if "reel/" in href:
                    return href.split("reel/")[-1].split("/")[0]
    except Exception:
        return None
from urllib.parse import urlparse, parse_qs
import logging

logger = logging.getLogger(__name__)


def get_post_id_from_url(driver):
    """
    Extracts the Facebook post ID from the current browser URL.

    Facebook URLs can have different formats, such as:
    - https://www.facebook.com/groups/<group_id>/posts/<post_id>/
    - https://www.facebook.com/groups/<group_id>/permalink/<post_id>/
    - https://www.facebook.com/story.php?story_fbid=<post_id>&id=<group_id>
    - https://www.facebook.com/permalink.php?story_fbid=<post_id>&id=<group_id>
    - https://www.facebook.com/groups/<group_id>?view=permalink&id=<post_id>

    Returns:
        post_id (str) or None if not found
    """
    try:
        url = driver.current_url

        # Pattern 1: /posts/<post_id>
        if "posts/" in url:
            post_id = url.split("posts/")[1].split("/")[0]
            return post_id

        # Pattern 2: /permalink/<post_id>
        elif "permalink/" in url:
            post_id = url.split("permalink/")[1].split("/")[0]
            return post_id

        # Pattern 3: story_fbid=<post_id>
        elif "story_fbid=" in url:
            parsed_url = urlparse(url)
            query_params = parse_qs(parsed_url.query)
            post_id = query_params.get("story_fbid", [None])[0]
            return post_id

        # Pattern 4: fbid=<post_id>
        elif "fbid=" in url:
            parsed_url = urlparse(url)
            query_params = parse_qs(parsed_url.query)
            post_id = query_params.get("fbid", [None])[0]
            return post_id

        # Pattern 5: view=permalink&id=<post_id>
        elif "view=permalink" in url and "id=" in url:
            parsed_url = urlparse(url)
            query_params = parse_qs(parsed_url.query)
            post_id = query_params.get("id", [None])[0]
            return post_id

        else:
            logger.warning("[!] Could not recognize post ID pattern in URL.")
            return None

    except Exception as e:
        logger.error(f"[X] Failed to extract post ID from URL: {e}")
        return None
# utils.py
from urllib.parse import urlparse, parse_qs

def get_post_id_from_url(driver):
    """
    Fallback: Extract post ID from Facebook post URL.
    """
    try:
        url = driver.current_url

        if "posts/" in url:
            return url.split("posts/")[1].split("/")[0]
        elif "permalink/" in url:
            return url.split("permalink/")[1].split("/")[0]
        elif "story_fbid=" in url:
            return parse_qs(urlparse(url).query).get("story_fbid", [None])[0]
        elif "fbid=" in url:
            return parse_qs(urlparse(url).query).get("fbid", [None])[0]
        elif "view=permalink" in url and "id=" in url:
            return parse_qs(urlparse(url).query).get("id", [None])[0]
    except Exception as e:
        logger.warning(f"[!] URL fallback post ID extraction failed: {e}")
    return None

import random
import time
import os
import re
import csv

from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException, NoSuchElementException, ElementClickInterceptedException
)

# Get a random comment from a CSV file
def get_random_comment(file_path="data/comments.csv"):
    if not os.path.exists(file_path):
        print(f"[!] Comment file not found: {file_path}")
        return "Nice post!"

    with open(file_path, encoding="utf-8") as f:
        reader = csv.reader(f)
        comments = [row[0] for row in reader if row]
        return random.choice(comments) if comments else "Great!"

# Scroll the page to load posts
def scroll_to_load_posts(driver, scroll_pause=2, scroll_count=3):
    for _ in range(scroll_count):
        driver.execute_script("window.scrollBy(0, window.innerHeight);")
        time.sleep(scroll_pause)

# Simulate human typing in comment box
def type_like_human(element, text, delay_range=(0.05, 0.2)):
    for char in text:
        element.send_keys(char)
        time.sleep(random.uniform(*delay_range))

# Submit comment
def submit_comment(comment_box):
    comment_box.send_keys(Keys.ENTER)

# Click the comment button for a post
def click_comment_button(driver):
    try:
        comment_btn = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, 'div[aria-label="Leave a comment"]'))
        )
        comment_btn.click()
        return True
    except TimeoutException:
        print("[!] Comment button not found.")
        return False

# Get post ID from URL as fallback
def get_post_id_from_url(driver):
    url = driver.current_url
    match = re.search(r"posts/(\d+)|permalink/(\d+)|story_fbid=(\d+)", url)
    if match:
        return next(group for group in match.groups() if group)
    return None

# Get post ID from the post's DOM (div[id^='_r_...'])
def get_post_id_from_dom(driver):
    try:
        post_elements = driver.find_elements(By.XPATH, '//div[@data-ad-preview="message"]')
        for post in post_elements:
            post_id = post.get_attribute("id")
            if post_id and "_r_" in post_id:
                return post_id.strip()
        return None
    except NoSuchElementException:
        print("[!] No post ID element found in DOM.")
        return None

def get_post_id_from_url(driver):
    """
    Extracts Facebook post ID from the current browser URL.
    Useful when you're on a direct post page (after driver.get).

    Returns:
        str or None: Extracted post ID if found, otherwise None.
    """
    url = driver.current_url
    patterns = [
        r"/posts/(\d+)",
        r"/permalink/(\d+)",
        r"story_fbid=(\d+)",
        r"/videos/(\d+)",
        r"fbid=(\d+)",
        r"/photo.php\?fbid=(\d+)",
        r"/reel/(\d+)",
    ]

    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)

    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    for key in ['fbid', 'story_fbid']:
        if key in query:
            return query[key][0]

    return None
