"""
Top-browsing supplement for subreddits that didn't hit 100 posts with search.
Browses /top directly across multiple time windows, then applies male filter.
"""
import requests
import pandas as pd
import time
import re
from datetime import datetime

MIN_UPVOTES  = 100
MIN_COMMENTS = 5
TARGET_POSTS = 150
LIMIT        = 100
HEADERS      = {"User-Agent": "Mozilla/5.0 (compatible; research-scraper/1.0)"}

# Subreddits that need top-up + their existing CSV to merge with
TARGETS = {
    "ForeverAlone":    "forever_alone_posts.csv",
    "datingoverthirty":"datingoverthirty_posts.csv",
    "datingoverforty": "datingoverforty_posts.csv",
}

TIME_FILTERS = ["all", "year", "month"]

# ── More inclusive male patterns ─────────────────────────────────────────
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
    r"\bI\s*\([Mm][,\s\d]",
    r"\b[Mm]\s*/\s*\d{1,2}\b",
    r"\b\d{1,2}\s*/\s*[Mm]\b",
    r"\bhe/him\b",
    r"\bmy\s+(?:ex[\s-]?(?:wife|girlfriend|gf)|ex\s+wife)\b",  # divorced men
    r"\bmy\s+(?:son|dad|father|brother)\b.{0,60}\bI\b",        # family context male
    r"\bdating\s+(?:women|ladies|girls|a\s+woman)\b",
    r"\bwomen\s+I\s+date\b",
    r"\bgirlfriend\b.{0,40}\bI\b",   # "girlfriend ... I" likely male OP
    r"\bI\b.{0,40}\bgirlfriend\b",
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
    r"\bmen\s+I\s+date\b",
]

def is_male_post(title: str, body: str) -> bool:
    text = f"{title} {str(body or '')}"
    if any(re.search(p, text, re.IGNORECASE) for p in FEMALE_PATTERNS):
        return False
    if any(re.search(p, text, re.IGNORECASE) for p in MALE_PATTERNS):
        return True
    return False

def fetch_top(subreddit: str, time_filter: str, after: str = None) -> tuple:
    url = f"https://www.reddit.com/r/{subreddit}/top.json"
    params = {"t": time_filter, "limit": LIMIT}
    if after:
        params["after"] = after
    try:
        r = requests.get(url, headers=HEADERS, params=params, timeout=15)
        if r.status_code == 429:
            print("  Rate limited — waiting 20s...")
            time.sleep(20)
            r = requests.get(url, headers=HEADERS, params=params, timeout=15)
        r.raise_for_status()
        data = r.json()
        posts = data["data"].get("children", [])
        after = data["data"].get("after")
        return posts, after
    except Exception as e:
        print(f"  Request failed: {e}")
        return [], None

def fetch_subreddit_top(subreddit: str, existing_ids: set) -> list:
    results = []

    for time_filter in TIME_FILTERS:
        after = None
        pages = 0
        while len(results) + len(existing_ids) < TARGET_POSTS and pages < 5:
            posts, after = fetch_top(subreddit, time_filter, after)
            if not posts:
                break
            pages += 1

            for child in posts:
                p = child["data"]
                if p["id"] in existing_ids:
                    continue
                if p["score"] < MIN_UPVOTES or p["num_comments"] < MIN_COMMENTS:
                    continue
                title = p.get("title", "")
                body  = (p.get("selftext", "") or "")[:1000].strip()
                if not is_male_post(title, body):
                    continue

                existing_ids.add(p["id"])
                results.append({
                    "id":           p["id"],
                    "title":        title,
                    "subreddit":    p["subreddit"],
                    "score":        p["score"],
                    "num_comments": p["num_comments"],
                    "upvote_ratio": p.get("upvote_ratio", ""),
                    "url":          f"https://reddit.com{p['permalink']}",
                    "created_date": datetime.utcfromtimestamp(
                                        p["created_utc"]).strftime("%Y-%m-%d"),
                    "author":       p.get("author", ""),
                    "post_body":    body,
                    "flair":        p.get("link_flair_text", "") or "",
                })

            print(f"  t={time_filter} page {pages}: {len(results)} new posts found")
            if not after:
                break
            time.sleep(1.5)

        if len(results) + len(existing_ids) >= TARGET_POSTS:
            break

    return results

def main():
    for subreddit, filename in TARGETS.items():
        print(f"\n{'='*60}")
        print(f"Top-browsing r/{subreddit}")

        # Load existing posts
        try:
            existing = pd.read_csv(filename)
            existing_ids = set(existing["id"].astype(str))
            print(f"  Existing: {len(existing)} posts — need {TARGET_POSTS - len(existing)} more")
        except FileNotFoundError:
            existing = pd.DataFrame()
            existing_ids = set()
            print(f"  No existing file — starting fresh")

        if len(existing) >= TARGET_POSTS:
            print(f"  Already at target ({len(existing)} posts). Skipping.")
            continue

        new_posts = fetch_subreddit_top(subreddit, existing_ids)

        if not new_posts:
            print(f"  No additional posts found.")
            continue

        new_df = pd.DataFrame(new_posts)
        combined = pd.concat([existing, new_df], ignore_index=True)
        combined.drop_duplicates(subset="id", inplace=True)
        combined.sort_values("score", ascending=False, inplace=True)
        combined.reset_index(drop=True, inplace=True)
        combined.to_csv(filename, index=False, encoding="utf-8-sig")

        print(f"\n  Total saved: {len(combined)} posts → '{filename}'")
        print(f"  Score range: {combined['score'].min()}–{combined['score'].max()}")
        print("\n  Top 5:")
        for _, row in combined.head(5).iterrows():
            print(f"    [{row['score']:>5}] {row['title'][:70]}")

if __name__ == "__main__":
    main()
