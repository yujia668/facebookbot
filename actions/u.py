# actions/get_friendlists.py

import os
import re
import time
import random
import pandas as pd
from datetime import datetime
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

from utils.utils import logger

# ─── Configuration ──────────────────────────────────────────────

PROFILE_LIST_PATH            = 'data/target.csv'
FRIEND_HISTORY_PATH          = 'data/friendlist.csv'

# daily / per-account limits
GLOBAL_FRIEND_SCRAPE_LIMIT   = 1000
PER_ACCOUNT_FRIEND_LIMIT     = 200

# CSS / XPATH selectors
PROFILE_FRIENDS_TAB_SELECTOR = "a[href*='/friends_all']"
FRIEND_ITEM_SELECTOR         = "div[role='main'] a[href*='profile.php']"
MAIN_SCROLLABLE_SELECTOR     = "div[role='main']"


# ─── Persistence ─────────────────────────────────────────────────

def load_history(path=FRIEND_HISTORY_PATH):
    if os.path.exists(path):
        df = pd.read_csv(path, dtype=str)
        return set(zip(df['user_id'], df['friend_id'])), df
    cols = ['user_id','friend_id','friend_link','friend_name','scrape_date']
    return set(), pd.DataFrame(columns=cols)

def save_history(df, path=FRIEND_HISTORY_PATH):
    df.to_csv(path, index=False)
    logger.info(f"[+] Friend history saved ({len(df)}) to {path}")


# ─── Human-like Helpers ─────────────────────────────────────────

def human_delay(min_sec=1.0, max_sec=3.0):
    d = random.uniform(min_sec, max_sec)
    logger.debug(f"[⏱] Sleeping {d:.2f}s")
    time.sleep(d)

def safe_click(driver, elem):
    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", elem)
    time.sleep(0.2)
    try:
        elem.click()
    except:
        driver.execute_script("arguments[0].click();", elem)
    time.sleep(0.3)


# ─── Scraper Class ──────────────────────────────────────────────

class FriendListScraper:
    def __init__(self, driver):
        self.driver = driver
        self.history_keys, self.history_df = load_history()
        self.today = datetime.now().strftime('%Y-%m-%d')

        # how many we’ve already scraped globally today
        done_today = self.history_df[self.history_df.scrape_date == self.today].shape[0]
        self.remaining_global = GLOBAL_FRIEND_SCRAPE_LIMIT - done_today
        if self.remaining_global < 0:
            self.remaining_global = 0

    def load_target_profiles(self):
        if not os.path.exists(PROFILE_LIST_PATH):
            logger.error(f"No profile list: {PROFILE_LIST_PATH}")
            return pd.DataFrame()
        df = pd.read_csv(PROFILE_LIST_PATH, dtype=str)
        # only those we haven’t scraped today at all:
        scraped_today = set(self.history_df[self.history_df.scrape_date == self.today]['user_id'])
        return df[~df['id'].isin(scraped_today)]

    def extract_friend_id(self, href):
        m = re.search(r'id=(\d+)', href)
        return m.group(1) if m else None

    def get_friends_for_profile(self, user_id, friend_limit):
        """
        Navigate to that user’s friends_all page and scroll to collect up to friend_limit entries.
        """
        url = f"{self.driver.current_url.split('?')[0].split('/friends_all')[0]}/friends_all"
        self.driver.get(url)
        human_delay(2,4)

        try:
            tab = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, PROFILE_FRIENDS_TAB_SELECTOR))
            )
            safe_click(self.driver, tab)
            human_delay(1,2)
        except TimeoutException:
            logger.warning(f"⚠️ No Friends tab for {user_id}")
            return []

        # now scroll within the main container
        try:
            main = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, MAIN_SCROLLABLE_SELECTOR))
            )
        except TimeoutException:
            logger.warning("Could not find scrollable container")
            return []

        friends = []
        seen_ids = set()
        last_h = self.driver.execute_script("return arguments[0].scrollHeight;", main)

        while len(friends) < friend_limit:
            elems = main.find_elements(By.CSS_SELECTOR, FRIEND_ITEM_SELECTOR)
            for el in elems:
                try:
                    name = el.text.strip()
                    link = el.get_attribute('href')
                    fid = self.extract_friend_id(link)
                    key = (user_id, fid)
                    if name and fid and key not in self.history_keys and fid not in seen_ids:
                        friends.append({'user_id':     user_id,
                                        'friend_id':   fid,
                                        'friend_link': link,
                                        'friend_name': name,
                                        'scrape_date': self.today})
                        seen_ids.add(fid)
                        if len(friends) >= friend_limit:
                            break
                except Exception:
                    continue

            # scroll down
            self.driver.execute_script("arguments[0].scrollBy(0, arguments[0].scrollHeight);", main)
            human_delay(1,2)
            new_h = self.driver.execute_script("return arguments[0].scrollHeight;", main)
            if new_h == last_h:
                break
            last_h = new_h

        return friends

    def run(self):
        if self.remaining_global <= 0:
            logger.error("Global friend‐scrape limit reached for today.")
            return []

        profiles = self.load_target_profiles()
        if profiles.empty:
            logger.info("No new profiles to scrape today.")
            return []

        all_new = []
        for _, row in profiles.iterrows():
            if self.remaining_global <= 0:
                break

            uid = row['id']
            # how many this account already had scraped today?
            done_acc = self.history_df[
                (self.history_df.user_id == uid) &
                (self.history_df.scrape_date == self.today)
            ].shape[0]
            remain_acc = PER_ACCOUNT_FRIEND_LIMIT - done_acc
            if remain_acc <= 0:
                logger.debug(f"Per-account limit reached for {uid}")
                continue

            to_grab = min(remain_acc, self.remaining_global)
            logger.info(f"⏩ Scraping up to {to_grab} friends for {uid}")

            new_friends = self.get_friends_for_profile(uid, to_grab)
            if not new_friends:
                continue

            # record them
            for rec in new_friends:
                all_new.append(rec)
                self.history_keys.add((rec['user_id'], rec['friend_id']))

            # append to DataFrame and decrement global
            self.history_df = pd.concat([self.history_df, pd.DataFrame(new_friends)], ignore_index=True)
            self.remaining_global -= len(new_friends)

            logger.info(f"✅ Collected {len(new_friends)} friends for {uid} — remaining global: {self.remaining_global}")
            human_delay(2,4)

        # save at end
        save_history(self.history_df)
        logger.info(f"🏁 Done: new friend relations = {len(all_new)}")
        return all_new
