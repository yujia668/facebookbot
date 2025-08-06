import os
import json
import time
import re
import logging
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

from sessions.proxies_manager import ProxyManager
# ─── Setup logging ────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format='[%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler()
])
# silence overly chatty libs
for lib in ("selenium", "urllib3", "google"):
    logging.getLogger(lib).setLevel(logging.WARNING)
logger = logging.getLogger(__name__)
# Path to your account JSON
# ─── Account JSON ─────────────────────────────────────────────────────────────
ACCOUNTS_JSON = "data/fb_account_details.json"

def load_accounts(path=ACCOUNTS_JSON):
    if not os.path.exists(path):
        logger.error(f"No account file at {path}")
        return []
    with open(path, 'r', encoding='utf-8') as f:
        try:
            accts = json.load(f)
            if isinstance(accts, list):
                return accts
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse {path}: {e}")
    return []

def _save_accounts(accounts, path=ACCOUNTS_JSON):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(accounts, f, indent=2)
    logger.info(f"Saved {len(accounts)} accounts to {path}")

def update_account_field(email, field, value, path=ACCOUNTS_JSON):
    accounts = load_accounts(path)
    updated = False
    for acct in accounts:
        if acct.get('email','').strip().lower() == email.strip().lower():
            acct[field] = value
            updated = True
            break
    if updated:
        _save_accounts(accounts, path)
    else:
        logger.warning(f"No account found with email {email}")


def create_driver(proxy_url=None):
    chrome_opts = Options()

    # ─── 1) Anti-bot / stealth tweaks ─────────────────────────────────────────
    chrome_opts.add_argument("--disable-blink-features=AutomationControlled")
    chrome_opts.add_argument("--start-maximized")

    # ─── 2) Turn off almost every background / metrics subsystem ───────────────
    chrome_opts.add_argument("--disable-background-networking")
    chrome_opts.add_argument("--disable-default-apps")
    chrome_opts.add_argument("--disable-extensions")
    chrome_opts.add_argument("--disable-sync")
    chrome_opts.add_argument("--metrics-recording-only")
    chrome_opts.add_argument("--disable-component-update")
    chrome_opts.add_argument("--disable-domain-reliability")
    chrome_opts.add_argument("--disable-client-side-phishing-detection")
    chrome_opts.add_argument("--safebrowsing-disable-auto-update")
    chrome_opts.add_argument("--log-level=3")  # fatal only

    # ─── 3) Apply proxy if given ────────────────────────────────────────────────
 
        # proxy
    if proxy_url:
        chrome_opts.add_argument(f"--proxy-server={proxy_url}")
        logger.info(f"[Proxy] Using {proxy_url}")
    else:
        logger.info("[Proxy] Direct connection")

    # create Service with no log file
    service = Service(log_path=os.devnull)

    # launch
    driver = webdriver.Chrome(service=service, options=chrome_opts)

    # stealth
    driver.execute_cdp_cmd(
      "Page.addScriptToEvaluateOnNewDocument",
      {"source": "Object.defineProperty(navigator, 'webdriver', {get: () => false});"}
    )
    return driver

def is_logged_in(driver, email):
    try:
        WebDriverWait(driver, 10).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )
    except TimeoutException:
        pass
    els = driver.find_elements(
        By.CSS_SELECTOR,
        "div[aria-label='New message'], div[aria-label='Create a post']"
    )
    if els:
        logger.info(f"[+] Logged in: {email}")
        return True
    return False

def _parse_cookie_str(cookie_str):
    cookies = []
    for pair in cookie_str.split(';'):
        if '=' in pair:
            k, v = pair.strip().split('=', 1)
            cookies.append({'name': k, 'value': v})
    return cookies

