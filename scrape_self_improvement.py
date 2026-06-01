"""
Scrape Reddit for men working on becoming the best version of themselves.
Uses Arctic Shift API — no auth required.

Target: 100 qualifying threads per community + top comments per thread.

Criteria:
  - Posts: score ≥ 20, num_comments ≥ 10
  - Comments: score ≥ 10
  - Male poster (gender filter applied)
  - Relevant to male self-improvement (signal filter applied)

Outputs:
  self_improvement_threads.csv   — 100 posts per community
  self_improvement_comments.csv  — top comments (score ≥ 10) per qualifying post
"""

import requests
import pandas as pd
import time
import re
from datetime import datetime
from typing import Optional

# ── Config ────────────────────────────────────────────────────────────────────
MIN_POST_SCORE    = 20
MIN_COMMENTS      = 10
MIN_COMMENT_SCORE = 10
TARGET_PER_SUB    = 100

POSTS_FILE    = "self_improvement_threads.csv"
COMMENTS_FILE = "self_improvement_comments.csv"

POSTS_API    = "https://arctic-shift.photon-reddit.com/api/posts/search"
COMMENTS_API = "https://arctic-shift.photon-reddit.com/api/comments/search"
HEADERS      = {"User-Agent": "self-improvement-research/1.0"}

POST_FIELDS    = "id,title,score,num_comments,selftext,created_utc,author,subreddit,url,link_flair_text"
COMMENT_FIELDS = "id,link_id,score,body,created_utc,author,subreddit"

# ── Communities ───────────────────────────────────────────────────────────────
# (subreddit_name, community_category)
SUBREDDITS = [
    ("selfimprovement",    "Core Self-Improvement"),
    ("getdisciplined",     "Core Self-Improvement"),
    ("DecidingToBeBetter", "Core Self-Improvement"),
    ("selfhelp",           "Core Self-Improvement"),
    ("manprovement",       "Male-Specific"),
    ("becomeaman",         "Male-Specific"),
    ("AskMen",             "Male Identity"),
    ("AskMenOver30",       "Male Identity"),
    ("AskMenOver40",       "Male Identity"),
    ("MensLib",            "Male Identity"),
    ("NoFap",              "Discipline & Habits"),
    ("Stoicism",           "Philosophy & Mindset"),
    ("socialskills",       "Social & Confidence"),
    ("malementalhealth",   "Mental Health"),
    ("productivity",       "Discipline & Habits"),
]

QUERIES = [
    # Stuck / stagnant
    "I feel stuck in life",
    "my life is going nowhere",
    "wasting my potential",
    "wasting my life",
    "life on autopilot",
    "not where I want to be",
    "falling behind in life",
    "coasting through life",
    "not living up to my potential",
    "I know I can do more but I don't",
    # No discipline
    "I have no discipline",
    "can't stick to anything",
    "I start things and quit",
    "keep self-sabotaging",
    "I know what I should do but I don't",
    "why can't I follow through",
    "I have no willpower",
    "procrastinating my life away",
    "can't build habits",
    "why do I give up so easily",
    "addicted to comfort",
    "I'm lazy and I hate it",
    # No purpose / direction
    "I have no purpose",
    "don't know what I want in life",
    "feel empty inside",
    "nothing matters to me",
    "my job means nothing to me",
    "I don't know who I am",
    "I have no goals",
    "I don't know my values",
    # Identity
    "not the man I want to be",
    "I don't recognize myself anymore",
    "ashamed of who I've become",
    "I used to have ambition",
    "I lost myself",
    "not proud of myself",
    "I hate who I am",
    "I need to become a better man",
    "I've let myself go",
    "become a better man",
    "what does it mean to be a man",
    # Post-setback
    "hit rock bottom",
    "starting over at 30",
    "starting over at 40",
    "starting over after divorce",
    "rebuilding my life",
    "after my divorce I realized",
    "rock bottom was the best thing",
    "turning my life around",
    "I decided to change my life",
    "wake up call",
    # Comparison
    "everyone has their life together but me",
    "I'm behind my peers",
    "men my age already have",
    "nothing to show for it at 30",
    "comparing myself to other men",
    "feel like a failure compared to",
    # Active builder
    "working on myself",
    "best version of myself",
    "self improvement journey",
    "discipline changed my life",
    "habits that changed my life",
    "how I transformed myself",
    "morning routine changed everything",
    "self improvement results",
    "one year of self improvement",
    "what working on yourself actually looks like",
]


