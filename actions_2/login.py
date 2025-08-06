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

# ====== 🔐 HARDCODED CREDENTIALS ======
EMAIL = "scuff-shut-same@duck.com"
PASSWORD = "Man1234"
PROXY = ""  # Optional: "http://username:password@ip:port"

def gui_log(msg):
    print(msg)

def create_driver(proxy_url=None):
    options = Options()
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--start-maximized")

    if proxy_url:
        proxy_clean = proxy_url.replace("http://", "")
        options.add_argument(f"--proxy-server={proxy_clean}")

    driver = webdriver.Chrome(options=options)

    # Basic stealth: remove navigator.webdriver
    driver.execute_cdp_cmd(
        "Page.addScriptToEvaluateOnNewDocument",
        {"source": "Object.defineProperty(navigator, 'webdriver', {get: () => false});"}
    )
    return driver

def login(driver, email, password):
    driver.get("https://web.facebook.com/login")
    try:
        WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.ID, "email")))
        driver.find_element(By.ID, "email").send_keys(email)
        driver.find_element(By.ID, "pass").send_keys(password + Keys.RETURN)
        time.sleep(5)  # Let the page load

        # Check login status
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

def main():
    gui_log(f"[>] Logging in as: {EMAIL}")
    driver = create_driver(PROXY)

    if login(driver, EMAIL, PASSWORD):
        save_cookies(driver, EMAIL)

    driver.quit()

if __name__ == "__main__":
    main()
