import os
import time
import random

from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

from data.comment_manager import CommentsManager
from utils.utils import logger

# ─── Constants ────────────────────────────────────────────────

SEARCH_INPUT_CSS = 'input[aria-label="Search Facebook"]'
POSTS_TAB_XPATH = '//a[contains(@href,"/search/posts") and contains(.,"Posts")]'
RECENT_SWITCH_CSS = 'input[role="switch"][aria-label="Recent Posts"]'
KEYWORDS_FILE = 'data/keywords.txt'
COMMENT_BOX_CSS = 'div[aria-label="Write a comment…"][contenteditable="true"]'

# ─── Human-like Behavior ──────────────────────────────────────

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

def safe_click(driver, elem):
    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", elem)
    time.sleep(0.2)
    try:
        elem.click()
    except:
        driver.execute_script("arguments[0].click();", elem)
    time.sleep(0.2)

def safe_type(elem, text):
    for ch in text:
        elem.send_keys(ch)
        time.sleep(0.02)

# ─── Comment Box Handling ─────────────────────────────────────

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

def open_comment_box(driver):
    try:
        button = driver.find_element(By.CSS_SELECTOR, "div[aria-label='Leave a comment']")
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", button)
        human_delay(2, 4)
        button.click()
        logger.info("✅ Clicked 'Leave a comment'")
    except Exception:
        if not click_comment_button_js(driver):
            return None

    try:
        comment_box = WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, COMMENT_BOX_CSS))
        )
        return comment_box
    except TimeoutException:
        logger.warning("❌ Could not find comment input box after clicking.")
        return None

def submit_comment(driver):
    try:
        ActionChains(driver).send_keys(Keys.ENTER).perform()
        logger.info("[✓] Comment submitted")
        return True
    except Exception as e:
        logger.warning(f"[!] Submit failed: {e}")
        return False

# ─── Main Execution ───────────────────────────────────────────

def run(driver, count):
    if not os.path.exists(KEYWORDS_FILE):
        print(f"[!] Missing keywords file: {KEYWORDS_FILE}")
        return

    with open(KEYWORDS_FILE, encoding='utf-8') as f:
        keywords = [l.strip() for l in f if l.strip()]

    if not keywords:
        print("[!] No keywords in keywords.txt")
        return

    cm = CommentsManager()
    sent = 0

    for kw in keywords:
        if sent >= count:
            break

        try:
            inp = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, SEARCH_INPUT_CSS))
            )
            safe_click(driver, inp)
            safe_type(inp, kw)
            inp.send_keys(Keys.ENTER)
            time.sleep(4)
        except Exception as e:
            print(f"[!] Search failed for '{kw}': {e}")
            continue

        try:
            tab = WebDriverWait(driver, 8).until(
                EC.element_to_be_clickable((By.XPATH, POSTS_TAB_XPATH))
            )
            safe_click(driver, tab)
            time.sleep(4)
        except Exception as e:
            print(f"[!] Could not switch to Posts tab: {e}")

        try:
            toggle = WebDriverWait(driver, 6).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, RECENT_SWITCH_CSS))
            )
            if toggle.get_attribute("aria-checked") != "true":
                driver.execute_script("arguments[0].scrollIntoView({block:'center'});", toggle)
                driver.execute_script("arguments[0].click();", toggle)
                print("✔️ Toggled “Recent posts” on")
            else:
                print("ℹ️ “Recent posts” already on")
        except TimeoutException:
            print("⚠️ Could not find “Recent posts” toggle.")

        time.sleep(4)
        driver.execute_script("window.scrollTo(0, 0);")

        for _ in range(4):
            driver.execute_script("window.scrollBy(0, window.innerHeight);")
            time.sleep(random.uniform(2, 3))

        posts = driver.find_elements(By.XPATH, "//div[@role='article']")

        for post in posts:
            try:
# Optional fallback or first try
                clicked = click_comment_button_js(post)
                if not clicked:
                    try:
                        comment_btn = post.find_element(By.XPATH, ".//div[@role='button' and contains(@aria-label,'Leave a comment')]")
                        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", comment_btn)
                        human_delay(2, 4)
                        comment_btn.click()
                    except Exception as e:
                        print(f"[!] Could not find standard comment button: {e}")
                        continue

                human_delay(2, 4)
                comment_btn.click()

                try:
                    comment = cm.next_comment()
                    safe_type(comment_box, comment)
                    comment_box.send_keys(Keys.ENTER)
                except:
                    comment_box = WebDriverWait(post, 5).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, COMMENT_BOX_CSS))
                    )

                comment = cm.next_comment()
                safe_type(comment_box, comment)
                comment_box.send_keys(Keys.ENTER)

                sent += 1
                print(f"✔️ [{sent}/{count}] “{comment}”")
                time.sleep(5)

                try:
                    close_btn = WebDriverWait(driver, 5).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, "div[aria-label='Close'][role='button']"))
                    )
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", close_btn)
                    try:
                        close_btn.click()
                    except:
                        driver.execute_script("arguments[0].click();", close_btn)
                    logger.info("✅ Closed comment popup")
                    return True
                except Exception as e:
                    logger.warning(f"⚠️ Could not close comment popup: {e}")
                    return False
                except:
                    pass

                if sent >= count:
                    break

            except Exception as e:
                print(f"[!] Failed to comment on a post: {e}")
                continue
