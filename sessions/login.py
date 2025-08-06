import os
import json
import time
import pandas as pd
import csv
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from proxies_manager import ProxyManager

import os
import time
import json
import re
import pandas as pd
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys


# Path to your account CSV
df_CSV_PATH = "data/login_details.csv"

# GUI logger placeholder
def gui_log(message): print(message)

# Load accounts
def load_accounts(csv_path: str = df_CSV_PATH):
    df = pd.read_csv(csv_path, dtype=str).fillna('')
    return df, df.to_dict(orient='records')

# Update cookies
def update_account_cookies(df, email, cookies_list, csv_path=df_CSV_PATH):
    idx = df.index[df['email'] == email]
    if not idx.empty:
        df.at[idx[0], 'cookies'] = json.dumps(cookies_list)
        df.to_csv(csv_path, index=False)
        gui_log(f"[+] Updated cookies for {email}")

# Update proxy

def update_account_proxy(df, email, proxy_url, csv_path=df_CSV_PATH):
    idx = df.index[df['email'] == email]
    if not idx.empty:
        df.at[idx[0], 'proxy'] = proxy_url
        df.to_csv(csv_path, index=False)
        gui_log(f"[+] Updated proxy for {email}: {proxy_url}")

# Create WebDriver
def create_driver(proxy_url=None):
    opts = Options()
    # Apply proxy settings
    pm = ProxyManager()
    if proxy_url:
        pm.apply_to_options(opts, proxy_url)
    else:
        choice = pm.choose_proxy()
        pm.apply_to_options(opts, choice)

    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_argument("--start-maximized")
    driver = webdriver.Chrome(options=opts)
    # Anti-detection
    driver.execute_cdp_cmd(
        "Page.addScriptToEvaluateOnNewDocument", 
        {"source": "Object.defineProperty(navigator, 'webdriver', {get: () => false});"}
    )
    return driver

# Check login state
def is_logged_in(driver, email):
    try:
        WebDriverWait(driver, 10).until(lambda d: d.execute_script("return document.readyState") == "complete")
    except:
        pass
    els = driver.find_elements(By.CSS_SELECTOR, "div[aria-label='New message'], div[aria-label='Create a post']")
    if els:
        gui_log(f"[+] Logged in: {email}")
        return True
    return False

# Cookie login
def cookie_login(driver, account):
    email = account['email']
    gui_log(f"Trying cookies for {email}")
    cookies_json = account.get('cookies','')
    if cookies_json:
        try:
            for c in json.loads(cookies_json):
                c.pop('sameSite',None)
                driver.add_cookie(c)
            gui_log(f"[+] Loaded cookies for {email}")
            driver.refresh()
            return True
        except Exception as e:
            gui_log(f"Cookie error {e}")
    return False

# Handle manual blocks: reCAPTCHA or device approval
def wait_for_manual_blocks(driver, timeout=180):
    gui_log("[!] Waiting for manual challenges (CAPTCHA or approval)...")
    start = time.time()
    while time.time() - start < timeout:
        page = driver.page_source.lower()
        if 'referer_frame' in page:
            gui_log("[!] reCAPTCHA detected, awaiting user...")
        elif 'check your notifications on another device' in page or 'waiting for approval' in page:
            gui_log("[!] Notification approval required, awaiting user...")
        else:
            gui_log("[+] No manual blocks detected.")
            return
        time.sleep(5)
    gui_log("[!] Manual challenge timeout")

# Submit two-factor authentication code
def two_factor_login(driver, account):
    email = account.get('email', '')
    gui_log(f"[>] Attempting 2FA login for {email}")
    try:
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.NAME, 'approvals_code')))
        driver.find_element(By.NAME, 'approvals_code').send_keys(account.get('2fa', ''))
        driver.find_element(By.NAME, 'checkpoint_submit_button').click()
        gui_log(f"[+] Submitted 2FA for {email}")
        wait_for_manual_blocks(driver)
        if is_logged_in(driver, email):
            gui_log(f"[+] Logged in via 2FA for {email}")
            return True
    except TimeoutException:
        gui_log(f"[!] No 2FA prompt for {email}")
    except Exception as e:
        gui_log(f"[!] 2FA error for {email}: {e}")
    return False

# Inject token into cookies for login
def token_login(driver, account):
    email = account.get('email', '')
    gui_log(f"[>] Attempting token login for {email}")
    token = account.get('token', '')
    if token:
        try:
            driver.add_cookie({'name': 'c_user', 'value': token})
            gui_log(f"[+] Injected token for {email}")
            driver.refresh()
            wait_for_manual_blocks(driver)
            if is_logged_in(driver, email):
                gui_log(f"[+] Logged in via token for {email}")
                return True
        except Exception as e:
            gui_log(f"[!] Token login error for {email}: {e}")
    else:
        gui_log(f"[!] No token available for {email}")
    return False

# Perform credential-based login
def credential_login(driver, account):
    email = account.get('email', '')
    gui_log(f"[>] Attempting credential login for {email}")
    driver.get("https://web.facebook.com/login")
    try:
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, 'login_form')))
    except TimeoutException:
        gui_log(f"[!] Login form not found for {email}")
        return False
    driver.find_element(By.ID, 'email').clear()
    driver.find_element(By.ID, 'email').send_keys(email)
    driver.find_element(By.ID, 'pass').clear()
    driver.find_element(By.ID, 'pass').send_keys(account.get('password', ''))
    driver.find_element(By.ID, 'loginbutton').click()
    time.sleep(50)
    wait_for_manual_blocks(driver)
    if is_logged_in(driver, email):
        gui_log(f"[+] Logged in via credentials for {email}")
        return True
    return False

