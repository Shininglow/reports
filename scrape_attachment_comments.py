"""
Scrape comments from the 3 attachment-style cluster CSVs.
No gender filter — attachment styles apply to everyone.
Classifies comments into attachment-theory relevant themes.
"""
import requests
import pandas as pd
import time
import re

MIN_COMMENT_SCORE  = 3
MIN_PER_POST       = 5
MAX_COMMENTS_FETCH = 100
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; research-scraper/1.0)"}

TARGETS = [
    ("anxious_posts.csv",      "anxious_comments.csv",      "anxious"),
    ("avoidant_posts.csv",     "avoidant_comments.csv",     "avoidant"),
    ("disorganized_posts.csv", "disorganized_comments.csv", "disorganized"),
]

# ── ATTACHMENT THEMES ─────────────────────────────────────────────────────────
THEMES = [
    ("Fear of abandonment",           [r"fear.{0,15}abandon", r"abandon.{0,20}fear", r"left behind", r"being left", r"terrified.{0,20}left", r"he.ll leave", r"she.ll leave", r"they.ll leave"]),
    ("Protest behavior",              [r"protest\s+behav", r"texting\s+(?:obsessively|constantly)", r"blow up.{0,20}phone", r"send.{0,20}message.{0,20}after", r"reach out.{0,20}anxiety", r"double text"]),
    ("Reassurance seeking",           [r"reassurance", r"need.{0,15}validation", r"seek.{0,15}validation", r"constant.{0,20}confirmation", r"need.{0,20}know.{0,20}(?:they|he|she) care"]),
    ("Avoidant deactivation",         [r"deactivat", r"shut.{0,10}down", r"pull.{0,10}away", r"withdraw", r"need.{0,10}space", r"walls?.{0,10}up", r"numb.{0,15}feel", r"emotionally\s+unavailable"]),
    ("Push-pull / hot and cold",      [r"push.{0,10}pull", r"hot.{0,10}and.{0,10}cold", r"runs?.{0,10}away.{0,30}comes?.{0,10}back", r"back.{0,10}and.{0,10}forth", r"breadcrumb", r"blowing\s+hot"]),
    ("Anxious-avoidant trap",         [r"anxious.{0,20}avoidant", r"avoidant.{0,20}anxious", r"AP.{0,20}DA", r"DA.{0,20}AP", r"the\s+trap", r"anxious.avoidant\s+(?:dynamic|cycle|pattern|relationship)"]),
    ("Fear of intimacy / closeness",  [r"fear.{0,15}intimacy", r"fear.{0,15}(?:getting\s+)?close", r"scare.{0,20}(?:of\s+)?close", r"vulnerable.{0,20}scare", r"open\s+up.{0,20}(?:scare|afraid|terrif)", r"walls?.{0,20}up"]),
    ("Childhood & trauma roots",      [r"childh", r"parent", r"mother", r"father", r"upbringing", r"trauma", r"neglect", r"abuse", r"early.{0,20}experience", r"how.{0,20}raised"]),
    ("Healing & therapy",             [r"therap", r"therapist", r"heal", r"inner\s+child", r"shadow\s+work", r"work.{0,10}on\s+(?:myself|yourself)", r"self.?aware", r"growth", r"progress", r"recover"]),
    ("Going secure / earned security",  [r"secur", r"earned\s+secur", r"going\s+secur", r"becoming\s+secur", r"more\s+secur", r"feel\s+secur", r"secure\s+attach"]),
    ("Breakup & no contact",          [r"no\s+contact", r"\bNC\b", r"break\s*up", r"broke\s+up", r"ex.{0,5}(?:who|is|was|has)", r"after\s+the\s+breakup", r"ended\s+(?:it|the\s+relationship)"]),
    ("Triggers & nervous system",     [r"trigger", r"nervous\s+system", r"dysregulat", r"hypervigilant", r"fight.or.flight", r"freeze\s+response", r"window\s+of\s+tolerance", r"co.?regulat"]),
    ("Self-awareness & patterns",     [r"pattern", r"recogni[sz]e", r"realized?", r"awareness", r"my\s+(?:own\s+)?behavior", r"I\s+do\s+this", r"I\s+used\s+to", r"catching\s+myself"]),
    ("Communication breakdown",       [r"can.t\s+(?:talk|communicate|express)", r"don.t\s+know\s+how\s+to\s+(?:say|express|tell)", r"stonewalling", r"silent\s+treatment", r"difficult\s+to\s+(?:open|express)", r"shut\s+down\s+when"]),
    ("Longing & missing (DA/FA)",     [r"miss\s+(?:them|him|her).{0,30}(?:reach|contact|text)", r"I\s+miss.{0,20}but", r"nostalg", r"longing.{0,20}(?:but|even\s+though)", r"still\s+think\s+about"]),
    ("Anxious spiral & rumination",   [r"spiral", r"ruminat", r"overthink", r"can.t\s+stop\s+thinking", r"obsess", r"anxiety\s+(?:spiral|attack|kick)", r"in\s+my\s+head", r"what\s+does\s+(?:this|it)\s+mean"]),
    ("Needs & boundaries",            [r"\bbound(?:ary|aries)\b", r"my\s+needs", r"unmet\s+needs", r"express\s+(?:my\s+)?needs", r"needs?\s+(?:aren.t|not)\s+(?:being\s+)?met", r"setting\s+limits?"]),
    ("Dating someone with this style",[r"dating\s+(?:an?|someone\s+with)\s+(?:anxious|avoidant|fearful|FA|DA|AP)", r"my\s+(?:DA|FA|AP)\s+(?:partner|ex|bf|gf)", r"partner\s+(?:is|has|was)\s+(?:anxious|avoidant|fearful)"]),
]

