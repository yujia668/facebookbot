# actions/target_user_request.py

import csv
import time
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

TARGETS_CSV = "data/targets.csv"  # CSV with header: userid,username

def _load_targets(n):
    """
    Read up to n rows from TARGETS_CSV (columns: userid,username).
    Returns a list of dicts: [{'userid':…, 'username':…}, …].
    """
    out = []
    with open(TARGETS_CSV, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            uid   = row.get('userid', '').strip()
            uname = row.get('username', '').strip()
            if not uid and not uname:
                continue
            out.append({'userid': uid, 'username': uname})
            if len(out) >= n:
                break
    return out

def run(driver, count):
    """
    Send up to `count` friend requests to users listed in data/targets.csv.

    For each target:
      1) Try visiting https://web.facebook.com/{userid}
      2) If no “Add Friend” button appears, visit https://web.facebook.com/{username}
      3) If an “Add Friend” button is found & clickable, click it.
    """
    targets = _load_targets(count)
    sent = 0

    for t in targets:
        # Build profile URLs
        primary  = f"https://web.facebook.com/{t['userid']}"    if t['userid']   else None
        fallback = f"https://web.facebook.com/{t['username']}" if t['username'] else None

        for url in (primary, fallback):
            if not url:
                continue

            driver.get(url)
            try:
                btn = WebDriverWait(driver, 8).until(
                    EC.element_to_be_clickable((
                        By.XPATH,
                        "//div[@role='button' and contains(@aria-label,'Add Friend')]"
                    ))
                )
                btn.click()
                sent += 1
                print(f"   ✔ Sent to {url} ({sent}/{count})")
                break  # stop trying fallback
            except Exception:
                # “Add Friend” not found here → try next URL
                continue

        if sent >= count:
            break

        time.sleep(2)

    print(f"✅ Done. {sent}/{count} friend-requests sent.")
