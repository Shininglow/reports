"""
Scrape Quora for men who had relationships, got burned, and are now guarded/alone.
Uses your logged-in Quora session (cookies exported from browser).

Setup: export cookies from quora.com using "Get cookies.txt LOCALLY" Chrome extension.
Output: quora_answers.csv
"""

import re
import time
import os
import pandas as pd
from playwright.sync_api import sync_playwright

COOKIES_FILE = os.path.expanduser("~/Downloads/www.quora.com_cookies.txt")
OUTPUT_FILE  = os.path.join(os.path.dirname(__file__), "quora_answers.csv")
MIN_TEXT_LENGTH = 150
SCORE_THRESHOLD = 3

# ── Search queries for Quora's internal search ───────────────────────────────
SEARCH_QUERIES = [
    "men gave up on relationships",
    "afraid to love again after being hurt",
    "she cheated I gave everything",
    "relationship destroyed me trust issues",
    "one-sided relationship gave more loved more",
    "done with relationships never again",
    "emotionally drained by relationship",
    "better off alone after breakup",
    "she left me after divorce rebuilding",
    "walls up closed off after relationship",
    "men sworn off dating relationships",
    "lost myself in a relationship",
    "can't trust women anymore",
    "relationship not worth the pain",
    "still recovering from breakup years later",
    "she used me emotionally taken advantage",
    "married wrong person regret emotional cost",
    "numb after breakup feel nothing",
    "nice guy syndrome relationship failed",
    "gave up on love after divorce",
]


# ── 1. Load cookies from Netscape format file ────────────────────────────────

def load_cookies(path: str) -> list[dict]:
    """Parse Netscape cookie file → Playwright cookie list."""
    cookies = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split("\t")
            if len(parts) < 7:
                continue
            domain, _, path_, secure, expires, name, value = parts[:7]
            try:
                exp = int(expires)
            except ValueError:
                exp = -1
            cookies.append({
                "name":     name,
                "value":    value,
                "domain":   domain.lstrip("."),
                "path":     path_,
                "secure":   secure.upper() == "TRUE",
                "httpOnly": False,
                "sameSite": "None",
                **({"expires": exp} if exp > 0 else {}),
            })
    return cookies


# ── 2. Search Quora → question URLs ──────────────────────────────────────────

def search_quora(page, query: str) -> list[tuple[str, str]]:
    """Use Quora's search to find question pages. Returns (title, url) pairs."""
    search_url = f"https://www.quora.com/search?q={query.replace(' ', '+')}&type=question"
    try:
        page.goto(search_url, wait_until="domcontentloaded", timeout=20000)
        time.sleep(4)

        # Check we're not on login page
        if "quora.com/login" in page.url or "Sign In" in page.title():
            print("  ⚠ Redirected to login — cookies may be expired", flush=True)
            return []

        results = []
        # Question links: /[Long-Hyphenated-Title] with no subpath
        links = page.locator("a[href^='/']").all()
        for link in links:
            try:
                href = link.get_attribute("href") or ""
                # Keep only question-slug paths (no /profile/, /topic/ etc.)
                if (href.startswith("/")
                        and len(href) > 30
                        and href.count("/") == 1
                        and not any(x in href for x in
                                    ["/profile/", "/topic/", "/search", "/login",
                                     "/business", "/about", "/careers", "?"])):
                    title = link.inner_text().strip()[:120]
                    full_url = "https://www.quora.com" + href
                    if title and len(title) > 15:
                        results.append((title, full_url))
            except Exception:
                pass
        return results
    except Exception as e:
        print(f"  Search error: {e}", flush=True)
        return []


# ── 3. Extract answer text from a question page ──────────────────────────────

