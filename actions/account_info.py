import time
import json
import os
import re
from datetime import datetime
from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from sessions.login_json     import load_accounts, login_account
from sessions.proxies_manager import ProxyManager

# Base directory for per-account logs
LOG_DIR = 'data/account_logs'
os.makedirs(LOG_DIR, exist_ok=True)

# -----------------------------------------------------------------------------
# Navigate to the user's About page via direct URL fallback
# -----------------------------------------------------------------------------
def navigate_to_profile(driver, timeout=10):
    """
    1) Open avatar dropdown ("Your profile").
    2) Click the "/me/" link to go to profile.
    3) Attempt to click the About tab; if any click fails, build the URL
       https://web.facebook.com/{username}/about and navigate directly.
    """
    wait = WebDriverWait(driver, timeout)
    # 1) Open avatar dropdown
    avatar = wait.until(
        EC.element_to_be_clickable((By.CSS_SELECTOR, "div[aria-label='Your profile'][role='button']"))
    )
    driver.execute_script("arguments[0].scrollIntoView(true); arguments[0].click();", avatar)
    time.sleep(1)

    # 2) Click "/me/" link
    profile_link = wait.until(
        EC.element_to_be_clickable((By.CSS_SELECTOR, "a[href='/me/']"))
    )
    driver.execute_script("arguments[0].scrollIntoView(true); arguments[0].click();", profile_link)
    time.sleep(2)

    # Try clicking About tab
    try:
        about_tab = wait.until(
            EC.element_to_be_clickable((By.XPATH, "//a[contains(@href, '/about') and not(contains(@href,'transparency'))]"))
        )
        driver.execute_script("arguments[0].scrollIntoView({block:'center'}); arguments[0].click();", about_tab)
        time.sleep(2)
        return
    except Exception:
        pass

    # Fallback to direct URL
    # extract username or id from current URL
    current = driver.current_url
    # if profile.php?id= or /username/
    m = re.search(r"facebook\.com/(?:profile\.php\?id=(\d+)|([^/?]+))", current)
    if m:
        user_part = m.group(1) or m.group(2)
        about_url = f"https://web.facebook.com/{user_part}/about"
    else:
        # fallback to /me/about
        about_url = "https://web.facebook.com/me/about"
    driver.get(about_url)
    time.sleep(2)

# -----------------------------------------------------------------------------
def get_account_name(driver, timeout=10):
    """
    Extract account display name from profile header via BS4 fallback.
    """
    try:
        # Primary: banner h1
        elem = WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div[role='banner'] h1"))
        )
        return elem.text.strip()
    except Exception:
        # Fallback: page source
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        h1 = soup.select_one("div[role='banner'] h1")
        if h1:
            return h1.get_text(strip=True)
        # Last resort: username in URL
        return driver.current_url.rstrip('/').split('/')[-1]

# -----------------------------------------------------------------------------
def get_creation_date(driver):
    """
    On the About page, extract creation date via BS4.
    """
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    span = soup.find('span', text=re.compile(r"\w+ \d{1,2}, \d{4}"))
    return span.get_text(strip=True) if span else ''

# -----------------------------------------------------------------------------
def get_follower_count(driver, timeout=10):
    """
    Navigate to followers page and read follower count.
    """
    driver.get('https://web.facebook.com/me/followers/')
    time.sleep(2)
    try:
        el = WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "a[href*='/followers/'] strong"))
        )
        return el.text.strip()
    except Exception:
        return ''

# -----------------------------------------------------------------------------
def get_basic_info(driver):
    """
    Visit Contact & Basic Info page and scrape birth date, gender, email, phone.
    """
    driver.get('https://web.facebook.com/me/about_contact_and_basic_info')
    time.sleep(2)
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    info = {}
    # Birth date
    born = soup.find(text=re.compile(r'Born'))
    if born:
        m = re.search(r"([A-Za-z]+ \d{1,2}, \d{4})", born)
        if m:
            info['birth_date'] = m.group(1)
    # Gender
    gender_elem = soup.find(text=re.compile(r'Gender'))
    if gender_elem and gender_elem.parent:
        sib = gender_elem.parent.find_next_sibling('div')
        if sib:
            info['gender'] = sib.get_text(strip=True)
    # Email
    email_img = soup.find('img', src=re.compile('email'))
    if email_img:
        span = email_img.find_next('span')
        if span:
            info['email'] = span.get_text(strip=True)
    # Phone
    phone_img = soup.find('img', src=re.compile('phone'))
    if phone_img:
        span = phone_img.find_next('span')
        if span:
            info['phone'] = span.get_text(strip=True)
    return info

# -----------------------------------------------------------------------------
def log_and_get_account_details(driver):
    """
    Navigate, scrape all details, return info dict.
    """
    navigate_to_profile(driver)
    details = {
        'login_time': datetime.now().isoformat(),
        'account_name': get_account_name(driver),
        'created_on': get_creation_date(driver),
        'follower_count': get_follower_count(driver)
    }
    details.update(get_basic_info(driver))
    return details

# -----------------------------------------------------------------------------
def run(proxy_manager: ProxyManager):
    """
    Login each account and save its info to per-account JSON files.
    """
    _, accounts = load_accounts('data/login_details.csv')
    if not accounts:
        print('❌ No accounts to process.')
        return

    for acc in accounts:
        email = acc.get('email', 'unknown')
        safe_name = re.sub(r'[^A-Za-z0-9]', '_', email)
        out_path = os.path.join(LOG_DIR, f'{safe_name}.json')

        driver, user = login_account(acc, proxy_manager)
        if not driver:
            print(f'⚠️ Skipping {email}')
            continue

        info = log_and_get_account_details(driver, user)
        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump(info, f, indent=2)
        print(f"[+] Saved info for {email} → {out_path}")

        driver.quit()

    print('✅ Account info scraping complete.')