def cookie_login(driver, account):
    email = account.get('email', '')
    logger(f"Trying cookies for {email}")
    cookies_data = account.get('cookies', '')
    if cookies_data:
        try:
            if cookies_data.strip().startswith('['):
                cookies = json.loads(cookies_data)
            else:
                cookies = _parse_cookie_str(cookies_data)
            for c in cookies:
                c.pop('sameSite', None)
                driver.add_cookie(c)
            logger(f"[+] Loaded cookies for {email}")
            driver.refresh()
            return True
        except Exception as e:
            logger(f"[!] Cookie error for {email}: {e}")
    return False

def wait_for_manual_blocks(driver, timeout=180):
    logger("[!] Waiting for manual challenges...")
    start = time.time()
    while time.time() - start < timeout:
        page = driver.page_source.lower()
        if 'referer_frame' in page:
            logger.info("[!] reCAPTCHA detected...")
        elif 'waiting for approval' in page:
            logger.info("[!] Device approval needed...")
        else:
            logger.info("[+] No manual blocks detected.")
            return
        time.sleep(5)
    logger("[!] Manual challenge timeout")

def two_factor_login(driver, account):
    email = account.get('email', '')
    logger(f"[>] Attempting 2FA for {email}")
    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.NAME, 'approvals_code'))
        )
        driver.find_element(By.NAME, 'approvals_code')\
              .send_keys(account.get('2fa', ''))
        driver.find_element(By.NAME, 'checkpoint_submit_button').click()
        wait_for_manual_blocks(driver)
        if is_logged_in(driver, email):
            logger(f"[+] 2FA login succeeded for {email}")
            return True
    except TimeoutException:
        logger.info(f"[!] No 2FA prompt for {email}")
    except Exception as e:
        logger(f"[!] 2FA error for {email}: {e}")
    return False

def token_login(driver, account):
    email = account.get('email', '')
    logger(f"[>] Attempting token login for {email}")
    token = account.get('token', '')
    if not token:
        logger(f"[!] No token available for {email}")
        return False
    try:
        driver.add_cookie({'name': 'c_user', 'value': token})
        logger(f"[+] Injected token for {email}")
        driver.refresh()
        wait_for_manual_blocks(driver)
        if is_logged_in(driver, email):
            logger(f"[+] Token login succeeded for {email}")
            return True
    except Exception as e:
        logger(f"[!] Token login error for {email}: {e}")
    return False

def credential_login(driver, account):
    email = account.get('email', '')
    logger(f"[>] Attempting credential login for {email}")
    driver.get("https://web.facebook.com/login")
    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, 'login_form'))
        )
    except TimeoutException:
        logger(f"[!] Login form not found for {email}")
        return False
    driver.find_element(By.ID, 'email').clear()
    driver.find_element(By.ID, 'email')\
          .send_keys(email)
    driver.find_element(By.ID, 'pass').clear()
    driver.find_element(By.ID, 'pass')\
          .send_keys(account.get('password', ''))
    driver.find_element(By.ID, 'loginbutton').click()
    time.sleep(10)
    wait_for_manual_blocks(driver)
    if is_logged_in(driver, email):
        logger(f"[+] Credential login succeeded for {email}")
        return True
    return False

def login_account(account, pm: ProxyManager, proxy_url=None):
    email = account.get('email', '')
    # pick a proxy if none was given
    if proxy_url is None:
        # first look for per-account field
        proxy_url = account.get('proxy') or pm.get_proxy_for(email)

    driver = create_driver(proxy_url)
    driver.get('https://web.facebook.com/')
    time.sleep(2)

# Cookie login
def cookie_login(driver, account):
    email = account.get('email', '')
    logger.info(f"Trying cookies for {email}")
    cookies_data = account.get('cookies', '')
    if cookies_data:
        try:
            cookies = json.loads(cookies_data) if cookies_data.strip().startswith('[') else _parse_cookie_str(cookies_data)
            for c in cookies:
                c.pop('sameSite', None)
                driver.add_cookie(c)
            logger(f"[+] Loaded cookies for {email}")
            driver.refresh()
            return True
        except Exception as e:
            logger(f"Cookie error {e}")
    return False

