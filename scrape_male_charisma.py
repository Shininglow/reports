"""
Scrape Reddit for men working on charm, charisma, social confidence, and presence.
Target: men who feel invisible/forgettable, have approach anxiety, no chemistry
on dates, or are actively rebuilding their social game after being burned.
Audience: Art of Charm / Charisma on Command / social-skills self-improvement.

Segments:
  - Socially Invisible / Forgettable
  - Approach Anxiety / Freezes Up
  - No Chemistry on Dates / Good on Paper
  - Nice Guy / No Backbone / Too Agreeable
  - Building Presence / Inner Game
  - Post-Hurt Reinvention / Rebuilding Confidence
  - Awkward / Overthinking / In My Head

Output: male_charisma_charm.csv (append-safe)
"""

import requests
import pandas as pd
import time
import re
from datetime import datetime
from typing import Optional

MIN_UPVOTES  = 20
MIN_COMMENTS = 2
OUTPUT_FILE  = "male_charisma_charm.csv"
HEADERS      = {
    "User-Agent": "script:attachment-research:v1.0 (personal research project)",
    "Accept": "application/json",
}

QUERIES = [
    # Invisible / forgettable
    "nobody notices me",
    "people forget about me",
    "boring forgettable personality",
    "I have no presence",
    "people don't remember me",
    "I'm invisible to women",
    "I blend into the background",
    "no one gravitates toward me",
    "people don't take me seriously",
    "I'm not memorable",

    # Approach anxiety / paralysis
    "approach anxiety",
    "can't approach women",
    "freeze up talking to women",
    "too scared to talk to women",
    "I overthink every interaction",
    "too nervous to approach",
    "I choke in social situations",
    "panic when talking to attractive women",
    "how to stop being scared to approach",
    "can't initiate conversations",

    # No chemistry / good on paper
    "good on paper but no chemistry",
    "women lose interest after first date",
    "women don't feel chemistry with me",
    "can't keep women interested",
    "dates go well but she pulls away",
    "women say I'm nice but nothing happens",
    "I'm boring on dates",
    "women friend zone me",
    "no spark no attraction",
    "she stopped texting after great date",
    "I tick all the boxes but women aren't attracted",
    "women like me as a friend not romantically",

    # Nice guy / doormat
    "too nice to women",
    "I'm too agreeable",
    "I'm a pushover with women",
    "I put women on a pedestal",
    "nice guy finish last",
    "women don't respect me",
    "I don't know how to be assertive",
    "I have no backbone in relationships",
    "I bend over backwards and she loses respect",
    "I people please too much",
    "I'm afraid of conflict with women",
    "I can't say no to women",

    # Inner game / presence building
    "working on my inner game",
    "how to develop charisma",
    "how to be more charming",
    "how to have more presence",
    "how to be magnetic",
    "how to stop being boring",
    "how to be more confident around women",
    "developing social confidence",
    "how to be more interesting",
    "how to have better conversations",
    "how to flirt naturally",
    "how to banter with women",
    "how to stop being awkward",
    "how to be more playful",
    "art of charm",
    "charisma on command",

    # Overthinking / in my head
    "I'm too in my head",
    "I overthink conversations",
    "I can't be spontaneous",
    "I'm too self-conscious",
    "I monitor myself too much in social situations",
    "I think too much when talking to women",
    "how to stop overthinking and just be natural",
    "social anxiety around women",
    "I rehearse conversations in my head",
    "I can't be present in conversations",

    # Post-hurt reinvention
    "rebuilding confidence after breakup",
    "I lost my confidence after she left",
    "used to be confident now I'm not",
    "heartbreak destroyed my social confidence",
    "becoming a better man after divorce",
    "improving myself after being rejected",
    "I gave up my personality for her",
    "became boring when I was in a relationship",
    "I stopped growing when I was with her",
    "reinventing myself after breakup",
]

SUBREDDITS = [
    # Direct charm / charisma
    "charisma",
    "socialskills",
    "seduction",
    "howtoflirt",
    # Self-improvement pipeline
    "selfimprovement",
    "decidingtobebetter",
    "becomeaman",
    "getdisciplined",
    "NoFap",
    # Dating / attraction application
    "dating_advice",
    "datingoverthirty",
    "datingoverfifty",
    "Tinder",
    "hingeapp",
    # Male identity / philosophy of confidence
    "AskMen",
    "AskMenOver30",
    "AskMenOver40",
    "Stoicism",
    # The "before" picture
    "socialanxiety",
    "lonely",
    "ForeverAlone",
    # Bridge communities (burned + rebuilding)
    "BreakUps",
    "ExNoContact",
]

TIME_FILTERS = ["all", "year"]


# ── Gender filter ─────────────────────────────────────────────────────────────

