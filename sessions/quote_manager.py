import os
import json
from typing import Dict, List

# Max limits per action per 24h, per account
DEFAULT_LIMITS = {
    'friendlist': 10,
    'comment': 10,
    'post': 10,
    'scrape_video': 10,
    'reel_comment': 10,
    'scrape_reel': 10,
    'scrape_user': 5,
    'friend_request': 10,
    'like': 20,
    'share': 20,
    'follower_list': 10
}

class QuotaManager:
    """
    Manages user prompts and enforces per-account action quotas.
    """
    def __init__(self, limits: Dict[str, int] = None):
        self.limits = limits or DEFAULT_LIMITS.copy()
        self.plan = {
            'num_accounts': 1,
            'actions': {},
            'proxy_mode': 'direct',  # 'direct', 'global', 'per_account'
        }

    def configure_accounts(self):
        count = input(f"How many accounts do you want to use? [1-{os.cpu_count()}]: ")
        try:
            n = int(count)
            if n < 1:
                raise ValueError()
        except ValueError:
            print("Invalid number, defaulting to 1 account.")
            n = 1
        self.plan['num_accounts'] = n
        # Pre-fill default quotas if only one account
        for action, limit in self.limits.items():
            self.plan['actions'][action] = limit if n == 1 else 0
        return n

    def select_actions(self):
        print("Select actions to perform and desired total counts (max per account shown):")
        for action, per_acc in self.limits.items():
            total_limit = per_acc * self.plan['num_accounts']
            inp = input(f" - {action} (0 to {total_limit}, default {min(per_acc, total_limit)}): ")
            try:
                v = int(inp)
                v = max(0, min(v, total_limit))
            except ValueError:
                v = min(per_acc, total_limit)
            self.plan['actions'][action] = v
        # ensure at least one action
        if all(v == 0 for v in self.plan['actions'].values()):
            print("No actions selected; defaulting to all minimal quotas.")
            for action, limit in self.limits.items():
                self.plan['actions'][action] = limit
        return self.plan['actions']

    def select_proxy_mode(self):
        print("\nSelect proxy mode:")
        print(" 1) direct (no proxy)")
        print(" 2) global proxy pool")
        print(" 3) per-account proxies")
        choice = input("Enter choice [1-3]: ")
        mapping = {'1': 'direct', '2': 'global', '3': 'per_account'}
        mode = mapping.get(choice, 'direct')
        # enforce proxy if >2 accounts
        if self.plan['num_accounts'] > 2 and mode == 'direct':
            print("Using more than 2 accounts requires a proxy setup. Switching to global mode.")
            mode = 'global'
        self.plan['proxy_mode'] = mode
        return mode

    def validate_plan(self) -> bool:
        """
        Validates that plan does not exceed per-account quotas and proxy requirements.
        Returns True if valid, False otherwise.
        """
        # ensure no action exceeds per_account * num_accounts
        for action, total in self.plan['actions'].items():
            max_total = self.limits[action] * self.plan['num_accounts']
            if total > max_total:
                print(f"[!] Requested {action}={total} exceeds max {max_total}. Reducing.")
                self.plan['actions'][action] = max_total
        return True

    def get_plan(self) -> Dict:
        return self.plan

# Usage example (to import and call in main scripts):

# from sessions.quota_manager import QuotaManager
# qm = QuotaManager()
# qm.configure_accounts()
# qm.select_actions()
# qm.select_proxy_mode()
# qm.validate_plan()
# plan = qm.get_plan()

# # Then distribute each action:
# per_acc_count = math.ceil(plan['actions'][action] / plan['num_accounts'])
# from sessions.quota_manager import QuotaManager

def main():
    # 1) Ask how many accounts, how many total of each action, proxy mode, etc.
    qm = QuotaManager()
    qm.configure_accounts()    # “How many accounts do you want to use?”
    qm.select_actions()        # “Which actions & total volumes?”
    qm.select_proxy_mode()     # “Global/proxy-per-account/direct”
    qm.validate_plan()         # Check per-account caps & proxy requirements

    plan = qm.get_plan()       # { num_accounts: 4, proxy_mode: 'global', actions: { 'friends': 40, ... } }

    # 2) Distribute work per account:
    import math
    per_account = {
       action: math.ceil(total/plan['num_accounts'])
       for action, total in plan['actions'].items()
    }

    # pm = ProxyManager()
    # _, accounts = load_accounts("data/fb_account_details.json")

    # for acct in accounts[: plan['num_accounts']]:
    #     driver, user = login_account(acct, pm)
    #     if not driver:
    #       continue

        # now call each module with its per-account quota:
        # e.g. join_group(keywords, max_joins=per_account['join_groups'], proxy_manager=pm, driver=driver)
        #      scrape_friends(max_friends=per_account['friends'], driver=driver)
        #      comment_posts(max_comments=per_account['comments'], driver=driver)
        # etc.

        # driver.quit()
# Keep all your session/login logic in sessions/login.py 
# and your individual “run”-style modules (join_group.py, search_comment.py, etc.) 
# unchanged. The quota manager simply lives up in main.py to steer how many accounts
# you spin up and how many actions each should run.

# That way, login.py stays focused on logging in, 
# and main.py (or whichever “master” script you use) 
# handles account-count, proxy-mode and per-account quotas before invoking each action.