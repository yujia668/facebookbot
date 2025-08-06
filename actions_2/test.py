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
from selenium.common.exceptions import StaleElementReferenceException

EMAIL = os.getenv("FB_EMAIL", "dayroom-suing-ream@duck.com")
PASSWORD = os.getenv("FB_PASSWORD", "Man1234")
PROXY = ""  # Optional

def gui_log(msg): print(msg)

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

def login_facebook(driver, email, password):
    driver.get("https://web.facebook.com/login")
    try:
        WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.ID, 'email')))
        driver.find_element(By.ID, 'email').send_keys(email)
        driver.find_element(By.ID, 'pass').send_keys(password)
        driver.find_element(By.ID, 'pass').send_keys(Keys.RETURN)
        time.sleep(15)
        if "login" not in driver.current_url.lower():
            gui_log("[✅] Login successful.")
            return True
    except Exception as e:
        gui_log(f"[❌] Login error: {e}")
    return False

def save_cookies(driver, email):
    folder = datetime.now().strftime('%Y-%m-%d')
    os.makedirs(f"sessions/{folder}", exist_ok=True)
    path = f"sessions/{folder}/{re.sub(r'[^\w\.@-]', '_', email)}_cookies.json"
    with open(path, "w") as f:
        json.dump(driver.get_cookies(), f, indent=4)
    gui_log(f"[💾] Cookies saved: {path}")

def scroll_and_comment(driver, max_comments=5):
    try:
        WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.CSS_SELECTOR, "input[aria-label='Search Facebook']")))
        gui_log("[📌] Performing search...")
        search = driver.find_element(By.CSS_SELECTOR, "input[aria-label='Search Facebook']")
        search.send_keys("john")
        search.send_keys(Keys.ENTER)
        time.sleep(5)

        gui_log("[➡️] Clicking 'Posts' tab...")
        posts_tab = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "//a[contains(@href, '/search/posts/?q=john')]"))
        )
        posts_tab.click()
        time.sleep(5)

        gui_log("[✅] Enabling 'Recent Posts'...")
        recent_toggle = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "input[aria-label='Recent Posts'][type='checkbox']"))
        )
        if not recent_toggle.get_attribute("aria-checked") == "true":
            recent_toggle.click()
        time.sleep(5)

        gui_log("[⬇️] Scrolling to load more posts...")
        feed = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, "div[role='feed']")))
        for i in range(15):  # scroll 15 times
            driver.execute_script("arguments[0].scrollBy(0, 1000);", feed)
            time.sleep(1)

        gui_log("[🧠] Collecting comment buttons...")
        buttons = driver.execute_script("""
            return Array.from(document.querySelectorAll('span'))
              .filter(el => el.textContent.trim() === "Comment")
              .map(el => el.closest('div[role="button"]'));
        """)

        gui_log(f"[✅] Found {len(buttons)} comment buttons.")
        comment_count = 0
        for idx, btn in enumerate(buttons):
            if comment_count >= max_comments:
                break
            if not btn:
                continue
            try:
                gui_log(f"[🖱️] Clicking comment button {idx + 1}")
                driver.execute_script("arguments[0].scrollIntoView({behavior:'smooth', block:'center'});", btn)
                time.sleep(1)
                driver.execute_script("""
                    const el = arguments[0];
                    el.dispatchEvent(new MouseEvent('mouseover', { bubbles: true }));
                    el.dispatchEvent(new MouseEvent('mousedown', { bubbles: true }));
                    el.dispatchEvent(new MouseEvent('mouseup', { bubbles: true }));
                    el.click();
                """, btn)

                time.sleep(2)
                input_box = driver.find_elements(By.CSS_SELECTOR, 'div[role="textbox"][contenteditable="true"]')
                if input_box:
                    gui_log("[💬] Comment box is open. Typing message...")
                    input_box[0].send_keys("Nice post!")
                    input_box[0].send_keys(Keys.ENTER)
                    gui_log("[✅] Comment sent!")
                    comment_count += 1
                    time.sleep(3)
            except StaleElementReferenceException:
                gui_log(f"[⚠️] Stale element for button {idx + 1}. Skipping...")
                continue
            except Exception as e:
                gui_log(f"[❌] Error on button {idx + 1}: {e}")
                continue

        gui_log(f"[🏁] Done. Commented on {comment_count} posts.")
    except Exception as e:
        gui_log(f"[❌] Scroll & comment failed: {e}")

def main():
    gui_log(f"[👤] Logging in as {EMAIL} using proxy: {PROXY or 'None'}")
    driver = create_driver(PROXY)
    if login_facebook(driver, EMAIL, PASSWORD):
        save_cookies(driver, EMAIL)
        scroll_and_comment(driver, max_comments=5)
    else:
        gui_log("[❌] Exiting due to login failure.")

if __name__ == "__main__":
    main()