# Save session cookies to folder and update CSV
# def save_session(driver, account, df, csv_path):
#     email = account['email']
#     folder = datetime.now().strftime('%Y-%m-%d')
#     os.makedirs(f'sessions/{folder}', exist_ok=True)
#     cookies = driver.get_cookies()
#     with open(f'sessions/{folder}/{email}_cookies.json', 'w') as f:
#         json.dump({'email': email, 'cookies': cookies, 'url': driver.current_url, 'timestamp': time.time()}, f, indent=4)
#     gui_log(f"[+] Session saved for {email}")
#     update_account_cookies(df, email, cookies, csv_path)
def login_account(account, pm: ProxyManager, proxy_url=None):
    email = account.get('email','')

    # 1) if you weren’t given one, ask ProxyManager
    if proxy_url is None:
        proxy_url = pm.get_proxy_for(email)

    # 2) launch your browser through exactly that proxy
        driver = create_driver(proxy_url=proxy_url)
        driver.get('https://web.facebook.com/')
        time.sleep(2)

        # 3) your existing cookie/two-factor/token/credential steps ...
        if cookie_login(driver, account) and is_logged_in(driver, email):
            return driver, account
        
        driver.quit()
        return None, None
    # 1) cookie
    if cookie_login(driver, account) and is_logged_in(driver, email):
        return driver, account
    # 2) two-factor
    if account.get('2fa') and two_factor_login(driver, account) and is_logged_in(driver, email):
        return driver, account
    # 3) token
    if account.get('token') and token_login(driver, account) and is_logged_in(driver, email):
        return driver, account
    # 4) credentials
    if credential_login(driver, account) and is_logged_in(driver, email):
        return driver, account
    driver.quit()
    return None, None

def main():
    csv_path = 'accounts_login.csv'
    # 1) load your CSV once
    df, accounts = load_accounts(csv_path)
    pm = ProxyManager()
    fail_count = 0

    for account in accounts:
        email = account.get('email', '').strip()
        if not email:
            gui_log('[!] Missing email, skipping.')
            continue

        # 2) per-account proxy field (may be blank)
        account_proxy = account.get("proxy") or None

        # 3) if none yet, prompt & save back
        if not account_proxy:
            print(f"\nNo proxy configured for {email}:")
            chosen = pm.choose_proxy()
            account_proxy = chosen or None

            # if they chose one, write it back into df & CSV right now
            if account_proxy:
                # find the right row index and set
                idx = df.index[df['email'] == email]
                if not idx.empty:
                    df.at[idx[0], 'proxy'] = account_proxy
                    df.to_csv(csv_path, index=False)
                    gui_log(f"[+] Saved per-account proxy for {email}: {account_proxy}")
            else:
                gui_log(f"[+] {email} will use the global proxy or direct connection")

        # 4) now build your driver with exactly that proxy_url
        driver = create_driver(proxy_url=account_proxy)
        driver.get('https://web.facebook.com/')
        time.sleep(3)

        # --- your existing login sequence below ---
        if cookie_login(driver, account):
            driver.refresh()
            if is_logged_in(driver, email):
                gui_log(f"[+] Logged in via cookies for {email}")
                save_session(driver, account, df, csv_path)
                driver.quit()
                continue
            else:
                gui_log(f"[!] Cookie login did not establish session for {email}")
            df, accounts = load_accounts()
            cookie_map = cookie_login()

            for account in accounts:
                driver, acc = login_account(account, cookie_map)
                if not driver:
                    continue
        if account.get('2fa') and two_factor_login(driver, account):
            save_session(driver, account, df, csv_path)
            driver.quit()
            continue

        if account.get('token') and token_login(driver, account):
            save_session(driver, account, df, csv_path)
            driver.quit()
            continue

        if credential_login(driver, account):
            save_session(driver, account, df, csv_path)
            fail_count = 0
        else:
            gui_log(f"[!] Login failed for {email}")
            fail_count += 1
            if fail_count >= 5:
                gui_log('[X] Too many failures, aborting.')
                break

        driver.quit()
        # Save session cookies
def save_session(driver, account, df=None, csv_path=df_CSV_PATH):
    raw_email = account['email']
    email = raw_email.strip()
    # sanitize filename
    safe_email = re.sub(r"[^\w\.@-]", "_", email)

    folder = datetime.now().strftime('%Y-%m-%d')
    dirpath = os.path.join('sessions', folder)
    os.makedirs(dirpath, exist_ok=True)

    filepath = os.path.join(dirpath, f"{safe_email}_cookies.json")
    cookies = driver.get_cookies()
    with open(filepath, 'w') as f:
        json.dump({'email': email, 'cookies': cookies, 'url': driver.current_url, 'timestamp': time.time()}, f, indent=4)
    gui_log(f"[+] Session saved for {email}")
    if df is not None:
        update_account_cookies(df, email, cookies, csv_path)


if __name__ == '__main__':
    main()
