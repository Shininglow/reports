"""
Fetches Amazon reviews for 3 attachment-theory books via RapidAPI.
Uses the "Real-Time Amazon Data" API (free tier: 100 requests/month).

Setup:
  1. Go to https://rapidapi.com/letscrape-6bRBa3QguO5/api/real-time-amazon-data
  2. Click "Subscribe to Test" → select Basic (Free) plan
  3. Copy your API key from the "Header Parameters" panel (X-RapidAPI-Key)
  4. Either:
     a) Set env var: export RAPIDAPI_KEY="your_key_here"
     b) Or paste it directly below where it says PASTE_YOUR_KEY_HERE

Run:
  python3 fetch_amazon_reviews_rapidapi.py
"""

import os
import time
import re
import requests
import pandas as pd

# ── CONFIG ─────────────────────────────────────────────────────────────────────
RAPIDAPI_KEY = os.environ.get("RAPIDAPI_KEY", "222ae887e2msha7f6e37a3a77591p171137jsndc5e999b2149")

BOOKS = [
    {"asin": "1585429139", "title": "Attached: The Science of Adult Attachment",      "author": "Amir Levine & Rachel Heller"},
    {"asin": "1641523557", "title": "Attachment Theory Workbook",                      "author": "Annie Chen"},
    {"asin": "B093HJF1T7", "title": "Attachment Theory: A Guide to Strengthening Relationships", "author": ""},
]

OUTPUT_FILE   = "amazon_book_reviews.csv"
MAX_PAGES     = 10      # 10 pages × 10 reviews = up to 100 per book (fits free tier)
DELAY_BETWEEN = 1.5     # seconds between requests

HOST    = "real-time-amazon-data.p.rapidapi.com"
REVIEWS_URL = f"https://{HOST}/product-reviews"

# ── HELPERS ────────────────────────────────────────────────────────────────────

def parse_stars(val) -> str:
    if not val:
        return ""
    m = re.search(r"([\d.]+)", str(val))
    return m.group(1) if m else str(val).strip()


def fetch_reviews_page(asin: str, page: int) -> dict:
    headers = {
        "x-rapidapi-key":  RAPIDAPI_KEY,
        "x-rapidapi-host": HOST,
    }
    params = {
        "asin":    asin,
        "country": "US",
        "page":    str(page),
        "sort_by": "TOP_REVIEWS",
        "verified_purchases_only": "false",
        "images_or_videos_only":   "false",
        "current_format_only":     "false",
    }
    try:
        r = requests.get(REVIEWS_URL, headers=headers, params=params, timeout=20)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.HTTPError as e:
        if r.status_code == 429:
            print(f"    Rate limited — waiting 60s...")
            time.sleep(60)
            return {}
        if r.status_code == 403:
            print(f"    403 Forbidden — check your API key and subscription.")
            return {}
        print(f"    HTTP error {r.status_code}: {e}")
        return {}
    except Exception as e:
        print(f"    Request error: {e}")
        return {}


def extract_reviews(data: dict, book: dict) -> list:
    """Pull review objects out of the API response."""
    reviews = []

    # The API returns reviews under data.reviews or similar
    items = (
        data.get("data", {}).get("reviews")
        or data.get("reviews")
        or data.get("data", {}).get("top_reviews")
        or []
    )

    if not items and "data" in data:
        # Sometimes the top level is the list
        raw = data["data"]
        if isinstance(raw, list):
            items = raw

    for item in items:
        if not isinstance(item, dict):
            continue

        body = (
            item.get("review_comment")
            or item.get("review_text")
            or item.get("body")
            or item.get("text")
            or ""
        ).strip()

        if not body:
            continue

        review_id = (
            item.get("id")
            or item.get("review_id")
            or item.get("reviewId")
            or ""
        )
        reviewer = (
            item.get("reviewer_name")
            or item.get("reviewer", {}).get("name") if isinstance(item.get("reviewer"), dict) else item.get("reviewer")
            or item.get("author")
            or ""
        )
        stars = parse_stars(
            item.get("review_star_rating")
            or item.get("star_rating")
            or item.get("rating")
            or item.get("stars")
            or ""
        )
        title = (
            item.get("review_title")
            or item.get("title")
            or ""
        ).strip()
        date = (
            item.get("review_date")
            or item.get("date")
            or item.get("reviewDate")
            or ""
        )
        # Normalise date: "Reviewed in the United States on January 15, 2024" → "January 15, 2024"
        date_match = re.search(r"on (.+)$", str(date))
        review_date = date_match.group(1) if date_match else str(date).strip()

        verified = bool(
            item.get("is_verified_purchase")
            or item.get("verified_purchase")
            or item.get("verified")
        )
        helpful_raw = (
            item.get("helpful_vote_statement")
            or item.get("helpful_votes")
            or item.get("helpful")
            or "0"
        )
        helpful_match = re.search(r"([\d,]+)", str(helpful_raw))
        helpful = helpful_match.group(1).replace(",", "") if helpful_match else "0"

        reviews.append({
            "book_asin":         book["asin"],
            "book_title":        book["title"],
            "book_author":       book["author"],
            "review_id":         str(review_id),
            "reviewer_name":     str(reviewer),
            "star_rating":       stars,
            "review_title":      title,
            "review_body":       body[:1500],
            "review_date":       review_date,
            "verified_purchase": verified,
            "helpful_votes":     helpful,
        })

    return reviews


