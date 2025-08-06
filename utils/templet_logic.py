import random
import csv

TEMPLATES = {
    "start": "@tag, {comment}",
    "middle": "{start}, @tag, {end}",
    "end": "{comment}, @tag"
}

def validate_template(comment):
    """
    Ensures the comment has exactly one comma to indicate tag placement.
    """
    comma_count = comment.count(",")
    if comma_count != 1:
        raise ValueError(f"Invalid template: must contain exactly one comma → {comment}")

def prompt_template_selection():
    """
    Prompts the user to choose one of the available tag templates.
    """
    while True:
        print("\n[🧩] Choose a tag placement template:")
        for i, (key, val) in enumerate(TEMPLATES.items(), 1):
            if key == "start":
                example = "@amina, I love this group"
            elif key == "middle":
                example = "She is wonderful, @amina, and loyal"
            elif key == "end":
                example = "I really love this group, @amina"
            print(f"{i}. {key.upper()} → {example}")
        
        choice = input("Enter your choice number (1–3): ").strip()
        if choice in ['1', '2', '3']:
            return list(TEMPLATES.keys())[int(choice) - 1]
        print("❌ Invalid input. Please enter 1, 2, or 3.")


def format_comment_with_tag(comment, tag, template_choice):
    """
    Insert tag into comment based on selected template.
    """
    validate_template(comment)

    if template_choice == "start":
        return f"@{tag} {comment.replace(',', '')}".strip()
    elif template_choice == "end":
        return f"{comment.replace(',', '')} @{tag}".strip()
    elif template_choice == "middle":
        parts = comment.split(",", 1)
        return f"{parts[0].strip()} @{tag} {parts[1].strip()}".strip()
    else:
        raise ValueError(f"Invalid template: {template_choice}")


def get_random_comment(path="data/comments.csv"):
    """
    Loads random comment from CSV file.
    """
    with open(path, encoding="utf-8") as f:
        reader = csv.reader(f)
        comments = [row[0].strip() for row in reader if row]
    return random.choice(comments)


def get_random_tag(path="data/tag.txt"):
    """
    Loads random tag from TXT file.
    """
    with open(path, encoding="utf-8") as f:
        tags = [line.strip().lstrip("@") for line in f if line.strip()]
    return random.choice(tags)


def get_formatted_comment(template_choice):
    """
    Generates one final formatted comment using a template.
    """
    comment = get_random_comment()
    tag = get_random_tag()
    return format_comment_with_tag(comment, tag, template_choice)