# ── Gender filter ─────────────────────────────────────────────────────────────
_FEMALE_RE = re.compile(
    r'\b\d{1,2}\s*f\b|\(f\)|\[f\]|\bi\s+\(f\b|\bshe/her\b|\bher/she\b',
    re.IGNORECASE,
)
_FEMALE_PHRASES = [
    "i'm a woman", "i am a woman", "as a woman", "as a girl",
    "i'm female", "i am female", "woman here", "female here",
    "i'm a girl", "i am a girl", "my husband", "my ex-husband",
    "us women", "we women", "as a wife", "i was pregnant",
    "my mascara", "my lipstick", "year old woman", "year-old woman",
    "my ex-boyfriend", "my ex boyfriend",
]

def is_female_poster(title: str, body: str) -> bool:
    text = title + " " + body
    if _FEMALE_RE.search(text[:500]):
        return True
    return any(p in (title + " " + body).lower() for p in _FEMALE_PHRASES)


# ── Relevance filters ─────────────────────────────────────────────────────────
_SI_SIGNALS = [
    "self improvement", "self-improvement", "personal development", "personal growth",
    "working on myself", "best version", "better version",
    "become a better", "becoming a better", "improve myself", "improving myself",
    "transform", "reinvent", "discipline", "habits", "routine", "consistency",
    "willpower", "procrastinat", "self-sabotage", "follow through", "stick to",
    "accountability", "goals", "purpose", "potential", "ambition", "drive",
    "identity", "who i am", "who i want to be", "masculinity", "manhood",
    "stuck", "stagnant", "going nowhere", "wasting", "autopilot",
    "falling behind", "nothing to show", "coasting",
    "rock bottom", "starting over", "rebuilding", "turning around",
    "wake up call", "decided to change",
]

def has_self_improvement_signal(text: str) -> bool:
    t = text.lower()
    return any(s in t for s in _SI_SIGNALS)

def has_personal_experience(text: str) -> bool:
    t = text.lower()
    return any(s in t for s in [
        "i am", "i'm", "i was", "i feel", "i felt", "i've been",
        "i used to", "i realized", "i noticed", "i struggle",
        "my problem", "my issue", "in my case", "i keep", "i can't",
        "i don't", "i hate", "all my life", "growing up",
        "at 30", "at 35", "at 40", "after my divorce",
        "i decided", "i started", "i committed",
    ])


# ── Segment tagging ───────────────────────────────────────────────────────────
def segment_tag(title: str, body: str) -> str:
    text = (title + " " + body).lower()

    if any(k in text for k in [
        "rock bottom", "starting over", "rebuilding my life", "after my divorce",
        "lost everything", "wake up call", "decided to change my life",
        "turning my life around", "comeback", "i hit bottom",
    ]):
        return "Post-Setback Reinvention"

    if any(k in text for k in [
        "no purpose", "don't know what i want", "feel empty", "nothing matters",
        "no passion", "job means nothing", "don't know who i am",
        "wake up and feel nothing", "no goals", "no direction",
        "what it means to be a man", "masculinity", "manhood", "identity",
    ]):
        return "Lost Purpose / No Direction"

    if any(k in text for k in [
        "no discipline", "can't stick", "i start and quit", "self-sabotag",
        "know what i should do but", "no willpower", "procrastinat",
        "give up so easily", "addicted to comfort", "lazy and i hate",
        "can't follow through", "can't build habits", "choose short term",
    ]):
        return "No Discipline / Can't Stick to Anything"

    if any(k in text for k in [
        "not the man i want to be", "don't recognize myself", "ashamed of who",
        "lost myself", "not proud of myself", "hate who i am",
        "let myself go", "not the father", "not the husband",
        "used to have ambition", "need to become a better man",
    ]):
        return "Identity Crisis / Not the Man I Want to Be"

    if any(k in text for k in [
        "stuck in life", "going nowhere", "wasting my potential", "wasting my life",
        "life on autopilot", "not growing", "not where i want to be",
        "falling behind", "coasting", "not living up",
    ]):
        return "Stuck / Stagnant / Going Nowhere"

    if any(k in text for k in [
        "everyone has their life together", "behind my peers", "men my age",
        "nothing to show for it", "comparing myself", "friends are ahead",
        "feel like a failure compared", "successful men my age",
    ]):
        return "Comparison / Falling Behind Other Men"

    if any(k in text for k in [
        "working on myself", "best version of myself", "self improvement journey",
        "discipline changed my life", "habits that changed", "how i transformed",
        "i decided to get serious", "morning routine", "one year of", "results",
    ]):
        return "Active Builder / Already on the Path"

    return "General Self-Improvement Struggle"


