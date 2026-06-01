"""
Final top-up pass — extra search queries + browse hot/controversial.
"""
import requests
import pandas as pd
import time
import re
from datetime import datetime

MIN_UPVOTES  = 100
MIN_COMMENTS = 5
TARGET_POSTS = 120
LIMIT        = 100
HEADERS      = {"User-Agent": "Mozilla/5.0 (compatible; research-scraper/1.0)"}

TARGETS = {
    "ForeverAlone":    ("forever_alone_posts.csv",    [
        "single forever", "never kissed", "never asked out", "rejected again",
        "will i ever", "hopeless", "no dates", "virgin", "alone at",
        "friendless", "no one wants me", "unlovable", "invisible to women",
    ]),
    "datingoverthirty": ("datingoverthirty_posts.csv", [
        "30s single", "dating in 30s", "still single", "back to dating",
        "divorced", "starting over", "never married", "lonely 30s",
        "meeting women", "no luck dating", "rejection", "dating apps 30s",
    ]),
    "datingoverforty": ("datingoverforty_posts.csv",  [
        "40s single", "dating in 40s", "divorced men", "widower",
        "starting over at 40", "lonely 40s", "never married 40",
        "online dating 40s", "meeting women 40s", "dating after divorce",
        "40 year old man", "single at 45",
    ]),
}

MALE_PATTERNS = [
    r'\b\d{1,2}[Mm]\b',
    r'\([Mm]\d{1,2}\)',
    r'\[[Mm]\d{1,2}\]',
    r'I\s*[\(\[]\d{1,2}[Mm][\)\]]',
    r'[\(\[]\d{1,2}[Mm][\)\]]',
    r"\bI'?m?\s+a\s+(?:man|male|guy|dude|bloke)\b",
    r"\bas\s+a\s+(?:man|male|guy|dude)\b",
    r"\bI\s+am\s+a\s+(?:man|male|guy)\b",
    r"\b(?:man|male|guy)\s+here\b",
    r"\bhe/him\b",
    r"\bmy\s+ex[\s-]?(?:wife|girlfriend|gf)\b",
    r"\bdating\s+(?:women|ladies|girls|a\s+woman)\b",
    r"\bgirlfriend\b.{0,60}\bI\b",
    r"\bI\b.{0,40}\bgirlfriend\b",
    r"\b(?:4[0-9]|3[0-9])[Mm]\b",   # 40M, 35M etc
    r"\bdivorced\s+(?:man|male|guy|dad|father)\b",
    r"\bwidower\b",
    r"\bsingle\s+dad\b",
    r"\bsingle\s+father\b",
]

FEMALE_PATTERNS = [
    r'\b\d{1,2}[Ff]\b',
    r'\([Ff]\d{1,2}\)',
    r'\[[Ff]\d{1,2}\]',
    r'I\s*[\(\[]\d{1,2}[Ff][\)\]]',
    r"I'?m?\s+a\s+(?:woman|female|girl|lady)",
    r"as\s+a\s+(?:woman|female|girl|lady)",
    r"\bshe/her\b",
    r"\bmy\s+(?:husband|boyfriend|bf)\b",
    r"\bdating\s+(?:men|guys|a\s+man)\b",
    r"\bsingle\s+mom\b",
    r"\bsingle\s+mother\b",
]

def is_male_post(title, body):
    text = f"{title} {str(body or '')}"
    if any(re.search(p, text, re.IGNORECASE) for p in FEMALE_PATTERNS):
        return False
    if any(re.search(p, text, re.IGNORECASE) for p in MALE_PATTERNS):
        return True
    return False

def get(url, params):
    try:
        r = requests.get(url, headers=HEADERS, params=params, timeout=15)
        if r.status_code == 429:
            print("  Rate limited — waiting 20s...")
            time.sleep(20)
            r = requests.get(url, headers=HEADERS, params=params, timeout=15)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"  Request failed: {e}")
        return None

def extract_post(p):
    title = p.get("title", "")
    body  = (p.get("selftext", "") or "")[:1000].strip()
    return title, body, {
        "id":           p["id"],
        "title":        title,
        "subreddit":    p["subreddit"],
        "score":        p["score"],
        "num_comments": p["num_comments"],
        "upvote_ratio": p.get("upvote_ratio", ""),
        "url":          f"https://reddit.com{p['permalink']}",
        "created_date": datetime.utcfromtimestamp(p["created_utc"]).strftime("%Y-%m-%d"),
        "author":       p.get("author", ""),
        "post_body":    body,
        "flair":        p.get("link_flair_text", "") or "",
    }

def main():
    for subreddit, (filename, queries) in TARGETS.items():
        print(f"\n{'='*60}")
        print(f"Final pass: r/{subreddit}")

        existing = pd.read_csv(filename)
        existing_ids = set(existing["id"].astype(str))
        print(f"  Starting with {len(existing)} posts — target {TARGET_POSTS}")

        new_rows = []

        # 1. Search with targeted queries
        for query in queries:
            if len(existing) + len(new_rows) >= TARGET_POSTS:
                break
            for tf in ["all", "year", "month"]:
                if len(existing) + len(new_rows) >= TARGET_POSTS:
                    break
                data = get(
                    f"https://www.reddit.com/r/{subreddit}/search.json",
                    {"q": query, "sort": "top", "t": tf, "limit": LIMIT, "restrict_sr": 1}
                )
                if not data:
                    time.sleep(1.5)
                    continue
                for child in data.get("data", {}).get("children", []):
                    p = child["data"]
                    if p["id"] in existing_ids:
                        continue
                    if p["score"] < MIN_UPVOTES or p["num_comments"] < MIN_COMMENTS:
                        continue
                    title, body, row = extract_post(p)
                    if not is_male_post(title, body):
                        continue
                    existing_ids.add(p["id"])
                    new_rows.append(row)
                time.sleep(1.2)

        # 2. Browse controversial (surfaces more personal posts)
        for tf in ["all", "year"]:
            if len(existing) + len(new_rows) >= TARGET_POSTS:
                break
            after = None
            for _ in range(3):
                params = {"t": tf, "limit": LIMIT}
                if after:
                    params["after"] = after
                data = get(
                    f"https://www.reddit.com/r/{subreddit}/controversial.json",
                    params
                )
                if not data:
                    break
                children = data.get("data", {}).get("children", [])
                after = data.get("data", {}).get("after")
                for child in children:
                    p = child["data"]
                    if p["id"] in existing_ids:
                        continue
                    if p["score"] < MIN_UPVOTES or p["num_comments"] < MIN_COMMENTS:
                        continue
                    title, body, row = extract_post(p)
                    if not is_male_post(title, body):
                        continue
                    existing_ids.add(p["id"])
                    new_rows.append(row)
                if not after:
                    break
                time.sleep(1.5)

        print(f"  Found {len(new_rows)} new posts")

        combined = pd.concat([existing, pd.DataFrame(new_rows)], ignore_index=True)
        combined.drop_duplicates(subset="id", inplace=True)
        combined.sort_values("score", ascending=False, inplace=True)
        combined.reset_index(drop=True, inplace=True)
        combined.to_csv(filename, index=False, encoding="utf-8-sig")

        print(f"  Total: {len(combined)} posts saved to '{filename}'")
        print(f"  Score range: {combined['score'].min()}–{combined['score'].max()}")

if __name__ == "__main__":
    main()
