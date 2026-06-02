"""
Fallback parser: reads locally-saved Amazon review HTML files and extracts reviews.

File naming convention (save your pages as):
  attached_p1.html, attached_p2.html ...
  workbook_p1.html, workbook_p2.html ...
  guide_p1.html,    guide_p2.html    ...

Or just drop any *.html files in the same folder — the script will process all of them.
"""
import glob
import re
import pandas as pd
from bs4 import BeautifulSoup

OUTPUT_FILE = "amazon_book_reviews.csv"

# Map filename prefixes to book metadata
BOOK_MAP = {
    "attached":  {"asin": "1585429139", "title": "Attached: The Science of Adult Attachment", "author": "Amir Levine & Rachel Heller"},
    "workbook":  {"asin": "1641523557", "title": "Attachment Theory Workbook", "author": "Annie Chen"},
    "guide":     {"asin": "B093HJF1T7", "title": "Attachment Theory: A Guide to Strengthening Relationships", "author": ""},
}

def detect_book(filename: str) -> dict:
    fname = filename.lower()
    for key, meta in BOOK_MAP.items():
        if key in fname:
            return meta
    # Try ASIN detection
    for meta in BOOK_MAP.values():
        if meta["asin"].lower() in fname:
            return meta
    return {"asin": "unknown", "title": fname, "author": ""}

def parse_stars(raw: str) -> str:
    m = re.search(r"([\d.]+)\s+out\s+of", raw or "")
    if m:
        return m.group(1)
    # Try class-based: a-star-4 -> "4"
    m2 = re.search(r"a-star-([\d-]+)", raw or "")
    return m2.group(1).replace("-", ".") if m2 else raw.strip()

def parse_file(filepath: str) -> list:
    book = detect_book(filepath)
    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        soup = BeautifulSoup(f.read(), "html.parser")

    reviews = []
    # Try both old (div data-hook) and new (li.review) Amazon HTML structures
    containers = soup.find_all("div", {"data-hook": "review"})
    if not containers:
        containers = soup.find_all("li", class_="review")
    print(f"  {filepath}: {len(containers)} review containers found")

    for container in containers:
        # Stars — try aria-label first, then class name
        star_el = (
            container.find("i", {"data-hook": "review-star-rating"})
            or container.find("i", {"data-hook": "cmps-review-star-rating"})
            or container.find("i", class_=re.compile(r"review-rating"))
        )
        stars = ""
        if star_el:
            stars = parse_stars(star_el.get("aria-label", ""))
            if not stars:
                cls = " ".join(star_el.get("class", []))
                stars = parse_stars(cls)

        # Title
        title_el = (
            container.find("a", {"data-hook": "review-title"})
            or container.find("span", {"data-hook": "review-title"})
            or container.find("a", class_=re.compile(r"review-title"))
        )
        title = title_el.get_text(strip=True) if title_el else ""
        title = re.sub(r"^\d\.?\d?\s+out\s+of\s+\d\s+stars?\s*", "", title).strip()

        # Body — try data-hook first, then class
        body_el = (
            container.find("span", {"data-hook": "review-body"})
            or container.find("span", class_=re.compile(r"review-text"))
        )
        body = body_el.get_text(separator=" ", strip=True) if body_el else ""

        # Date
        date_el = (
            container.find("span", {"data-hook": "review-date"})
            or container.find("span", class_=re.compile(r"review-date"))
        )
        date_raw = date_el.get_text(strip=True) if date_el else ""
        date_match = re.search(r"on (.+)$", date_raw)
        review_date = date_match.group(1) if date_match else date_raw

        # Reviewer
        author_el = container.find("span", {"class": "a-profile-name"})
        reviewer = author_el.get_text(strip=True) if author_el else ""

        # Verified
        verified_el = container.find("span", {"data-hook": "avp-badge"})
        verified = bool(verified_el)

        # Helpful votes
        helpful_el = (
            container.find("span", {"data-hook": "helpful-vote-statement"})
            or container.find("span", class_=re.compile(r"cr-vote-text"))
        )
        helpful_text = helpful_el.get_text(strip=True) if helpful_el else ""
        helpful_match = re.search(r"([\d,]+)", helpful_text)
        helpful_votes = helpful_match.group(1).replace(",", "") if helpful_match else "0"

        review_id = container.get("id", "")

        if not body:
            continue

        reviews.append({
            "book_asin":         book["asin"],
            "book_title":        book["title"],
            "book_author":       book["author"],
            "review_id":         review_id,
            "reviewer_name":     reviewer,
            "star_rating":       stars,
            "review_title":      title,
            "review_body":       body[:1500],
            "review_date":       review_date,
            "verified_purchase": verified,
            "helpful_votes":     helpful_votes,
            "source_file":       filepath,
        })

    return reviews

def main():
    html_files = sorted(glob.glob("*.html") + glob.glob("amazon_*.html"))
    if not html_files:
        print("No HTML files found in current directory.")
        print("Save Amazon review pages as HTML files and re-run this script.")
        return

    print(f"Found {len(html_files)} HTML file(s): {html_files}\n")

    all_reviews = []
    for fpath in html_files:
        reviews = parse_file(fpath)
        all_reviews.extend(reviews)

    if not all_reviews:
        print("No reviews extracted. Check that the files contain review data.")
        return

    df = pd.DataFrame(all_reviews)
    df.drop_duplicates(subset="review_id", inplace=True)
    df.sort_values(["book_asin", "review_date"], ascending=[True, False], inplace=True)
    df.reset_index(drop=True, inplace=True)
    df.to_csv(OUTPUT_FILE, index=False, encoding="utf-8-sig")

    print(f"\nSaved {len(df)} reviews → '{OUTPUT_FILE}'")
    for book_title, grp in df.groupby("book_title"):
        stars = pd.to_numeric(grp["star_rating"], errors="coerce")
        print(f"\n  {book_title}")
        print(f"    {len(grp)} reviews, avg {stars.mean():.2f}★")
        print(f"    {dict(grp['star_rating'].value_counts().sort_index())}")

if __name__ == "__main__":
    main()
