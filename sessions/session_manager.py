# sessions/session_manager.py

import sys
from colorama import Fore
from sessions.login_json import load_accounts, login_account, update_account_field
from sessions.proxies_manager import ProxyManager

class SessionManager:
    """
    Prompts the user for:
     - how many accounts to use
     - which action to perform
     - total tasks across all accounts
     - (for join-groups) keywords
     - one-time proxy fallback if needed

    Then logs in each account in turn, enforces per-account quotas,
    and returns a list of sessions: (driver, account_dict, quota, action_key).
    """

    # Map action_key → (human label, per-account max)
    ACTIONS = {
        "1": ("Join Groups",        5),
        "2": ("Search & Comment",   10),
        "3": ("Popup Group Comment",10),
        "4": ("Reel Search",        5),
        "5": ("Reel Comment",       5),
        "6": ("Scrape Friend List", 5),
        "7": ("Account Info",        5),
        "8": ("Reply Comment",      5),
        "9": ("Basic Summary",      5),        
        "10": ("target user request", 5),
        "11": ("Comment on post",       5),
        "12": ("comment on group", 10),
        "13": ("Account Info",        5),
        "14": ("Reply Comment",      5),
        "15": ("Basic Summary",      5),       


    }

    def __init__(self,
                 proxy_file   = 'data/proxies.txt',
                 accounts_file= 'data/fb_account_details.json'):
        self.pm       = ProxyManager(proxy_file=proxy_file)
        self.accounts = load_accounts(accounts_file)
        if not self.accounts:
            print(Fore.RED + "❌ No accounts configured.")
            sys.exit(1)

    def prompt(self):
        # 1) How many accounts?
        total_acc = len(self.accounts)
        n = int(input(f"▶️ How many accounts to use [1–{total_acc}]: "))
        if n < 1 or n > total_acc:
            print(Fore.RED + "⚠️ Invalid number of accounts.")
            sys.exit(1)

        # 2) Which action?
        print("\nActions:")
        for key, (label, _) in self.ACTIONS.items():
            print(f"  {key}) {label}")
        action = input("Select action [1–15]: ").strip()
        if action not in self.ACTIONS:
            print(Fore.RED + "⚠️ Invalid action.")
            sys.exit(1)
        label, per_acc_max = self.ACTIONS[action]

        # 3) Total tasks across all accounts
        max_total = per_acc_max * n
        t = int(input(f"▶️ Total '{label}' tasks [1–{max_total}]: "))
        if t < 1 or t > max_total:
            print(Fore.RED + f"⚠️ Must be between 1 and {max_total}.")
            sys.exit(1)

        # 4) If joining groups or reel search, prompt keywords
        keywords = []
        if action in ("1","4"):
            raw = input("▶️ Enter comma-separated keywords: ")
            keywords = [k.strip() for k in raw.split(",") if k.strip()]
            if not keywords:
                print(Fore.RED + "⚠️ Need at least one keyword.")
                sys.exit(1)

        # 5) One-time proxy fallback if global pool empty
        good_globals = self.pm._validate_proxies(self.pm.global_pool)
        fallback = None
        if not good_globals:
            print("\n🔸 No working global proxies found.  Choose:")
            print("  C) Custom proxy   D) Direct (no proxy)")
            c = input("Select C/D: ").strip().upper()
            if c == "C":
                fallback = input("▶️ Enter proxy URL: ").strip()
            else:
                fallback = None
            # remember for all accounts
            print(Fore.CYAN + f"[Fallback proxy] {fallback or 'DIRECT'}\n")

        return n, action, t, keywords, good_globals, fallback

    def run(self):
        n, action, total_tasks, keywords, good_globals, fallback = self.prompt()

        # divide tasks evenly (+1 for the first `rem` accounts)
        per, rem = divmod(total_tasks, n)

        sessions = []
        for idx, acct in enumerate(self.accounts[:n]):
            quota = per + (1 if idx < rem else 0)
            email = acct.get("email","").strip()
            print(Fore.YELLOW + f"[{idx+1}/{n}] {email}  → quota: {quota}")

            # choose proxy_url
            if acct.get("proxy"):
                proxy_url = acct["proxy"]
            elif good_globals:
                proxy_url = good_globals.pop(0)
                # save working global proxy back to account
                update_account_field(email, "proxy", proxy_url)
            else:
                proxy_url = fallback

            # login
            driver, user = login_account(acct, self.pm, proxy_url=proxy_url)
            if not driver:
                print(Fore.RED + f"   ✖ Login failed, skipping.")
                continue
            from sessions.login_json import save_session
            save_session(driver, user)

        sessions.append((driver, user, quota, action))
        return sessions, keywords
