import time, logging, random, json
import pandas as pd
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("GroupComment")

MAX_COMMENTS_PER_GROUP = 10


def get_random_comment(path="data/comments.csv"):
    try:
        df = pd.read_csv(path, header=None)
        comments = [c for c in df[0].dropna().tolist() if c.strip()]
        return random.choice(comments)
    except Exception as e:
        logger.warning(f"[!] Could not load comments: {e}")
        return "Great post!"


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
            logger.info("✅ Clicked 'Leave a comment' with JS")
            return True
        else:
            logger.warning("❌ JS could not find comment button")
            return False
    except Exception as e:
        logger.warning(f"❌ JS click failed: {e}")
        return False


def get_groups_for_user(email, path="data/fb_group_url.json"):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        for entry in data:
            if entry.get("username") == email:
                return entry.get("group_url", [])
    except Exception as e:
        logger.error(f"[!] Error loading group URL JSON: {e}")
    return []


def scroll_to_load_posts(driver, scrolls=3):
    logger.info("[↓] Scrolling to load group posts...")
    for _ in range(scrolls):
        driver.execute_script("window.scrollBy(0, window.innerHeight);")
        time.sleep(random.uniform(2.5, 3.5))


def click_comment_button(post, driver):
    try:
        button = post.find_element(By.XPATH, ".//div[@role='button' and @aria-label='Leave a comment']")
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", button)
        time.sleep(1)
        try:
            button.click()
        except:
            driver.execute_script("arguments[0].click();", button)
        logger.info("✅ Clicked 'Leave a comment'")
        return True
    except Exception:
        return click_comment_button_js(driver)


def type_comment(driver, text):
    try:
        comment_box = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "div[aria-label^='Comment as']"))
        )
        comment_box.click()
        comment_box.send_keys(text)
        logger.info("[✓] Comment typed successfully.")
        return True
    except Exception as e:
        logger.error(f"[!] Failed to type comment: {e}")
        return False


def submit_comment(driver):
    try:
        ActionChains(driver).send_keys(Keys.ENTER).perform()
        logger.info("[✓] Comment submitted with ENTER")
        return True
    except Exception as e:
        logger.warning(f"[!] Failed ENTER submit: {e}")
    return False


def close_comment_dialog(driver):
    try:
        close_btn = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "div[aria-label='Close'][role='button']"))
        )
        close_btn.click()
        logger.info("[✓] Closed comment dialog")
        return True
    except Exception as e:
        logger.warning(f"[!] Failed to close dialog: {e}")
        return False


def comment_n_groups(driver, acc, group_url, max_comments=10):
    logger.info(f"[→] Visiting group: {group_url}")
    driver.get(group_url)
    time.sleep(6)  # Let the page load

    scroll_to_load_posts(driver, scrolls=5)

    posts = driver.find_elements(By.XPATH, "//div[@role='article']")
    logger.info(f"[+] Found {len(posts)} posts to potentially comment on.")

    count = 0
    for post in posts:
        if count >= max_comments:
            break

        try:
            text = get_random_comment()  # Get comment first

            if click_comment_button(post, driver):
                if type_comment(driver, text):
                    submit_comment(driver)
                    time.sleep(random.uniform(2, 4))
                    ActionChains(driver).send_keys(Keys.ESCAPE).perform()

                    count += 1
                    time.sleep(random.uniform(5, 9))  # Wait before next
        except Exception as e:
            logger.warning(f"[!] Skipping post due to error: {e}")
            continue

    logger.info(f"[→] Finished {count}/{max_comments} comments in group.")


def run(driver, acc):
    try:
        email = acc.get("fbemail") or acc.get("email")
        logger.info(f"[🟢] Running group comment bot for {email}")

        groups = get_groups_for_user(email)
        if not groups:
            logger.warning(f"[!] No groups found for {email}")
            return

        for group_url in groups:
            try:
                comment_n_groups(driver, acc, group_url, max_comments=MAX_COMMENTS_PER_GROUP)
            except Exception as e:
                logger.error(f"[!] Error in group {group_url}: {e}")
            time.sleep(10)

    except Exception as e:
        logger.critical(f"[❌] Bot failed for account: {e}")


def comment_Pop(proxy_manager):
    from sessions.login import load_accounts, login_account
    df, accounts = load_accounts('data/login_details.csv')

    for acc in accounts:
        driver, acc = login_account(acc, proxy_manager)
        if not driver:
            continue
        run(driver, acc)
        driver.quit()
