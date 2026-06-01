"""
Scrape Reddit threads about Anxious, Avoidant, and Disorganized (Fearful-Avoidant)
attachment styles.

Three output CSVs:
  anxious_posts.csv       — Anxious / Preoccupied attachment
  avoidant_posts.csv      — Avoidant / Dismissive-Avoidant attachment
  disorganized_posts.csv  — Fearful-Avoidant / Disorganized attachment

Strategy:
  Phase 1 — Browse dedicated subreddits (/top, /new)
  Phase 2 — Search general subreddits with targeted queries, then classify
"""
import requests
import pandas as pd
import time
import re
from datetime import datetime

# ── CONFIG ────────────────────────────────────────────────────────────────────
MIN_UPVOTES  = 50
MIN_COMMENTS = 5
TARGET       = 200   # target posts per cluster
LIMIT        = 100
HEADERS      = {"User-Agent": "Mozilla/5.0 (compatible; research-scraper/1.0)"}

# ── DEDICATED SUBREDDITS (phase 1) ────────────────────────────────────────────
DEDICATED = {
    "anxious":      ["anxiousattachment"],
    "avoidant":     ["AvoidantAttachment"],
    "disorganized": ["fearfulavoidant"],
}

# ── GENERAL SUBREDDITS (phase 2) ──────────────────────────────────────────────
GENERAL_SUBS = [
    "relationships", "relationship_advice", "breakups",
    "ExNoContact", "datingoverthirty", "dating_advice",
]

# Targeted queries per cluster for general sub searches
QUERIES = {
    "anxious": [
        "anxious attachment", "preoccupied attachment", "anxiously attached",
        "abandonment anxiety", "abandonment issues in relationship",
        "protest behavior attachment", "need reassurance relationship",
        "hyperactivating attachment", "clingy anxious", "AP partner",
        "anxious avoidant dynamic", "anxious attachment and avoidant",
        "I have anxious attachment", "my anxious attachment",
    ],
    "avoidant": [
        "dismissive avoidant", "avoidant attachment", "avoidant partner",
        "emotionally unavailable partner", "deactivating attachment",
        "avoidant pulls away", "avoidant ex", "I am avoidant",
        "avoidant withdraws", "avoidant shuts down",
        "dismissive avoidant relationship", "avoidant walls up",
        "my DA partner", "dating a dismissive avoidant",
    ],
    "disorganized": [
        "fearful avoidant", "fearful-avoidant", "disorganized attachment",
        "FA attachment", "push pull relationship",
        "hot and cold attachment", "I am fearful avoidant",
        "fearful avoidant ex", "fearful avoidant partner",
        "FA deactivating", "want love fear intimacy",
        "disorganized attachment relationship",
        "anxious avoidant disorganized",
    ],
}

# ── CLASSIFICATION PATTERNS ───────────────────────────────────────────────────
ANXIOUS_PATTERNS = [
    r"\banxious\s+attach",
    r"\bpreoccupied\s+attach",
    r"\banxiously\s+attach",
    r"\babandonment\s+(anxiety|fear|issues)",
    r"\bprotest\s+behav",
    r"\bhyperactivat",
    r"\bneed\s+(?:constant\s+)?reassurance",
    r"\b(?:I\s+(?:am|have)|my)\s+anxious\s+attach",
    r"\bAP\s+(?:partner|attachment|style)\b",
    r"\banxious\s+style\b",
    r"\bclingy\b.{0,40}\brelationship\b",
]

AVOIDANT_PATTERNS = [
    r"\bdismissive.?avoidant",
    r"\bavoidant\s+attach",
    r"\bemotionally\s+unavailable",
    r"\bdeactivat",
    r"\bavoidant\s+(?:partner|ex|style|person|man|woman|guy|girl)\b",
    r"\b(?:I\s+(?:am|have)|my)\s+(?:dismissive\s+)?avoidant\s+attach",
    r"\bDA\s+(?:partner|ex|attachment|style)\b",
    r"\bpulls?\s+away.{0,30}\bavoidant",
    r"\bwalls?\s+up.{0,20}\brelationship",
    r"\bfear\s+(?:of\s+)?(?:intimacy|commitment|closeness).{0,30}avoidant",
    r"\bavoidant\s+withdraws?",
]