def classify_comment(text: str) -> str:
    t = text.lower()
    for theme, patterns in THEMES:
        if any(re.search(p, t, re.IGNORECASE) for p in patterns):
            return theme
    return "General / Other"


def fetch_raw_comments(url: str, post_id: str, min_score: int) -> list:
    json_url = url.rstrip("/") + ".json"
    for attempt in range(2):
        try:
            r = requests.get(
                json_url, headers=HEADERS,
                params={"limit": MAX_COMMENTS_FETCH, "sort": "top"},
                timeout=20
            )
            if r.status_code == 429:
                wait = 30 if attempt == 0 else 60
                print(f"    Rate limited — waiting {wait}s...")
                time.sleep(wait)
                continue
            r.raise_for_status()
            data = r.json()
            break
        except Exception as e:
            print(f"    Failed: {e}")
            return []
    else:
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
            body   = (d.get("body") or "").strip()
            score  = d.get("score", 0)
            author = d.get("author", "")
            if (body
                    and body not in ("[deleted]", "[removed]")
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


def get_comments(url: str, post_id: str) -> list:
    """Fetch comments, fall back to score>=1 if fewer than MIN_PER_POST found."""
    for min_score in [MIN_COMMENT_SCORE, 1]:
        raw = fetch_raw_comments(url, post_id, min_score)
        if len(raw) >= MIN_PER_POST:
            return raw
        if min_score == 1:
            return raw
    return []


def main():
    for posts_file, comments_file, label in TARGETS:
        print(f"\n{'='*62}")
        print(f"Cluster: {label}  →  {comments_file}")
        print(f"{'='*62}")

        posts_df = pd.read_csv(posts_file)
        posts_df = posts_df.sort_values("score", ascending=False).reset_index(drop=True)
        total = len(posts_df)
        print(f"  {total} posts to process")

        all_rows = []

        for i, (_, post) in enumerate(posts_df.iterrows(), 1):
            post_id  = str(post["id"])
            url      = str(post["url"])
            title    = str(post.get("title", ""))[:60]
            perspective = str(post.get("post_perspective", ""))

            print(f"  [{i:>3}/{total}] {title}")

            comments = get_comments(url, post_id)
            print(f"         → {len(comments)} comments kept")

            for c in comments:
                all_rows.append({
                    "post_id":          post_id,
                    "post_title":       post.get("title", ""),
                    "post_subreddit":   post.get("subreddit", label),
                    "post_score":       post.get("score", 0),
                    "post_url":         url,
                    "post_perspective": perspective,
                    "attachment_type":  post.get("attachment_type", label),
                    "comment_id":       c["comment_id"],
                    "comment_author":   c["comment_author"],
                    "comment_score":    c["comment_score"],
                    "comment_body":     c["comment_body"],
                    "comment_url":      c["comment_url"],
                    "theme":            classify_comment(c["comment_body"]),
                })

            time.sleep(2.0)

        if not all_rows:
            print(f"  No comments collected.")
            continue

        df_out = pd.DataFrame(all_rows)
        df_out.sort_values(
            ["post_score", "comment_score"],
            ascending=[False, False],
            inplace=True
        )
        df_out.reset_index(drop=True, inplace=True)
        df_out.to_csv(comments_file, index=False, encoding="utf-8-sig")

        posts_with = df_out["post_id"].nunique()
        print(f"\n  Saved {len(df_out)} comments from {posts_with} posts  →  '{comments_file}'")
        print(f"  Comments per theme:")
        for theme, count in df_out["theme"].value_counts().items():
            print(f"    {count:>5}  {theme}")


if __name__ == "__main__":
    main()
