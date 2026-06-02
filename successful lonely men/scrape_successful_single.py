"""
Scrapes Reddit for threads about men who are successful / have good self-esteem
but cannot attract women or find a relationship.
Target: ≥100 upvotes, ≥10 comments, ≥100 unique threads.
Output: single_successful_men.csv
"""

import requests
import pandas as pd
import time
from datetime import datetime

# --- Settings ---
MIN_UPVOTES  = 50    # lower bar so personal stories qualify
MIN_COMMENTS = 10
TARGET_COUNT = 150
LIMIT        = 100
OUTPUT_FILE  = "single_successful_men.csv"
HEADERS      = {"User-Agent": "Mozilla/5.0 (compatible; research-scraper/1.0)"}

# Short keyword queries — Reddit search does AND on these words.
# Kept short so they match actual post language, not fabricated phrases.
QUERIES = [
    "good job invisible women",
    "career friends single can't attract",
    "life together single women",
    "not depressed just lonely single",
    "successful single women not interested",
    "happy life no girlfriend",
    "invisible romantically",
    "women don't notice me",
    "friendzoned good career",
    "never had girlfriend career",
    "good life no luck women",
    "confident single women not attracted",
    "everything right women not interested",
    "stable life single women",
    "good person women not interested romantically",
]

# Personal-story subreddits — these have first-person narratives, not advice
SUBREDDITS = [
    "ForeverAlone",
    "lonely",
    "self",
    "AskMen",
    "AskMenOver30",
    "TrueOffMyChest",
    "offmychest",
    "datingoverthirty",
    "dating_advice",
    "socialskills",
]

TIME_FILTERS = ["all", "year"]


