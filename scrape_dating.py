import requests
import pandas as pd
import time
from datetime import datetime

QUERIES = [
    "can't find girlfriend",
    "never had girlfriend",
    "always single man",
    "men dating struggles",
    "forever alone male",
    "single man lonely",
    "no girlfriend lonely",
    "men can't date",
]

SUBREDDITS = [
    "lonely",
    "ForeverAlone",
    "AskMen",
    "dating_advice",
    "dating",
    "relationship_advice",
    "self",
    "offmychest",
    "TrueOffMyChest",
    "socialskills",
    "AskMenOver30",
    "Tinder",
]

MIN_UPVOTES = 100
MIN_COMMENTS = 5
TIME_FILTERS = ["year", "all"]
LIMIT = 100
OUTPUT_FILE = "male_dating_threads.csv"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; research-scraper/1.0)"
}


def search_subreddit(subreddit, query, time_filter):
    url = f"https://www.reddit.com/r/{subreddit}/search.json"
    params = {
        "q": query,
        "sort": "top",
        "t": time_filter,
        "limit": LIMIT,
        "restrict_sr": 1,
    }
    try:
        r = requests.get(url, headers=HEADERS, params=params, timeout=15)
        if r.status_code == 429:
            print("  Rate limited — waiting 15s...")
            time.sleep(15)
            r = requests.get(url, headers=HEADERS, params=params, timeout=15)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"  Request failed: {e}")
        return None


def extract_posts(data):
    posts = []
    if not data or "data" not in data:
        return posts
    for child in data["data"].get("children", []):
        posts.append(child["data"])
    return posts


def fetch_all():
    seen = set()
    results = []
    total = len(SUBREDDITS) * len(QUERIES) * len(TIME_FILTERS)
    count = 0

    for subreddit in SUBREDDITS:
        for query in QUERIES:
            for time_filter in TIME_FILTERS:
                count += 1
                print(f"[{count}/{total}] r/{subreddit} | '{query}' | {time_filter}")

                data = search_subreddit(subreddit, query, time_filter)
                posts = extract_posts(data)

                for p in posts:
                    if p["id"] in seen:
                        continue
                    if p["score"] < MIN_UPVOTES or p["num_comments"] < MIN_COMMENTS:
                        continue

                    seen.add(p["id"])
                    results.append({
                        "id": p["id"],
                        "title": p["title"],
                        "subreddit": p["subreddit"],
                        "score": p["score"],
                        "num_comments": p["num_comments"],
                        "upvote_ratio": p.get("upvote_ratio", ""),
                        "url": f"https://reddit.com{p['permalink']}",
                        "created_date": datetime.utcfromtimestamp(p["created_utc"]).strftime("%Y-%m-%d"),
                        "author": p.get("author", ""),
                        "post_body": (p.get("selftext", "") or "")[:1000].strip(),
                        "flair": p.get("link_flair_text", "") or "",
                    })

                time.sleep(1.5)

    return results


def main():
    print(f"Searching {len(SUBREDDITS)} subreddits x {len(QUERIES)} queries x {len(TIME_FILTERS)} time filters\n")
    results = fetch_all()

    if not results:
        print("\nNo posts found.")
        return

    df = pd.DataFrame(results)
    df.drop_duplicates(subset="id", inplace=True)
    df.sort_values("score", ascending=False, inplace=True)
    df.reset_index(drop=True, inplace=True)
    df.to_csv(OUTPUT_FILE, index=False, encoding="utf-8-sig")

    print(f"\nSaved {len(df)} posts to '{OUTPUT_FILE}'")
    print("\nTop 5 by score:")
    print(df[["title", "subreddit", "score", "num_comments"]].head().to_string(index=False))


if __name__ == "__main__":
    main()
