# actions/group_comment.py

import os
import csv
import json
import time
import random
import logging
from datetime import datetime
import pandas as pd
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from sessions.login_json     import load_accounts, login_account

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("GroupComment")

MAX_COMMENTS_PER_GROUP = 10

# ─── Human-like behavior helpers ───────────────────────────────

def human_delay(min_sec=3, max_sec=6):
    delay = random.uniform(min_sec, max_sec)
    logger.debug(f"[⏳] Human-like delay: {delay:.2f}s")
    time.sleep(delay)

def take_micro_break():
    if random.random() < 0.2:
        logger.info("[😴] Taking a short human-like break...")
        time.sleep(random.uniform(15, 30))

def random_exploration(driver):
    if random.random() < 0.2:
        logger.debug("[🧍] Bot exploring the page randomly...")
        driver.execute_script("window.scrollBy(0, -300);")
        time.sleep(random.uniform(1, 3))

def type_like_human(driver, text):
    actions = ActionChains(driver)
    for char in text:
        actions.send_keys(char).perform()
        time.sleep(random.uniform(0.05, 0.15))

# ─── Comment utilities ─────────────────────────────────────────

def get_random_comment(path="data/comments.csv"):
    try:
        df = pd.read_csv(path, header=None)
        return random.choice(df[0].tolist())
    except Exception as e:
        logger.warning(f"[!] Could not load comments: {e}")
        return "Great post!"

def click_comment_button(post, driver, text):
    try:
        button = post.find_element(By.CSS_SELECTOR, "div[aria-label='Leave a comment']")
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", button)
        human_delay(5, 9)
        button.click()
        logger.info("✅ Clicked 'Leave a comment'")
        return True
    except Exception:
        return click_comment_button_js(driver)

def click_comment_button_js(driver):
    try:
        js = """
        let buttons = document.querySelectorAll("div[role='button'][aria-label='Leave a comment']");
        if (buttons.length > 0) {
            buttons[0].scrollIntoView({block: 'center'});
            buttons[0].click();
            return true;
        } else {
            return false;
        }
        """
        result = driver.execute_script(js)
        if result:
            logger.info("✅ JS fallback: clicked 'Leave a comment'")
            return True
    except Exception as e:
        logger.warning(f"❌ JS click failed: {e}")
        human_delay(5, 9)
    return False

def submit_comment(driver):
    try:
        ActionChains(driver).send_keys(Keys.ENTER).perform()
        logger.info("[✓] Comment submitted")
        return True
    except Exception as e:
        logger.warning(f"[!] Submit failed: {e}")
    return False

def scroll_to_load_posts(driver, scrolls=5):
    logger.info("[↓] Scrolling to load posts...")
    for i in range(scrolls):
        driver.execute_script("window.scrollBy(0, window.innerHeight);")
        time.sleep(random.uniform(2.5, 3.5))
        random_exploration(driver)
        take_micro_break()

# ─── Tracking & logging ───────────────────────────────────────

def setup_individual_logger(email):
    today = datetime.now().strftime("%Y-%m-%d")
    log_dir = f"logs/{email}"
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, f"{today}.log")
    file_handler = logging.FileHandler(log_file)
    file_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
    file_handler.setLevel(logging.INFO)
    logger.addHandler(file_handler)

def log_today_comment_stats(acc):
    today = datetime.now().strftime("%Y-%m-%d")
    year, month, day = today.split("-")
    tracking = acc.get("tracking", {})
    total_comments = tracking.get("total_comments", {})
    today_count = total_comments.get(year, {}).get(month, {}).get(day, 0)
    logger.info(f"[📊] Today’s comment count for {acc['email']}: {today_count}")

def export_tracking_to_csv(account_file="data/fb_group_url.json", output_file="exports/comments_report.csv"):
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    try:
        with open(account_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(["Email", "Date", "Comments"])
            for entry in data:
                email = entry.get("email", "N/A")
                tracking = entry.get("tracking", {}).get("total_comments", {})
                for year, months in tracking.items():
                    for month, days in months.items():
                        for day, count in days.items():
                            writer.writerow([email, f"{year}-{month}-{day}", count])
        logger.info("[📁] Exported comment stats to CSV.")
    except Exception as e:
        logger.error(f"[❌] Export failed: {e}")

# ─── Core logic ───────────────────────────────────────────────

def comment_in_group(driver, acc, group_url, max_comments=10):
    logger.info(f"[→] Visiting group: {group_url}")
    driver.get(group_url)
    time.sleep(6)

    scroll_to_load_posts(driver, scrolls=5)
    posts = driver.find_elements(By.XPATH, "//div[@role='article']")
    logger.info(f"[+] Found {len(posts)} posts to potentially comment on.")

    count = 0
    for post in posts:
        if count >= max_comments:
            break
        try:
            text = get_random_comment()
            logger.info(f"[🗨️] Comment: {text}")
            if click_comment_button(post, driver, text):
                type_like_human(driver, text)
                submit_comment(driver)
                time.sleep(random.uniform(2, 4))
                ActionChains(driver).send_keys(Keys.ESCAPE).perform()
                count += 1
                logger.info("[⏳] Sleeping before next...")
                time.sleep(random.uniform(5, 9))
        except Exception as e:
            logger.warning(f"[!] Skipping post: {e}")
            continue

    logger.info(f"[→] Finished {count}/{max_comments} comments in group.")

def get_groups_for_user(email, path="data/fb_group_url.json"):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        for entry in data:
            if entry.get("username") == email:
                return entry.get("group_url", [])
    except Exception as e:
        logger.error(f"[!] Failed to get groups for {email}: {e}")
    return []

def run(driver, acc):
    try:
        email = acc.get("fbemail") or acc.get("email")
        setup_individual_logger(email)
        logger.info(f"[🟢] Starting for {email}")
        log_today_comment_stats(acc)
        groups = get_groups_for_user(email)
        if not groups:
            logger.warning(f"[!] No groups found for {email}")
            return

        for group_url in groups:
            try:
                comment_in_group(driver, acc, group_url, max_comments=MAX_COMMENTS_PER_GROUP)
            except Exception as e:
                logger.error(f"[!] Error in group {group_url}: {e}")
            time.sleep(10)

    except Exception as e:
        logger.critical(f"[❌] Bot crashed: {e}")

def comment_Pop(proxy_manager):
    from sessions.login import load_accounts, login_account
    df, accounts = load_accounts('data/login_details.csv')

    for acc in accounts:
        driver, acc = login_account(acc, proxy_manager)
        if not driver:
            continue
        run(driver, acc)
        driver.quit()
        export_tracking_to_csv()