def extract_answers(page, url: str) -> list[str]:
    """Visit a Quora question page and return list of answer text blocks."""
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=20000)
        time.sleep(5)

        # Dismiss any modal/overlay
        for selector in ['button[aria-label="Close"]', 'div[class*="modal"] button',
                         'button:has-text("Dismiss")', 'button:has-text("No thanks")']:
            try:
                btn = page.locator(selector).first
                if btn.is_visible():
                    btn.click()
                    time.sleep(0.5)
            except Exception:
                pass

        # Try to expand truncated answers
        for _ in range(3):
            more = page.locator('button:has-text("more"), span:has-text("Continue Reading")').all()
            if not more:
                break
            for btn in more[:6]:
                try:
                    btn.click()
                    time.sleep(0.4)
                except Exception:
                    pass

        body_text = page.inner_text("body")

        # Split into paragraph-sized blocks
        blocks, current = [], []
        for line in body_text.split("\n"):
            line = line.strip()
            if len(line) > 40:
                current.append(line)
            else:
                if current:
                    combined = " ".join(current)
                    if len(combined) >= MIN_TEXT_LENGTH:
                        blocks.append(combined)
                    current = []
        if current:
            combined = " ".join(current)
            if len(combined) >= MIN_TEXT_LENGTH:
                blocks.append(combined)

        # Deduplicate
        seen, unique = set(), []
        for b in blocks:
            key = b[:100]
            if key not in seen:
                seen.add(key)
                unique.append(b)
        return unique
    except Exception as e:
        print(f"  Page error: {e}", flush=True)
        return []


# ── 4. Filters & scoring ─────────────────────────────────────────────────────

def is_female_answer(text: str) -> bool:
    t = text.lower()
    return any(s in t for s in [
        "i'm a woman", "i am a woman", "as a woman", "as a girl",
        "i'm female", "i am female", "woman here", "my husband cheated",
        "my ex-husband", "as a wife", "us women", "we women",
    ])


def has_relevant_signal(text: str) -> bool:
    t = text.lower()
    signals = [
        "gave everything", "gave my all", "she cheated", "cheated on me",
        "she left me", "she betrayed", "she used me", "taken advantage",
        "done with relationships", "never again", "sworn off",
        "not worth it", "better off alone", "given up on love",
        "drained me", "destroyed me", "broke me", "trust issues",
        "walls up", "afraid to love", "scared to love", "one-sided",
        "wasn't reciprocated", "after the divorce", "still recovering",
        "numb", "closed off", "can't trust", "don't trust",
        "my ex", "ex-girlfriend", "ex-wife", "we broke up",
        "lost myself", "in a relationship for", "years together",
        "she didn't appreciate", "never been the same",
    ]
    return any(s in t for s in signals)


def score_answer(text: str) -> tuple[int, str]:
    t = text.lower()
    score = 0

    male_strong = [
        "i'm a man", "i am a man", "as a man", "i'm a guy", "as a guy",
        "my girlfriend", "my ex-girlfriend", "my ex-wife", "i dated",
        "she cheated on me", "she left me", "my wife left", "my divorce",
    ]
    score += sum(2 for s in male_strong if s in t)
    score += sum(1 for s in ["she said", "she wasn't", "her ex", "she only",
                              "she didn't", "dated a woman", "met a girl"] if s in t)

    personal = [
        "i used to", "i was", "i realized", "i struggled", "i gave",
        "i loved her", "i trusted", "i thought we", "i put her first",
        "i sacrificed", "i gave everything", "my experience", "my story",
        "after my divorce", "after my breakup", "after she left",
        "after she cheated", "i went through", "this happened to me",
    ]
    score += sum(2 for s in personal if s in t)

    disappointment = [
        "gave everything", "gave my all", "one-sided", "she cheated",
        "she used me", "abandoned", "betrayed", "drained me",
        "destroyed me", "broke me", "trust issues", "walls up",
        "afraid to love", "never again", "sworn off", "better off alone",
        "given up", "don't trust", "can't trust", "stopped caring",
    ]
    score += sum(2 for s in disappointment if s in t)

    if len(text) > 300:  score += 1
    if len(text) > 700:  score += 1
    if len(text) > 1200: score += 2

    segment = "General / Disappointed in Love"
    if any(s in t for s in ["cheated", "infidelity", "unfaithful", "betrayed"]):
        segment = "Betrayed / Cheated On"
    elif any(s in t for s in ["divorce", "married", "marriage", "ex-wife"]):
        segment = "Post-Divorce Rebuilder"
    elif any(s in t for s in ["gave everything", "one-sided", "not reciprocated"]):
        segment = "One-Sided Giver / Depleted"
    elif any(s in t for s in ["drained", "lost myself", "became a shell"]):
        segment = "Emotionally Drained / Lost Self"
    elif any(s in t for s in ["done with", "sworn off", "never again", "given up"]):
        segment = "Resigned / Sworn Off Love"
    elif any(s in t for s in ["can't trust", "walls up", "afraid to love", "numb"]):
        segment = "Guarded / Can't Trust Again"
    elif any(s in t for s in ["used me", "she only wanted", "taken advantage"]):
        segment = "Used / Taken Advantage Of"

    return score, segment


