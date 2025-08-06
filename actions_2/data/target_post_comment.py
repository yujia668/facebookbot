import json
import os
import re
import time
import random
import csv
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains

# ====== 🔐 HARDCODED CREDENTIALS ======
EMAIL = "scuff-shut-same@duck.com"
PASSWORD = "Man1234"
PROXY = ""  # Optional: "http://username:password@ip:port"

POST_TXT = "data/post_url.csv"        # One post URL per line
COMMENT_TXT = "data/comment.txt"      # One comment per line

def gui_log(msg):
    print(f"{datetime.now().strftime('%H:%M:%S')} {msg}")

def create_driver(proxy_url=None):
    options = Options()
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--start-maximized")

    if proxy_url:
        proxy_clean = proxy_url.replace("http://", "")
        options.add_argument(f"--proxy-server={proxy_clean}")

    driver = webdriver.Chrome(options=options)
    driver.execute_cdp_cmd(
        "Page.addScriptToEvaluateOnNewDocument",
        {"source": "Object.defineProperty(navigator, 'webdriver', {get: () => false});"}
    )
    return driver

def load_cookies(driver, email):
    safe_email = re.sub(r"[^\w\.@-]", "_", email)
    folder = datetime.now().strftime('%Y-%m-%d')
    path = f"sessions/{folder}/{safe_email}_cookies.json"

    if not os.path.exists(path):
        gui_log(f"[!] No cookie file found: {path}")
        return False

    try:
        driver.get("https://web.facebook.com")
        with open(path, "r") as f:
            cookies = json.load(f)
            for cookie in cookies:
                if 'sameSite' in cookie:
                    del cookie['sameSite']
                driver.add_cookie(cookie)
        gui_log(f"[🍪] Cookies loaded from {path}")
        driver.refresh()
        time.sleep(5)
        return True
    except Exception as e:
        gui_log(f"[!] Error loading cookies: {e}")
        return False

def is_logged_in(driver):
    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, "//div[@aria-label='Your profile']"))
        )
        gui_log("[✅] Already logged in via cookies.")
        return True
    except:
        return False

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

def save_cookies(driver, email):
    safe_email = re.sub(r"[^\w\.@-]", "_", email)
    folder = datetime.now().strftime('%Y-%m-%d')
    os.makedirs(f"sessions/{folder}", exist_ok=True)
    path = f"sessions/{folder}/{safe_email}_cookies.json"
    cookies = driver.get_cookies()
    with open(path, "w") as f:
        json.dump(cookies, f, indent=2)
    gui_log(f"[+] Cookies saved to {path}")

def read_post_urls(filepath):
    if not os.path.exists(filepath):
        gui_log(f"[!] Post URL file not found: {filepath}")
        return []
    with open(filepath, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        return [row[0].strip() for row in reader if row]

def read_comments(filepath):
    if not os.path.exists(filepath):
        gui_log(f"[!] Comment file not found: {filepath}")
        return []
    with open(filepath, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]

def comment_on_target_post(driver, post_url, comment_text, timeout=10):
    try:
        gui_log(f"[→] Visiting post: {post_url}")
        driver.get(post_url)
        WebDriverWait(driver, timeout).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        time.sleep(4)

        comment_box = WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((By.XPATH, "//div[starts-with(@aria-label, 'Comment as') and @contenteditable='true']"))
        )

        driver.execute_script("arguments[0].scrollIntoView(true);", comment_box)
        comment_box.click()
        time.sleep(1)

        ActionChains(driver)\
            .move_to_element(comment_box)\
            .click()\
            .send_keys(comment_text)\
            .send_keys(Keys.RETURN)\
            .perform()

        gui_log(f"[💬] Sent comment: {comment_text}")
        time.sleep(random.randint(2, 5))
    except Exception as e:
        gui_log(f"[❌] Failed to send comment on {post_url}: {e}")

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
        post_urls = read_post_urls(POST_TXT)
        comments = read_comments(COMMENT_TXT)

        if not post_urls or not comments:
            gui_log("[!] No posts or comments to process.")
            driver.quit()
            return

        for url in post_urls:
            comment = random.choice(comments)
            comment_on_target_post(driver, url, comment)

    driver.quit()
    gui_log("[✅] Done.")

if __name__ == "__main__":
    main()
