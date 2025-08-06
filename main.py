# main.py

import os, sys
from colorama import Fore, init

from sessions.session_manager import SessionManager
from actions.join_group      import search_groups, join_facebook_groups
from actions.comment_on_search_post import run as open_comment_box
# from actions.comment_on_search import run as comment_in_group
from actions.comment_on_search_post import run as comment_in_group

from actions.group_comment   import comment_Pop
from actions.reel_search     import ReelScraper
from actions.reel_comment    import run as run_for_account
from actions.account_friendlist import FriendListScraper
from actions.account_info      import run as account_info
from actions.reply_comment   import    reply_on_group
from actions.account_basic_details import run as account_summary
from actions.target_user_request import run as send_friend_requests
import sys, logging
from utils.comment_on_search_post import run as comment_on_post 

def clear_screen():
    os.system('cls' if os.name=='nt' else 'clear')

def main():
    init(autoreset=True)

    # suppress urllib3 retry warnings
    logging.getLogger('urllib3').setLevel(logging.ERROR)
    clear_screen()
    print(Fore.MAGENTA + "🎮 Facebook Automation Started\n")

    sm = SessionManager(
        proxy_file='data/proxies.txt',
        accounts_file='data/fb_account_details.json',
    )

    sessions, keywords = sm.run()
    

    for driver, acct, quota, action in sessions:
        email = acct.get("email","").strip()
        print(Fore.CYAN + f"\n➤ {email} — Action {action}  ×  {quota}")

        try:
            if action == "1":         # Join Groups
                joined = 0
                for kw in keywords:
                    if joined >= quota:
                        break
                    if not search_groups(driver, kw):
                        print(Fore.YELLOW + f"   ⚠ No results for '{kw}'")
                        continue
                    urls = join_facebook_groups(
                        driver,
                        acct.get("username", email),
                        max_joins=quota - joined
                    )
                    joined += len(urls)
                print(Fore.GREEN + f"   ✔ Joined {joined}/{quota} groups")

            elif action == "2":       # Search & Comment Posts
                open_comment_box(driver, quota)

            elif action == "3":       # Popup-style Group Comment
                comment_in_group(driver, quota)

            elif action == "4":       # Reel Search
                joined = 0
                for kw in keywords:
                    if joined >= quota:
                        break
                    scraper = ReelScraper(driver, {
                        'search_input': '//*[@aria-label="Search Facebook"]',
                        'reel_link':    'a[href*="/reel/"]'
                    })
                    scraper.max_reels = quota - joined
                    results = scraper.scrape([kw])
                    joined += len(results)
                print(Fore.GREEN + f"   ✔ Collected {joined}/{quota} reels")

            elif action == "5":       # Reel Comment
                 run_for_account(driver, quota)

            elif action == "6":       # Scrape Friend List
                FriendListScraper(driver, quota)

            elif action == "7":       # Scrape Account Info
                account_info(driver, quota)

            elif action == "8":       # Reply Comment
                reply_on_group(driver, quota)

            elif action == "9":       # Basic Account Summary
                account_summary(driver, quota)
            elif action == "10":       # Basic Account Summary
                comment_on_post(driver, quota)
            # … inside your per-session loop …
            elif action == "11":       # Basic Account Summary
                comment_Pop(driver, quota)
            # … inside your per-session loop …
            elif action == "12":  # friend requests
                from actions.target_user_request import run as target_request
                target_request(driver, quota)
                for driver, account, quota, _ in sessions:
                    print(f"\n➤ {account['email']} — sending {quota} friend-requests")
                    send_friend_requests(driver, quota)
                    driver.quit()
            else:
                print(Fore.RED + f"Unknown action: {action}")

        except Exception as e:
            print(Fore.RED + f"[!] Error during action {action} on {email}: {e}")

        finally:
            driver.quit()

    print(Fore.GREEN + "\n✅ All done.\n")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n👋 Exiting…")
        sys.exit(0)
