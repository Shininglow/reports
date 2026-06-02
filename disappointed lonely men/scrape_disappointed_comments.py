"""
Scrape top comments from posts already collected in disappointed_men.csv.
Commenters responding to "burned/disappointed man" posts often share their
own similar experiences — rich raw voice for audience research.
Output: disappointed_men_comments.csv
"""

import requests
import pandas as pd
import time
import re
from datetime import datetime

INPUT_FILE     = "disappointed_men.csv"
OUTPUT_FILE    = "disappointed_men_comments.csv"
MIN_UPVOTES    = 10
MIN_LENGTH     = 120
TOP_N_POSTS    = 200   # take top posts by score to limit API calls
COMMENTS_LIMIT = 100   # per post
HEADERS        = {
    "User-Agent": "script:attachment-research:v1.0 (personal research project)",
    "Accept": "application/json",
}


# ── Gender + quality filters ──────────────────────────────────────────────────

_FEMALE_RE = re.compile(
    r'\b\d{1,2}\s*f\b|\(f\)|\[f\]|\bi\s+\(f\b|\bshe/her\b|\bher/she\b',
    re.IGNORECASE,
)

_FEMALE_PHRASES = [
    "i'm a woman", "i am a woman", "as a woman", "as a girl",
    "i'm female", "i am female", "woman here", "female here",
    "i'm a girl", "i am a girl",
    "my husband", "my ex-husband", "my boyfriend cheated",
    "us women", "we women", "as a wife",
    "i was pregnant", "months pregnant",
    "wearing makeup", "wearing make up", "my mascara", "my lipstick",
    "year old girl", "year-old girl", "year old woman", "year-old woman",
    "my ex-boyfriend", "my ex boyfriend",
]


def is_female_comment(text: str) -> bool:
    if _FEMALE_RE.search(text[:500]):
        return True
    t = text.lower()
    return any(phrase in t for phrase in _FEMALE_PHRASES)


def has_personal_signal(text: str) -> bool:
    """Comment must share a personal experience, not just give advice."""
    t = text.lower()
    signals = [
        "i went through", "i was in", "same happened to me", "happened to me",
        "been through this", "i've been there", "i can relate", "i relate",
        "i know the feeling", "i know how you feel", "i felt the same",
        "my ex", "my divorce", "my breakup", "my relationship",
        "she cheated on me", "she left me", "she used me", "she betrayed",
        "i gave everything", "i gave my all", "gave 100%",
        "i lost myself", "i was destroyed", "it broke me",
        "i trusted her", "i loved her", "i sacrificed",
        "i swore off", "i gave up on", "i'm done with",
        "after my divorce", "after the breakup", "after she left",
        "i used to be", "i was once", "years ago i",
        "i've been single since", "haven't dated since",
        "i'm still recovering", "still haven't",
        "this is exactly me", "this is me", "this is my life",
        "i wrote this", "did you write this about me",
        "word for word my story", "could have written this",
    ]
    return any(s in t for s in signals)


def has_disappointment_signal(text: str) -> bool:
    t = text.lower()
    signals = [
        "drained me", "emotionally exhausted", "broke me", "destroyed me",
        "shattered me", "crushed me", "lost myself", "never been the same",
        "don't trust", "can't trust", "trust issues", "walls up",
        "closed off", "numb", "afraid to love", "scared to love",
        "gave everything", "gave my all", "one-sided", "she cheated",
        "she used me", "she manipulated", "done with relationships",
        "sworn off", "never again", "not worth it", "better off alone",
        "given up on love", "gave up on dating", "stopped trying",
        "used me", "taken advantage", "she left when",
        "after the divorce", "since the breakup",
    ]
    return any(s in t for s in signals)


def segment_tag(text: str) -> str:
    t = text.lower()
    if any(k in t for k in ["cheated", "infidelity", "unfaithful", "she lied", "betrayed"]):
        return "Betrayed / Cheated On"
    if any(k in t for k in ["divorce", "married", "marriage", "ex-wife", "after my divorce"]):
        return "Post-Divorce Rebuilder"
    if any(k in t for k in ["gave everything", "gave my all", "one-sided", "not reciprocated", "she didn't appreciate"]):
        return "One-Sided Giver / Depleted"
    if any(k in t for k in ["drained", "exhausted", "lost myself", "emotionally depleted", "became a shell"]):
        return "Emotionally Drained / Lost Self"
    if any(k in t for k in ["done with", "sworn off", "never again", "better off alone", "not worth it", "giving up", "given up"]):
        return "Resigned / Sworn Off Love"
    if any(k in t for k in ["can't trust", "don't trust", "trust issues", "walls up", "closed off", "afraid to love", "numb"]):
        return "Guarded / Can't Trust Again"
    if any(k in t for k in ["used me", "she only wanted", "taken advantage", "she was using", "she left when"]):
        return "Used / Taken Advantage Of"
    return "General / Disappointed in Love"