_FEMALE_RE = re.compile(
    r'\b\d{1,2}\s*f\b|\(f\)|\[f\]|\bi\s+\(f\b|\bshe/her\b|\bher/she\b',
    re.IGNORECASE,
)
_FEMALE_PHRASES = [
    "i'm a woman", "i am a woman", "as a woman", "as a girl",
    "i'm female", "i am female", "woman here", "female here",
    "i'm a girl", "i am a girl",
    "my husband", "my ex-husband",
    "us women", "we women", "as a wife",
    "i was pregnant", "months pregnant",
    "wearing makeup", "wearing make up", "my mascara", "my lipstick",
    "year old girl", "year-old girl", "year old woman", "year-old woman",
    "my ex-boyfriend", "my ex boyfriend",
]


def is_female_poster(title: str, body: str) -> bool:
    text = title + " " + body
    if _FEMALE_RE.search(text[:500]):
        return True
    t = text.lower()
    return any(phrase in t for phrase in _FEMALE_PHRASES)


# ── Relevance filters ─────────────────────────────────────────────────────────

def has_charisma_signal(text: str) -> bool:
    """Post must be about charm, charisma, or social confidence — not generic life advice."""
    t = text.lower()
    signals = [
        # core charm/charisma vocabulary
        "charisma", "charming", "magnetic", "presence", "banter",
        "flirt", "flirting", "playful", "wit", "witty", "smooth",
        "inner game", "outer game", "social skills", "social confidence",
        "art of charm", "charisma on command",
        # approach / attraction
        "approach", "approach anxiety", "cold approach", "open her",
        "chemistry", "attraction", "attracted to me", "draws people in",
        "women are drawn to", "spark", "tension",
        # confidence / presence
        "confident", "confidence", "self-assured", "eye contact",
        "body language", "vocal tonality", "voice tone", "deep voice",
        "walk with purpose", "take up space", "assertive", "assertiveness",
        # the "problem" signals
        "invisible", "forgettable", "boring", "bland", "awkward",
        "in my head", "overthink", "self-conscious", "freeze up",
        "choke", "nervous around", "too nice", "nice guy",
        "doormat", "pushover", "people please", "no backbone",
        "friend zone", "friendzone", "put her on a pedestal",
        # improvement vocabulary
        "working on myself", "improving myself", "becoming better",
        "developing charisma", "learning to flirt", "getting better socially",
        "building confidence", "reinventing myself",
    ]
    return any(s in t for s in signals)


def has_personal_experience(text: str) -> bool:
    """Prefer posts sharing a personal struggle, not just asking generic questions."""
    t = text.lower()
    signals = [
        "i am", "i'm", "i was", "i feel", "i felt", "i've been",
        "i used to", "i realized", "i noticed", "i struggle",
        "my problem", "my issue", "my situation", "in my case",
        "i freeze", "i choke", "i blank", "i panic",
        "women don't", "she doesn't", "she lost interest",
        "i put her", "i bend", "i can't", "i don't know how",
        "i've always", "i've never", "all my life",
        "growing up", "since my breakup", "after my divorce",
    ]
    return any(s in t for s in signals)


# ── Segment tagging ───────────────────────────────────────────────────────────

def segment_tag(title: str, body: str) -> str:
    text = (title + " " + body).lower()

    if any(k in text for k in [
        "invisible", "forgettable", "no presence", "people forget",
        "nobody notices", "blend into", "not memorable", "people don't remember",
        "no one gravitates", "people don't take me seriously",
    ]):
        return "Socially Invisible / Forgettable"

    if any(k in text for k in [
        "approach anxiety", "freeze up", "freeze when", "choke", "can't approach",
        "too scared", "too nervous", "panic when", "paralyzed", "i freeze",
        "scared to approach", "can't initiate",
    ]):
        return "Approach Anxiety / Freezes Up"

    if any(k in text for k in [
        "no chemistry", "no spark", "friend zone", "friendzone",
        "good on paper", "women lose interest", "she loses interest",
        "she pulled away", "she stopped texting", "dates go well but",
        "nice but nothing", "tick all the boxes", "women like me as a friend",
        "can't keep women interested", "boring on dates",
    ]):
        return "No Chemistry on Dates / Good on Paper"

    if any(k in text for k in [
        "too nice", "nice guy", "doormat", "pushover", "people please",
        "no backbone", "too agreeable", "bend over backwards",
        "put her on a pedestal", "can't say no", "afraid of conflict",
        "she doesn't respect", "women don't respect",
    ]):
        return "Nice Guy / No Backbone"

    if any(k in text for k in [
        "in my head", "overthink", "overthinking", "self-conscious",
        "monitor myself", "can't be natural", "can't be spontaneous",
        "too aware of myself", "rehearse", "social anxiety",
        "i think too much", "can't be present", "too calculated",
    ]):
        return "Awkward / Overthinking / In My Head"

    if any(k in text for k in [
        "after my breakup", "after she left", "after my divorce",
        "lost my confidence", "used to be confident", "heartbreak",
        "rebuilding", "reinventing", "becoming a better man",
        "i gave up my personality", "became boring in the relationship",
        "improving myself after", "i stopped growing",
    ]):
        return "Post-Hurt Reinvention / Rebuilding"

    if any(k in text for k in [
        "working on", "inner game", "developing charisma", "building presence",
        "how to be more charming", "learning to flirt", "getting better",
        "charisma on command", "art of charm", "magnetic", "becoming magnetic",
        "improving social skills", "social calibration",
    ]):
        return "Building Presence / Inner Game"

    return "General / Social Confidence Struggle"


