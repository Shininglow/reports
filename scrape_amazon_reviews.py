"""
Scrape Amazon customer reviews for 3 attachment-theory books.
Saves all reviews to a single CSV: amazon_book_reviews.csv

If Amazon blocks requests (CAPTCHA detected), the script will print
instructions for the manual HTML fallback method.
"""
import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import re
import random
from datetime import datetime

# ── BOOKS ─────────────────────────────────────────────────────────────────────
BOOKS = [
    {
        "asin":  "1585429139",
        "title": "Attached: The Science of Adult Attachment",
        "author": "Amir Levine & Rachel Heller",
    },
    {
        "asin":  "1641523557",
        "title": "Attachment Theory Workbook",
        "author": "Annie Chen",
    },
    {
        "asin":  "B093HJF1T7",
        "title": "Attachment Theory: A Guide to Strengthening Relationships",
        "author": "",
    },
]

OUTPUT_FILE = "amazon_book_reviews.csv"
MAX_PAGES   = 20   # up to 20 pages × 10 reviews = 200 reviews per book
DELAY_MIN   = 2.5
DELAY_MAX   = 4.5

# ── HEADERS (mimic real Chrome browser) ───────────────────────────────────────
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;"
        "q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection":  "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Cache-Control": "max-age=0",
}

def delay():
    time.sleep(random.uniform(DELAY_MIN, DELAY_MAX))

def is_blocked(soup) -> bool:
    """Detect CAPTCHA / robot-check page."""
    text = soup.get_text().lower()
    return (
        "robot check" in text
        or "enter the characters you see below" in text
        or "sorry, we just need to make sure you" in text
        or "captcha" in text
        or soup.find("form", {"action": re.compile(r"captcha", re.I)}) is not None
    )

def parse_stars(raw: str) -> str:
    """Extract '4.0' from '4.0 out of 5 stars'."""
    m = re.search(r"([\d.]+)\s+out\s+of", raw or "")
    return m.group(1) if m else raw.strip()

def fetch_page(session, asin: str, page: int, sort: str = "recent"):
    url = (
        f"https://www.amazon.com/product-reviews/{asin}/"
        f"ref=cm_cr_arp_d_paging_btm_next_{page}"
        f"?pageNumber={page}&sortBy={sort}&reviewerType=all_reviews"
    )
    try:
        r = session.get(url, headers=HEADERS, timeout=20)
        r.raise_for_status()
        return BeautifulSoup(r.text, "html.parser"), url
    except Exception as e:
        print(f"    Request error: {e}")
        return None, url

def parse_reviews(soup, book: dict, page: int) -> list:
    reviews = []
    for container in soup.find_all("div", {"data-hook": "review"}):
        # Rating
        star_el = container.find("i", {"data-hook": "review-star-rating"}) or \
                  container.find("i", {"data-hook": "cmps-review-star-rating"})
        stars = parse_stars(star_el["class"][-1].replace("a-star-", "").replace("-", ".") if star_el else "")
        # Try the aria-label if class parsing fails
        if not stars and star_el:
            stars = parse_stars(star_el.get("aria-label", ""))

        # Title
        title_el = container.find("a", {"data-hook": "review-title"}) or \
                   container.find("span", {"data-hook": "review-title"})
        title = title_el.get_text(strip=True) if title_el else ""
        # Strip leading star text from title (Amazon sometimes includes it)
        title = re.sub(r"^\d\.?\d?\s+out\s+of\s+\d\s+stars?\s*", "", title).strip()

        # Body
        body_el = container.find("span", {"data-hook": "review-body"})
        body = body_el.get_text(separator=" ", strip=True) if body_el else ""

        # Date
        date_el = container.find("span", {"data-hook": "review-date"})
        date_raw = date_el.get_text(strip=True) if date_el else ""
        # "Reviewed in the United States on January 15, 2024"
        date_match = re.search(r"on (.+)$", date_raw)
        review_date = date_match.group(1) if date_match else date_raw

        # Reviewer name
        author_el = container.find("span", {"class": "a-profile-name"})
        reviewer = author_el.get_text(strip=True) if author_el else ""

        # Verified purchase
        verified_el = container.find("span", {"data-hook": "avp-badge"})
        verified = bool(verified_el)

        # Helpful votes
        helpful_el = container.find("span", {"data-hook": "helpful-vote-statement"})
        helpful_text = helpful_el.get_text(strip=True) if helpful_el else ""
        helpful_match = re.search(r"([\d,]+)", helpful_text)
        helpful_votes = helpful_match.group(1).replace(",", "") if helpful_match else "0"

        # Review ID
        review_id = container.get("id", "")

        if not body:
            continue

        reviews.append({
            "book_asin":        book["asin"],
            "book_title":       book["title"],
            "book_author":      book["author"],
            "review_id":        review_id,
            "reviewer_name":    reviewer,
            "star_rating":      stars,
            "review_title":     title,
            "review_body":      body[:1500],
            "review_date":      review_date,
            "verified_purchase": verified,
            "helpful_votes":    helpful_votes,
            "page":             page,
            "review_url":       f"https://www.amazon.com/dp/{book['asin']}#review-{review_id}",
        })
    return reviews