def scrape_book(book: dict) -> list:
    asin  = book["asin"]
    title = book["title"]
    print(f"\n  [{asin}] {title}")

    all_reviews = []
    seen_ids    = set()

    for page in range(1, MAX_PAGES + 1):
        print(f"    Page {page}...", end=" ", flush=True)
        data = fetch_reviews_page(asin, page)

        if not data:
            print("no data returned, stopping.")
            break

        # Check for API-level errors
        if data.get("status") == "ERROR" or data.get("error"):
            msg = data.get("message") or data.get("error") or "unknown error"
            print(f"API error: {msg}")
            break

        reviews = extract_reviews(data, book)

        if not reviews:
            # Dump first-level keys so we can debug if needed
            print(f"0 reviews (keys: {list(data.keys())[:6]})")
            if page == 1:
                print(f"    Full response sample: {str(data)[:500]}")
            break

        new = [r for r in reviews if r["review_id"] not in seen_ids]
        for r in new:
            seen_ids.add(r["review_id"])
        all_reviews.extend(new)
        print(f"{len(reviews)} reviews ({len(new)} new) — total {len(all_reviews)}")

        if len(new) == 0:
            print(f"    No new reviews on page {page}, stopping.")
            break

        time.sleep(DELAY_BETWEEN)

    print(f"  → {len(all_reviews)} unique reviews for '{title}'")
    return all_reviews


# ── MAIN ───────────────────────────────────────────────────────────────────────

def main():
    if RAPIDAPI_KEY == "PASTE_YOUR_KEY_HERE":
        print("ERROR: No API key set.")
        print("Edit this script and replace PASTE_YOUR_KEY_HERE with your RapidAPI key,")
        print("or run:  RAPIDAPI_KEY='your_key' python3 fetch_amazon_reviews_rapidapi.py")
        return

    all_rows = []
    for i, book in enumerate(BOOKS):
        rows = scrape_book(book)
        all_rows.extend(rows)
        if i < len(BOOKS) - 1:
            print(f"  Cooling down 3s...")
            time.sleep(3)

    if not all_rows:
        print("\nNo reviews collected. Possible causes:")
        print("  • Invalid or unsubscribed API key")
        print("  • API response format has changed (check the printed keys above)")
        print("  • Free tier quota exhausted (100 req/month on Basic plan)")
        return

    df = pd.DataFrame(all_rows)
    df.drop_duplicates(subset="review_id", inplace=True)
    df.sort_values(["book_asin", "review_date"], ascending=[True, False], inplace=True)
    df.reset_index(drop=True, inplace=True)
    df.to_csv(OUTPUT_FILE, index=False, encoding="utf-8-sig")

    print(f"\n{'='*60}")
    print(f"Saved {len(df)} reviews → '{OUTPUT_FILE}'")
    print(f"\nBreakdown by book:")
    for book_title, grp in df.groupby("book_title"):
        stars = pd.to_numeric(grp["star_rating"], errors="coerce")
        print(f"\n  {book_title[:55]}")
        print(f"    {len(grp)} reviews, avg rating: {stars.mean():.2f}★")
        dist = grp["star_rating"].value_counts().sort_index().to_dict()
        print(f"    Rating distribution: {dist}")


if __name__ == "__main__":
    main()
