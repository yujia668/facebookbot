import json
import os
import re
import time
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import csv
from pathlib import Path

EMAIL = os.getenv("FB_EMAIL", "scuff-shut-same@duck.com")
PASSWORD = os.getenv("FB_PASSWORD", "Man1234")
PROXY = ""

def gui_log(msg):
    print(msg)

def save_profile_links(profile_url, about_url, csv_path="data/profiles.csv"):
    Path("data").mkdir(exist_ok=True)
    existing_rows = set()

    # Read existing rows first
    if os.path.exists(csv_path):
        with open(csv_path, "r", encoding="utf-8") as f:
            for line in f:
                existing_rows.add(line.strip())

    new_row = f"{profile_url},{about_url}"
    if new_row in existing_rows:
        gui_log("[⚠️] Duplicate profile link found. Skipping save.")
        return

    # Save if it's new
    with open(csv_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if os.stat(csv_path).st_size == 0:
            writer.writerow(["profile_link", "about_link"])
        writer.writerow([profile_url, about_url])
    gui_log(f"[💾] Saved links to {csv_path}")

def create_driver(proxy_url=None):
    options = Options()
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--start-maximized")
    options.add_experimental_option("detach", True)
    if proxy_url:
        proxy_clean = proxy_url.replace("http://", "")
        options.add_argument(f"--proxy-server={proxy_clean}")
    driver = webdriver.Chrome(options=options)
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": "Object.defineProperty(navigator, 'webdriver', {get: () => false});"
    })
    return driver

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
def scroll_to_contact_section(driver, max_attempts=10, delay=1.5):
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


def get_cookie_path(email):
    safe_email = re.sub(r"[^\w\.@-]", "_", email)
    folder = datetime.now().strftime('%Y-%m-%d')
    os.makedirs(f"sessions/{folder}", exist_ok=True)
    return f"sessions/{folder}/{safe_email}_cookies.json"

def save_cookies(driver, email):
    path = get_cookie_path(email)
    with open(path, "w") as f:
        json.dump(driver.get_cookies(), f, indent=2)
    gui_log(f"[+] Cookies saved to {path}")

def load_cookies(driver, email):
    path = get_cookie_path(email)
    if not os.path.exists(path):
        return False
    try:
        with open(path, "r") as f:
            cookies = json.load(f)
        driver.get("https://web.facebook.com/")
        for cookie in cookies:
            cookie.pop('sameSite', None)
            driver.add_cookie(cookie)
        driver.refresh()
        gui_log("[🍪] Loaded cookies and refreshed.")
        return True
    except Exception as e:
        gui_log(f"[!] Failed to load cookies: {e}")
        return False

def is_logged_in(driver):
    try:
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, "//div[@aria-label='Your profile']")))
        gui_log("[✅] Already logged in via cookies.")
        return True
    except:
        return False

def login(driver, email, password):
    gui_log("[🔐] Attempting manual login...")
    driver.get("https://web.facebook.com/login")
    try:
        WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.ID, "email")))
        driver.find_element(By.ID, "email").send_keys(email)
        driver.find_element(By.ID, "pass").send_keys(password + Keys.RETURN)
        time.sleep(15)
        if "login" not in driver.current_url.lower():
            gui_log("[✅] Logged in manually.")
            return True
        else:
            gui_log("[❌] Login failed.")
    except Exception as e:
        gui_log(f"[!] Login error: {e}")
    return False

def scrape_contact_info(driver):
    from bs4 import BeautifulSoup

    gui_log("[🔍] Scraping contact and basic info using BeautifulSoup...")

    scroll_to_contact_section(driver)

    time.sleep(2)
    html = driver.page_source
    soup = BeautifulSoup(html, "html.parser")

    fields = {
        "Mobile": "",
        "Email": "",
        "Birthday": "",
        "Gender": "",
        "Address": "",
        "Website": "",
    }

    for label in fields:
        try:
            label_span = soup.find("span", string=lambda t: t and t.strip().lower() == label.lower())
            if not label_span:
                gui_log(f"[⚠️] {label} label not found.")
                continue

            container_div = label_span.find_parent("div", class_=lambda c: c and ("x1y1aw1k" in c or "x1n2onr6" in c))
            if not container_div:
                gui_log(f"[⚠️] Parent div not found for {label}.")
                continue

            value_span = container_div.find("span", class_="x1lliihq")
            if value_span and value_span.text.strip() != label:
                fields[label] = value_span.text.strip()
                gui_log(f"[📄] {label}: {fields[label]}")
            else:
                gui_log(f"[⚠️] {label} value not found or matches label.")
        except Exception as e:
            gui_log(f"[❌] Error scraping {label}: {e}")

    return fields

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
        save_profile_links(current_url, about_url)
        contact_url = about_url.replace("about", "about_contact_and_basic_info")
        gui_log(f"[➡️] Navigating to Contact Info: {contact_url}")
        driver.get(contact_url)
        scroll_to_normal(driver)
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, "//span[contains(text(), 'Contact') or contains(text(), 'Mobile')]"))
        )
        gui_log("[✅] Arrived on Contact and Basic Info page.")
        time.sleep(3)
    except Exception as e:
        gui_log(f"[❌] Failed at profile navigation: {e}")
        gui_log("[🟡] Scrolling slowly to reveal content...")
        for _ in range(5):
            driver.execute_script("window.scrollBy(0, window.innerHeight);")
            time.sleep(2)
    info = scrape_contact_info(driver)
    Path("data").mkdir(exist_ok=True)
    contact_csv = "data/contact_info.csv"
    with open(contact_csv, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=info.keys())
        if f.tell() == 0:
            writer.writeheader()
        writer.writerow(info)
    gui_log(f"[💾] Contact info saved to {contact_csv}")

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
