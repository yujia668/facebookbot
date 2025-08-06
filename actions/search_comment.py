# actions/search_comment.py

import os
import re
import time
import random
import pandas as pd
from datetime import datetime
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

from data.comment_manager import CommentsManager
from utils.utils import logger

# ─── Configuration ──────────────────────────────────────────────

KEYWORDS_FILE     = 'data/keywords.txt'
HISTORY_PATH      = 'data/comment_history.csv'

SEARCH_INPUT_CSS  = 'input[aria-label="Search Facebook"]'
POSTS_TAB_XPATH   = '//a[contains(@href,"/search/posts") and contains(.,"Posts")]'
RECENT_SWITCH_CSS = 'input[role="switch"][aria-label="Recent Posts"]'
POST_ARTICLE_XPATH= "//div[@role='article']"
LEAVE_COMMENT_BTN = 'div[aria-label="Leave a comment"][role="button"]'
COMMENT_BOX_CSS   = 'div[aria-label="Write a comment…"][contenteditable="true"]'


# ─── Persistence ─────────────────────────────────────────────────

def load_history(path=HISTORY_PATH):
    if os.path.exists(path):
        df = pd.read_csv(path, dtype=str)
        return set(df['post_id']), df
    df = pd.DataFrame(columns=['post_id','timestamp','comment'])
    return set(), df

def save_history(df, path=HISTORY_PATH):
    df.to_csv(path, index=False)
    logger.info(f"[+] Comment history saved ({len(df)}) to {path}")


# ─── Human-like Helpers ─────────────────────────────────────────

def human_delay(min_sec=1.0, max_sec=3.0):
    d = random.uniform(min_sec, max_sec)
    logger.debug(f"[⏱] Pausing {d:.2f}s")
    time.sleep(d)

def safe_click(driver, elem):
    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", elem)
    time.sleep(0.2)
    try: elem.click()
    except: driver.execute_script("arguments[0].click();", elem)
    time.sleep(0.3)

def type_like_human(elem, text):
    for c in text:
        elem.send_keys(c)
        time.sleep(random.uniform(0.03, 0.12))


# ─── Manager ────────────────────────────────────────────────────

class SearchCommentManager:
    def __init__(self, driver, max_posts=5, comment_quota=20):
        self.driver = driver
        self.max_posts = max_posts
        self.quota     = comment_quota
        self.cm        = CommentsManager()
        self.history_ids, self.history_df = load_history()

    def extract_post_id(self, url):
        m = re.search(r'/posts/(\d+)', url)
        return m.group(1) if m else url

    def search_posts(self, keyword):
        # 1) search box
        inp = WebDriverWait(self.driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, SEARCH_INPUT_CSS))
        )
        safe_click(self.driver, inp)
        inp.clear()
        type_like_human(inp, keyword)
        inp.send_keys(Keys.ENTER)
        human_delay(2,4)

        # 2) switch to Posts tab
        try:
            tab = WebDriverWait(self.driver, 8).until(
                EC.element_to_be_clickable((By.XPATH, POSTS_TAB_XPATH))
            )
            safe_click(self.driver, tab)
            human_delay(2,4)
        except TimeoutException:
            logger.warning("Could not click Posts tab")

        # 3) toggle Recent Posts
        try:
            sw = WebDriverWait(self.driver, 6).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, RECENT_SWITCH_CSS))
            )
            if sw.get_attribute("aria-checked") != "true":
                safe_click(self.driver, sw)
                logger.info("✔️ Recent Posts ON")
            else:
                logger.info("ℹ️ Recent Posts already ON")
            human_delay(1,2)
        except TimeoutException:
            logger.warning("No Recent Posts toggle")

        # 4) scroll a bit
        for _ in range(3):
            self.driver.execute_script("window.scrollBy(0,window.innerHeight);")
            human_delay(1,2)

        # collect post-URLs
        anchors = self.driver.find_elements(By.CSS_SELECTOR, "a[href*='/posts/']")
        links   = [a.get_attribute('href') for a in anchors if '/posts/' in a.get_attribute('href')]
        # dedupe and preserve order
        seen = set(); unique = []
        for l in links:
            if l not in seen:
                seen.add(l); unique.append(l)
        return unique

    def open_comment_box(self, post_elem):
        # click that post’s own “Leave a comment”
        try:
            btn = post_elem.find_element(By.CSS_SELECTOR, LEAVE_COMMENT_BTN)
            safe_click(self.driver, btn)
        except NoSuchElementException:
            return None

        # wait for its comment box
        try:
            box = WebDriverWait(post_elem, 5).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, COMMENT_BOX_CSS))
            )
            return box
        except TimeoutException:
            return None

    def run(self):
        # load keywords
        if not os.path.exists(KEYWORDS_FILE):
            logger.error(f"No keywords file: {KEYWORDS_FILE}")
            return
        with open(KEYWORDS_FILE, encoding='utf-8') as f:
            kws = [l.strip() for l in f if l.strip()]
        if not kws:
            logger.error("keywords.txt is empty")
            return

        total_sent = 0
        for kw in kws:
            if total_sent >= self.quota:
                break

            posts = self.search_posts(kw)
            for url in posts:
                if total_sent >= self.quota:
                    break

                post_id = self.extract_post_id(url)
                if post_id in self.history_ids:
                    logger.debug(f"Skipping {post_id} (already done)")
                    continue

                # navigate directly into the feed to click within article
                self.driver.get(url)
                human_delay(2,4)

                # find the article container
                try:
                    art = WebDriverWait(self.driver, 5).until(
                        EC.presence_of_element_located((By.XPATH, POST_ARTICLE_XPATH))
                    )
                except TimeoutException:
                    logger.warning(f"❌ Cannot locate article for {url}")
                    continue

                # open its comment box
                box = self.open_comment_box(art)
                if not box:
                    logger.warning("❌ No comment box")
                    continue

                # type & submit
                comment = self.cm.next_comment()
                type_like_human(box, comment)
                human_delay(0.5,1.2)
                ActionChains(self.driver).send_keys(Keys.ENTER).perform()

                # record it
                ts = datetime.now().isoformat()
                self.history_df.loc[len(self.history_df)] = {
                    'post_id': post_id,
                    'timestamp': ts,
                    'comment': comment
                }
                self.history_ids.add(post_id)
                total_sent += 1
                logger.info(f"✅ [{total_sent}/{self.quota}] “{comment}”")

                # clean up
                human_delay(2,4)
                try:
                    ActionChains(self.driver).send_keys(Keys.ESCAPE).perform()
                except: pass
                human_delay(1,2)

        # done
        save_history(self.history_df)
        logger.info(f"🏁 Finished: sent {total_sent} comments.")
