import requests
import pandas as pd
import time
import re
from datetime import datetime

# ── CONFIG ──────────────────────────────────────────────────────────────
MIN_UPVOTES   = 100
MIN_COMMENTS  = 5
TARGET_POSTS  = 150       # collect up to this many per subreddit
LIMIT         = 100       # Reddit API page size
HEADERS       = {"User-Agent": "Mozilla/5.0 (compatible; research-scraper/1.0)"}

SUBREDDITS = {
    "ForeverAlone":    "forever_alone_posts.csv",
    "dating_advice":   "dating_advice_posts.csv",
    "datingoverthirty":"datingoverthirty_posts.csv",
    "datingoverforty": "datingoverforty_posts.csv",
}

# Broad queries — male filter handles precision
QUERIES = [
    "never had girlfriend",
    "can't find girlfriend",
    "always single",
    "forever alone",
    "dating struggles",
    "lonely single",
    "no girlfriend",
    "dating advice men",
    "single man",
    "never been in relationship",
]

TIME_FILTERS = ["year", "all"]

# ── MALE DETECTION ───────────────────────────────────────────────────────
# High-precision patterns — matches posts where OP explicitly identifies as male
MALE_PATTERNS = [
    r'\b\d{1,2}[Mm]\b',               # 25M, 32m
    r'\([Mm]\d{1,2}\)',               # (M25), (m32)
    r'\[[Mm]\d{1,2}\]',               # [M25]
    r'\b\d{1,2}[Mm],\s*\d{1,2}[Mm]', # 25M, 27M style multi
    r'I\s*[\(\[]M[\)\]]',             # I (M) or I [M]
    r'I\s*[\(\[]\d{1,2}[Mm][\)\]]',  # I (25M) or I [25M]
    r'[\(\[]\d{1,2}[Mm][\)\]]',       # (25M) anywhere in title
    r"\bI'?m?\s+a\s+(?:man|male|guy)\b",
    r"\bas\s+a\s+(?:man|male|guy)\b",
    r"\bI\s+am\s+a\s+(?:man|male|guy)\b",
    r"\b(?:man|male|guy)\s+here\b",
    r"\bI\s*\(M[,\s\d]",              # I (M, 30) or I (M30
    r"\bM\s*/\s*\d{1,2}\b",           # M/30
    r"\b\d{1,2}\s*/\s*[Mm]\b",        # 30/M
    r"\bhim\b.{0,30}\bme\b",          # "him" referring to others, I'm male implied
    r"\bbrother\b|\bson\b",            # family context (less reliable, use cautiously)
]

# Negative patterns — if these appear the poster is likely female
FEMALE_PATTERNS = [
    r'\b\d{1,2}[Ff]\b',
    r'\([Ff]\d{1,2}\)',
    r'\[[Ff]\d{1,2}\]',
    r'I\s*[\(\[]\d{1,2}[Ff][\)\]]',
    r"I'?m?\s+a\s+(?:woman|female|girl|lady)",
    r"as\s+a\s+(?:woman|female|girl)",
    r"I\s+am\s+a\s+(?:woman|female|girl)",
    r"\bshe/her\b",
    r"\bmy\s+(?:husband|boyfriend|bf)\b",
    r"\bmy\s+(?:son|daughter)\b.{0,30}\bI\b",  # mom context
]

def is_male_post(title: str, body: str) -> bool:
    text = f"{title} {str(body or '')}"
    # Reject if clearly female
    if any(re.search(p, text, re.IGNORECASE) for p in FEMALE_PATTERNS):
        return False
    # Accept if clearly male
    if any(re.search(p, text, re.IGNORECASE) for p in MALE_PATTERNS):
        return True
    return False

# ── SCRAPING ─────────────────────────────────────────────────────────────
def search_subreddit(subreddit: str, query: str, time_filter: str):
    url = f"https://www.reddit.com/r/{subreddit}/search.json"
    params = {"q": query, "sort": "top", "t": time_filter,
              "limit": LIMIT, "restrict_sr": 1}
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


def fetch_subreddit(subreddit: str) -> pd.DataFrame:
    seen    = set()
    results = []
    total_combos = len(QUERIES) * len(TIME_FILTERS)
    combo = 0

    for query in QUERIES:
        for time_filter in TIME_FILTERS:
            combo += 1
            print(f"  [{combo}/{total_combos}] '{query}' | {time_filter} "
                  f"({len(results)} collected so far)")

            data = search_subreddit(subreddit, query, time_filter)
            if not data or "data" not in data:
                time.sleep(1.5)
                continue

            for child in data["data"].get("children", []):
                if len(results) >= TARGET_POSTS:
                    break
                p = child["data"]

                if p["id"] in seen:
                    continue
                if p["score"] < MIN_UPVOTES or p["num_comments"] < MIN_COMMENTS:
                    continue

                title = p.get("title", "")
                body  = (p.get("selftext", "") or "")[:1000].strip()

                if not is_male_post(title, body):
                    continue

                seen.add(p["id"])
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

            if len(results) >= TARGET_POSTS:
                print(f"  Reached target of {TARGET_POSTS} posts.")
                break
            time.sleep(1.5)

        if len(results) >= TARGET_POSTS:
            break

    df = pd.DataFrame(results)
    if not df.empty:
        df.drop_duplicates(subset="id", inplace=True)
        df.sort_values("score", ascending=False, inplace=True)
        df.reset_index(drop=True, inplace=True)
    return df


# ── MAIN ─────────────────────────────────────────────────────────────────
def main():
    for subreddit, filename in SUBREDDITS.items():
        print(f"\n{'='*60}")
        print(f"Scraping r/{subreddit} → {filename}")
        print(f"{'='*60}")

        df = fetch_subreddit(subreddit)

        if df.empty:
            print(f"  No posts found for r/{subreddit}")
            continue

        df.to_csv(filename, index=False, encoding="utf-8-sig")
        print(f"\n  Saved {len(df)} posts to '{filename}'")
        print(f"  Score range: {df['score'].min()}–{df['score'].max()}")
        print("\n  Top 5:")
        for _, row in df.head(5).iterrows():
            print(f"    [{row['score']:>5}] {row['title'][:70]}")


if __name__ == "__main__":
    main()
