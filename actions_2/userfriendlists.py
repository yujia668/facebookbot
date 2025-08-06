import os
import re
import json
import time
from datetime import datetime
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from bs4 import BeautifulSoup

# ───── CONFIG ─────────────────────────────
EMAIL = "scuff-shut-same@duck.com"
PASSWORD = "Man1234"
PROXY = ""  # Optional proxy: "http://user:pass@ip:port"
SESSION_DIR = "sessions"
FOLLOWERS_FILE = "data/followerlist.txt"
FRIENDS_FILE = "data/friendlist.txt"
# ───── LOGGING ────────────────────────────
def gui_log(msg):
    print(msg)

# ───── SETUP ──────────────────────────────
def ensure_dirs():
    os.makedirs("data", exist_ok=True)
    os.makedirs(SESSION_DIR, exist_ok=True)

def get_cookie_path(email):
    safe_email = re.sub(r"[^\w\.@-]", "_", email.strip())
    return os.path.join(SESSION_DIR, f"{safe_email}_cookies.json")

# ───── COOKIES ────────────────────────────
def save_cookies(driver, email):
    path = get_cookie_path(email)
    cookies = driver.get_cookies()
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"timestamp": time.time(), "cookies": cookies}, f, indent=2)
    gui_log(f"[+] Cookies saved to {path}")

def scroll_to_normal(driver, max_attempts=10, delay=1.5):
    gui_log("[🟡] Scrolling gradually to locate contact section...")
    for attempt in range(max_attempts):
        try:
            target = driver.find_element(By.CSS_SELECTOR, "div.x1iyjqo2")
            driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", target)
            gui_log("[✅] Contact section is now in view.")
            return True
        except:
            driver.execute_script("window.scrollBy(0, window.innerHeight / 2);")
            time.sleep(delay)
    gui_log("[❌] Could not bring contact section into view after scrolling.")
    return False

def scrape_and_save_list(driver, url, outfile, label):
    driver.get(url)
    time.sleep(5)
    soup = BeautifulSoup(driver.page_source, "html.parser")
    items = soup.find_all("a", href=True)
    names = [a.get_text(strip=True) for a in items if a.get_text(strip=True)]
    os.makedirs("data", exist_ok=True)
    with open(outfile, "w", encoding="utf-8") as f:
        for name in names:
            f.write(name + "\n")
    gui_log(f"[📄] {label} list saved to {outfile} ({len(names)} entries)")

def load_cookies(driver, email):
    path = get_cookie_path(email)
    if not os.path.exists(path):
        return False
    try:
        with open(path, "r", encoding="utf-8") as f:
            payload = json.load(f)
        cookies = payload.get("cookies", [])
        driver.get("https://web.facebook.com/")
        WebDriverWait(driver, 10).until(lambda d: d.execute_script("return document.readyState") == "complete")
        for cookie in cookies:
            cookie.pop("sameSite", None)
            if "expiry" in cookie:
                cookie["expiry"] = int(cookie["expiry"])
            try:
                driver.add_cookie(cookie)
            except:
                pass
        time.sleep(2)
        gui_log("[✅] Session restored via cookies.")
        return True
    except Exception as e:
        gui_log(f"[!] Failed to load cookies: {e}")
    return False

# ───── LOGIN / SESSION ────────────────────
def is_logged_in(driver):
    try:
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, "//div[@aria-label='Your profile']")))
        gui_log("[✅] Already logged in via cookies.")
        return True
    except:
        return False
def login(driver, email, password):
    gui_log("[🔐] Attempting login...")
    driver.get("https://web.facebook.com/login")
    try:
        WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.ID, "email")))
        driver.find_element(By.ID, "email").clear()
        driver.find_element(By.ID, "email").send_keys(email)
        driver.find_element(By.ID, "pass").clear()
        driver.find_element(By.ID, "pass").send_keys(password + Keys.RETURN)
        WebDriverWait(driver, 15).until(lambda d: d.execute_script("return document.readyState") == "complete")
        time.sleep(3)
        gui_log("[✅] Logged in manually.")
        return True
    except Exception as e:
        gui_log(f"[!] Login error: {e}")
    return False

# ───── DRIVER ─────────────────────────────
def create_driver(proxy_url=None):
    options = Options()
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--start-maximized")
    options.add_experimental_option("detach", True)
    if proxy_url:
        cleaned = proxy_url.replace("http://", "").replace("https://", "")
        options.add_argument(f"--proxy-server={cleaned}")
    driver = webdriver.Chrome(options=options)
    try:
        driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": "Object.defineProperty(navigator, 'webdriver', {get: () => false});"
        })
    except:
        pass
    return driver

# ───── SCROLL UTILITY ─────────────────────
def scroll_to_load_all(driver, pause=1.0, max_no_change=5, max_total_attempts=60):
    last_height = driver.execute_script("return document.body.scrollHeight")
    stable_count = 0
    attempts = 0
    while attempts < max_total_attempts and stable_count < max_no_change:
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(pause)
        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            stable_count += 1
        else:
            stable_count = 0
            last_height = new_height
        attempts += 1
    gui_log(f"[🔄] Scrolling complete (attempts={attempts}, stable_count={stable_count})")

    
def click_profile(driver):
    try:
        gui_log("[🟡] Waiting for profile button...")
        profile_button = WebDriverWait(driver, 15).until(
            EC.element_to_be_clickable((By.XPATH, "//div[@role='button' and @aria-label='Your profile']"))
        )
        profile_button.click()
        gui_log("[✅] Profile button clicked.")
        time.sleep(2)
        gui_log("[🟡] Waiting for profile link /me/")
        profile_link = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "//a[@href='/me/']"))
        )
        profile_link.click()
        gui_log("[✅] Profile page opened.")
        time.sleep(3)
        current_url = driver.current_url
        gui_log(f"[🌐] Profile URL: {current_url}")
        if "facebook.com/profile.php?id=" in current_url:
            profile_id = current_url.split("id=")[-1].split("&")[0]
            about_url = f"https://web.facebook.com/profile.php?id={profile_id}&sk=about"
        else:
            username = current_url.rstrip('/').split("/")[-1]
            about_url = f"https://web.facebook.com/{username}/about"
        gui_log(f"[➡️] Navigating to: {about_url}")
        driver.get(about_url)
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, "//span[contains(text(), 'Overview') or contains(text(), 'About')]"))
        )
        gui_log("[✅] Arrived on About page.")
        time.sleep(3)
    
        followers_link = WebDriverWait(driver, 15).until(
    EC.element_to_be_clickable((By.XPATH, "//a[contains(@href, '/followers/')]"))
)
        followers_link.click()

        gui_log(f"[❌] Failed at profile navigation: {e}")
        gui_log("[🟡] Scrolling slowly to reveal content...")
        for _ in range(5):
            driver.execute_script("window.scrollBy(0, window.innerHeight);")
            time.sleep(2)
            # Parse page with BeautifulSoup
        soup = BeautifulSoup(driver.page_source, "html.parser")

        # Followers
        followers_link = soup.find("a", href=re.compile("/followers/"))
        followers_url = "https://web.facebook.com" + followers_link["href"] if followers_link else ""
        driver.get(followers_url)


        # Save main links

        # Scrape and save followers/friends
        if followers_url:
            scrape_and_save_list(driver, followers_url, FOLLOWERS_FILE, "Followers")

    except Exception as e:
        gui_log(f"[❌] Error collecting links: {e}")
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
        click_profile(driver)
    driver.quit()

if __name__ == "__main__":
    main()