DISORGANIZED_PATTERNS = [
    r"\bfearful.?avoidant",
    r"\bdisorganized\s+attach",
    r"\bFA\s+(?:partner|ex|attachment|style|deactivat)\b",
    r"\b(?:I\s+(?:am|have)|my)\s+(?:fearful.?avoidant|disorganized)\s+attach",
    r"\bpush.?pull\s+(?:relationship|dynamic|pattern)",
    r"\bhot\s+and\s+cold.{0,30}\brelationship",
    r"\bwant\s+(?:love|connection).{0,30}fear\s+(?:it|intimacy|getting\s+close)",
    r"\bfear\s+(?:abandon|intimacy).{0,40}same\s+time",
    r"\bfearful\s+avoidant\s+(?:ex|partner|person|man|woman)",
]

def classify(title: str, body: str, subreddit: str):
    """Return 'anxious', 'avoidant', 'disorganized', or None (unknown)."""
    # Subreddit-based shortcut
    sub = subreddit.lower()
    if sub in ("anxiousattachment",):
        return "anxious"
    if sub in ("avoidantattachment",):
        return "avoidant"
    if sub in ("fearfulavoidant",):
        return "disorganized"

    text = f"{title} {str(body or '')}"

    # Check most specific first (disorganized), then avoidant, then anxious
    if any(re.search(p, text, re.IGNORECASE) for p in DISORGANIZED_PATTERNS):
        return "disorganized"
    if any(re.search(p, text, re.IGNORECASE) for p in AVOIDANT_PATTERNS):
        return "avoidant"
    if any(re.search(p, text, re.IGNORECASE) for p in ANXIOUS_PATTERNS):
        return "anxious"
    return None

def perspective(title: str, body: str) -> str:
    """Detect whether OP is writing about themselves or about a partner."""
    text = f"{title} {str(body or '')}"
    self_patterns = [
        r"\bI\s+(?:am|have|had|identify\s+as|think\s+I'?m?)\s+(?:an?\s+)?(?:anxious|avoidant|fearful|dismissive|disorganized)\b",
        r"\bmy\s+(?:anxious|avoidant|fearful|dismissive|disorganized)\s+attach",
        r"\bas\s+(?:an?\s+)?(?:anxious|avoidant|FA|DA|AP)\b",
        r"\bI'?m?\s+(?:an?\s+)?(?:anxious|avoidant|FA|DA|AP)\b",
        r"\bI\s+(?:struggle|deal)\s+with\s+(?:anxious|avoidant)",
        r"\bmy\s+(?:own\s+)?attachment\s+style\b",
    ]
    partner_patterns = [
        r"\bmy\s+(?:partner|ex|girlfriend|boyfriend|gf|bf|husband|wife|SO)\s+(?:is|has|was)\s+(?:an?\s+)?(?:anxious|avoidant|fearful|dismissive)",
        r"\bdating\s+(?:an?\s+)?(?:anxious|avoidant|fearful|dismissive|FA|DA)\b",
        r"\b(?:partner|ex|gf|bf|SO)\s+(?:with|who\s+has)\s+(?:anxious|avoidant|fearful)",
        r"\bmy\s+(?:DA|FA|AP)\s+(?:ex|partner|boyfriend|girlfriend)\b",
    ]
    if any(re.search(p, text, re.IGNORECASE) for p in self_patterns):
        return "self-reflection"
    if any(re.search(p, text, re.IGNORECASE) for p in partner_patterns):
        return "partner-perspective"
    return "general"

# ── API HELPERS ───────────────────────────────────────────────────────────────
def get(url: str, params: dict):
    for attempt in range(2):
        try:
            r = requests.get(url, headers=HEADERS, params=params, timeout=15)
            if r.status_code == 429:
                wait = 30 if attempt == 0 else 60
                print(f"    Rate limited — waiting {wait}s...")
                time.sleep(wait)
                continue
            r.raise_for_status()
            return r.json()
        except Exception as e:
            print(f"    Request failed: {e}")
            time.sleep(2)
    return None

def extract(p: dict) -> tuple[str, str, dict]:
    title = p.get("title", "")
    body  = (p.get("selftext", "") or "")[:1200].strip()
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

