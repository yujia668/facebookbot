# utils/group_loader.py

import json
from pathlib import Path

def get_groups_for_user(email, path='data/fb_group_url.json'):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        for account in data:
            if account['username'] == email:
                return account['group_url']
    except Exception as e:
        print(f"[!] Error loading groups: {e}")
    return []