# Helper: parse "k=v; k2=v2" into list of cookie dicts
def _parse_cookie_str(cookie_str):
    cookies = []
    for pair in cookie_str.split(';'):
        if '=' in pair:
            k, v = pair.strip().split('=', 1)
            cookies.append({'name': k, 'value': v})
    return cookies

# Handle manual blocks: reCAPTCHA or device approval
def wait_for_manual(driver, timeout=180):
    logger.info("[!] Waiting for manual challenges (CAPTCHA or approval)...")
    start = time.time()
    while time.time() - start < timeout:
        page = driver.page_source.lower()
        if 'referer_frame' in page:
            logger.warning("[!] reCAPTCHA detected, awaiting user...")
        elif 'check your notifications on another device' in page or 'waiting for approval' in page:
            logger.warning("[!] Notification approval required, awaiting user...")
        else:
            logger.info("[+] No manual blocks detected.")
            return
        time.sleep(5)
    logger.error("[!] Manual challenge timeout")

# Submit two-factor authentication code
def cookie_login(driver, acct):
    email = acct.get('email','')
    data = acct.get('cookies','').strip()
    if not data:
        return False
    logger.info(f"{email}: trying cookie login")
    try:
        raw = json.loads(data) if data.startswith('[') else _parse_cookie_str(data)
        for c in raw:
            c.pop('sameSite',None)
            driver.add_cookie(c)
        driver.refresh()
        if is_logged_in(driver,email):
            logger.info(f"{email}: cookie login succeeded")
            return True
    except Exception as e:
        logger.error(f"{email}: cookie error: {e}")
    return False

# def wait_for_manual(driver, timeout=180):
#     logger.info("Waiting for manual challenge...")
#     start = time.time()
#     while time.time()-start < timeout:
#         page = driver.page_source.lower()
#         if 'referer_frame' in page:
#             logger.warning("reCAPTCHA detected")
#         elif 'waiting for approval' in page:
#             logger.warning("Device approval required")
#         else:
#             return
#         time.sleep(5)
#     logger.error("Manual challenge timeout")

def two_factor_login(driver, acct):
    email = acct.get('email','')
    code = acct.get('2fa','').strip()
    if not code:
        return False
    logger.info(f"{email}: attempting 2FA")
    try:
        WebDriverWait(driver,10).until(EC.presence_of_element_located((By.NAME,'approvals_code')))
        driver.find_element(By.NAME,'approvals_code').send_keys(code)
        driver.find_element(By.NAME,'checkpoint_submit_button').click()
        wait_for_manual(driver)
        if is_logged_in(driver,email):
            logger.info(f"{email}: 2FA succeeded")
            return True
    except TimeoutException:
        logger.warning(f"{email}: no 2FA prompt")
    except Exception as e:
        logger.error(f"{email}: 2FA error: {e}")
    return False

def token_login(driver, acct):
    email = acct.get('email','')
    token = acct.get('token','').strip()
    if not token:
        return False
    logger.info(f"{email}: attempting token login")
    try:
        driver.add_cookie({'name':'c_user','value':token})
        driver.refresh()
        wait_for_manual(driver)
        if is_logged_in(driver,email):
            logger.info(f"{email}: token login succeeded")
            return True
    except Exception as e:
        logger.error(f"{email}: token error: {e}")
    return False

def credential_login(driver, acct):
    email = acct.get('email','')
    pwd   = acct.get('password','')
    if not pwd:
        return False
    logger.info(f"{email}: attempting credentials login")
    driver.get("https://web.facebook.com/login")
    try:
        WebDriverWait(driver,10).until(EC.presence_of_element_located((By.ID,'login_form')))
    except TimeoutException:
        logger.error(f"{email}: login form not found")
        return False
    driver.find_element(By.ID,'email').send_keys(email)
    driver.find_element(By.ID,'pass').send_keys(pwd)
    driver.find_element(By.ID,'loginbutton').click()
    time.sleep(5)
    wait_for_manual(driver)
    if is_logged_in(driver,email):
        logger.info(f"{email}: credentials login succeeded")
        return True
    return False


