# actions/join_group.py

import os
import json
import time
import logging
from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

logger = logging.getLogger("JoinGroups")
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Where we store, per-user, which group URLs have already been joined
ACCOUNTS_PATH = "data/fb_group_url.json"


def _persist_group_urls(username, new_urls):
    """
    Internal: load or initialize ACCOUNTS_PATH, append any new_urls for this username,
    then write back.
    """
    if os.path.exists(ACCOUNTS_PATH):
        try:
            with open(ACCOUNTS_PATH, "r", encoding="utf-8") as f:
                accounts = json.load(f)
        except json.JSONDecodeError:
            accounts = []
    else:
        accounts = []

    rec = next((r for r in accounts if r.get("username") == username), None)
    if rec is None:
        rec = {"username": username, "group_url": []}
        accounts.append(rec)
        logger.info(f"🆕 Created record for {username}")

    existing = set(rec.get("group_url", []))
    to_add = [u for u in new_urls if u not in existing]
    if to_add:
        rec["group_url"].extend(to_add)
        logger.info(f"✅ Persisting {len(to_add)} new groups for {username}")
    else:
        logger.info(f"ℹ️ No new groups to add for {username}")

    os.makedirs(os.path.dirname(ACCOUNTS_PATH), exist_ok=True)
    with open(ACCOUNTS_PATH, "w", encoding="utf-8") as f:
        json.dump(accounts, f, indent=2)
    logger.debug(f"💾 Wrote accounts to {ACCOUNTS_PATH}")


class JoinGroupManager:
    def __init__(self, driver, username, max_joins=10):
        """
        :param driver:    logged-in Selenium WebDriver
        :param username:  string key used in ACCOUNTS_PATH
        :param max_joins: how many groups to join this run
        """
        self.driver = driver
        self.username = username
        self.max_joins = max_joins

    def search_groups(self, search_term):
        """
        Search Facebook for group pages matching `search_term`.
        Returns True if the results UI appeared, False on error.
        """
        try:
            inp = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, '//*[@aria-label="Search Facebook"]'))
            )
            inp.click()
            time.sleep(1)
            inp.send_keys(search_term, Keys.ENTER)
            logger.info(f"🔍 Searching for groups: '{search_term}'")
        except TimeoutException:
            logger.error("❌ Could not find the Facebook search bar")
            return False

        try:
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.XPATH, '//a[contains(@href, "/groups/")]'))
            )
            logger.info("📋 Group search results loaded")
        except TimeoutException:
            logger.warning("⚠️ No group results detected")

        # Optional “See all” if it exists
        try:
            see_all = WebDriverWait(self.driver, 5).until(
                EC.element_to_be_clickable(( By.XPATH, '//a/div[contains(., "See all")]'))
            )
            see_all.click()
            logger.info("📄 Clicked ‘See all’ to expand groups list")
            time.sleep(2)
        except TimeoutException:
            logger.debug("ℹ️ No ‘See all’ button present")

        return True

    def join_groups(self):
        """
        Scroll through the loaded group search results, click up to max_joins “Join” buttons,
        and persist each joined group's URL. Returns list of joined URLs.
        """
        joined = []
        count = 0
        scrolls = 0

        while count < self.max_joins and scrolls < 10:
            # scroll to load more groups
            self.driver.execute_script("window.scrollBy(0, document.body.scrollHeight);")
            time.sleep(2)
            scrolls += 1

            # parse current page
            soup = BeautifulSoup(self.driver.page_source, "html.parser")
            links = [
                a["href"].split("?")[0]
                for a in soup.find_all("a", href=True)
                if a["href"].split("?")[0].startswith("https://web.facebook.com/groups/")
            ]
            unique_links = list(dict.fromkeys(links))

            # find and click Join buttons
            buttons = self.driver.find_elements(
                By.XPATH,
                '//span[text()="Join"]/ancestor::div[@role="button"]'
            )
            logger.info(f"🔘 Found {len(buttons)} Join buttons (joined so far: {count})")

            for btn in buttons:
                if count >= self.max_joins:
                    break
                try:
                    self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", btn)
                    self.driver.execute_script("arguments[0].click();", btn)
                    logger.info(f"➕ Joined group #{count+1}")
                    time.sleep(5)

                    # record URL
                    if count < len(unique_links):
                        url = unique_links[count]
                        joined.append(url)
                        _persist_group_urls(self.username, [url])
                        count += 1
                except Exception as e:
                    logger.warning(f"⚠️ Failed to click Join #{count+1}: {e}")

        logger.info(f"✅ Joined total: {count}/{self.max_joins}")
        return joined


def search_groups(driver, search_term):
    """
    Free function for main.py:
      returns True if group‐search UI is up, False on failure.
    """
    mgr = JoinGroupManager(driver, username=None, max_joins=0)
    return mgr.search_groups(search_term)


def join_facebook_groups(driver, username, max_joins=10):
    """
    Free function for main.py:
      attempts to join up to `max_joins` groups, returns list of joined URLs.
    """
    mgr = JoinGroupManager(driver, username=username, max_joins=max_joins)
    return mgr.join_groups()

