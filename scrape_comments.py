import requests
import pandas as pd
import time
import re

INPUT_FILE = "male_dating_final.csv"
OUTPUT_FILE = "male_dating_comments.csv"

MIN_COMMENT_SCORE = 5
TOP_N_POSTS = 80          # scrape top N posts by relevance score
MAX_COMMENTS_PER_POST = 50

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; research-scraper/1.0)"}

# Map keywords to JTBD theme names
JTBD_THEMES = [
    ("Breaking the inexperience loop",          [r"no experience", r"inexperienced", r"never dated", r"never had.{0,10}girlfriend", r"red flag.{0,20}inexperience", r"inexperience.{0,20}red flag"]),
    ("Understanding what is blocking them",     [r"doing everything right", r"done everything", r"gym.{0,20}career", r"what.{0,20}wrong with me", r"why.{0,20}doesn.t work", r"what am I doing wrong"]),
    ("Getting over approach anxiety",           [r"approach", r"freeze", r"can.t talk to", r"too scared", r"nerve", r"anxiety.{0,20}talk", r"asking.{0,20}out"]),
    ("Learning the mechanics of dating",        [r"what to say", r"how to flirt", r"escalat", r"first date", r"texting", r"what to do on a date", r"no idea how"]),
    ("Decoding why less-deserving men succeed", [r"bad guys", r"jerks.{0,20}girlfriend", r"treat.{0,20}badly", r"why do women", r"nice guys finish last", r"good guy.{0,20}single"]),
    ("Escaping the friend zone",                [r"friend.?zone", r"friendzoned", r"just friends", r"platonic", r"she sees me as", r"male friend"]),
    ("Coping with physical loneliness",         [r"touch", r"hug", r"physical.{0,20}lonely", r"ache", r"warmth", r"held", r"physical contact"]),
    ("Processing the shame of being late",      [r"embarrass", r"ashamed", r"too old", r"late.{0,20}start", r"weird.{0,20}age", r"\d0s?.{0,10}never", r"no one my age"]),
    ("Finding where to meet women",             [r"where to meet", r"how to meet", r"dating app", r"tinder", r"bumble", r"hinge", r"in real life", r"offline"]),
    ("Building self-worth",                     [r"self.?worth", r"self.?esteem", r"value", r"confidence", r"believe in yourself", r"love yourself", r"identity"]),
    ("Managing neurodivergence in dating",      [r"autis", r"adhd", r"neurodiverg", r"spectrum", r"asperger", r"social cues", r"neurotypical"]),
    ("Destigmatizing the experience",           [r"incel", r"stigma", r"forever alone", r"judged", r"label", r"people assume", r"not an incel"]),
    ("Dealing with comparison pain",            [r"social media", r"instagram", r"couples", r"valentine", r"seeing couples", r"everyone else", r"friends are married"]),
    ("Understanding rejection",                 [r"rejected", r"rejection", r"ghost", r"ghosted", r"no response", r"why she", r"what went wrong"]),
    ("Fear of intimacy after abstinence",       [r"cling", r"too much", r"overwhelm", r"first time", r"intimate", r"clingy", r"deprivation"]),
]


def classify_comment(text: str) -> str:
    text_lower = text.lower()
    for theme, patterns in JTBD_THEMES:
        if any(re.search(p, text_lower, re.IGNORECASE) for p in patterns):
            return theme
    return "General / Other"


def fetch_comments(url: str, post_id: str) -> list:
    json_url = url.rstrip("/") + ".json"
    try:
        r = requests.get(json_url, headers=HEADERS, params={"limit": MAX_COMMENTS_PER_POST, "sort": "top"}, timeout=20)
        if r.status_code == 429:
            print("  Rate limited — waiting 20s...")
            time.sleep(20)
            r = requests.get(json_url, headers=HEADERS, params={"limit": MAX_COMMENTS_PER_POST, "sort": "top"}, timeout=20)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        print(f"  Failed to fetch comments: {e}")
        return []

    comments = []
    if not isinstance(data, list) or len(data) < 2:
        return []

    def extract(node):
        if not isinstance(node, dict):
            return
        kind = node.get("kind")
        d = node.get("data", {})
        if kind == "t1":  # comment
            body = (d.get("body") or "").strip()
            score = d.get("score", 0)
            if body and body != "[deleted]" and body != "[removed]" and score >= MIN_COMMENT_SCORE:
                comments.append({
                    "comment_id": d.get("id", ""),
                    "comment_author": d.get("author", ""),
                    "comment_body": body[:800],
                    "comment_score": score,
                    "comment_url": f"https://reddit.com/r/{d.get('subreddit','')}/comments/{post_id}/_/{d.get('id','')}/"
                })
            # recurse into replies
            replies = d.get("replies")
            if isinstance(replies, dict):
                for child in replies.get("data", {}).get("children", []):
                    extract(child)
        elif kind == "Listing":
            for child in d.get("children", []):
                extract(child)

    for child in data[1]["data"].get("children", []):
        extract(child)

    return comments


def main():
    df = pd.read_csv(INPUT_FILE)
    df = df.sort_values("relevance_score", ascending=False).head(TOP_N_POSTS).reset_index(drop=True)
    print(f"Scraping comments from top {len(df)} posts...\n")

    all_rows = []

    for i, (_, post) in enumerate(df.iterrows(), 1):
        print(f"[{i}/{len(df)}] r/{post['subreddit']} | {post['title'][:60]}")
        comments = fetch_comments(post["url"], post["id"])
        kept = [c for c in comments if c["comment_score"] >= MIN_COMMENT_SCORE]
        print(f"  → {len(kept)} comments with {MIN_COMMENT_SCORE}+ upvotes")

        for c in kept:
            all_rows.append({
                "post_id":            post["id"],
                "post_title":         post["title"],
                "post_subreddit":     post["subreddit"],
                "post_url":           post["url"],
                "post_relevance":     post["relevance_score"],
                "comment_id":         c["comment_id"],
                "comment_author":     c["comment_author"],
                "comment_score":      c["comment_score"],
                "comment_body":       c["comment_body"],
                "comment_url":        c["comment_url"],
                "jtbd_theme":         classify_comment(c["comment_body"]),
            })

        time.sleep(2)

    result = pd.DataFrame(all_rows)
    result.sort_values(["jtbd_theme", "comment_score"], ascending=[True, False], inplace=True)
    result.reset_index(drop=True, inplace=True)
    result.to_csv(OUTPUT_FILE, index=False, encoding="utf-8-sig")

    print(f"\nSaved {len(result)} comments to '{OUTPUT_FILE}'")
    print("\nComments per JTBD theme:")
    print(result["jtbd_theme"].value_counts().to_string())


if __name__ == "__main__":
    main()
