import os
import time
import json
import random
import logging

from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

# === Logging Setup ===
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("ReplyComment")


# === Helpers ===
def wait(min_sec=1, max_sec=2):
    time.sleep(random.uniform(min_sec, max_sec))

def load_comments(filepath="data/comments.csv"):
    if not os.path.exists(filepath):
        logger.error("❌ comments.csv not found.")
        return []
    with open(filepath, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]

def parse_reply_with_tag(text):
    if '@' not in text:
        return text, None, None
    before, tag_and_rest = text.split('@', 1)
    if ',' in tag_and_rest:
        tag, after = tag_and_rest.split(',', 1)
    else:
        tag, after = tag_and_rest, ""
    return before.strip(), tag.strip(), after.strip()

def human_typing(element, message):
    for char in message:
        element.send_keys(char)
        time.sleep(random.uniform(0.04, 0.1))

def click_and_focus(driver, element):
    driver.execute_script("""
        arguments[0].scrollIntoView({block: 'center'});
        arguments[0].focus();
        const evt = new Event('focus', { bubbles: true });
        arguments[0].dispatchEvent(evt);
    """, element)
    time.sleep(1)
    try:
        element.click()
    except:
        driver.execute_script("arguments[0].click();", element)
    time.sleep(1)

def locate_reply_box(driver):
    try:
        return WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR,
                "div[role='textbox'][contenteditable='true'][aria-label^='Reply to '][data-lexical-editor='true']"))
        )
    except Exception as e:
        logger.warning(f"⚠️ Could not locate reply box: {e}")
        return None

def click_submit_reply_button(driver):
    try:
        submit_btn = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "div[role='button'][aria-label='Comment']"))
        )
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", submit_btn)
        time.sleep(1)
        try:
            submit_btn.click()
        except:
            driver.execute_script("arguments[0].click();", submit_btn)

        logger.info("✅ Clicked submit comment button.")
        return True
    except Exception as e:
        logger.warning(f"❌ Failed to click submit comment button: {e}")
        return False

def reply_with_tag(driver, full_text):
    box = locate_reply_box(driver)
    if not box:
        logger.warning("❌ Reply box not found.")
        return False

    click_and_focus(driver, box)
    before, tag, after = parse_reply_with_tag(full_text)

    try:
        if tag:
            human_typing(box, before + " @" + tag)
            time.sleep(2)
            box.send_keys(Keys.ARROW_DOWN)
            time.sleep(1)
            box.send_keys(Keys.ENTER)
            if after:
                box.send_keys(" " + after)
        else:
            human_typing(box, full_text)

        time.sleep(1)
        box.send_keys(Keys.ENTER)

        logger.info(f"✅ Replied: {full_text}")
        return True

    except Exception as e:
        logger.warning(f"❌ Failed to type reply: {e}")
        return False

def reply_to_comment(driver, reply_button, comment_text):
    try:
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", reply_button)
        wait()
        reply_button.click()
        logger.info("✅ Clicked reply button")

        if not reply_with_tag(driver, comment_text):
            return False
        return click_submit_reply_button(driver)

    except Exception as e:
        logger.warning(f"⚠️ Skipped reply due to: {e}")
        return False


# === Main group logic ===
def reply_on_group(driver, group_url, comments):
    try:
        driver.get(group_url)
        logger.info(f"🌐 Visiting group: {group_url}")
        wait(5, 7)

        for _ in range(random.randint(3, 5)):
            driver.execute_script("window.scrollBy(0, 1000);")
            wait(1, 2)

        reply_buttons = driver.find_elements(By.XPATH, "//div[@role='button' and text()='Reply']")
        logger.info(f"💬 Found {len(reply_buttons)} reply buttons")

        if not reply_buttons:
            logger.warning("⚠️ No reply buttons found.")
            return

        num_replies = min(len(reply_buttons), random.randint(1, 3))
        for i in range(num_replies):
            comment_text = random.choice(comments)
            reply_to_comment(driver, reply_buttons[i], comment_text)
            wait(2, 4)

    except Exception as e:
        logger.warning(f"❌ Error in group {group_url}: {e}")


# === Public Entrypoint ===


