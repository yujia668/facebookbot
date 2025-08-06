import os
import json
import time
import re
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.service import Service
import random
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from proxies_manager import ProxyManager
import os
# ─── 1) Silence TensorFlow / Abseil ────────────────────────────────────────────
os.environ['TF_CPP_MIN_LOG_LEVEL']   = '3'
os.environ['ABSL_CPP_MIN_LOG_LEVEL'] = '3'

def gui_log(message):
    print(message)
# ─── 2) Paths ───────────────────────────────────────────────────────────────────
ACCOUNTS_JSON    = "data/fb_accounts_details.json"
FINGERPRINT_JSON = "data/fingerprint.json"
SESSIONS_DIR     = "sessions"

# ─── 3) Load & save account records ─────────────────────────────────────────────

def load_accounts(json_path: str = ACCOUNTS_JSON):
    if not os.path.exists(json_path):
        return []
    with open(json_path, 'r', encoding='utf-8') as f:
        try:
            data = json.load(f)
            return data if isinstance(data, list) else []
        except json.JSONDecodeError:
            print(f"[!] Failed to parse {json_path}")
            return []

def _save_accounts(accts, json_path: str = ACCOUNTS_JSON):
    os.makedirs(os.path.dirname(json_path), exist_ok=True)
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(accts, f, indent=2)

def update_account_field(email, field, value, json_path: str = ACCOUNTS_JSON):
    accts = load_accounts(json_path)
    for acct in accts:
        if acct.get('email','').strip().lower() == email.strip().lower():
            acct[field] = value
            _save_accounts(accts, json_path)
            return
    print(f"[!] No account found for {email}")

# ─── 4) Fingerprint loader & stealth script builder ────────────────────────────
def _load_fingerprint(path: str = FINGERPRINT_JSON) -> dict:
    with open(path, 'r', encoding='utf-8') as f:
        fps = json.load(f)
    if isinstance(fps, list) and fps:
        return random.choice(fps)
    elif isinstance(fps, dict):
        return fps
    else:
        raise ValueError(f"Unexpected fingerprint format: {type(fps)}")

def _build_stealth_js(fp: dict) -> str:
    ua        = fp['attr'].get('navigator.userAgent', "").replace("'", r"\'")
    lang      = fp.get('lang', 'en-US')
    langs     = fp['attr'].get('navigator.languages') or [lang]
    languages = json.dumps(langs)

    css = fp.get('css', {})
    w  = css.get('width', 1366)
    h  = css.get('height', 768)
    cd = css.get('color-index', css.get('color-depth', 24))
    dr = css.get('device-memory', 4)
    hc = css.get('hardwareConcurrency', 4)

    lines = [
        "Object.defineProperty(navigator, 'webdriver', {get: () => false});",
        f"Object.defineProperty(navigator, 'userAgent',  {{get: () => '{ua}'}});",
        f"Object.defineProperty(navigator, 'language',   {{get: () => '{lang}'}});",
        f"Object.defineProperty(navigator, 'languages',  {{get: () => {languages}}});",
        f"Object.defineProperty(screen,    'width',      {{get: () => {w}}});",
        f"Object.defineProperty(screen,    'height',     {{get: () => {h}}});",
        # …you can add more overrides here if desired…
    ]
    return "\n".join(lines)

# ─── 5) Unified driver factory ─────────────────────────────────────────────────



def create_driver(proxy_url=None):
    chrome_opts = Options()
    os.environ['TF_CPP_MIN_LOG_LEVEL']   = '3'
    os.environ['ABSL_CPP_MIN_LOG_LEVEL'] = '3'

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
    from proxies_manager import ProxyManager
    pm = ProxyManager()
    if proxy_url:
        pm.apply_to_options(chrome_opts, proxy_url)
    else:
        # your own log entry; this will still print
        print("[ProxyManager] ▶️ Direct (no proxy)")
    # silence chromedriver output:
    service = Service(log_path=os.devnull)    # anti-detection flags
    chrome_opts.add_argument("--disable-blink-features=AutomationControlled")
    chrome_opts.add_argument("--start-maximized")

    # proxy
    pm = ProxyManager()
    if proxy_url:
        pm.apply_to_options(chrome_opts, proxy_url)
    else:
        print("[ProxyManager] ▶️ Direct (no proxy)")

    # instantiate
    driver = webdriver.Chrome(service=service, options=chrome_opts)
    # stealth injection
    fp = _load_fingerprint()
    stealth_js = _build_stealth_js(fp)
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {"source": stealth_js})

    return driver

# ─── 6) Login state checks & helpers ────────────────────────────────────────────

def is_logged_in(driver, email):
    try:
        WebDriverWait(driver, 10).until(lambda d: d.execute_script("return document.readyState") == "complete")
    except TimeoutException:
        pass
    # presence of a familiar post-login UI element
    els = driver.find_elements(By.CSS_SELECTOR,
        "div[aria-label='New message'], div[aria-label='Create a post']")
    if els:
        print(f"[+] Logged in: {email}")
        return True
    return False