# ── SCRAPING FUNCTIONS ────────────────────────────────────────────────────────
def browse_subreddit(subreddit: str, sort: str, time_filter: str,
                     seen: set, bucket: list, target: int, pages: int = 5):
    after = None
    for _ in range(pages):
        if len(bucket) >= target:
            break
        params = {"limit": LIMIT, "t": time_filter}
        if after:
            params["after"] = after
        data = get(f"https://www.reddit.com/r/{subreddit}/{sort}.json", params)
        if not data:
            break
        children = data.get("data", {}).get("children", [])
        after    = data.get("data", {}).get("after")
        for child in children:
            p = child["data"]
            if p["id"] in seen:
                continue
            if p["score"] < MIN_UPVOTES or p["num_comments"] < MIN_COMMENTS:
                continue
            title, body, row = extract(p)
            ctype = classify(title, body, p["subreddit"])
            if not ctype:
                continue
            row["attachment_type"] = ctype
            row["post_perspective"] = perspective(title, body)
            seen.add(p["id"])
            bucket.append(row)
        if not after:
            break
        time.sleep(1.5)

def search_subreddit(subreddit: str, query: str, time_filter: str,
                     seen: set, buckets: dict, targets: dict):
    data = get(
        f"https://www.reddit.com/r/{subreddit}/search.json",
        {"q": query, "sort": "top", "t": time_filter,
         "limit": LIMIT, "restrict_sr": 1}
    )
    if not data:
        return
    for child in data.get("data", {}).get("children", []):
        p = child["data"]
        if p["id"] in seen:
            continue
        if p["score"] < MIN_UPVOTES or p["num_comments"] < MIN_COMMENTS:
            continue
        title, body, row = extract(p)
        ctype = classify(title, body, p["subreddit"])
        if not ctype:
            continue
        if len(buckets[ctype]) >= targets[ctype]:
            continue
        row["attachment_type"] = ctype
        row["post_perspective"] = perspective(title, body)
        seen.add(p["id"])
        buckets[ctype].append(row)

# ── MAIN ──────────────────────────────────────────────────────────────────────
def main():
    buckets = {"anxious": [], "avoidant": [], "disorganized": []}
    targets = {"anxious": TARGET, "avoidant": TARGET, "disorganized": TARGET}
    seen    = set()

    # ─── PHASE 1: dedicated subreddits ───────────────────────────────────────
    for ctype, subs in DEDICATED.items():
        for sub in subs:
            print(f"\n{'='*60}")
            print(f"Phase 1 — r/{sub}  ({ctype})")
            for sort, tf in [("top","all"),("top","year"),("top","month"),("new","week")]:
                if len(buckets[ctype]) >= targets[ctype]:
                    break
                print(f"  Browsing /{sort} t={tf} ... ({len(buckets[ctype])} collected)")
                browse_subreddit(sub, sort, tf, seen, buckets[ctype], targets[ctype])
                time.sleep(1.5)
            print(f"  → {len(buckets[ctype])} posts after phase 1")

    # ─── PHASE 2: general subreddits with targeted queries ───────────────────
    print(f"\n{'='*60}")
    print("Phase 2 — General subreddits with targeted queries")

    for ctype, queries in QUERIES.items():
        if len(buckets[ctype]) >= targets[ctype]:
            print(f"  {ctype}: already at target, skipping phase 2")
            continue
        print(f"\n  → {ctype} (need {targets[ctype] - len(buckets[ctype])} more)")
        for query in queries:
            if len(buckets[ctype]) >= targets[ctype]:
                break
            for sub in GENERAL_SUBS:
                if len(buckets[ctype]) >= targets[ctype]:
                    break
                for tf in ["year", "all"]:
                    search_subreddit(sub, query, tf, seen, buckets, targets)
                    time.sleep(1.2)

    # ─── SAVE ─────────────────────────────────────────────────────────────────
    FILES = {
        "anxious":      "anxious_posts.csv",
        "avoidant":     "avoidant_posts.csv",
        "disorganized": "disorganized_posts.csv",
    }

    print(f"\n{'='*60}")
    for ctype, rows in buckets.items():
        fname = FILES[ctype]
        if not rows:
            print(f"  {ctype}: no posts collected")
            continue
        df = pd.DataFrame(rows)
        df.drop_duplicates(subset="id", inplace=True)
        df.sort_values("score", ascending=False, inplace=True)
        df.reset_index(drop=True, inplace=True)
        df.to_csv(fname, index=False, encoding="utf-8-sig")
        print(f"\n  {ctype.upper()} → '{fname}' ({len(df)} posts)")
        print(f"    Score range: {df['score'].min()}–{df['score'].max()}, avg: {df['score'].mean():.0f}")
        print(f"    Perspectives: {df['post_perspective'].value_counts().to_dict()}")
        print(f"    Top 5:")
        for _, r in df.head(5).iterrows():
            print(f"      [{r['score']:>5}] {r['title'][:72]}")

if __name__ == "__main__":
    main()
