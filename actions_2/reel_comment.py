import json
import os
import re
import time
import random
import csv
from datetime import datetime
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# === 🔐 Credentials & Config ===
EMAIL = "scuff-shut-same@duck.com"
PASSWORD = "Man1234"
PROXY = ""  # Optional: "http://user:pass@host:port"

REELS_CSV = "data/reel_url.csv"
COMMENTS_CSV = "data/comment.csv"
COOKIE_DIR = "sessions"

def gui_log(msg):
    print(f"{datetime.now().strftime('%H:%M:%S')} {msg}")

def create_driver(proxy_url=None):
    options = Options()
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--start-maximized")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)

    if proxy_url:
        proxy_clean = proxy_url.replace("http://", "")
        options.add_argument(f"--proxy-server={proxy_clean}")

    driver = webdriver.Chrome(options=options)
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": "Object.defineProperty(navigator, 'webdriver', {get: () => false})"
    })
    return driver

def login(driver, email, password):
    driver.get("https://web.facebook.com/login")
    try:
        WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.ID, "email")))
        driver.find_element(By.ID, "email").send_keys(email)
        driver.find_element(By.ID, "pass").send_keys(password + Keys.RETURN)
        time.sleep(5)
        if "login" not in driver.current_url.lower():
            gui_log("[✅] Logged in successfully.")
            return True
        else:
            gui_log("[❌] Login failed or checkpoint triggered.")
    except Exception as e:
        gui_log(f"[!] Login error: {e}")
    return False
def is_logged_in(driver):
    try:
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, "//div[@aria-label='Your profile']")))
        gui_log("[✅] Already logged in via cookies.")
        return True
    except:
        return False
def save_cookies(driver, email):
    safe_email = re.sub(r"[^\w\.@-]", "_", email)
    folder = datetime.now().strftime('%Y-%m-%d')
    path = f"{COOKIE_DIR}/{folder}"
    os.makedirs(path, exist_ok=True)
    with open(f"{path}/{safe_email}_cookies.json", "w") as f:
        json.dump(driver.get_cookies(), f, indent=2)
    gui_log(f"[💾] Cookies saved for {email}")
def load_cookies(driver, email):
    safe_email = re.sub(r"[^\w\.@-]", "_", email)
    folder = datetime.now().strftime('%Y-%m-%d')
    cookie_path = f"{COOKIE_DIR}/{folder}/{safe_email}_cookies.json"
    if os.path.exists(cookie_path):
        try:
            with open(cookie_path, "r") as f:
                cookies = json.load(f)
            driver.get("https://web.facebook.com")  # Required before adding cookies
            for cookie in cookies:
                if 'sameSite' in cookie:
                    if cookie['sameSite'] == 'None':
                        cookie['sameSite'] = 'Strict'  # avoid compatibility issues
                driver.add_cookie(cookie)
            gui_log("[🍪] Cookies loaded successfully.")
            driver.refresh()
            time.sleep(3)
            return True
        except Exception as e:
            gui_log(f"[!] Failed to load cookies: {e}")
    else:
        gui_log("[ℹ️] No cookies found. Will login manually.")
    return False

def load_reel_urls(path=REELS_CSV):
    if not os.path.exists(path):
        gui_log("[❌] reel_urls.csv not found.")
        return []
    with open(path, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]

def load_comments(path=COMMENTS_CSV):
    if not os.path.exists(path):
        gui_log("[❌] comments.csv not found.")
        return []
    with open(path, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]
def comment_on_reel(driver, url, comment_text):
    try:
        gui_log(f"[→] Visiting: {url}")
        driver.get(url)
        WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        time.sleep(5)

        # Optional: Scroll down to make comment button visible
        driver.execute_script("window.scrollBy(0, 500);")
        time.sleep(2)

        # Step 1: Click the comment button
        try:
            comment_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((
                    By.XPATH,
                    '//div[@role="button" and @aria-label="Comment"]'
                ))
            )
            driver.execute_script("arguments[0].click();", comment_button)
            comment_button.click()
            driver.execute_script("arguments[0].click();", comment_button)
            gui_log("[🖱️] Clicked comment button.")
        except Exception as e:
            gui_log(f"[⚠️] Couldn't click comment button: {e}")
            return False

        # Step 2: Wait for the new comment box to load
        comment_box = None
        for i in range(20):  # Up to 20s
            try:
                comment_box = driver.find_element(
                    By.XPATH,
                    '//div[@role="textbox" and @contenteditable="true" and contains(@aria-label, "Write a comment")]'
                )
                if comment_box.is_displayed():
                    gui_log(f"[✅] Found comment box (try {i+1})")
                    break
            except:
                pass
            time.sleep(1)

        if not comment_box:
            gui_log("[❌] Comment box did not appear in time.")
            return False

        # Step 3: Type and submit comment
        try:
            comment_box.click()
            time.sleep(1)
            comment_box.send_keys(comment_text)
            time.sleep(1)
            comment_box.send_keys(Keys.RETURN)
            gui_log(f"[💬] Commented: {comment_text}")
            return True
        except Exception as e:
            gui_log(f"[❌] Failed to send comment: {e}")
            return False

    except Exception as e:
        gui_log(f"[⚠️] Unexpected error: {e}")
        return False


def main():
    gui_log(f"[>] Starting session for: {EMAIL}")
    driver = create_driver(PROXY)
    if load_cookies(driver, EMAIL):
        if not is_logged_in(driver):
            gui_log("[ℹ️] Cookies invalid or expired. Logging in again.")
            if login(driver, EMAIL, PASSWORD):
                save_cookies(driver, EMAIL)
    else:
        if login(driver, EMAIL, PASSWORD):
            save_cookies(driver, EMAIL)
    if is_logged_in(driver):

        urls = load_reel_urls()
        comments = load_comments()

        if not urls or not comments:
            gui_log("[❌] No reel URLs or comments to process.")
            driver.quit()
            return

        for i, url in enumerate(urls):
            comment = random.choice(comments)
            comment_on_reel(driver, url, comment)
            time.sleep(random.randint(6, 10))

    driver.quit()

if __name__ == "__main__":
    main()
