"""
Converts Apify Amazon Reviews Scraper JSON export → standardized CSV.

Supports both common Apify Amazon scraper output formats.
Place the downloaded JSON file in the same folder and run:
    python3 parse_apify_reviews.py

Or pass a filename: python3 parse_apify_reviews.py my_export.json
"""
import json
import sys
import re
import glob
import pandas as pd
from pathlib import Path

OUTPUT_FILE = "amazon_book_reviews.csv"

# Map ASINs to clean book metadata
BOOK_META = {
    "1585429139": {
        "title":  "Attached: The Science of Adult Attachment",
        "author": "Amir Levine & Rachel Heller",
    },
    "1641523557": {
        "title":  "Attachment Theory Workbook",
        "author": "Annie Chen",
    },
    "B093HJF1T7": {
        "title":  "Attachment Theory: A Guide to Strengthening Relationships",
        "author": "",
    },
}

def extract_asin(url_or_asin: str) -> str:
    """Pull ASIN from a URL or return as-is if already an ASIN."""
    if not url_or_asin:
        return ""
    # /dp/XXXXXXXXXX or /product/XXXXXXXXXX or /gp/product/XXXXXXXXXX
    m = re.search(r"/(?:dp|product|gp/product)/([A-Z0-9]{10})", url_or_asin, re.I)
    if m:
        return m.group(1).upper()
    # Already looks like an ASIN
    if re.match(r"^[A-Z0-9]{10}$", url_or_asin, re.I):
        return url_or_asin.upper()
    return url_or_asin

def parse_stars(val) -> str:
    """Normalise star rating to a single number string like '4' or '4.0'."""
    if val is None:
        return ""
    s = str(val)
    m = re.search(r"([\d.]+)", s)
    return m.group(1) if m else s.strip()

def normalise_review(raw: dict) -> dict:
    """
    Map fields from various Apify actor output shapes to a standard schema.
    Handles the two most common formats:
      Format A: {asin, title, text, rating, date, author, ...}
      Format B: {productASIN, reviewTitle, reviewBody, starRating, reviewDate, reviewerName, ...}
    """
    # ── ASIN / product identifier ──────────────────────────────────────────
    asin = (
        extract_asin(raw.get("asin", ""))
        or extract_asin(raw.get("productASIN", ""))
        or extract_asin(raw.get("productUrl", ""))
        or extract_asin(raw.get("url", ""))
        or ""
    ).upper()

    meta = BOOK_META.get(asin, {"title": raw.get("productTitle", ""), "author": ""})

    # ── Review fields ──────────────────────────────────────────────────────
    review_id = (
        raw.get("id") or raw.get("reviewId") or raw.get("review_id") or ""
    )
    reviewer = (
        raw.get("reviewerName") or raw.get("author") or raw.get("reviewer") or ""
    )
    stars = parse_stars(
        raw.get("starRating") or raw.get("rating") or raw.get("stars") or ""
    )
    rev_title = (
        raw.get("reviewTitle") or raw.get("title") or ""
    )
    body = (
        raw.get("reviewBody") or raw.get("text") or raw.get("body") or raw.get("content") or ""
    )
    date = (
        raw.get("reviewDate") or raw.get("date") or raw.get("publishedDate") or ""
    )
    verified = bool(
        raw.get("verifiedPurchase") or raw.get("verified") or raw.get("isVerified")
    )
    helpful_raw = (
        raw.get("helpfulVotes") or raw.get("helpful") or raw.get("foundHelpful") or "0"
    )
    helpful_match = re.search(r"(\d+)", str(helpful_raw))
    helpful = helpful_match.group(1) if helpful_match else "0"

    return {
        "book_asin":         asin,
        "book_title":        meta["title"],
        "book_author":       meta["author"],
        "review_id":         str(review_id),
        "reviewer_name":     str(reviewer),
        "star_rating":       stars,
        "review_title":      str(rev_title).strip(),
        "review_body":       str(body)[:1500].strip(),
        "review_date":       str(date).strip(),
        "verified_purchase": verified,
        "helpful_votes":     helpful,
    }


def load_json(path: str) -> list:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    # Apify exports can be a list at root, or {"items": [...]}
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("items", "results", "data", "reviews"):
            if key in data and isinstance(data[key], list):
                return data[key]
    return [data]


def main():
    # Locate input file
    if len(sys.argv) > 1:
        candidates = [sys.argv[1]]
    else:
        candidates = (
            glob.glob("apify_reviews*.json")
            + glob.glob("amazon_reviews*.json")
            + glob.glob("dataset_*.json")
            + glob.glob("apify_export*.json")
        )

    if not candidates:
        print("No JSON file found.")
        print("Usage: python3 parse_apify_reviews.py <filename.json>")
        print("Or rename your Apify export to 'apify_reviews.json' and run again.")
        return

    all_reviews = []
    for path in candidates:
        if not Path(path).exists():
            print(f"File not found: {path}")
            continue
        print(f"Loading {path}...")
        raw_items = load_json(path)
        print(f"  {len(raw_items)} raw items found")
        for item in raw_items:
            norm = normalise_review(item)
            if norm["review_body"]:   # skip empty bodies
                all_reviews.append(norm)

    if not all_reviews:
        print("\nNo reviews extracted. Check the JSON structure.")
        print("Tip: open the file and check what keys the review objects have,")
        print("then let me know and I'll adjust the field mapping.")
        return

    df = pd.DataFrame(all_reviews)
    df.drop_duplicates(subset="review_id", inplace=True)
    df.sort_values(["book_asin", "review_date"], ascending=[True, False], inplace=True)
    df.reset_index(drop=True, inplace=True)
    df.to_csv(OUTPUT_FILE, index=False, encoding="utf-8-sig")

    print(f"\n✓ Saved {len(df)} reviews → '{OUTPUT_FILE}'")
    print()

    for asin, grp in df.groupby("book_asin"):
        title = grp["book_title"].iloc[0]
        stars = pd.to_numeric(grp["star_rating"], errors="coerce")
        dist  = grp["star_rating"].value_counts().sort_index().to_dict()
        print(f"  [{asin}] {title}")
        print(f"    {len(grp)} reviews  |  avg {stars.mean():.2f}★")
        print(f"    Distribution: {dist}")
        print()


if __name__ == "__main__":
    main()
