import os
import sys
import time
import threading
import requests
from selenium.webdriver.chrome.options import Options

# -----------------------------------------------------------------------------
# Module: proxy_manager.py
# Purpose: Load, test, and apply SOCKS4/5 and HTTP(S) proxies for Selenium
# -----------------------------------------------------------------------------

PROXY_FILE = 'proxies.txt'

class ProxyManager:
    def __init__(self, proxy_file=PROXY_FILE):
        self.proxy_file = proxy_file
        self.proxies = self._load_proxies()

    def _load_proxies(self):
        """
        Read proxies.txt, return list of proxy URL strings.
        Each line in proxies.txt should be a valid proxy URL, e.g.: 
          socks5://user:pass@host:port
          http://host:port
          https://host:port
          socks4://host:port
        Lines starting with # or blank are ignored.
        """
        if not os.path.exists(self.proxy_file):
            return []

        proxies = []
        with open(self.proxy_file, 'r') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                proxies.append(line)
        return proxies

    def get_system_proxy(self):
        """
        Return system proxy from environment variables, or None.
        """
        for env in ('HTTPS_PROXY', 'HTTP_PROXY', 'https_proxy', 'http_proxy'):
            val = os.environ.get(env)
            if val:
                return val
        return None

    def test_proxy(self, proxy_url, timeout=5):
        """
        Quickly test if proxy is working by fetching httpbin.org/ip
        Returns True if successful, False otherwise.
        """
        try:
            resp = requests.get('https://httpbin.org/ip', proxies={'http': proxy_url, 'https': proxy_url}, timeout=timeout)
            return resp.status_code == 200
        except Exception:
            return False

    def list_proxies(self, include_system=True):
        """
        Return available proxies with optional system proxy at index 0.
        """
        items = []
        if include_system:
            sys_proxy = self.get_system_proxy()
            if sys_proxy:
                items.append(('SYSTEM', sys_proxy))
        for idx, p in enumerate(self.proxies, start=1 if include_system and self.get_system_proxy() else 0):
            items.append((str(idx), p))
        return items

    def choose_proxy(self):
        """
        Prompt user to select a proxy or enter custom.
        Returns chosen proxy URL string or None for direct.
        """
        items = self.list_proxies()
        print("Available proxies:")
        for key, proxy in items:
            print(f" {key}) {proxy}")
        print(" C) Enter custom proxy URL")
        print(" N) No proxy (direct connection)")

        choice = input("Select proxy key: ").strip()
        if choice.upper() == 'N':
            return None
        if choice.upper() == 'C':
            return input("Enter proxy URL: ").strip() or None
        for key, proxy in items:
            if key == choice:
                return proxy
        print("Invalid selection, using direct connection.")
        return None

    def apply_to_options(self, options: Options, proxy_url: str):
        """
        Given a Selenium Chrome Options object, apply the proxy setting.
        """
        if not proxy_url:
            print("[ProxyManager] No proxy, direct connection.")
            return

        # prepend protocol if missing
        if '://' not in proxy_url:
            proxy_url = 'http://' + proxy_url

        print(f"[ProxyManager] Applying proxy: {proxy_url}")
        options.add_argument(f'--proxy-server={proxy_url}')

# Example usage:
# pm = ProxyManager()
# proxy_url = pm.choose_proxy()
# chrome_opts = webdriver.ChromeOptions()
# pm.apply_to_options(chrome_opts, proxy_url)
# driver = webdriver.Chrome(options=chrome_opts)
