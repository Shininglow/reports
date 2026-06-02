"""
Parses locally-saved Goodreads review HTML pages into a CSV.

How to save the pages:
  1. Log into goodreads.com in your browser
  2. Open each book's review page:
       https://www.goodreads.com/book/show/9547888/reviews?sort=newest
       https://www.goodreads.com/book/show/45213441/reviews?sort=newest
       https://www.goodreads.com/book/show/51625633/reviews?sort=newest
  3. Wait for reviews to fully load, then press Cmd+S
     → choose "Web Page, Complete"
  4. Save files using this naming convention:
       attached_p1.html, attached_p2.html ...
       workbook_p1.html, workbook_p2.html ...
       guide_p1.html,    guide_p2.html    ...
  5. Move all HTML files to this folder and run:
       python3 parse_goodreads_html.py

Tip: click "Next page" on Goodreads, wait for load, then Cmd+S again for each page.
"""

import glob
import re
import pandas as pd
from bs4 import BeautifulSoup

OUTPUT_FILE = "goodreads_book_reviews.csv"

BOOK_MAP = {
    "attached":  {"id": "9547888",  "title": "Attached: The Science of Adult Attachment",                "author": "Amir Levine & Rachel Heller"},
    "workbook":  {"id": "45213441", "title": "Attachment Theory Workbook",                               "author": "Annie Chen"},
    "guide":     {"id": "51625633", "title": "Attachment Theory: A Guide to Strengthening Relationships","author": ""},
}


def detect_book(filename: str) -> dict:
    fname = filename.lower()
    for key, meta in BOOK_MAP.items():
        if key in fname:
            return meta
    for meta in BOOK_MAP.values():
        if meta["id"] in fname:
            return meta
    return {"id": "unknown", "title": fname, "author": ""}


def parse_rating(container) -> str:
    # aria-label: "4 out of 5 stars"
    for el in container.find_all(attrs={"aria-label": True}):
        label = el.get("aria-label", "")
        m = re.search(r"([\d.]+)\s+out\s+of\s+5", label, re.I)
        if m:
            return m.group(1)
    # class-based: staticStars stars4, RatingStars__small--4
    for el in container.find_all(class_=True):
        cls = " ".join(el.get("class", []))
        m = re.search(r"stars(\d)|star[_\-](\d)|--(\d)\b", cls, re.I)
        if m:
            return next(g for g in m.groups() if g)
    return ""


def parse_file(filepath: str) -> list:
    book = detect_book(filepath)
    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        soup = BeautifulSoup(f.read(), "html.parser")

    # New Goodreads design
    containers = soup.find_all("article", class_=re.compile(r"ReviewCard", re.I))
    # Older Goodreads design fallback
    if not containers:
        containers = soup.find_all("div", class_="review")

    print(f"  {filepath}: {len(containers)} review containers found")

    reviews = []
    for container in containers:
        # ── Body ──────────────────────────────────────────────────────────────
        body = ""
        for attrs in [
            {"class": re.compile(r"Formatted", re.I)},
            {"data-testid": "reviewText"},
            {"class": re.compile(r"reviewText|reviewBody", re.I)},
        ]:
            el = container.find(["span", "div", "section"], attrs=attrs)
            if el:
                inner = el.find("span", class_=re.compile(r"Formatted", re.I))
                body = (inner or el).get_text(separator=" ", strip=True)
                if body:
                    break

        if not body:
            continue

        # ── Reviewer ──────────────────────────────────────────────────────────
        name_el = (
            container.find(attrs={"data-testid": "name"})
            or container.find("a",    class_=re.compile(r"reviewer|user", re.I))
            or container.find("span", class_=re.compile(r"reviewer", re.I))
        )
        reviewer = name_el.get_text(strip=True) if name_el else ""

        # ── Rating ────────────────────────────────────────────────────────────
        stars = parse_rating(container)

        # ── Date ──────────────────────────────────────────────────────────────
        date_el = (
            container.find(attrs={"data-testid": "review-date-link"})
            or container.find("a",    class_=re.compile(r"date|when", re.I))
            or container.find("span", class_=re.compile(r"date|when", re.I))
        )
        review_date = date_el.get_text(strip=True) if date_el else ""

        # ── Review ID ─────────────────────────────────────────────────────────
        review_id = (
            container.get("id", "")
            or container.get("data-review-id", "")
            or ""
        )

        # ── Helpful votes ─────────────────────────────────────────────────────
        helpful_el = container.find(
            ["button", "span"],
            attrs={"data-testid": re.compile(r"helpful|like|vote", re.I)},
        )
        helpful_text  = helpful_el.get_text(strip=True) if helpful_el else "0"
        helpful_match = re.search(r"(\d+)", helpful_text)
        helpful       = helpful_match.group(1) if helpful_match else "0"

        reviews.append({
            "book_id":       book["id"],
            "book_title":    book["title"],
            "book_author":   book["author"],
            "review_id":     review_id,
            "reviewer_name": reviewer,
            "star_rating":   stars,
            "review_body":   body[:1500].strip(),
            "review_date":   review_date,
            "helpful_votes": helpful,
            "source_file":   filepath,
        })

    return reviews


def main():
    html_files = sorted(
        glob.glob("attached*.html")
        + glob.glob("workbook*.html")
        + glob.glob("guide*.html")
        + glob.glob("goodreads*.html")
    )

    if not html_files:
        print("No HTML files found.")
        print("Save Goodreads review pages using Cmd+S and name them:")
        print("  attached_p1.html, workbook_p1.html, guide_p1.html, etc.")
        return

    print(f"Found {len(html_files)} file(s): {html_files}\n")

    all_reviews = []
    for fpath in html_files:
        reviews = parse_file(fpath)
        all_reviews.extend(reviews)

    if not all_reviews:
        print("\nNo reviews extracted.")
        print("The page may not have loaded fully before saving.")
        print("Try: wait ~5 seconds after the page loads before pressing Cmd+S.")
        return

    df = pd.DataFrame(all_reviews)
    df.drop_duplicates(subset="review_id", inplace=True)
    df.sort_values(["book_id", "review_date"], ascending=[True, False], inplace=True)
    df.reset_index(drop=True, inplace=True)
    df.to_csv(OUTPUT_FILE, index=False, encoding="utf-8-sig")

    print(f"\nSaved {len(df)} reviews → '{OUTPUT_FILE}'")
    for title, grp in df.groupby("book_title"):
        stars = pd.to_numeric(grp["star_rating"], errors="coerce")
        print(f"\n  {title}")
        print(f"    {len(grp)} reviews, avg {stars.mean():.2f}★")
        print(f"    {dict(grp['star_rating'].value_counts().sort_index())}")


if __name__ == "__main__":
    main()
