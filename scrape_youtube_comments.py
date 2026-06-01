"""
Scrape YouTube video comments for the "successful but romantically lonely men" audience.
Uses YouTube Data API v3 — free tier gives ~500-1000 comments per video.

Setup (one-time):
  1. Go to https://console.cloud.google.com/
  2. Create a project → Enable "YouTube Data API v3"
  3. Credentials → Create API Key → paste it into API_KEY below

Usage:
  - Add video URLs or IDs to VIDEO_URLS list below, then run:
    python scrape_youtube_comments.py
  - Output: youtube_comments.csv in the same folder
"""

import os
import re
import time
import csv
import requests
import pandas as pd
from datetime import datetime
from typing import Optional

# ── CONFIG ──────────────────────────────────────────────────────────────────
API_KEY = "AIzaSyBvAmkfv6i8n9cRE6ZuKhuHo_K09IC49jI"

VIDEO_URLS = []  # leave empty — loaded from CSV below

CSV_SOURCE  = "/Users/viktoriia.shyrokova/Downloads/Relationship skills - Sheet7.csv"
OUTPUT_FILE = os.path.join(os.path.dirname(__file__), "youtube_comments.csv")

MAX_COMMENTS_PER_VIDEO = 500        # set to None to get all comments
MIN_LIKES              = 0          # minimum comment likes (0 = include all)
MIN_TEXT_LENGTH        = 50         # YouTube comments are shorter than Reddit posts
SCORE_THRESHOLD        = 3         # slightly lower than Reddit — comments are shorter
# ─────────────────────────────────────────────────────────────────────────────


def extract_video_id(url_or_id: str) -> str:
    """Accept a full YouTube URL or bare video ID."""
    url = url_or_id.strip()
    # already a bare ID (11 chars, no slashes)
    if re.match(r'^[A-Za-z0-9_-]{11}$', url):
        return url
    # youtu.be/ID or youtube.com/watch?v=ID or /embed/ID or /shorts/ID
    m = re.search(r'(?:v=|youtu\.be/|/embed/|/shorts/)([A-Za-z0-9_-]{11})', url)
    if m:
        return m.group(1)
    raise ValueError(f"Cannot extract video ID from: {url}")


def get_video_title(video_id: str) -> str:
    url = "https://www.googleapis.com/youtube/v3/videos"
    params = {"part": "snippet", "id": video_id, "key": API_KEY}
    r = requests.get(url, params=params, timeout=15)
    r.raise_for_status()
    items = r.json().get("items", [])
    if items:
        return items[0]["snippet"]["title"]
    return video_id


def fetch_comments(video_id: str, max_results: Optional[int]) -> list[dict]:
    """Fetch top-level comments + their replies for a video."""
    base_url = "https://www.googleapis.com/youtube/v3/commentThreads"
    params = {
        "part":       "snippet,replies",
        "videoId":    video_id,
        "key":        API_KEY,
        "maxResults": 100,          # max allowed per page
        "order":      "relevance",  # 'relevance' or 'time'
        "textFormat": "plainText",
    }

    comments = []
    page_token = None
    fetched = 0

    while True:
        if page_token:
            params["pageToken"] = page_token
        try:
            r = requests.get(base_url, params=params, timeout=20)
            if r.status_code == 403:
                data = r.json()
                reason = data.get("error", {}).get("errors", [{}])[0].get("reason", "")
                if reason == "commentsDisabled":
                    print(f"  Comments disabled for video {video_id} — skipping.")
                    return []
                print(f"  403 error: {data.get('error', {}).get('message', 'unknown')}")
                return comments
            r.raise_for_status()
        except requests.RequestException as e:
            print(f"  Request failed: {e}")
            break

        data = r.json()
        for item in data.get("items", []):
            top = item["snippet"]["topLevelComment"]["snippet"]
            comments.append({
                "comment_id":    item["snippet"]["topLevelComment"]["id"],
                "author":        top.get("authorDisplayName", ""),
                "text":          top.get("textDisplay", ""),
                "likes":         top.get("likeCount", 0),
                "published_at":  top.get("publishedAt", "")[:10],
                "reply_count":   item["snippet"].get("totalReplyCount", 0),
                "is_reply":      False,
            })
            fetched += 1

            # include replies if present
            replies = item.get("replies", {}).get("comments", [])
            for rep in replies:
                rs = rep["snippet"]
                comments.append({
                    "comment_id":   rep["id"],
                    "author":       rs.get("authorDisplayName", ""),
                    "text":         rs.get("textDisplay", ""),
                    "likes":        rs.get("likeCount", 0),
                    "published_at": rs.get("publishedAt", "")[:10],
                    "reply_count":  0,
                    "is_reply":     True,
                })

            if max_results and fetched >= max_results:
                return comments

        page_token = data.get("nextPageToken")
        if not page_token:
            break
        time.sleep(0.3)

    return comments


# ── FILTERS (same audience as Reddit pipeline) ───────────────────────────────