def scrape_book(session, book: dict) -> list:
    asin  = book["asin"]
    title = book["title"]
    print(f"\n  Book: {title}  (ASIN {asin})")

    # Warm-up: visit the product page first to pick up cookies
    print(f"  Warming up session on product page...")
    warm_url = f"https://www.amazon.com/dp/{asin}"
    try:
        r = session.get(warm_url, headers=HEADERS, timeout=20)
        soup_warm = BeautifulSoup(r.text, "html.parser")
        if is_blocked(soup_warm):
            print(f"  ⚠ CAPTCHA on product page — see manual fallback instructions below.")
            return []
    except Exception as e:
        print(f"  Warm-up failed: {e}")
    delay()

    all_reviews = []

    for sort in ["recent", "helpful"]:
        print(f"\n  Fetching sort={sort} reviews...")
        seen_ids = {r["review_id"] for r in all_reviews}

        for page in range(1, MAX_PAGES + 1):
            soup, url = fetch_page(session, asin, page, sort)
            if soup is None:
                print(f"    Page {page}: fetch failed, stopping.")
                break

            if is_blocked(soup):
                print(f"    Page {page}: CAPTCHA detected — stopping this sort.")
                print(f"    ⚠ Try again later or use the manual HTML method.")
                break

            reviews = parse_reviews(soup, book, page)
            new = [r for r in reviews if r["review_id"] not in seen_ids]

            if not reviews:
                # Check if there truly are no reviews or the page structure changed
                no_reviews = soup.find("div", {"data-hook": "no-reviews-section"})
                if no_reviews or page > 1:
                    print(f"    Page {page}: no more reviews.")
                    break
                else:
                    print(f"    Page {page}: 0 reviews parsed (structure may have changed).")
                    break

            for r in new:
                seen_ids.add(r["review_id"])
            all_reviews.extend(new)

            print(f"    Page {page:>2}: {len(reviews)} reviews ({len(new)} new) — total {len(all_reviews)}")
            delay()

    print(f"\n  → {len(all_reviews)} reviews collected for '{title}'")
    return all_reviews


def print_fallback_instructions():
    print("""
╔══════════════════════════════════════════════════════════════╗
║              MANUAL FALLBACK — if script is blocked          ║
╠══════════════════════════════════════════════════════════════╣
║  For each book, in your browser:                             ║
║                                                              ║
║  1. Open the reviews URL:                                    ║
║     amazon.com/product-reviews/{ASIN}?pageNumber=1          ║
║  2. Wait for the page to fully load                          ║
║  3. File → Save Page As → "Webpage, Complete" (Cmd+S)       ║
║     Save as: attached_reviews_p1.html  etc.                  ║
║  4. Repeat for pages 2, 3... until reviews run out           ║
║  5. Run: python3 parse_amazon_html.py                        ║
║     (the companion parsing script)                           ║
╚══════════════════════════════════════════════════════════════╝
""")


def main():
    session = requests.Session()
    session.headers.update(HEADERS)

    all_rows = []

    for book in BOOKS:
        reviews = scrape_book(session, book)
        all_rows.extend(reviews)
        if book != BOOKS[-1]:
            print(f"\n  Cooling down 8s before next book...")
            time.sleep(8)

    if not all_rows:
        print("\nNo reviews collected. Amazon likely blocked all requests.")
        print_fallback_instructions()
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
        print(f"  {book_title[:50]}")
        print(f"    {len(grp)} reviews, avg rating: {stars.mean():.2f}★")
        print(f"    Rating distribution: {dict(grp['star_rating'].value_counts().sort_index())}")

    if not all_rows:
        print_fallback_instructions()


if __name__ == "__main__":
    main()
