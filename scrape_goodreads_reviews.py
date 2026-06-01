"""
Scrapes Goodreads reviews for 3 attachment-theory books.
Max 10 pages × 30 reviews = up to 300 reviews per book (900 total).

Run:
    python3 scrape_goodreads_reviews.py
"""

import re
import time
import random
import requests
import pandas as pd
from bs4 import BeautifulSoup

# ── CONFIG ─────────────────────────────────────────────────────────────────────
BOOKS = [
    {"id": "9547888",  "title": "Attached: The Science of Adult Attachment",               "author": "Amir Levine & Rachel Heller"},
    {"id": "45213441", "title": "Attachment Theory Workbook",                               "author": "Annie Chen"},
    {"id": "51625633", "title": "Attachment Theory: A Guide to Strengthening Relationships","author": ""},
]

OUTPUT_FILE = "goodreads_book_reviews.csv"
MAX_PAGES   = 10     # Goodreads caps at 10 pages per book
DELAY_MIN   = 2.5
DELAY_MAX   = 4.5

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept":          "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection":      "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest":  "document",
    "Sec-Fetch-Mode":  "navigate",
    "Sec-Fetch-Site":  "none",
    "Cache-Control":   "max-age=0",
}

# ── HELPERS ────────────────────────────────────────────────────────────────────

def delay():
    time.sleep(random.uniform(DELAY_MIN, DELAY_MAX))


def is_blocked(soup) -> bool:
    text = soup.get_text().lower()
    return "sign in" in text[:500] or "captcha" in text or "robot" in text[:500]


def parse_rating(container) -> str:
    """Extract numeric star rating from a ReviewCard container."""
    # New Goodreads: aria-label like "4 out of 5 stars"
    for el in container.find_all(attrs={"aria-label": True}):
        label = el.get("aria-label", "")
        m = re.search(r"([\d.]+)\s+out\s+of\s+5", label, re.I)
        if m:
            return m.group(1)

    # Class-based: RatingStars__small--4, staticStars starsX
    for el in container.find_all(class_=True):
        cls = " ".join(el.get("class", []))
        m = re.search(r"stars(\d)|star[_-](\d)|--(\d)\b", cls, re.I)
        if m:
            return next(g for g in m.groups() if g)

    return ""


def parse_review_card(container, book: dict) -> dict:
    """Parse one ReviewCard article → dict."""
    # ── Body ──────────────────────────────────────────────────────────────────
    body = ""
    for selector in [
        {"class": re.compile(r"Formatted", re.I)},
        {"data-testid": "reviewText"},
        {"class": re.compile(r"reviewText", re.I)},
    ]:
        el = container.find(["span", "div", "section"], attrs=selector)
        if el:
            # Prefer the innermost Formatted span
            inner = el.find("span", class_=re.compile(r"Formatted", re.I))
            body = (inner or el).get_text(separator=" ", strip=True)
            if body:
                break

    if not body:
        return {}

    # ── Reviewer name ──────────────────────────────────────────────────────────
    name_el = (
        container.find(attrs={"data-testid": "name"})
        or container.find("a", class_=re.compile(r"reviewer|user", re.I))
        or container.find("span", class_=re.compile(r"reviewer", re.I))
    )
    reviewer = name_el.get_text(strip=True) if name_el else ""

    # ── Star rating ────────────────────────────────────────────────────────────
    stars = parse_rating(container)

    # ── Date ──────────────────────────────────────────────────────────────────
    date_el = (
        container.find(attrs={"data-testid": "review-date-link"})
        or container.find("a",    class_=re.compile(r"date|when", re.I))
        or container.find("span", class_=re.compile(r"date|when", re.I))
    )
    review_date = date_el.get_text(strip=True) if date_el else ""

    # ── Review ID ──────────────────────────────────────────────────────────────
    review_id = (
        container.get("id", "")
        or container.get("data-review-id", "")
        or container.get("data-testid", "")
    )

    # ── Helpful votes ─────────────────────────────────────────────────────────
    helpful_el = container.find(
        ["button", "span"],
        attrs={"data-testid": re.compile(r"helpful|like|vote", re.I)},
    )
    helpful_text  = helpful_el.get_text(strip=True) if helpful_el else ""
    helpful_match = re.search(r"(\d+)", helpful_text)
    helpful       = helpful_match.group(1) if helpful_match else "0"

    return {
        "book_id":       book["id"],
        "book_title":    book["title"],
        "book_author":   book["author"],
        "review_id":     str(review_id),
        "reviewer_name": reviewer,
        "star_rating":   stars,
        "review_body":   body[:1500].strip(),
        "review_date":   review_date,
        "helpful_votes": helpful,
        "source":        "goodreads",
    }


