# actions/group_comment.py

import os
import json
import time
import random
import logging
import pandas as pd
import datetime
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

logger = logging.getLogger("GroupComment")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

# ─── CONFIG ─────────────────────────────────────────────────
COMMENTS_CSV       = "data/comments.csv"
GROUP_URLS_JSON    = "data/fb_group_url.json"
HISTORY_CSV        = "data/group_comment_history.csv"
MAX_COMMENTS_PER_GROUP = 10

# ─── UTILITIES ──────────────────────────────────────────────

def human_delay(a=1.5, b=3.0):
    t = random.uniform(a, b)
    logger.debug(f"[⏳] Sleeping {t:.2f}s")
    time.sleep(t)

def safe_click(driver, elem):
    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", elem)
    human_delay(0.2, 0.5)
    try:
        elem.click()
    except:
        driver.execute_script("arguments[0].click();", elem)
    human_delay(0.2, 0.5)

def safe_type(elem, text):
    for ch in text:
        elem.send_keys(ch)
        time.sleep(random.uniform(0.03, 0.1))

def js_click_comment(driver):
    """Fallback JS click on the first ‘Leave a comment’ button."""
    js = """
      const btns = document.querySelectorAll("div[role='button'][aria-label='Leave a comment']");
      if (!btns.length) return false;
      btns[0].scrollIntoView({block:'center'}); btns[0].click();
      return true;
    """
    return driver.execute_script(js)

# ─── PERSISTENCE ────────────────────────────────────────────

def load_comments(path=COMMENTS_CSV):
    if not os.path.exists(path):
        logger.warning(f"[!] {path} not found, using default comment.")
        return ["Great post!"]
    df = pd.read_csv(path, header=None)
    return df[0].dropna().astype(str).tolist()

def load_group_urls(username):
    if not os.path.exists(GROUP_URLS_JSON):
        return []
    try:
        with open(GROUP_URLS_JSON, "r", encoding="utf-8") as f:
            data = json.load(f)
        rec = next((r for r in data if r.get("username")==username), {})
        return rec.get("group_url", [])
    except Exception as e:
        logger.error(f"[!] Could not read {GROUP_URLS_JSON}: {e}")
        return []

def load_history(path=HISTORY_CSV):
    if os.path.exists(path):
        df = pd.read_csv(path, dtype=str)
        return set(df['post_id']), df
    cols = ['username','group_url','post_id','timestamp']
    return set(), pd.DataFrame(columns=cols)

def save_history(df, path=HISTORY_CSV):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    df.to_csv(path, index=False)
    logger.info(f"[+] History saved ({len(df)}) to {path}")

# ─── CORE LOGIC ─────────────────────────────────────────────

def scroll_to_load_posts(driver, scrolls=4):
    logger.info("[↓] Scrolling to load group posts…")
    for _ in range(scrolls):
        driver.execute_script("window.scrollBy(0, window.innerHeight);")
        human_delay(2.0, 3.5)

def comment_in_group(driver, username, group_url, comments, history_ids, history_df):
    logger.info(f"[→] Visiting group: {group_url}")
    driver.get(group_url)
    human_delay(4, 6)

    scroll_to_load_posts(driver, scrolls=5)
    posts = driver.find_elements(By.XPATH, "//div[@role='article']")
    logger.info(f"[+] Found {len(posts)} posts in group")

    count = 0
    for post in posts:
        if count >= MAX_COMMENTS_PER_GROUP:
            break

        # try to get unique post id from data-ft or link
        try:
            fid = post.get_attribute("data-ft")
        except:
            fid = post.get_attribute("id") or str(random.random())

        if fid in history_ids:
            continue

        # 1) click the ‘Leave a comment’ button
        try:
            btn = post.find_element(By.XPATH, ".//div[@role='button' and contains(@aria-label,'Leave a comment')]")
            safe_click(driver, btn)
        except:
            if not js_click_comment(driver):
                logger.warning("⚠️ No comment button found, skipping post")
                continue

        human_delay(1, 2)

        # 2) type a random comment
        try:
            box = WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.XPATH, "//div[@contenteditable='true'][@aria-label='Write a comment']"))
            )
        except TimeoutException:
            logger.warning("⚠️ Comment box never appeared")
            continue

        comment = random.choice(comments)
        safe_type(box, comment)

        # 3) submit it
        ActionChains(driver).send_keys(Keys.ENTER).perform()
        logger.info(f"[✓] Commented: “{comment}”")
        human_delay(1, 2)

        # 4) record in history & close (ESC)
        ts = datetime.now().isoformat()
        history_df.loc[len(history_df)] = {
            'username': username,
            'group_url': group_url,
            'post_id': fid,
            'timestamp': ts
        }
        history_ids.add(fid)

        try:
            ActionChains(driver).send_keys(Keys.ESCAPE).perform()
        except:
            pass

        count += 1
        human_delay(3, 6)

    logger.info(f"[→] Done {count}/{MAX_COMMENTS_PER_GROUP} comments in group")

def run(driver, acc):
    """
    Entry – call this from your main.py after logging in each account.
    """
    username = acc.get("username") or acc.get("email")
    logger.info(f"[🟢] Starting group comments for {username}")

    comments   = load_comments()
    group_urls = load_group_urls(username)
    if not group_urls:
        logger.warning(f"[!] No groups for {username}")
        return

    history_ids, history_df = load_history()

    for url in group_urls:
        comment_in_group(driver, username, url, comments, history_ids, history_df)
        human_delay(5, 10)

    save_history(history_df)
    logger.info(f"[✔] Finished all groups for {username}")
