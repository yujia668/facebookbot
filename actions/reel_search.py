# actions/reel_search.py

import os
import time
import pandas as pd
from datetime import datetime
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup

# -----------------------------------------------------------------------
# Module: reel_search.py
# Purpose: For each keyword (from data/keywords.txt) search FB Reels,
#          dedupe via history, save new ones to history + results CSVs.
# -----------------------------------------------------------------------

HISTORY_PATH = 'reel_history.csv'
RESULTS_PATH = 'reel_results.csv'
KEYWORDS_FILE = 'data/keywords.txt'

SELECTORS = {
    'search_input': '//*[@aria-label="Search Facebook"]',
    'reel_link':    'a[href*="/reel/"]'
}


def load_history(path=HISTORY_PATH):
    if os.path.exists(path):
        df = pd.read_csv(path, dtype=str)
        return set(df['reel_id']), df
    return set(), pd.DataFrame(columns=['reel_id', 'timestamp'])


def save_history(df, path=HISTORY_PATH):
    df.to_csv(path, index=False)
    print(f"[+] Reel history updated ({len(df)}) → {path}")


class ReelScraper:
    def __init__(self, driver, max_reels=50, delay_seconds=2):
        self.driver = driver
        self.max_reels = max_reels
        self.delay = delay_seconds
        self.history_ids, self.history_df = load_history()

    def extract_reel_id(self, url):
        return url.rstrip('/').split('/')[-1]

    def search_reels(self, keyword):
        self.driver.get('https://www.facebook.com')
        inp = WebDriverWait(self.driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, SELECTORS['search_input']))
        )
        inp.click()
        inp.clear()
        inp.send_keys(keyword, Keys.ENTER)
        time.sleep(self.delay)

        found = set()
        last_h = self.driver.execute_script("return document.body.scrollHeight")

        while len(found) < self.max_reels:
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            for a in soup.select(SELECTORS['reel_link']):
                href = a.get('href')
                if href and '/reel/' in href:
                    full = href if href.startswith('http') else f"https://www.facebook.com{href}"
                    found.add(full)
                    if len(found) >= self.max_reels:
                        break

            # scroll to load more
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(self.delay)
            new_h = self.driver.execute_script("return document.body.scrollHeight")
            if new_h == last_h:
                break
            last_h = new_h

        return list(found)

    def scrape(self, keywords):
        results = []
        collected = 0

        for kw in keywords:
            print(f"--- Searching Reels for: {kw} ---")
            urls = self.search_reels(kw)

            for url in urls:
                if collected >= self.max_reels:
                    break
                rid = self.extract_reel_id(url)
                if rid in self.history_ids:
                    print(f"[-] Skipping old reel {rid}")
                    continue

                ts = datetime.utcnow().isoformat()
                self.history_df.loc[len(self.history_df)] = {
                    'reel_id':  rid,
                    'timestamp': ts
                }
                self.history_ids.add(rid)

                results.append({
                    'keyword':   kw,
                    'reel_id':   rid,
                    'reel_url':  url,
                    'timestamp': ts
                })
                collected += 1
                print(f"[+] Collected {rid} ({collected}/{self.max_reels})")
                time.sleep(self.delay)

            if collected >= self.max_reels:
                break

        # persist
        save_history(self.history_df)
        pd.DataFrame(results).to_csv(RESULTS_PATH, index=False)
        print(f"[+] Saved {len(results)} new reels → {RESULTS_PATH}")
        return results

    # alias so SessionManager can do: scraper = ReelScraper(...); scraper.run(...)
    run = scrape


def run(driver, count):
    """
    Entry point for SessionManager:
      - Reads up to `count` keywords from data/keywords.txt
      - Instantiates ReelScraper with max_reels=count
      - Returns the list of collected reels
    """
    if not os.path.exists(KEYWORDS_FILE):
        print(f"[!] Missing keywords file: {KEYWORDS_FILE}")
        return []

    with open(KEYWORDS_FILE, encoding='utf-8') as f:
        keywords = [l.strip() for l in f if l.strip()]

    if not keywords:
        print("[!] No keywords found in keywords.txt")
        return []

    scraper = ReelScraper(driver, max_reels=count)
    return scraper.scrape(keywords)
