"""
Scrape Reddit for men who have had relationships, been burned/disappointed,
and are now alone, guarded, or given up on love entirely.
Target: men who tried, got hurt, and don't want to repeat the experience.
Output: disappointed_men.csv
"""

import requests
import pandas as pd
import time
import re
from datetime import datetime

MIN_UPVOTES  = 75
MIN_COMMENTS = 5
OUTPUT_FILE  = "disappointed_men.csv"
HEADERS      = {
    "User-Agent": "script:attachment-research:v1.0 (personal research project)",
    "Accept": "application/json",
}

QUERIES = [
    "relationship drained me emotionally",
    "gave everything relationship got nothing",
    "relationships aren't worth it anymore",
    "done with relationships never again",
    "better off alone after relationship",
    "ex destroyed me emotionally",
    "lost myself in relationship",
    "one sided relationship gave my all",
    "she left when i needed her most",
    "she cheated i gave her everything",
    "never felt chosen never felt wanted",
    "poured my heart out she didn't care",
    "don't trust women anymore after",
    "afraid to love again",
    "scared of relationships after being hurt",
    "numb after relationship ended",
    "gave up on love after divorce",
    "don't want another relationship after",
    "relationships cause more pain than joy",
    "love isn't worth the pain",
    "sworn off relationships",
    "never want to marry after divorce",
    "she used me financially",
    "she only wanted me when convenient",
    "she left me for someone worse",
    # additional queries for expanded subreddits
    "she was using me entire time",
    "emotionally unavailable after relationship",
    "dead inside after breakup",
    "walls up can't let anyone in",
    "going no contact healing myself",
    "stopped believing in love",
    "marriage destroyed me",
    "divorce changed me forever",
    "she manipulated me for years",
    "realized she never loved me",
    "gave up trying to find love",
    "intimacy gone she stopped caring",
    "she checked out of marriage",
    "never opening up again",
    "heartbreak changed who i am",
]

SUBREDDITS = [
    "BreakUps",
    "Divorce",
    "TrueOffMyChest",
    "offmychest",
    "lonely",
    "self",
    "AskMen",
    "AskMenOver30",
    "datingoverthirty",
    "ForeverAlone",
    "survivinginfidelity",
    # expanded — high-signal communities for burned/disappointed men
    "ExNoContact",          # men going no-contact after painful splits
    "DeadBedrooms",         # intimacy-starved, often married men hitting a wall
    "NarcissisticAbuse",    # men who were manipulated/used
    "relationship_advice",  # mainstream but huge volume of male stories
    "mentalhealth",         # emotional aftermath, men talking about numbness
    "nosurf",               # men withdrawing from life after heartbreak (adjacent)
    "Separated",            # separation before/without divorce
    "AsianMasculinity",     # male-specific angle on relationships
    "AskMenOver40",         # post-divorce rebuilder demographic
    "dating",               # general dating struggles
]

TIME_FILTERS = ["all", "year"]


def search_reddit(subreddit, query, time_filter):
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


def is_female_poster(title, body):
    text = (title + " " + body).lower()
    female_tags = re.compile(r'\b\d{1,2}f\b|\(f\)|\(f,|\bi \(f|\[f\]')
    if female_tags.search(text[:400]):
        return True
    female_words = [
        'my husband', 'my boyfriend', 'my fiance', 'as a woman',
        "i'm a woman", 'i am a woman', 'i am female', "i'm female",
        'as a girl', "i'm a girl", 'my ex-husband',
    ]
    return any(f in text for f in female_words)


def has_prior_relationship(text):
    """Must have actually been in a relationship — not just rejection."""
    t = text.lower()
    signals = [
        'my ex', 'ex-girlfriend', 'ex girlfriend', 'ex-wife', 'ex wife',
        'we broke up', 'she broke up', 'i broke up', 'after the breakup',
        'after the divorce', 'my divorce', 'we divorced', 'was married',
        'my marriage', 'my wife left', 'she left me', 'she cheated',
        'she was unfaithful', 'she betrayed', 'long term relationship',
        'long-term relationship', 'we were together for', 'years together',
        'we dated for', 'dated for years', 'in a relationship for',
        'we were in a relationship', 'was with her for', 'was with someone',
        'my last relationship', 'previous relationship', 'past relationship',
        'my last girlfriend', 'she used me', 'she took advantage',
        'she only wanted', 'gave her everything', 'gave my all',
        'in love with her', 'was in love', 'loved her', 'fell in love',
        'had a girlfriend', 'had a wife', 'had a partner',
        'spent years with', 'built a life with',
    ]
    return any(s in t for s in signals)