# ── API helpers ───────────────────────────────────────────────────────────────
def api_get(url: str, params: dict) -> Optional[list]:
    for attempt in range(3):
        try:
            time.sleep(0.8)
            r = requests.get(url, headers=HEADERS, params=params, timeout=20)
            if r.status_code == 429:
                wait = 30 * (attempt + 1)
                print(f"  Rate limited — waiting {wait}s...", flush=True)
                time.sleep(wait)
                continue
            if r.status_code != 200:
                return None
            return r.json().get("data", []) or []
        except Exception as e:
            print(f"  Request failed: {e}", flush=True)
            time.sleep(5)
    return None


# ── Phase 1: Posts ────────────────────────────────────────────────────────────
def scrape_posts(existing_ids: set) -> list[dict]:
    all_posts = []
    seen = set(existing_ids)

    for subreddit, category in SUBREDDITS:
        sub_posts = []
        print(f"\n[{subreddit}] targeting {TARGET_PER_SUB} posts...", flush=True)

        for query in QUERIES:
            if len(sub_posts) >= TARGET_PER_SUB:
                break

            posts = api_get(POSTS_API, {
                "query":     query,
                "subreddit": subreddit,
                "limit":     100,
                "fields":    POST_FIELDS,
            })
            if not posts:
                continue

            for p in posts:
                if len(sub_posts) >= TARGET_PER_SUB:
                    break

                pid = str(p.get("id", ""))
                if not pid or pid in seen:
                    continue
                if p.get("score", 0) < MIN_POST_SCORE:
                    continue
                if p.get("num_comments", 0) < MIN_COMMENTS:
                    continue

                body = (p.get("selftext", "") or "").strip()
                if len(body) < 100 or body in ("[removed]", "[deleted]"):
                    continue

                title = p.get("title", "")
                combined = title + " " + body

                if is_female_poster(title, body):
                    continue
                if not has_self_improvement_signal(combined):
                    continue
                if not has_personal_experience(combined) and len(body) < 200:
                    continue

                seen.add(pid)
                sub_posts.append({
                    "post_id":          pid,
                    "title":            title,
                    "subreddit":        subreddit,
                    "community_category": category,
                    "score":            p.get("score", 0),
                    "num_comments":     p.get("num_comments", 0),
                    "url":              p.get("url", ""),
                    "created_date":     datetime.utcfromtimestamp(
                                            int(p["created_utc"])
                                        ).strftime("%Y-%m-%d") if p.get("created_utc") else "",
                    "author":           p.get("author", ""),
                    "post_body":        body[:2000],
                    "segment_tag":      segment_tag(title, body),
                    "flair":            p.get("link_flair_text", "") or "",
                    "matched_query":    query,
                })

        print(f"  → {len(sub_posts)} qualifying posts found", flush=True)
        all_posts.extend(sub_posts)

    return all_posts


