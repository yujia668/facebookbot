# data/comment_manager.py

import os
import random
import re

TEMPLATES_FILE = "data/comments.txt"   # lines containing exactly one pair of ""
MENTIONS_FILE  = "data/mentions.txt"   # each line is a username, e.g. mrabu

class CommentsManager:
    def __init__(self):
        # 1) load templates that have exactly one pair of quotes
        if not os.path.exists(TEMPLATES_FILE):
            raise FileNotFoundError(f"Missing {TEMPLATES_FILE}")
        raw = [line.strip() for line in open(TEMPLATES_FILE, encoding="utf-8") if line.strip()]
        self.templates = []
        for t in raw:
            # count literal double-quote characters
            if t.count('"') != 2:
                continue
            # we expect them to be adjacent: ""
            if '""' not in t:
                continue
            self.templates.append(t)
        if not self.templates:
            raise ValueError("No valid templates with exactly one \"\" placeholder found")
        
        # 2) load mentions
        if not os.path.exists(MENTIONS_FILE):
            raise FileNotFoundError(f"Missing {MENTIONS_FILE}")
        self.mentions = [m.strip() for m in open(MENTIONS_FILE, encoding="utf-8") if m.strip()]
        if not self.mentions:
            raise ValueError("No mentions found in mention.txt")

        # simple round-robin
        self._i = 0

    def next_comment(self):
        # pick template and mention in lock-step (or random.choice if you prefer)
        tpl = self.templates[self._i % len(self.templates)]
        mention = self.mentions[self._i % len(self.mentions)]
        self._i += 1

        # replace placeholder with @mention
        # tpl has exactly one '""'
        comment = tpl.replace('""', f"@{mention}")
        return comment