def has_disappointment_signal(text):
    """Must show the experience was negative and left them guarded/reluctant."""
    t = text.lower()
    signals = [
        # emotional damage
        'drained me', 'drained by', 'emotionally exhausted',
        'broke me', 'destroyed me', 'shattered me', 'crushed me',
        'lost myself', 'lost who i was', 'became a shell',
        'never been the same', 'changed me forever',
        'don\'t trust', 'can\'t trust', 'trust issues',
        'built walls', 'walls up', 'closed off', 'numb',
        'afraid to love', 'scared to love', 'scared of relationships',
        'can\'t open up', 'can\'t be vulnerable',
        # giving too much
        'gave everything', 'gave my all', 'gave 100', 'gave so much',
        'sacrificed', 'put her first', 'always her needs', 'forgot myself',
        'one-sided', 'one sided', 'wasn\'t reciprocated', 'not reciprocated',
        'she never', 'she didn\'t appreciate', 'she took for granted',
        # betrayal
        'cheated on me', 'she cheated', 'she lied', 'was a lie',
        'used me', 'manipulated me', 'she only wanted', 'taken advantage',
        'she left when', 'abandoned me', 'she was using',
        # giving up
        'done with relationships', 'never again', 'sworn off',
        'not worth it', 'relationships aren\'t worth',
        'better off alone', 'decided to stay single', 'giving up on love',
        'given up on love', 'gave up on love', 'given up on dating',
        'don\'t want a relationship', 'don\'t want another relationship',
        'not looking for a relationship', 'not interested in dating',
        'stopped trying', 'stopped caring',
        # aftermath
        'after the divorce', 'since the breakup', 'after we split',
        'my last relationship destroyed', 'still recovering',
        'haven\'t dated since', 'haven\'t been with anyone since',
        'been alone ever since', 'alone after',
    ]
    return any(s in t for s in signals)


def segment_tag(title, body):
    text = (title + " " + body).lower()
    if any(k in text for k in ['cheated', 'infidelity', 'unfaithful', 'betrayed', 'she lied']):
        return "Betrayed / Cheated On"
    if any(k in text for k in ['divorce', 'married', 'marriage', 'ex-wife', 'ex wife']):
        return "Post-Divorce Rebuilder"
    if any(k in text for k in ['gave everything', 'gave my all', 'one-sided', 'one sided',
                                'she didn\'t appreciate', 'took for granted', 'not reciprocated']):
        return "One-Sided Giver / Depleted"
    if any(k in text for k in ['drained', 'exhausted', 'lost myself', 'forgot myself',
                                'became a shell', 'never been the same']):
        return "Emotionally Drained / Lost Self"
    if any(k in text for k in ['done with', 'sworn off', 'never again', 'better off alone',
                                'not worth it', 'giving up on love', 'given up']):
        return "Resigned / Sworn Off Love"
    if any(k in text for k in ['can\'t trust', 'don\'t trust', 'trust issues',
                                'built walls', 'walls up', 'closed off', 'numb',
                                'afraid to love', 'scared to love']):
        return "Guarded / Can't Trust Again"
    if any(k in text for k in ['used me', 'used for money', 'she only wanted', 'taken advantage',
                                'she left when', 'abandoned']):
        return "Used / Taken Advantage Of"
    return "General / Disappointed in Love"


def fetch_all(existing_ids: set = None):
    seen = set(existing_ids or [])
    results = []
    total = len(SUBREDDITS) * len(QUERIES) * len(TIME_FILTERS)
    count = 0

    for subreddit in SUBREDDITS:
        for query in QUERIES:
            for time_filter in TIME_FILTERS:
                count += 1
                if count % 50 == 0:
                    print(f"[{count}/{total}] found so far: {len(results)}", flush=True)

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
                    if len(body) < 120 or body in ("[removed]", "[deleted]"):
                        continue

                    title = p["title"]
                    combined = (title + " " + body).lower()

                    if is_female_poster(title, body):
                        continue
                    if not has_prior_relationship(combined):
                        continue
                    if not has_disappointment_signal(combined):
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
                        "created_date":  datetime.utcfromtimestamp(p["created_utc"]).strftime("%Y-%m-%d"),
                        "author":        p.get("author", ""),
                        "post_body":     body[:2000],
                        "segment_tag":   segment_tag(title, body),
                        "matched_query": query,
                        "flair":         p.get("link_flair_text", "") or "",
                    })

    return results


def main():
    print(f"Scraping for: burned / disappointed men who tried and gave up")
    print(f"Target: ≥{MIN_UPVOTES} upvotes, ≥{MIN_COMMENTS} comments\n")

    # Load existing posts so we don't re-fetch or overwrite them
    existing_records = []
    existing_ids: set = set()
    try:
        existing_df = pd.read_csv(OUTPUT_FILE)
        existing_ids = set(existing_df["id"].astype(str))
        existing_records = existing_df.to_dict("records")
        print(f"Loaded {len(existing_records)} existing posts — will append new ones only.\n", flush=True)
    except FileNotFoundError:
        pass

    new_results = fetch_all(existing_ids)
    all_records = existing_records + new_results

    if not all_records:
        print("No posts found.")
        return

    df = pd.DataFrame(all_records)
    df.drop_duplicates(subset="id", inplace=True)
    df.sort_values("score", ascending=False, inplace=True)
    df.reset_index(drop=True, inplace=True)
    df.to_csv(OUTPUT_FILE, index=False, encoding="utf-8-sig")

    print(f"\n✓ Saved {len(df)} posts total ({len(new_results)} new) to '{OUTPUT_FILE}'")
    print(f"\nSegment distribution:\n{df['segment_tag'].value_counts().to_string()}")
    print(f"\nTop 15 by score:")
    print(df[['title', 'subreddit', 'score', 'num_comments', 'segment_tag']].head(15).to_string(index=False))


if __name__ == "__main__":
    main()
