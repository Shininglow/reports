"""
Scrape comments for each of the 4 cluster CSVs.
Applies male-detection filter to comments (same regex as post scraper).
Falls back to MIN_SCORE=1 for posts where fewer than MIN_PER_POST male
comments are found at the primary threshold, to guarantee coverage.
"""
import requests
import pandas as pd
import time
import re

# ── CONFIG ──────────────────────────────────────────────────────────────────
MIN_COMMENT_SCORE  = 3    # primary upvote threshold for comments
MIN_PER_POST       = 5    # minimum male comments to keep per post (fallback)
MAX_COMMENTS_FETCH = 100  # how many top comments to pull per post
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; research-scraper/1.0)"}

TARGETS = [
    ("forever_alone_posts.csv",      "forever_alone_comments.csv",      "ForeverAlone"),
    ("dating_advice_posts.csv",      "dating_advice_comments.csv",      "dating_advice"),
    ("datingoverthirty_posts.csv",   "datingoverthirty_comments.csv",   "datingoverthirty"),
    ("datingoverforty_posts.csv",    "datingoverforty_comments.csv",    "datingoverforty"),
]

# ── GENDER PATTERNS ──────────────────────────────────────────────────────────
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
    r"\bhe/him\b",
    r"\bmy\s+ex[\s-]?(?:wife|girlfriend|gf)\b",
    r"\bdating\s+(?:women|ladies|girls|a\s+woman)\b",
    r"\bgirlfriend\b.{0,60}\bI\b",
    r"\bI\b.{0,40}\bgirlfriend\b",
    r"\b(?:4[0-9]|3[0-9])[Mm]\b",
    r"\bdivorced\s+(?:man|male|guy|dad|father)\b",
    r"\bwidower\b",
    r"\bsingle\s+dad\b",
    r"\bsingle\s+father\b",
    r"\bI\s+was\s+in\s+(?:your|the\s+same|a\s+similar)\s+(?:situation|boat|spot|place)\b",
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
    r"\bsingle\s+mom\b",
    r"\bsingle\s+mother\b",
]

def is_male_comment(text: str) -> bool:
    if any(re.search(p, text, re.IGNORECASE) for p in FEMALE_PATTERNS):
        return False
    if any(re.search(p, text, re.IGNORECASE) for p in MALE_PATTERNS):
        return True
    return False  # unknown gender — exclude to keep dataset clean

# ── JTBD THEMES ──────────────────────────────────────────────────────────────
JTBD_THEMES = [
    ("Breaking the inexperience loop",          [r"no experience", r"inexperienced", r"never dated", r"never had.{0,10}girlfriend", r"inexperience"]),
    ("Understanding what is blocking them",     [r"doing everything right", r"done everything", r"what.{0,20}wrong with me", r"why.{0,20}doesn.t work", r"what am I doing wrong"]),
    ("Getting over approach anxiety",           [r"approach", r"freeze", r"can.t talk to", r"too scared", r"nerve", r"anxiety.{0,20}talk", r"asking.{0,20}out"]),
    ("Learning the mechanics of dating",        [r"what to say", r"how to flirt", r"escalat", r"first date", r"texting", r"what to do on a date", r"no idea how"]),
    ("Decoding why less-deserving men succeed", [r"bad guys", r"jerks.{0,20}girl", r"treat.{0,20}badly", r"why do women", r"nice guys finish last"]),
    ("Escaping the friend zone",                [r"friend.?zone", r"friendzoned", r"just friends", r"platonic", r"she sees me as"]),
    ("Coping with physical loneliness",         [r"touch", r"hug", r"physical.{0,20}lonely", r"ache", r"warmth", r"held", r"physical contact"]),
    ("Processing the shame of being late",      [r"embarrass", r"ashamed", r"too old", r"late.{0,20}start", r"weird.{0,20}age", r"\d0s?.{0,10}never", r"no one my age"]),
    ("Finding where to meet women",             [r"where to meet", r"how to meet", r"dating app", r"tinder", r"bumble", r"hinge", r"in real life", r"offline"]),
    ("Building self-worth",                     [r"self.?worth", r"self.?esteem", r"value", r"confidence", r"believe in yourself", r"love yourself", r"identity"]),
    ("Managing neurodivergence in dating",      [r"autis", r"adhd", r"neurodiverg", r"spectrum", r"asperger", r"social cues"]),
    ("Destigmatizing the experience",           [r"incel", r"stigma", r"forever alone", r"judged", r"label", r"not an incel"]),
    ("Dealing with comparison pain",            [r"social media", r"instagram", r"couples", r"valentine", r"everyone else", r"friends are married"]),
    ("Understanding rejection",                 [r"rejected", r"rejection", r"ghost", r"ghosted", r"no response", r"what went wrong"]),
    ("Fear of intimacy after abstinence",       [r"cling", r"too much", r"overwhelm", r"first time", r"intimate", r"clingy", r"deprivation"]),
    ("Starting over after loss",                [r"divorce", r"divorced", r"breakup", r"broke up", r"ex.?wife", r"starting over", r"rebuild"]),
    ("Heartbreak and age",                      [r"too late", r"too old", r"never find", r"never again", r"at my age", r"heartbreak"]),
    ("Dating app fatigue",                      [r"swipe", r"app.{0,20}exhaust", r"app.{0,20}drain", r"delete.{0,15}app", r"app is broken", r"app.{0,20}useless", r"app fatigue"]),
]