def is_female_commenter(text: str) -> bool:
    t = text.lower()
    female_signals = [
        "i'm a woman", "i am a woman", "as a woman", "as a girl",
        "i'm female", "i am female", "woman here", "female here",
        "my husband", "my boyfriend read", "bought this for my husband",
        "as a wife", "as a girlfriend", "i'm a feminist", "i am a feminist",
        "speaking as a woman", "as females", "us women",
        "my ovaries", "my panties",
    ]
    return any(s in t for s in female_signals)


def has_stability_signal(text: str) -> bool:
    t = text.lower()
    signals = [
        "good career", "good job", "stable job", "full-time", "my job",
        "my career", "my work", "employed", "i work as", "i work at",
        "financially", "net worth", "own a house", "my apartment",
        "my own place", "good income", "salary",
        "i have friends", "good friends", "social life", "social circle",
        "people like me",
        "gym", "work out", "workout", "in shape", "physically fit",
        "i exercise", "i run", "i lift", "good shape",
        "degree", "graduated", "college", "university", "masters", "phd",
        "happy with my life", "love my life", "i'm happy", "i am happy",
        "content with", "i enjoy my life", "life is good",
        "doing well", "life is great", "not depressed",
        "life together", "everything going for me",
        "on paper", "checks all the boxes", "tick all the boxes",
        "i'm confident", "good self-esteem", "i like myself", "i love myself",
        "successful", "comfortable financially", "self-sufficient",
    ]
    return any(s in t for s in signals)


def has_romantic_struggle(text: str) -> bool:
    t = text.lower()
    signals = [
        "never had a girlfriend", "never been in a relationship",
        "invisible to women", "can't attract", "women are not interested",
        "women aren't interested", "no luck with women", "no luck dating",
        "never been on a date", "never kissed", "can't find a girlfriend",
        "can't get a girlfriend", "never had a relationship",
        "just see me as a friend", "friendzoned", "friend zone",
        "still single", "been single for", "always single",
        "just want a girlfriend", "can't find love", "no matches",
        "give up on dating", "giving up on dating",
        "no girlfriend", "single for years",
        "women don't want me", "women don't like me",
        "women only see me as", "romantically invisible",
        "never been in love", "struggle with dating", "struggled with dating",
        "rejected by women", "women reject me", "women never approach",
        "nice guy", "doormat", "people pleaser", "approval seeking",
        "too nice", "nice guys finish last",
        "emotionally closed", "can't be vulnerable", "walls up",
        "late bloomer", "never dated",
    ]
    return any(s in t for s in signals)


def score_comment(text: str) -> tuple[int, str]:
    t = text.lower()
    score = 0

    # male perspective
    male_strong = [
        "i'm a man", "i am a man", "as a man", "i'm a guy", "as a guy",
        "being a man", "male here", "i'm male",
        "my wife", "my ex-wife", "i dated", "i was dating",
        "i asked her out", "i liked her", "she rejected",
    ]
    male_weak = [
        "girlfriend", "dated a woman", "met a girl", "asked her",
        "she said", "she wasn't", "women i",
    ]
    score += sum(2 for s in male_strong if s in t)
    score += sum(1 for s in male_weak if s in t)

    # personal story
    personal = [
        "i used to", "i was", "i realized", "i struggled",
        "this changed my", "changed my life", "i can relate",
        "resonated with me", "this hit me", "i've been", "i had been",
        "my experience", "my story", "i now understand", "i finally",
        "i grew up", "when i was younger", "in my twenties", "in my thirties",
        "after my divorce", "after my breakup", "after she left",
        "this video helped me", "this video changed",
    ]
    score += sum(2 for s in personal if s in t)

    # life success signals
    success = [
        "good job", "career", "successful", "financially", "my job",
        "my career", "gym", "work out", "educated", "degree",
        "good life", "doing well", "stable", "confident in other areas",
        "good at my job", "accomplished", "comfortable", "self-sufficient",
    ]
    score += sum(1 for s in success if s in t)

    # dating / romantic struggle
    dating_struggle = [
        "struggled with women", "never had a girlfriend", "no luck with women",
        "couldn't attract", "women weren't interested", "always friendzoned",
        "nice guy", "too nice", "never dated", "rejected",
        "struggling with dating", "couldn't connect with women",
        "nice guy syndrome", "doormat", "pleaser", "approval seeking",
        "couldn't express myself", "suppressed emotions",
        "invisible to women", "women didn't notice me",
        "couldn't be vulnerable", "emotionally closed",
        "no romantic experience", "she left me", "she lost interest",
        "too available", "too needy", "clingy", "desperate",
        "chased women", "put women on a pedestal",
        "covert contracts", "passive aggressive",
    ]
    score += sum(2 for s in dating_struggle if s in t)

    # insight / transformation
    insight = [
        "eye-opening", "life-changing", "wake-up call", "aha moment",
        "i finally understand", "now i see", "transformed",
        "changed how i", "shifted my perspective", "made me realize",
        "opened my eyes", "helped me understand", "never thought about",
        "completely changed", "breakthrough", "profound",
        "deeply resonated", "spoke to me directly",
        "felt like it was written for me", "describes me perfectly",
        "this is my story", "this is exactly me", "i recognized myself",
        "i saw myself in", "hit close to home",
    ]
    score += sum(2 for s in insight if s in t)

    # length bonus
    if len(text) > 200:  score += 1
    if len(text) > 500:  score += 1
    if len(text) > 1000: score += 2

    # segment tag
    segment = "General / Dating Struggle"
    if any(s in t for s in ["nice guy", "people pleaser", "doormat", "approval seeking",
                             "covert contracts", "too nice", "give to get", "resentful"]):
        segment = "Nice Guy / Approval-Seeking Pattern"
    elif any(s in t for s in ["emotionally closed", "walls up", "closed off",
                               "can't open up", "can't be vulnerable"]):
        segment = "Emotionally Closed Off"
    elif any(s in t for s in ["career", "focused on work", "late bloomer", "prioritized career"]):
        segment = "Career-First Late Bloomer"
    elif any(s in t for s in ["friendzone", "friendzoned", "just see me as", "invisible to women"]):
        segment = "Unseen Good Guy"
    elif any(s in t for s in ["masculine", "masculinity", "polarity", "purpose", "presence"]):
        segment = "Masculine Identity / Polarity"

    return score, segment