# ── Phase 2: Comments ─────────────────────────────────────────────────────────
def scrape_comments(posts: list[dict], existing_comment_ids: set) -> list[dict]:
    seen = set(existing_comment_ids)
    all_comments = []
    total = len(posts)

    for i, post in enumerate(posts):
        if (i + 1) % 50 == 0:
            print(f"  Comments: {i+1}/{total} posts processed ({len(all_comments)} comments so far)", flush=True)

        post_id = post["post_id"]
        comments = api_get(COMMENTS_API, {
            "link_id": f"t3_{post_id}",
            "limit":   100,
            "fields":  COMMENT_FIELDS,
        })
        if not comments:
            continue

        for c in comments:
            cid = str(c.get("id", ""))
            if not cid or cid in seen:
                continue
            if c.get("score", 0) < MIN_COMMENT_SCORE:
                continue

            body = (c.get("body", "") or "").strip()
            if len(body) < 30 or body in ("[removed]", "[deleted]"):
                continue

            seen.add(cid)
            all_comments.append({
                "comment_id":         cid,
                "post_id":            post_id,
                "post_title":         post["title"],
                "subreddit":          post["subreddit"],
                "community_category": post["community_category"],
                "segment_tag":        post["segment_tag"],
                "comment_score":      c.get("score", 0),
                "comment_body":       body[:1500],
                "created_date":       datetime.utcfromtimestamp(
                                          int(c["created_utc"])
                                      ).strftime("%Y-%m-%d") if c.get("created_utc") else "",
                "author":             c.get("author", ""),
                "post_url":           post["url"],
            })

    return all_comments


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    print("=" * 60)
    print("Scraping: men becoming the best version of themselves")
    print(f"Source:   Arctic Shift API (no auth required)")
    print(f"Criteria: posts score≥{MIN_POST_SCORE}, comments≥{MIN_COMMENTS} | comment score≥{MIN_COMMENT_SCORE}")
    print(f"Target:   {TARGET_PER_SUB} posts per community × {len(SUBREDDITS)} communities")
    print("=" * 60)

    # ── Load existing posts ───────────────────────────────────────────────────
    existing_posts = []
    existing_post_ids: set = set()
    try:
        df_existing = pd.read_csv(POSTS_FILE)
        existing_post_ids = set(df_existing["post_id"].astype(str))
        existing_posts = df_existing.to_dict("records")
        print(f"\nLoaded {len(existing_posts)} existing posts — appending new only.\n")
    except FileNotFoundError:
        print("\nNo existing posts file — starting fresh.\n")

    # ── Load existing comments ────────────────────────────────────────────────
    existing_comments = []
    existing_comment_ids: set = set()
    try:
        df_exc = pd.read_csv(COMMENTS_FILE)
        existing_comment_ids = set(df_exc["comment_id"].astype(str))
        existing_comments = df_exc.to_dict("records")
        print(f"Loaded {len(existing_comments)} existing comments — appending new only.\n")
    except FileNotFoundError:
        pass

    # ── Phase 1: Posts ────────────────────────────────────────────────────────
    print("\n── PHASE 1: Scraping posts ──────────────────────────────")
    new_posts = scrape_posts(existing_post_ids)
    all_posts = existing_posts + new_posts

    df_posts = pd.DataFrame(all_posts)
    df_posts.drop_duplicates(subset="post_id", inplace=True)
    df_posts.sort_values(["subreddit", "score"], ascending=[True, False], inplace=True)
    df_posts.reset_index(drop=True, inplace=True)
    df_posts.to_csv(POSTS_FILE, index=False, encoding="utf-8-sig")

    print(f"\n── PHASE 1 RESULTS ──────────────────────────────────────")
    print(f"Total posts saved: {len(df_posts)}")
    print(f"\nPosts per community:")
    print(df_posts.groupby(["community_category", "subreddit"])["post_id"].count().to_string())
    print(f"\nSegment distribution:")
    print(df_posts["segment_tag"].value_counts().to_string())

    # ── Phase 2: Comments ─────────────────────────────────────────────────────
    print(f"\n── PHASE 2: Scraping comments ({len(df_posts)} posts) ────────")
    posts_for_comments = df_posts.to_dict("records")
    new_comments = scrape_comments(posts_for_comments, existing_comment_ids)
    all_comments = existing_comments + new_comments

    df_comments = pd.DataFrame(all_comments)
    if not df_comments.empty:
        df_comments.drop_duplicates(subset="comment_id", inplace=True)
        df_comments.sort_values(["subreddit", "comment_score"], ascending=[True, False], inplace=True)
        df_comments.reset_index(drop=True, inplace=True)
        df_comments.to_csv(COMMENTS_FILE, index=False, encoding="utf-8-sig")

    print(f"\n── FINAL RESULTS ────────────────────────────────────────")
    print(f"Posts:    {len(df_posts)} → {POSTS_FILE}")
    print(f"Comments: {len(df_comments)} → {COMMENTS_FILE}")
    if not df_comments.empty:
        print(f"\nComments per community:")
        print(df_comments.groupby("subreddit")["comment_id"].count().to_string())


if __name__ == "__main__":
    main()
