# comment_manager.py

import os
import json
import re

class CommentManager:
    def __init__(self, json_path: str = "data/quotes.json"):
        if not os.path.exists(json_path):
            raise FileNotFoundError(f"Template file not found: {json_path}")
        with open(json_path, "r", encoding="utf-8") as f:
            self.templates = json.load(f)
        # Build a lookup map: id → template string
        self._by_id = {int(t["id"]): t["template"] for t in self.templates}

    def list_templates(self):
        """Print available templates with their IDs."""
        print("Available templates:")
        for tid, tmpl in self._by_id.items():
            print(f"  {tid}. {tmpl}")

    def choose_template(self) -> int:
        """Prompt the user to pick a template ID."""
        self.list_templates()
        while True:
            choice = input("Choose template number: ").strip()
            if choice.isdigit() and int(choice) in self._by_id:
                return int(choice)
            print("❌ Invalid selection, try again.")

    def apply(self, comment: str, mention: str, template_id: int) -> str:
        """
        Apply the chosen template to your comment and mention.
        
        - comment:    your free-form text (can include quotes)
        - mention:    the @username (no quotes around it)
        - template_id: which template ID to use
        """
        if template_id not in self._by_id:
            raise ValueError(f"No template with id {template_id}")

        raw_tmpl = self._by_id[template_id]
        filled = raw_tmpl.format(comment=comment, mention=mention)

        # Clean up any double-quote artifacts:
        #    collapse "" → "
        cleaned = re.sub(r'""+', '"', filled)
        #    remove stray quotes adjacent to @mention
        cleaned = re.sub(r'"@', '@', cleaned)
        cleaned = re.sub(r'@"', '@', cleaned)

        return cleaned


if __name__ == "__main__":
    cm = CommentManager()
    text = input("Enter your comment text: ").strip()
    mention = input("Enter the @mention: ").strip()
    template_id = cm.choose_template()
    result = cm.apply(text, mention, template_id)
    print("\n📝 Final comment:")
    print(result)


from comment_manager import CommentManager

cm = CommentManager("data/quotes.json")
# ask user once which template to use
tmpl_id = cm.choose_template()

# later, whenever you need to format a comment:
comment_text = "I love this feature"
user_mention  = "@alice"
final = cm.apply(comment_text, user_mention, tmpl_id)
# → e.g.  I love this feature"@alice"I love this feature