# ── MAIN ─────────────────────────────────────────────────────────────────────

def load_videos_from_csv(path: str) -> list[tuple[str, str]]:
    """Return list of (channel_name, url) from the Sheet7 CSV."""
    pairs = []
    with open(path, newline="", encoding="utf-8-sig") as f:
        for row in csv.reader(f):
            if len(row) < 2:
                continue
            channel = row[0].strip()
            url     = row[1].strip()
            if channel and url and url.startswith("http"):
                pairs.append((channel, url))
    return pairs


def process_video(channel_name: str, video_url: str) -> list[dict]:
    video_id = extract_video_id(video_url)
    print(f"\n{'='*60}")
    print(f"Channel  : {channel_name}")
    print(f"Video ID : {video_id}")

    title = get_video_title(video_id)
    print(f"Title    : {title}")

    raw = fetch_comments(video_id, MAX_COMMENTS_PER_VIDEO)
    print(f"Fetched  : {len(raw)} comments")

    results = []
    for c in raw:
        text = c["text"].strip()
        if len(text) < MIN_TEXT_LENGTH:
            continue
        if c["likes"] < MIN_LIKES:
            continue
        if is_female_commenter(text):
            continue
        if not (has_stability_signal(text) or has_romantic_struggle(text)):
            continue

        score, segment = score_comment(text)
        if score < SCORE_THRESHOLD:
            continue

        results.append({
            "channel_name":  channel_name,
            "video_id":      video_id,
            "video_title":   title,
            "video_url":     f"https://youtu.be/{video_id}",
            "comment_id":    c["comment_id"],
            "author":        c["author"],
            "likes":         c["likes"],
            "reply_count":   c["reply_count"],
            "is_reply":      c["is_reply"],
            "published_at":  c["published_at"],
            "relevance_score": score,
            "segment_tag":   segment,
            "comment_text":  text,
        })

    results.sort(key=lambda x: (x["relevance_score"], x["likes"]), reverse=True)
    print(f"Relevant : {len(results)} comments (score ≥ {SCORE_THRESHOLD})")
    return results


def main():
    if API_KEY == "YOUR_API_KEY_HERE":
        print("ERROR: Please set your API key in the API_KEY variable at the top of this file.")
        print("Get one at: https://console.cloud.google.com/ → YouTube Data API v3 → Credentials")
        return

    videos = load_videos_from_csv(CSV_SOURCE)
    if not videos:
        print(f"ERROR: No videos found in {CSV_SOURCE}")
        return

    print(f"Loaded {len(videos)} videos from CSV")

    all_results = []
    for channel, url in videos:
        try:
            results = process_video(channel, url)
            all_results.extend(results)
        except Exception as e:
            print(f"  Failed for {url}: {e}")
        time.sleep(1)

    if not all_results:
        print("\nNo relevant comments found. Try lowering the score threshold or MIN_TEXT_LENGTH.")
        return

    df = pd.DataFrame(all_results)
    df.drop_duplicates(subset="comment_id", inplace=True)
    df.sort_values(["relevance_score", "likes"], ascending=False, inplace=True)
    df.reset_index(drop=True, inplace=True)
    df.to_csv(OUTPUT_FILE, index=False, encoding="utf-8-sig")

    print(f"\n{'='*60}")
    print(f"DONE — {len(df)} relevant comments saved to:")
    print(f"  {OUTPUT_FILE}")
    print(f"\nSegment distribution:")
    print(df["segment_tag"].value_counts().to_string())
    print(f"\nTop 10 by relevance:")
    for _, r in df.head(10).iterrows():
        print(f"  [{r.relevance_score}pts | {r.likes}❤] {r.comment_text[:100]}")


if __name__ == "__main__":
    main()
