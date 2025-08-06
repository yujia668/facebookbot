# actions/account_summary.py

from sessions.login_json     import load_accounts, login_account
from sessions.proxies_manager import ProxyManager
from actions.account_info import log_and_get_account_details

def run(proxy_manager: ProxyManager):
    df, accounts = load_accounts("data/login_details.csv")

    if not accounts:
        print("❌ No accounts found.")
        return

    for acc in accounts:
        driver, acc = login_account(acc, proxy_manager)
        if not driver:
            print(f"⚠️ Skipping login for {acc.get('email')}")
            continue

        try:
            details = log_and_get_account_details(driver)
            print(f"\n📄 Account Info for {acc.get('email')}:\n")
            for key, value in details.items():
                print(f"  {key}: {value}")
        finally:
            driver.quit()

    print("\n✅ All accounts processed.")