def classify_comment(text: str) -> str:
    text_lower = text.lower()
    for theme, patterns in JTBD_THEMES:
        if any(re.search(p, text_lower, re.IGNORECASE) for p in patterns):
            return theme
    return "General / Other"


# ── COMMENT FETCHER ───────────────────────────────────────────────────────────
def fetch_raw_comments(url: str, post_id: str, min_score: int) -> list:
    json_url = url.rstrip("/") + ".json"
    try:
        r = requests.get(
            json_url, headers=HEADERS,
            params={"limit": MAX_COMMENTS_FETCH, "sort": "top"},
            timeout=20
        )
        if r.status_code == 429:
            print("    Rate limited — waiting 20s...")
            time.sleep(20)
            r = requests.get(
                json_url, headers=HEADERS,
                params={"limit": MAX_COMMENTS_FETCH, "sort": "top"},
                timeout=20
            )
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        print(f"    Failed: {e}")
        return []

    if not isinstance(data, list) or len(data) < 2:
        return []

    raw = []

    def extract(node):
        if not isinstance(node, dict):
            return
        kind = node.get("kind")
        d    = node.get("data", {})
        if kind == "t1":
            body  = (d.get("body") or "").strip()
            score = d.get("score", 0)
            author = d.get("author", "")
            if (body and body not in ("[deleted]", "[removed]")
                    and score >= min_score):
                raw.append({
                    "comment_id":     d.get("id", ""),
                    "comment_author": author,
                    "comment_body":   body[:800],
                    "comment_score":  score,
                    "comment_url": (
                        f"https://reddit.com/r/{d.get('subreddit','')}"
                        f"/comments/{post_id}/_/{d.get('id','')}/"
                    ),
                })
            replies = d.get("replies")
            if isinstance(replies, dict):
                for child in replies.get("data", {}).get("children", []):
                    extract(child)
        elif kind == "Listing":
            for child in d.get("children", []):
                extract(child)

    for child in data[1]["data"].get("children", []):
        extract(child)

    return raw


def get_male_comments(url: str, post_id: str, post_author: str) -> list:
    """
    Fetch male comments.  OP replies are always counted as male
    (post was already gender-filtered).  Non-OP comments require
    an explicit male signal.  Falls back to score>=1 if fewer than
    MIN_PER_POST male comments found at primary threshold.
    """
    for min_score in [MIN_COMMENT_SCORE, 1]:
        raw = fetch_raw_comments(url, post_id, min_score)
        result = []
        for c in raw:
            is_op = (c["comment_author"].lower() == str(post_author).lower())
            if is_op or is_male_comment(c["comment_body"]):
                result.append(c)
        if len(result) >= MIN_PER_POST:
            return result
        if min_score == 1:
            return result  # best we can do
    return []


# ── MAIN ─────────────────────────────────────────────────────────────────────
def main():
    for posts_file, comments_file, label in TARGETS:
        print(f"\n{'='*62}")
        print(f"Cluster: r/{label}  →  {comments_file}")
        print(f"{'='*62}")

        posts_df = pd.read_csv(posts_file)
        posts_df = posts_df.sort_values("score", ascending=False).reset_index(drop=True)
        total = len(posts_df)
        print(f"  {total} posts to process")

        all_rows = []

        for i, (_, post) in enumerate(posts_df.iterrows(), 1):
            title   = str(post.get("title", ""))[:60]
            post_id = str(post["id"])
            url     = str(post["url"])
            author  = str(post.get("author", ""))

            print(f"  [{i:>3}/{total}] {title}")

            comments = get_male_comments(url, post_id, author)
            print(f"         → {len(comments)} male comments kept")

            for c in comments:
                all_rows.append({
                    "post_id":        post_id,
                    "post_title":     post.get("title", ""),
                    "post_subreddit": post.get("subreddit", label),
                    "post_score":     post.get("score", 0),
                    "post_url":       url,
                    "comment_id":     c["comment_id"],
                    "comment_author": c["comment_author"],
                    "comment_score":  c["comment_score"],
                    "comment_body":   c["comment_body"],
                    "comment_url":    c["comment_url"],
                    "jtbd_theme":     classify_comment(c["comment_body"]),
                })

            time.sleep(2.0)

        if not all_rows:
            print(f"  No comments collected for {label}.")
            continue

        df_out = pd.DataFrame(all_rows)
        df_out.sort_values(
            ["post_score", "comment_score"],
            ascending=[False, False],
            inplace=True
        )
        df_out.reset_index(drop=True, inplace=True)
        df_out.to_csv(comments_file, index=False, encoding="utf-8-sig")

        posts_with_comments = df_out["post_id"].nunique()
        print(f"\n  Saved {len(df_out)} comments from {posts_with_comments} posts  →  '{comments_file}'")
        print(f"  Comments per JTBD theme:")
        for theme, count in df_out["jtbd_theme"].value_counts().items():
            print(f"    {count:>5}  {theme}")


if __name__ == "__main__":
    main()
