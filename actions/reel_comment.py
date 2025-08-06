# actions/reel_comment.py

import os
import time
import pandas as pd
from datetime import datetime
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from data.comment_manager import CommentsManager
from utils.utils import logger

# ─── CONFIG ────────────────────────────────────────────────────────────────────
REELS_CSV       = 'reels_to_comment.csv'
HISTORY_CSV     = 'reel_comment_history.csv'
DELAY_SECONDS   = 30  # seconds between comments

SELECTORS = {
    'comment_box':    'div[aria-label^="Comment as"]',
    'comment_button': 'div[aria-label="Comment"]'
}


def load_history(path=HISTORY_CSV):
    """Load or initialize history of commented Reels."""
    if os.path.exists(path):
        df = pd.read_csv(path, dtype=str)
        return set(df['reel_url']), df
    return set(), pd.DataFrame(columns=['reel_url', 'comment', 'timestamp'])


def save_history(df, path=HISTORY_CSV):
    df.to_csv(path, index=False)
    logger.info(f"[+] Reel comment history saved ({len(df)}) to {path}")


class ReelCommentManager:
    def __init__(self, driver, max_comments):
        self.driver = driver
        self.max_comments = max_comments
        self.history_urls, self.history_df = load_history()
        self.cm = CommentsManager()
        self.sel = SELECTORS

    def comment_on_reel(self, url, comment_text):
        self.driver.get(url)
        # wait for the comment box, click, type & submit
        box = WebDriverWait(self.driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, self.sel['comment_box']))
        )
        box.click()
        box.send_keys(comment_text)

        btn = WebDriverWait(self.driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, self.sel['comment_button']))
        )
        btn.click()

    def run_for_account(self):
        """
        Reads REELS_CSV, skips any in HISTORY_CSV,
        then auto-pulls comments from CommentsManager until max_comments.
        """
        # load all target URLs
        df = pd.read_csv(REELS_CSV, dtype=str)
        all_urls = [u for u in df['reel_url'].dropna().unique()]

        done = 0
        for url in all_urls:
            if done >= self.max_comments:
                break
            if url in self.history_urls:
                logger.debug(f"[-] Already commented on {url}, skipping.")
                continue

            # get next comment from your CommentsManager
            comment_text = self.cm.next_comment()

            try:
                self.comment_on_reel(url, comment_text)
                ts = datetime.now().isoformat()
                new_entry = {
                    'reel_url': url,
                    'comment': comment_text,
                    'timestamp': ts
                }
                self.history_df = self.history_df.append(new_entry, ignore_index=True)
                self.history_urls.add(url)
                done += 1
                logger.info(f"[+] [{done}/{self.max_comments}] commented on {url}")
            except Exception as e:
                logger.warning(f"[!] Failed to comment on {url}: {e}")

            time.sleep(DELAY_SECONDS)

        save_history(self.history_df)
        logger.info(f"✅ Finished: commented on {done} reels.")


def run(driver, max_comments):
    """
    Top-level entrypoint.
    driver       – an already-logged-in Selenium WebDriver
    max_comments – how many reels you’re allowed to comment on this session
    """
    mgr = ReelCommentManager(driver, max_comments)
    mgr.run_for_account()