def fetch_comments(post_url: str) -> list[dict]:
    """
    Fetch top comments from a Reddit post.
    post_url e.g. https://reddit.com/r/self/comments/1fpm7sw/title_slug/
    """
    # Normalise URL → JSON endpoint
    url = post_url.rstrip("/")
    if not url.endswith(".json"):
        url = url + ".json"

    params = {"sort": "top", "limit": COMMENTS_LIMIT, "depth": 1}
    for attempt in range(3):
        try:
            time.sleep(1.5)
            r = requests.get(url, headers=HEADERS, params=params, timeout=15)
            if r.status_code == 429:
                wait = 30 * (attempt + 1)
                print(f"  Rate limited — waiting {wait}s...", flush=True)
                time.sleep(wait)
                continue
            r.raise_for_status()
            data = r.json()
            # Reddit returns [post_listing, comment_listing]
            if not isinstance(data, list) or len(data) < 2:
                return []
            children = data[1]["data"].get("children", [])
            comments = []
            for child in children:
                if child.get("kind") != "t1":
                    continue
                c = child["data"]
                body = (c.get("body", "") or "").strip()
                if body in ("[removed]", "[deleted]", ""):
                    continue
                comments.append({
                    "comment_id":   c.get("id", ""),
                    "author":       c.get("author", ""),
                    "score":        c.get("score", 0),
                    "body":         body,
                    "created_date": datetime.utcfromtimestamp(
                        c.get("created_utc", 0)
                    ).strftime("%Y-%m-%d"),
                })
            return comments
        except Exception as e:
            print(f"  Request failed: {e}", flush=True)
            time.sleep(5)
    return []


def main():
    # Load source posts
    posts_df = pd.read_csv(INPUT_FILE)
    posts_df.sort_values("score", ascending=False, inplace=True)
    posts_df = posts_df.head(TOP_N_POSTS).reset_index(drop=True)
    print(f"Processing top {len(posts_df)} posts from {INPUT_FILE}\n", flush=True)

    # Load existing comments to avoid re-scraping
    seen_ids: set[str] = set()
    records = []
    try:
        existing = pd.read_csv(OUTPUT_FILE)
        seen_ids = set(existing["comment_id"].astype(str))
        records = existing.to_dict("records")
        print(f"Loaded {len(existing)} existing comments.", flush=True)
    except FileNotFoundError:
        pass

    for i, row in posts_df.iterrows():
        post_url  = row["url"]
        post_id   = row["id"]
        post_title = row.get("title", "")
        post_sub  = row.get("subreddit", "")
        post_seg  = row.get("segment_tag", "")

        print(f"[{i+1}/{len(posts_df)}] r/{post_sub} — {post_title[:60]}", flush=True)
        comments = fetch_comments(post_url)

        kept = 0
        for c in comments:
            if c["comment_id"] in seen_ids:
                continue
            if c["score"] < MIN_UPVOTES:
                continue
            body = c["body"]
            if len(body) < MIN_LENGTH:
                continue
            if is_female_comment(body):
                continue
            # Need either personal signal OR disappointment signal (not just advice)
            if not has_personal_signal(body) and not has_disappointment_signal(body):
                continue

            seen_ids.add(c["comment_id"])
            records.append({
                "comment_id":       c["comment_id"],
                "post_id":          post_id,
                "post_title":       post_title,
                "post_subreddit":   post_sub,
                "post_segment":     post_seg,
                "post_url":         post_url,
                "author":           c["author"],
                "score":            c["score"],
                "created_date":     c["created_date"],
                "comment_body":     body[:2000],
                "segment_tag":      segment_tag(body),
            })
            kept += 1

        print(f"  → {len(comments)} comments fetched, {kept} kept", flush=True)

    if not records:
        print("\nNo comments collected.", flush=True)
        return

    df = pd.DataFrame(records)
    df.drop_duplicates(subset="comment_id", inplace=True)
    df.sort_values("score", ascending=False, inplace=True)
    df.reset_index(drop=True, inplace=True)
    df.to_csv(OUTPUT_FILE, index=False, encoding="utf-8-sig")

    print(f"\n{'='*60}")
    print(f"✓ Saved {len(df)} comments to '{OUTPUT_FILE}'")
    print(f"\nSegment distribution:\n{df['segment_tag'].value_counts().to_string()}")
    print(f"\nTop 15 by score:")
    print(df[["post_subreddit", "score", "segment_tag", "comment_body"]]
          .head(15)
          .assign(comment_body=lambda x: x["comment_body"].str[:120])
          .to_string(index=False))


if __name__ == "__main__":
    main()