def search_reddit(subreddit, query, time_filter):
    url = f"https://www.reddit.com/r/{subreddit}/search.json"
    params = {
        "q":           query,
        "sort":        "top",
        "t":           time_filter,
        "limit":       LIMIT,
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


def tag_segment(title, body):
    """Rough segment tag based on keywords in title + body."""
    text = (title + " " + body).lower()
    if any(k in text for k in ["invisible", "friend zone", "friendzone", "friend only", "see me as a friend", "just a friend"]):
        return "Unseen Good Guy"
    if any(k in text for k in ["closed off", "walls", "emotionally unavailable", "hard to read"]):
        return "Emotionally Closed Off"
    if any(k in text for k in ["career", "work", "job", "late bloomer", "prioritised work", "focused on career"]):
        return "Career-First Late Bloomer"
    if any(k in text for k in ["divorce", "breakup", "ex", "lost relationship", "long term", "restart"]):
        return "Post-Loss Restarter"
    if any(k in text for k in ["prepared", "self improvement", "work on myself", "not ready", "improving"]):
        return "Theoretical One"
    if any(k in text for k in ["apps", "tinder", "hinge", "bumble", "matches", "online dating"]):
        return "App-Burned Defeatist"
    if any(k in text for k in ["approach", "too scared", "can't talk to", "initiate", "frozen"]):
        return "Approach-Frozen Man"
    return "General / Unspecified"


def fetch_all():
    seen    = set()
    results = []
    total   = len(SUBREDDITS) * len(QUERIES) * len(TIME_FILTERS)
    count   = 0

    for subreddit in SUBREDDITS:
        for query in QUERIES:
            for time_filter in TIME_FILTERS:
                count += 1
                print(f"[{count}/{total}] r/{subreddit} | '{query[:45]}' | {time_filter}  (found so far: {len(results)})")

                data = search_reddit(subreddit, query, time_filter)
                if not data or "data" not in data:
                    time.sleep(1.5)
                    continue

                for child in data["data"].get("children", []):
                    p = child["data"]

                    if p["id"] in seen:
                        continue
                    if p.get("score", 0) < MIN_UPVOTES:
                        continue
                    if p.get("num_comments", 0) < MIN_COMMENTS:
                        continue
                    # skip non-text posts
                    if not p.get("is_self", False):
                        continue

                    body = (p.get("selftext", "") or "").strip()
                    # skip removed/deleted bodies shorter than 100 chars
                    if len(body) < 100 or body in ("[removed]", "[deleted]"):
                        continue

                    title_lower = p["title"].lower()
                    body_lower  = body.lower()
                    combined    = title_lower + " " + body_lower

                    # Skip guides, PSAs, advice posts, female-perspective titles
                    skip_titles = [
                        "guide", "psa:", "tip:", "tips:", "reminder:", "how to ",
                        "a handy", "advice for", "things to", "ladies:", "girls,",
                        "women:", "for women", "as a woman", "i (f", "i (f)",
                        "my boyfriend", "my husband", "my wife ", "she cheated",
                        "he cheated", "should i break", "update:", "vibrator",
                    ]
                    if any(t in title_lower for t in skip_titles):
                        continue

                    # Must be first-person in the opening 500 chars
                    first_person = ["i am ", "i'm ", "i've ", "i have ", "i feel ",
                                    "i (m", "i never ", "i don't ", "i can't ",
                                    "my life ", "i just ", "i'm not ", "i work "]
                    if not any(s in body_lower[:500] for s in first_person):
                        continue

                    # Must have at least 2 distinct "doing OK" signals
                    ok_signals = {
                        "job":       ["good job", "stable job", "full-time", "my job", "my career",
                                      "my work", "employed", "i work as", "i work at"],
                        "finance":   ["financially", "net worth", "own a house", "my apartment",
                                      "my own place", "rent my", "good income", "salary"],
                        "social":    ["i have friends", "good friends", "social life", "social circle",
                                      "people like me", "people enjoy", "friends like me"],
                        "health":    ["gym", "work out", "workout", "in shape", "physically fit",
                                      "i exercise", "i run", "i lift", "good shape"],
                        "education": ["degree", "graduated", "college", "university", "masters", "phd"],
                        "happiness": ["happy with my life", "love my life", "i'm happy", "i am happy",
                                      "content with", "i enjoy my life", "life is good",
                                      "doing well", "life is great", "life is fine", "not depressed",
                                      "i'm not depressed", "life is fulfilling", "i have a good life",
                                      "life together", "everything going for me", "going for me",
                                      "on paper", "by most measures", "checks all the boxes",
                                      "tick all the boxes", "i'm confident", "self-esteem is fine",
                                      "good self-esteem", "i like myself", "i love myself"],
                    }
                    ok_count = sum(1 for signals in ok_signals.values()
                                   if any(s in combined for s in signals))
                    if ok_count < 2:
                        continue

                    # Must contain a clear romantic struggle signal
                    struggle_signals = [
                        "still single", "never had a girlfriend", "no girlfriend",
                        "can't attract", "women aren't interested", "women are not interested",
                        "women don't like me", "women never", "invisible to women",
                        "women don't see me", "friendzone", "friend zone",
                        "no luck with women", "no luck dating", "struggling with dating",
                        "struggle with dating", "women don't notice", "romantically invisible",
                        "never been approached", "no romantic", "not interested in me",
                        "women only see me as", "just see me as a friend", "can't find a girlfriend",
                        "can't get a girlfriend", "women don't approach", "just want a girlfriend",
                        "just want a relationship", "never been in a relationship",
                    ]
                    if not any(s in combined for s in struggle_signals):
                        continue

                    seen.add(p["id"])
                    results.append({
                        "id":            p["id"],
                        "title":         p["title"],
                        "subreddit":     p["subreddit"],
                        "score":         p["score"],
                        "num_comments":  p["num_comments"],
                        "upvote_ratio":  round(p.get("upvote_ratio", 0), 2),
                        "url":           f"https://reddit.com{p['permalink']}",
                        "created_date":  datetime.utcfromtimestamp(p["created_utc"]).strftime("%Y-%m-%d"),
                        "author":        p.get("author", ""),
                        "post_body":     body[:1500],
                        "segment_tag":   tag_segment(p["title"], body),
                        "matched_query": query,
                        "flair":         p.get("link_flair_text", "") or "",
                    })

                time.sleep(1.5)

                if len(results) >= TARGET_COUNT * 5:
                    print(f"\nReached {len(results)} results — stopping early.")
                    return results

    return results


def main():
    print(f"Target: ≥{MIN_UPVOTES} upvotes, ≥{MIN_COMMENTS} comments, ≥{TARGET_COUNT} threads\n")
    results = fetch_all()

    if not results:
        print("\nNo posts found. Try lowering MIN_UPVOTES.")
        return

    df = pd.DataFrame(results)
    df.drop_duplicates(subset="id", inplace=True)
    df.sort_values("score", ascending=False, inplace=True)
    df.reset_index(drop=True, inplace=True)
    df.to_csv(OUTPUT_FILE, index=False, encoding="utf-8-sig")

    print(f"\n✓ Saved {len(df)} threads to '{OUTPUT_FILE}'")
    print(f"\nSegment distribution:")
    print(df["segment_tag"].value_counts().to_string())
    print(f"\nTop 10 by score:")
    print(df[["title", "subreddit", "score", "num_comments", "segment_tag"]].head(10).to_string(index=False))


if __name__ == "__main__":
    main()