def _try_with_proxy(account, proxy_url):
    """
    Helper: spin up a driver with proxy_url and attempt
    cookie → 2FA → token → credentials. Returns the driver
    on success, or None on failure.
    """
    driver = create_driver(proxy_url)
    driver.get('https://web.facebook.com/')
    time.sleep(2)

    email = account.get('email', '').strip()
    # 1) Cookies
    if cookie_login(driver, account) and is_logged_in(driver, email):
        return driver
    # 2) Two-factor
    if account.get('2fa') and two_factor_login(driver, account) and is_logged_in(driver, email):
        return driver
    # 3) Token
    if account.get('token') and token_login(driver, account) and is_logged_in(driver, email):
        return driver
    # 4) Credentials
    if credential_login(driver, account) and is_logged_in(driver, email):
        return driver

    driver.quit()
    return None


def login_account(account, pm: ProxyManager, proxy_url=None):
    """
    proxy_url is ALWAYS passed in from run().
    Returns (driver, account) on success or (None, None) on failure.
    """
    email = account.get('email','').strip()
    if not email:
        return None, None

    # Launch through exactly that proxy (or direct if None)
    driver = create_driver(proxy_url)
    driver.get('https://web.facebook.com/')
    time.sleep(2)

    # 1) try cookies
    if cookie_login(driver, account) and is_logged_in(driver, email):
        return driver, account

    # 2) try 2FA
    if account.get('2fa') and two_factor_login(driver, account) and is_logged_in(driver, email):
        return driver, account

    # 3) try token
    if account.get('token') and token_login(driver, account) and is_logged_in(driver, email):
        return driver, account

    # 4) fall back to credentials
    if credential_login(driver, account) and is_logged_in(driver, email):
        return driver, account

    # give up
    driver.quit()
    return None, None



def save_session(driver, account):
    email = account.get('email', '').strip()
    safe_email = re.sub(r"[^\w\.@-]", "_", email)
    folder = datetime.now().strftime('%Y-%m-%d')
    dirpath = os.path.join('sessions', folder)
    os.makedirs(dirpath, exist_ok=True)

    filepath = os.path.join(dirpath, f"{safe_email}_cookies.json")
    cookies = driver.get_cookies()
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump({
            'email': email,
            'cookies': cookies,
            'url': driver.current_url,
            'timestamp': time.time()
        }, f, indent=2)
    logger.info(f"[+] Session saved for {email}")
    update_account_field(email, 'cookies', json.dumps(cookies))


def run(pm: ProxyManager):
    accounts = load_accounts()
    if not accounts:
        logger.error("No accounts found.")
        return

    # validate global proxies once
    good_global = pm._validate_proxies(pm.global_pool)

    # if none work: prompt exactly once
    fallback = None
    if not good_global:
        choice = pm.choose_manual(None)    # “C)ustom or D)irect”
        fallback = choice                 # either a URL or None
        logger.info(f"[Fallback] {fallback or 'direct'}")

    for acct in accounts:
        email = acct.get('email','').strip()
        if not email:
            logger.warning("Skipping blank email")
            continue

        # determine proxy for this account
        if acct.get('proxy') is not None:
            proxy_url = acct['proxy'] or None
        elif good_global:
            proxy_url = good_global.pop(0)
        else:
            proxy_url = fallback

        driver, user = login_account(acct, pm, proxy_url=proxy_url)
        if not driver:
            logger.error(f"{email}: login failed")
            continue

        logger.info(f"{email}: login succeeded")
        save_session(driver, user)
        driver.quit()
if __name__ == "__main__":
    pm = ProxyManager()
    run(pm)