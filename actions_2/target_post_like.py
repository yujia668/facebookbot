import json
import os
import re
import time
import random
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

GROUP_LINKS_CSV = "data/group_link.csv"
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
                if 'sameSite' in cookie and cookie['sameSite'] == 'None':
                    cookie['sameSite'] = 'Strict'
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

def load_group_links(path=GROUP_LINKS_CSV):
    if not os.path.exists(path):
        gui_log("[❌] group_link.csv not found.")
        return []
    with open(path, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]

def like_post(driver, url):
    try:
        gui_log(f"[→] Visiting: {url}")
        driver.get(url)
        WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        time.sleep(5)

        # Scroll down to help render button
        driver.execute_script("window.scrollBy(0, 400);")
        time.sleep(2)

        # Find and click the Like button
        try:
            like_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, '//div[@role="button" and @aria-label="Like"]'))
            )
            driver.execute_script("arguments[0].click();", like_button)
            gui_log("[👍] Post liked successfully.")
            return True
        except Exception as e:
            gui_log(f"[❌] Failed to click Like button: {e}")
            return False

    except Exception as e:
        gui_log(f"[⚠️] Unexpected error while liking post: {e}")
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
        urls = load_group_links()
        if not urls:
            gui_log("[❌] No post URLs to process.")
            driver.quit()
            return

        for i, url in enumerate(urls):
            like_post(driver, url)
            time.sleep(random.randint(5, 8))

    driver.quit()

if __name__ == "__main__":
    main()
