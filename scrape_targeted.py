"""
Targeted scraper for: men who are happy/stable in life but can't attract women.
Uses tight query phrases that appear in authentic personal-story posts.
Output: targeted_successful_men.csv
"""

import requests
import pandas as pd
import time
import re
from datetime import datetime

MIN_UPVOTES  = 100
MIN_COMMENTS = 10
OUTPUT_FILE  = "targeted_successful_men.csv"
HEADERS      = {"User-Agent": "Mozilla/5.0 (compatible; research-scraper/1.1)"}

# Very tight queries — phrases that only appear in authentic first-person posts
QUERIES = [
    "never had girlfriend good career",
    "everything going for me single",
    "life together can't find girlfriend",
    "successful life but single",
    "good life no girlfriend",
    "have my life together single",
    "happy with life but lonely romantically",
    "stable life can't attract women",
    "good job good friends still single",
    "life is good but no girlfriend",
    "on paper great life single",
    "not depressed just lonely single",
    "confident but invisible to women",
    "good self-esteem no girlfriend",
    "checks all boxes single",
    "tick all boxes single",
    "good income single can't find",
    "financially stable never had girlfriend",
    "career focused single now what",
    "late bloomer dating never had girlfriend",
    "30s single never dated",
    "successful single women not interested",
    "gym career friends still single",
    "invisible to women despite",
    "women don't see me romantically",
    "never approached by women",
    "friendzoned good guy career",
    "men who are successful but alone",
    "35 never had girlfriend career",
    "30 never had girlfriend good life",
]

SUBREDDITS = [
    "ForeverAlone",
    "AskMenOver30",
    "AskMenOver40",
    "datingoverthirty",
    "datingoverforty",
    "dating_advice",
    "AskMen",
    "self",
    "lonely",
    "socialskills",
    "offmychest",
    "TrueOffMyChest",
]

TIME_FILTERS = ["all", "year"]


def search_reddit(subreddit, query, time_filter):
    url = f"https://www.reddit.com/r/{subreddit}/search.json"
    params = {"q": query, "sort": "top", "t": time_filter,
              "limit": 100, "restrict_sr": 1}
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


def is_female_poster(title, body):
    text = (title + " " + body).lower()
    female_tags = re.compile(r'\b\d{1,2}f\b|\(f\)|\(f,|\bi \(f|\[f\]')
    if female_tags.search(text[:400]):
        return True
    female_words = [
        'my husband', 'my boyfriend', 'my fiance', 'as a woman',
        "i'm a woman", 'i am a woman', 'i am female', "i'm female",
        'as a girl', "i'm a girl",
    ]
    return any(f in text for f in female_words)


def has_stability_signal(text):
    ok_signals = [
        'good career', 'stable job', 'own a ', 'financially stable',
        'doing well', 'have a job', 'have my life', 'not depressed',
        'happy with my life', "i'm happy", 'life is good', 'good self-esteem',
        'everything going for me', 'on paper', 'checks all the boxes',
        'tick all the boxes', 'life together', 'good income', 'good salary',
        'financially independent', 'good life', 'great life', 'my career',
        'i have friends', 'social life', 'i work out', 'i workout', 'gym',
        'my degree', 'college', 'university', 'graduated',
        'my apartment', 'my house', 'i rent', 'i own',
        'people like me', 'told i\'m', 'not ugly', 'good person',
        "i'm employed", 'full-time', 'well-paying', 'successful',
        'comfortable financially', 'self-sufficient', 'independent',
        'i like myself', 'i love myself', 'content with',
        'happy enough', 'life is fulfilling', 'confident',
    ]
    return any(s in text for s in ok_signals)