# ── Reddit fetching ───────────────────────────────────────────────────────────

def search_reddit(subreddit: str, query: str, time_filter: str) -> Optional[dict]:
    url = f"https://www.reddit.com/r/{subreddit}/search.json"
    params = {"q": query, "sort": "top", "t": time_filter,
              "limit": 100, "restrict_sr": 1}
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
            return r.json()
        except Exception as e:
            print(f"  Request failed: {e}", flush=True)
            time.sleep(5)
    return None


def checkpoint_save(existing_records: list, new_results: list):
    """Save current progress to disk so nothing is lost on interruption."""
    all_records = existing_records + new_results
    if not all_records:
        return
    df = pd.DataFrame(all_records)
    df.drop_duplicates(subset="id", inplace=True)
    df.sort_values("score", ascending=False, inplace=True)
    df.reset_index(drop=True, inplace=True)
    df.to_csv(OUTPUT_FILE, index=False, encoding="utf-8-sig")


def fetch_all(existing_ids: set = None, existing_records: list = None) -> list[dict]:
    seen = set(existing_ids or [])
    results = []
    total = len(SUBREDDITS) * len(QUERIES) * len(TIME_FILTERS)
    count = 0

    for subreddit in SUBREDDITS:
        for query in QUERIES:
            for time_filter in TIME_FILTERS:
                count += 1
                if count % 100 == 0:
                    print(f"[{count}/{total}] found so far: {len(results)}", flush=True)
                    checkpoint_save(existing_records or [], results)

                data = search_reddit(subreddit, query, time_filter)
                if not data or "data" not in data:
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
                    combined = title + " " + body

                    if is_female_poster(title, body):
                        continue
                    if not has_charisma_signal(combined):
                        continue
                    # either a personal post or a strong charm-topic question
                    if not has_personal_experience(combined) and len(body) < 200:
                        continue

                    seen.add(p["id"])
                    results.append({
                        "id":            p["id"],
                        "title":         title,
                        "subreddit":     p["subreddit"],
                        "score":         p["score"],
                        "num_comments":  p["num_comments"],
                        "upvote_ratio":  round(p.get("upvote_ratio", 0), 2),
                        "url":           f"https://reddit.com{p['permalink']}",
                        "created_date":  datetime.utcfromtimestamp(
                            p["created_utc"]
                        ).strftime("%Y-%m-%d"),
                        "author":        p.get("author", ""),
                        "post_body":     body[:2000],
                        "segment_tag":   segment_tag(title, body),
                        "matched_query": query,
                        "flair":         p.get("link_flair_text", "") or "",
                    })

    return results


def main():
    print("Scraping: men on charm, charisma, social confidence & presence")
    print(f"Target: ≥{MIN_UPVOTES} upvotes, ≥{MIN_COMMENTS} comments\n")

    # Append-safe: load existing posts so re-runs only add new ones
    existing_records = []
    existing_ids: set = set()
    try:
        existing_df = pd.read_csv(OUTPUT_FILE)
        existing_ids = set(existing_df["id"].astype(str))
        existing_records = existing_df.to_dict("records")
        print(f"Loaded {len(existing_records)} existing posts — will append new ones only.\n",
              flush=True)
    except FileNotFoundError:
        pass

    new_results = fetch_all(existing_ids, existing_records)
    all_records = existing_records + new_results

    if not all_records:
        print("No posts found.")
        return

    df = pd.DataFrame(all_records)
    df.drop_duplicates(subset="id", inplace=True)
    df.sort_values("score", ascending=False, inplace=True)
    df.reset_index(drop=True, inplace=True)
    df.to_csv(OUTPUT_FILE, index=False, encoding="utf-8-sig")

    print(f"\n{'='*60}")
    print(f"✓ Saved {len(df)} posts total ({len(new_results)} new) to '{OUTPUT_FILE}'")
    print(f"\nSegment distribution:\n{df['segment_tag'].value_counts().to_string()}")
    print(f"\nSubreddit distribution:\n{df['subreddit'].value_counts().head(15).to_string()}")
    print(f"\nTop 15 by score:")
    print(df[["title", "subreddit", "score", "num_comments", "segment_tag"]]
          .head(15)
          .to_string(index=False))


if __name__ == "__main__":
    main()