def _parse_cookie_str(cookie_str):
    out = []
    for pair in cookie_str.split(';'):
        if '=' in pair:
            k, v = pair.strip().split('=',1)
            out.append({'name':k, 'value':v})
    return out

def cookie_login(driver, account):
    email = account.get('email','')
    cdata = account.get('cookies','')
    if not cdata:
        return False
    print(f"[>] Loading cookies for {email}")
    try:
        cookies = json.loads(cdata) if cdata.strip().startswith('[') else _parse_cookie_str(cdata)
        for c in cookies:
            c.pop('sameSite', None)
            driver.add_cookie(c)
        driver.refresh()
        return True
    except Exception as e:
        print(f"[!] Cookie error for {email}: {e}")
        return False

def wait_for_manual_blocks(driver, timeout=180):
    start = time.time()
    print("[!] Waiting for manual blocks…")
    while time.time() - start < timeout:
        page = driver.page_source.lower()
        if 'referer_frame' in page:
            print("[!] reCAPTCHA detected…")
        elif 'waiting for approval' in page:
            print("[!] Device approval…")
        else:
            return
        time.sleep(5)
    print("[!] Manual challenge timeout")

def two_factor_login(driver, account):
    email = account.get('email','')
    try:
        WebDriverWait(driver,10).until(EC.presence_of_element_located((By.NAME,'approvals_code')))
        driver.find_element(By.NAME,'approvals_code')\
              .send_keys(account.get('2fa',''))
        driver.find_element(By.NAME,'checkpoint_submit_button').click()
        wait_for_manual_blocks(driver)
        return is_logged_in(driver, email)
    except TimeoutException:
        return False

def token_login(driver, account):
    token = account.get('token','')
    if not token:
        return False
    driver.add_cookie({'name':'c_user','value':token})
    driver.refresh()
    wait_for_manual_blocks(driver)
    return is_logged_in(driver, account.get('email',''))

def credential_login(driver, account):
    email = account.get('email','')
    driver.get("https://web.facebook.com/login")
    try:
        WebDriverWait(driver,10).until(EC.presence_of_element_located((By.ID,'login_form')))
    except TimeoutException:
        return False
    driver.find_element(By.ID,'email').send_keys(email)
    driver.find_element(By.ID,'pass').send_keys(account.get('password',''))
    driver.find_element(By.ID,'loginbutton').click()
    time.sleep(5)
    wait_for_manual_blocks(driver)
    return is_logged_in(driver, email)

# ─── 7) Top-level login_account and session saver ──────────────────────────────

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


def login_account(account, pm: ProxyManager):
    """
    1) Try per-account proxy
    2) Fallback to validated global proxies
    3) Prompt once for custom or direct; save that choice
    Returns (driver, account) on success, or (None, None) on failure.
    """
    email = account.get('email', '').strip()
    if not email:
        return None, None

    # 1) Per-account proxy
    acct_proxy = account.get('proxy') or None
    if acct_proxy:
        drv = _try_with_proxy(account, acct_proxy)
        if drv:
            return drv, account
        print(f"[!] Per-account proxy {acct_proxy!r} failed for {email}, falling back…")

    # 2) Validate & try global pool
    good = pm._validate_proxies(pm.global_pool)
    for proxy in good:
        drv = _try_with_proxy(account, proxy)
        if drv:
            # persist this working global proxy to the account
            update_account_field(email, 'proxy', proxy)
            print(f"[+] Using global proxy {proxy!r} for {email}")
            return drv, account

    # 3) Ask user once (custom or direct), then save
    choice = pm.choose_manual(email)    # “S)ystem… C)ustom… D)irect”
    # save into JSON (empty string = direct)
    update_account_field(email, 'proxy', choice or '')
    drv = _try_with_proxy(account, choice)
    if drv:
        return drv, account

    # nothing worked
    return None, None

def save_session(driver, account):
    email = account.get('email','').strip()
    safe = re.sub(r"[^\w@.-]", "_", email)
    folder = datetime.now().strftime("%Y-%m-%d")
    path   = os.path.join(SESSIONS_DIR, folder)
    os.makedirs(path, exist_ok=True)
    fn = os.path.join(path, f"{safe}_cookies.json")
    cookies = driver.get_cookies()
    with open(fn,'w',encoding='utf-8') as f:
        json.dump({'email':email,'cookies':cookies}, f, indent=2)
    update_account_field(email, 'cookies', json.dumps(cookies))

def run(pm: ProxyManager):
    for acct in load_accounts():
        driver, user = login_account(acct, pm)
        if not driver:
            print(f"[!] Skipping {acct.get('email')}")
            continue
        save_session(driver, user)
        driver.quit()

if __name__ == "__main__":
    pm = ProxyManager()
    run(pm)