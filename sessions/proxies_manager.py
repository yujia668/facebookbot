import threading, queue, os, json, time, requests
from selenium.webdriver.chrome.options import Options

class ProxyManager:
    def __init__(self,
                 proxy_file='data/proxies.txt',
                 per_account_file='data/account_proxies.json'):
        self.proxy_file = proxy_file
        self.per_account_file = per_account_file
        self._load_global_pool()
        self._load_account_map()

    def _load_global_pool(self):
        self.global_pool = []
        if os.path.exists(self.proxy_file):
            with open(self.proxy_file) as f:
                self.global_pool = [line.strip() for line in f if line.strip()]

    def _load_account_map(self):
        if os.path.exists(self.per_account_file):
            with open(self.per_account_file) as f:
                self.account_map = json.load(f)
        else:
            self.account_map = {}

    def _save_account_map(self):
        with open(self.per_account_file, 'w') as f:
            json.dump(self.account_map, f, indent=2)

    def _test_one(self, raw, q):
        try:
            r = requests.get('https://httpbin.org/ip', proxies={'http': raw, 'https': raw},
                             timeout=5)
            if r.status_code == 200:
                q.put(raw)
        except:
            pass

    def _validate_proxies(self, candidates):
        """Returns list of working proxies (may be empty)."""
        q = queue.Queue()
        threads = []
        for p in candidates:
            t = threading.Thread(target=self._test_one, args=(p, q))
            t.daemon = True
            t.start()
            threads.append(t)
        for t in threads:
            t.join()
        good = []
        while not q.empty():
            good.append(q.get())
        return good

    def get_system_proxy(self):
        for env in ('HTTPS_PROXY','HTTP_PROXY','https_proxy','http_proxy'):
            if v := os.environ.get(env):
                return v
        return None

    def choose_manual(self, email=None):
        """Prompt user: either enter custom or direct."""
        print("\n🔸 No working proxies available.  Choose:")
        print(" C) Custom proxy")
        print(" D) Direct connection")
        sel = input("Select (C/D): ").strip().upper()
        if sel == 'C':
            p = input("Enter proxy URL (scheme://host:port): ").strip()
            return p or None
        return None

    def get_proxy_for(self, email):
        """
        1) Try per-account proxy (if set & working)
        2) Else try system proxy + validated global pool
        3) If none works, ask user once for custom or direct
        """
        # 1) per-account override
        acct = self.account_map.get(email)
        if acct:
            good = self._validate_proxies([acct])
            if good:
                return good[0]
            print(f"⚠️ Account proxy failed, falling back: {acct}")

        # 2) system proxy first
        sys_p = self.get_system_proxy()
        candidates = []
        if sys_p:
            candidates.append(sys_p)
        candidates += self.global_pool

        good = self._validate_proxies(candidates)
        if good:
            return good[0]

        # 3) finally prompt once
        return self.choose_manual(email)

    def apply_to_options(self, options: Options, proxy_url: str):
        if not proxy_url:
            print("[ProxyManager] ▶️ Direct (no proxy)")
        else:
            if '://' not in proxy_url:
                proxy_url = 'http://' + proxy_url
            print(f"[ProxyManager] ▶️ Using proxy {proxy_url}")
            options.add_argument(f"--proxy-server={proxy_url}")