def has_romantic_struggle(text):
    signals = [
        'never had a girlfriend', 'never been in a relationship',
        'invisible to women', "can't attract", 'women are not interested',
        "women aren't interested", 'no luck with women', 'no luck dating',
        'never been on a date', 'never kissed', 'never been kissed',
        "women don't notice", "can't find a girlfriend", "can't get a girlfriend",
        'never had a relationship', 'never been approached',
        'just see me as a friend', 'friendzoned', 'friend zone',
        'still single', 'been single for', 'always single',
        'just want a girlfriend', "can't find love", 'no matches',
        'give up on dating', 'giving up on dating',
        'no girlfriend', 'never been with a woman', 'single for years',
        'romantically unsuccessful', 'never had a date',
        'women don\'t want me', 'women don\'t like me',
        'women only see me as', 'romantically invisible',
        'women never approach', 'never been in love',
    ]
    return any(s in text for s in signals)


def segment_tag(title, body):
    text = (title + " " + body).lower()
    if any(k in text for k in ['invisible', 'friend zone', 'friendzone', 'just see me as']):
        return "Unseen Good Guy"
    if any(k in text for k in ['career', 'work', 'job', 'late bloomer', 'focused on career']):
        return "Career-First Late Bloomer"
    if any(k in text for k in ['divorce', 'breakup', 'ex ', 'restart']):
        return "Post-Loss Restarter"
    if any(k in text for k in ['apps', 'tinder', 'hinge', 'bumble', 'matches', 'online dating']):
        return "App-Burned Defeatist"
    if any(k in text for k in ['approach', 'scared', "can't talk to", 'initiate', 'frozen']):
        return "Approach-Frozen Man"
    if any(k in text for k in ['closed off', 'walls', 'emotionally unavailable']):
        return "Emotionally Closed Off"
    return "General / Stable but Lonely"


def fetch_all():
    seen = set()
    results = []
    total = len(SUBREDDITS) * len(QUERIES) * len(TIME_FILTERS)
    count = 0

    for subreddit in SUBREDDITS:
        for query in QUERIES:
            for time_filter in TIME_FILTERS:
                count += 1
                print(f"[{count}/{total}] r/{subreddit} | '{query[:40]}' | {time_filter}  (found: {len(results)})")

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
                    if not p.get("is_self", False):
                        continue

                    body = (p.get("selftext", "") or "").strip()
                    if len(body) < 100 or body in ("[removed]", "[deleted]"):
                        continue

                    title = p["title"]
                    combined = (title + " " + body).lower()

                    if is_female_poster(title, body):
                        continue

                    if not has_stability_signal(combined):
                        continue

                    if not has_romantic_struggle(combined):
                        continue

                    seen.add(p["id"])
                    results.append({
                        "id":           p["id"],
                        "title":        title,
                        "subreddit":    p["subreddit"],
                        "score":        p["score"],
                        "num_comments": p["num_comments"],
                        "upvote_ratio": round(p.get("upvote_ratio", 0), 2),
                        "url":          f"https://reddit.com{p['permalink']}",
                        "created_date": datetime.utcfromtimestamp(p["created_utc"]).strftime("%Y-%m-%d"),
                        "author":       p.get("author", ""),
                        "post_body":    body[:2000],
                        "segment_tag":  segment_tag(title, body),
                        "matched_query": query,
                        "flair":        p.get("link_flair_text", "") or "",
                    })

                time.sleep(1.5)

    return results


def main():
    print(f"Target: ≥{MIN_UPVOTES} upvotes, ≥{MIN_COMMENTS} comments\n")
    results = fetch_all()

    if not results:
        print("No posts found.")
        return

    df = pd.DataFrame(results)
    df.drop_duplicates(subset="id", inplace=True)
    df.sort_values("score", ascending=False, inplace=True)
    df.reset_index(drop=True, inplace=True)
    df.to_csv(OUTPUT_FILE, index=False, encoding="utf-8-sig")

    print(f"\n✓ Saved {len(df)} threads to '{OUTPUT_FILE}'")
    print(f"\nSegment distribution:\n{df['segment_tag'].value_counts().to_string()}")
    print(f"\nTop 15 by score:")
    print(df[['title', 'subreddit', 'score', 'num_comments', 'segment_tag']].head(15).to_string(index=False))


if __name__ == "__main__":
    main()