# ── 5. Main ──────────────────────────────────────────────────────────────────

def main():
    if not os.path.exists(COOKIES_FILE):
        print(f"ERROR: Cookies file not found at {COOKIES_FILE}")
        print("Export cookies from quora.com using 'Get cookies.txt LOCALLY' extension.")
        return

    cookies = load_cookies(COOKIES_FILE)
    print(f"Loaded {len(cookies)} cookies from {os.path.basename(COOKIES_FILE)}", flush=True)

    all_urls: dict[str, str] = {}
    records = []
    seen_texts: set[str] = set()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 900},
            locale="en-US",
        )
        ctx.add_cookies(cookies)
        page = ctx.new_page()

        # ── Verify login ──────────────────────────────────────────────────────
        page.goto("https://www.quora.com", wait_until="domcontentloaded", timeout=20000)
        time.sleep(3)
        body_check = page.inner_text("body")
        if "Sign In" in page.title() or "sign up" in body_check.lower()[:200]:
            print("⚠ Not logged in — cookies may be expired. Re-export and try again.")
            browser.close()
            return
        print(f"✓ Logged in. Title: {page.title()[:60]}\n", flush=True)

        # ── Phase 1: discover question URLs via Quora search ──────────────────
        print(f"Phase 1: Searching Quora for question URLs ({len(SEARCH_QUERIES)} queries)...\n", flush=True)
        for i, query in enumerate(SEARCH_QUERIES):
            print(f"  [{i+1}/{len(SEARCH_QUERIES)}] '{query}'", flush=True)
            results = search_quora(page, query)
            new = 0
            for title, url in results:
                if url not in all_urls:
                    all_urls[url] = title
                    new += 1
            print(f"    → {len(results)} results, {new} new (total: {len(all_urls)})", flush=True)
            time.sleep(2)

        print(f"\nFound {len(all_urls)} unique question pages.\n", flush=True)

        # ── Phase 2: scrape each question page ───────────────────────────────
        print("Phase 2: Extracting answers...\n", flush=True)
        for i, (url, title) in enumerate(all_urls.items()):
            print(f"[{i+1}/{len(all_urls)}] {title[:70]}...", flush=True)
            answers = extract_answers(page, url)

            kept = 0
            for ans_text in answers:
                key = ans_text[:80]
                if key in seen_texts:
                    continue
                if is_female_answer(ans_text):
                    continue
                if not has_relevant_signal(ans_text):
                    continue
                score, segment = score_answer(ans_text)
                if score < SCORE_THRESHOLD:
                    continue
                seen_texts.add(key)
                records.append({
                    "question_title":  title,
                    "question_url":    url,
                    "answer_text":     ans_text[:2500],
                    "text_length":     len(ans_text),
                    "relevance_score": score,
                    "segment_tag":     segment,
                })
                kept += 1
            print(f"  → {len(answers)} blocks extracted, {kept} kept", flush=True)
            time.sleep(2)

        browser.close()

    if not records:
        print("\nNo relevant answers found. Try lowering SCORE_THRESHOLD.", flush=True)
        return

    df = pd.DataFrame(records)
    df.sort_values("relevance_score", ascending=False, inplace=True)
    df.reset_index(drop=True, inplace=True)
    df.to_csv(OUTPUT_FILE, index=False, encoding="utf-8-sig")

    print(f"\n{'='*60}")
    print(f"✓ Saved {len(df)} answers to quora_answers.csv")
    print(f"\nSegment distribution:")
    print(df["segment_tag"].value_counts().to_string())
    print(f"\nTop 10 by relevance score:")
    for _, row in df.head(10).iterrows():
        print(f"\n  [score {row.relevance_score}] {row.question_title[:65]}")
        print(f"  {row.answer_text[:180]}")


if __name__ == "__main__":
    main()