def parse_page(soup, book: dict) -> list:
    """Find all ReviewCard containers on a page and parse them."""
    # New Goodreads design
    containers = soup.find_all("article", class_=re.compile(r"ReviewCard", re.I))

    # Older Goodreads fallback
    if not containers:
        containers = soup.find_all("div", class_="review")

    reviews = []
    for c in containers:
        row = parse_review_card(c, book)
        if row:
            reviews.append(row)
    return reviews


def fetch_page(session, book_id: str, page: int, sort: str = "newest") -> BeautifulSoup:
    """Fetch a Goodreads reviews page (tries /reviews sub-path, falls back to main)."""
    urls = [
        f"https://www.goodreads.com/book/show/{book_id}/reviews"
        f"?sort={sort}&page={page}&language_code=en",
        f"https://www.goodreads.com/book/show/{book_id}"
        f"?page={page}&sort={sort}",
    ]
    for url in urls:
        try:
            r = session.get(url, headers=HEADERS, timeout=25)
            if r.status_code == 404:
                continue
            r.raise_for_status()
            soup = BeautifulSoup(r.text, "html.parser")
            if is_blocked(soup):
                print(f"    Blocked / login wall detected.")
                return None
            return soup
        except Exception as e:
            print(f"    Request error: {e}")
    return None


# ── SCRAPE ONE BOOK ────────────────────────────────────────────────────────────

def scrape_book(session, book: dict) -> list:
    print(f"\n  [{book['id']}] {book['title']}")
    all_reviews = []
    seen_ids    = set()

    for page in range(1, MAX_PAGES + 1):
        print(f"    Page {page}...", end=" ", flush=True)
        soup = fetch_page(session, book["id"], page)

        if soup is None:
            print("fetch failed, stopping.")
            break

        reviews = parse_page(soup, book)

        if not reviews:
            # Debug: show what containers we did find
            cards = soup.find_all("article")
            divs  = soup.find_all("div", class_="review")
            print(f"0 reviews (articles={len(cards)}, div.review={len(divs)})")
            if page == 1:
                # Save raw HTML for manual inspection
                with open(f"debug_goodreads_{book['id']}_p{page}.html", "w", encoding="utf-8") as f:
                    f.write(soup.prettify())
                print(f"    → Saved debug HTML: debug_goodreads_{book['id']}_p{page}.html")
            break

        new = [r for r in reviews if r["review_id"] not in seen_ids]
        for r in new:
            seen_ids.add(r["review_id"])
        all_reviews.extend(new)
        print(f"{len(reviews)} reviews ({len(new)} new) — total {len(all_reviews)}")

        if len(new) == 0:
            print(f"    No new reviews, stopping.")
            break

        delay()

    print(f"  → {len(all_reviews)} unique reviews")
    return all_reviews


# ── MAIN ───────────────────────────────────────────────────────────────────────

def main():
    session = requests.Session()

    all_rows = []
    for i, book in enumerate(BOOKS):
        rows = scrape_book(session, book)
        all_rows.extend(rows)
        if i < len(BOOKS) - 1:
            print(f"  Cooling down 6s...")
            time.sleep(6)

    if not all_rows:
        print("\nNo reviews collected.")
        print("Goodreads may require JavaScript for review content.")
        print("Check the saved debug_goodreads_*.html files to see what was returned.")
        return

    df = pd.DataFrame(all_rows)
    df.drop_duplicates(subset="review_id", inplace=True)
    df.sort_values(["book_id", "review_date"], ascending=[True, False], inplace=True)
    df.reset_index(drop=True, inplace=True)
    df.to_csv(OUTPUT_FILE, index=False, encoding="utf-8-sig")

    print(f"\n{'='*60}")
    print(f"Saved {len(df)} reviews → '{OUTPUT_FILE}'")
    for title, grp in df.groupby("book_title"):
        stars = pd.to_numeric(grp["star_rating"], errors="coerce")
        print(f"\n  {title[:55]}")
        print(f"    {len(grp)} reviews, avg {stars.mean():.2f}★")
        dist = grp["star_rating"].value_counts().sort_index().to_dict()
        print(f"    Distribution: {dist}")


if __name__ == "__main__":
    main()
