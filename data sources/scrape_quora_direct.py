"""
Scrape Quora without authentication.
Strategy: test a curated list of likely question slugs directly.
Most Quora pages are publicly readable — we just need valid URLs.
Output: quora_answers.csv (appends to existing if present)
"""

import time
import os
import re
import pandas as pd
from playwright.sync_api import sync_playwright

OUTPUT_FILE     = os.path.join(os.path.dirname(__file__), "quora_answers.csv")
MIN_TEXT_LENGTH = 150
SCORE_THRESHOLD = 5   # raised from 3 — needs clear male + disappointment signals

# Curated list of likely question slugs — tested patterns that work on Quora
CANDIDATE_SLUGS = [
    # Giving up on love / relationships
    "Why-do-some-men-give-up-on-dating",
    "Why-do-men-give-up-on-finding-love",
    "What-makes-men-give-up-on-relationships",
    "Why-do-many-men-give-up-on-dating",
    "Is-it-okay-to-give-up-on-love-after-being-hurt",
    "Why-do-men-stop-trying-in-relationships",
    "Why-have-I-given-up-on-relationships",
    "Is-it-normal-to-give-up-on-love-after-heartbreak",
    "Why-do-men-swear-off-relationships-after-a-bad-breakup",
    "Is-it-better-to-be-alone-than-be-in-a-toxic-relationship",

    # Cheating / betrayal
    "What-does-it-feel-like-to-be-cheated-on",
    "How-do-you-recover-emotionally-from-being-cheated-on",
    "Why-do-men-take-cheating-so-hard",
    "What-does-betrayal-in-a-relationship-feel-like",
    "How-does-being-cheated-on-change-a-man",
    "What-does-it-feel-like-when-your-partner-cheats-on-you",
    "Why-is-being-cheated-on-so-devastating",
    "Can-you-ever-forgive-a-partner-who-cheated",
    "How-do-men-feel-after-being-cheated-on",
    "What-do-you-do-when-you-find-out-your-girlfriend-cheated",
    "Why-does-being-cheated-on-feel-so-personal",
    "How-long-does-it-take-to-recover-from-being-cheated-on",

    # Trust issues / walls up
    "How-do-you-trust-again-after-being-betrayed",
    "Can-you-ever-trust-someone-again-after-they-cheated",
    "How-do-you-overcome-trust-issues-from-past-relationships",
    "What-does-it-mean-to-have-walls-up-in-a-relationship",
    "How-do-I-learn-to-trust-people-again-after-being-hurt",
    "What-causes-trust-issues-in-relationships",
    "How-do-you-open-up-emotionally-after-being-hurt",
    "Why-am-I-scared-to-fall-in-love-again",
    "Why-am-I-afraid-to-love-again-after-being-hurt",
    "How-do-you-stop-being-afraid-of-love",
    "Why-do-I-keep-my-walls-up-in-relationships",
    "What-does-it-mean-when-someone-says-they-have-walls-up",
    "How-do-you-get-someone-to-open-up-emotionally",

    # Emotional numbness / shutdown
    "What-does-emotional-numbness-feel-like-after-a-breakup",
    "How-do-you-stop-feeling-numb-after-a-breakup",
    "Why-do-I-feel-nothing-after-a-breakup",
    "What-does-heartbreak-feel-like-for-men",
    "How-do-men-deal-with-depression-after-a-breakup",
    "Why-do-men-go-quiet-after-a-breakup",
    "Why-do-men-become-distant-after-a-breakup",
    "How-do-men-really-feel-after-a-breakup",
    "What-is-it-like-to-have-your-heart-broken",
    "How-do-you-stop-the-pain-of-heartbreak",
    "Why-does-heartbreak-hurt-so-much",
    "What-does-it-feel-like-to-lose-someone-you-love",

    # One-sided love / giving too much
    "What-does-it-feel-like-to-love-someone-more-than-they-love-you",
    "How-do-you-deal-with-unrequited-love",
    "What-is-it-like-to-always-love-more-than-you-are-loved",
    "How-do-you-know-if-your-relationship-is-one-sided",
    "What-does-it-feel-like-to-give-everything-in-a-relationship",
    "How-do-you-stop-loving-someone-who-doesnt-love-you-back",
    "What-does-it-feel-like-to-love-someone-who-does-not-love-you-back",
    "Why-do-I-always-love-more-than-I-am-loved",
    "What-is-a-one-sided-relationship-like",
    "How-do-you-handle-being-in-a-one-sided-relationship",
    "What-does-it-mean-when-a-relationship-is-one-sided",

    # Being used / taken advantage of
    "What-does-it-feel-like-to-be-used-in-a-relationship",
    "How-do-you-know-if-someone-is-using-you-in-a-relationship",
    "What-is-it-like-to-realize-you-were-being-used",
    "How-do-you-recover-from-being-emotionally-manipulated",
    "What-does-it-feel-like-to-be-emotionally-manipulated",
    "How-do-you-know-if-you-are-being-manipulated-in-a-relationship",
    "What-does-it-feel-like-to-be-taken-for-granted",
    "How-do-you-deal-with-being-taken-for-granted-in-a-relationship",

    # Losing yourself in a relationship
    "What-does-it-feel-like-to-lose-yourself-in-a-relationship",
    "How-do-you-find-yourself-again-after-a-relationship",
    "What-does-it-mean-to-lose-your-identity-in-a-relationship",
    "How-do-you-stop-losing-yourself-in-relationships",
    "Why-do-people-lose-themselves-in-relationships",

    # Divorce / rebuilding
    "How-do-men-emotionally-recover-from-divorce",
    "What-is-it-like-to-rebuild-after-a-divorce",
    "How-do-you-start-dating-again-after-a-divorce",
    "What-does-it-feel-like-to-go-through-a-divorce",
    "What-is-the-hardest-part-of-going-through-a-divorce",
    "How-do-you-move-on-after-a-divorce",
    "What-does-life-feel-like-after-divorce",
    "How-do-divorced-men-feel-about-dating-again",
    "What-is-dating-after-divorce-like-for-men",
    "Is-it-worth-getting-married-again-after-a-divorce",
    "Why-do-men-not-want-to-remarry-after-divorce",

    # Loneliness after relationships
    "How-do-men-deal-with-loneliness-after-a-breakup",
    "What-is-it-like-to-be-alone-after-a-long-relationship",
    "How-do-you-cope-with-loneliness-after-a-relationship",
    "What-does-loneliness-feel-like-after-a-breakup",
    "Why-do-I-feel-so-alone-after-my-breakup",
    "Is-it-better-to-be-alone-than-in-a-bad-relationship",
    "How-do-you-get-used-to-being-alone-after-a-relationship",
    "Why-do-I-feel-more-lonely-in-a-relationship-than-alone",

    # Emotional drainage / exhaustion
    "How-do-you-know-if-a-relationship-is-draining-you",
    "What-does-it-feel-like-to-be-emotionally-drained-by-a-relationship",
    "How-do-you-recover-from-an-emotionally-exhausting-relationship",
    "What-are-the-signs-you-are-emotionally-drained-in-a-relationship",

    # Men and emotions
    "Why-do-men-find-it-hard-to-express-emotions",
    "How-do-men-deal-with-emotional-pain",
    "Why-do-men-bottle-up-their-feelings",
    "What-do-men-feel-after-a-breakup",
    "Do-men-grieve-relationships-differently-than-women",
    "Why-dont-men-talk-about-their-feelings-after-a-breakup",
    "How-do-men-cope-with-heartbreak",
    "How-long-does-it-take-for-a-man-to-get-over-a-breakup",
    "Why-are-breakups-harder-for-men",

    # Nice guy / giving too much
    "What-is-nice-guy-syndrome-and-why-is-it-harmful",
    "How-do-you-stop-being-a-pushover-in-relationships",
    "Why-do-nice-guys-get-taken-advantage-of-in-relationships",
    "What-does-it-mean-to-be-a-nice-guy-in-a-bad-way",
    "How-do-I-stop-putting-everyone-else-first-in-relationships",

    # Sworn off / resigned
    "Is-it-possible-to-be-happy-without-a-romantic-relationship",
    "Why-do-some-people-choose-to-stay-single-forever",
    "Is-it-worth-being-in-a-relationship",
    "Are-relationships-worth-the-pain",
    "Why-do-relationships-cause-so-much-pain",
    "Is-love-really-worth-it",

    # General relationship disappointment
    "What-does-it-feel-like-when-a-relationship-ends-badly",
    "How-do-you-deal-with-a-painful-breakup",
    "What-is-the-worst-part-of-a-bad-breakup",
    "How-do-you-get-over-someone-who-broke-your-heart",
    "What-makes-some-breakups-so-devastating",
    "How-do-you-stop-thinking-about-someone-who-hurt-you",

    # Additional male-specific slugs
    "What-is-it-like-for-a-man-to-be-cheated-on",
    "How-does-a-man-feel-when-his-girlfriend-cheats",
    "Why-do-men-shut-down-emotionally-after-heartbreak",
    "How-do-men-process-grief-after-a-relationship",
    "What-does-it-feel-like-to-be-a-man-who-lost-everything-in-a-divorce",
    "Why-do-some-men-give-up-on-women-after-a-bad-relationship",
    "What-happens-to-a-man-emotionally-after-being-cheated-on",
    "Why-do-men-become-cold-after-being-hurt-in-a-relationship",
    "What-does-it-mean-when-a-man-says-he-is-done-with-relationships",
    "How-do-men-feel-after-being-used-in-a-relationship",
    "What-is-it-like-to-give-everything-to-a-woman-and-get-nothing-back",
    "Why-do-men-become-emotionally-unavailable-after-heartbreak",
    "How-do-you-rebuild-yourself-after-a-toxic-relationship",
    "What-does-betrayal-feel-like-for-a-man",
    "How-do-men-deal-with-being-abandoned-by-someone-they-love",
]


# ── Login wall / paywalled page markers ──────────────────────────────────────
QUORA_LOGIN_MARKERS = [
    "Be part of the conversation",
    "Sign In to Quora",
    "Log In to Quora",
    "Sign Up to see all",
    "Sign up with email",
    "to read all answers",
    "Access more answers by",
    "to continue reading",
    "Read all answers",
    "Get 1 free unlock",
]


def page_has_answers(body_text: str) -> bool:
    """Return True only if the page appears to contain actual answer content."""
    if len(body_text) < 600:
        return False
    for marker in QUORA_LOGIN_MARKERS:
        if marker in body_text[:2000]:
            return False
    # Must contain at least one personal-narrative indicator
    personal = [
        "I was", "I had", "I went", "I felt", "I gave", "I loved",
        "I trusted", "I dated", "I used to", "I realized", "I went through",
        "she cheated", "she left", "my ex", "my girlfriend", "my wife",
        "after the divorce", "after the breakup", "we broke up",
    ]
    t = body_text.lower()
    return sum(1 for p in personal if p.lower() in t) >= 2


def extract_answers(page, url: str) -> list[str]:
    """Visit a Quora question page and return list of answer text blocks."""
    # Try ?share=1 which sometimes bypasses the login gate
    share_url = url if "?" in url else url + "?share=1"
    for attempt_url in [share_url, url]:
        try:
            page.goto(attempt_url, wait_until="domcontentloaded", timeout=20000)
            time.sleep(2.5)

            body_text = page.inner_text("body", timeout=15000)

            if not page_has_answers(body_text):
                continue

            # Split into paragraph blocks
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


# ── Comprehensive female filter ───────────────────────────────────────────────
_FEMALE_RE = re.compile(
    r'\b\d{1,2}\s*f\b'           # "22f", "22 f"
    r'|\(f\)'                    # (f)
    r'|\[f\]'                    # [f]
    r'|\bi\s+\(f\b'              # i (f
    r'|\bshe/her\b'
    r'|\bher/she\b',
    re.IGNORECASE,
)

_FEMALE_PHRASES = [
    # explicit self-identification
    "i'm a woman", "i am a woman", "as a woman", "as a girl",
    "i'm female", "i am female", "woman here", "female here",
    "i'm a girl", "i am a girl", "i, as a woman", "i as a woman",
    # relational signals (she is the protagonist)
    "my husband", "my ex-husband", "my boyfriend cheated", "my partner cheated",
    "us women", "we women", "as wives", "as a wife",
    # biological female signals
    "i was pregnant", "i'm pregnant", "4 months pregnant", "months pregnant",
    "during my pregnancy",
    # female-coded appearance/behaviour
    "wearing make up", "wearing makeup", "putting on makeup", "my mascara",
    "my eyeliner", "my lipstick", "i do my nails", "my nail polish",
    "wore a dress", "my handbag", "my purse",
    # age + gender combo
    "year old girl", "year-old girl", "year old woman", "year-old woman",
    # typical female relationship framing
    "my ex-boyfriend", "my ex boyfriend",
]


def is_female_answer(text: str) -> bool:
    t = text.lower()
    if _FEMALE_RE.search(text[:500]):
        return True
    return any(phrase in t for phrase in _FEMALE_PHRASES)


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
        "i loved her", "i gave her", "i sacrificed", "i trusted her",
        "she was using me", "she only wanted", "she left when",
        "after she cheated", "after she left", "my girlfriend left",
        "after my divorce", "been hurt before", "been burned",
        "swore off", "stopped trying", "stopped caring",
    ]
    return any(s in t for s in signals)


def score_answer(text: str) -> tuple[int, str]:
    t = text.lower()
    score = 0

    # Strong male signals (+2 each)
    male_strong = [
        "i'm a man", "i am a man", "as a man", "i'm a guy", "as a guy",
        "my girlfriend", "my ex-girlfriend", "my ex-wife", "i dated a girl",
        "i dated a woman", "she cheated on me", "she left me", "my wife left",
        "my divorce", "i married her", "i proposed", "she was my girlfriend",
        "my ex left", "she broke up with me", "she ended it",
    ]
    score += sum(2 for s in male_strong if s in t)

    # Softer male signals (+1 each)
    soft_male = [
        "she said", "she wasn't", "her ex", "she only",
        "she didn't", "dated a woman", "met a girl", "she was",
        "she told me", "she never", "she always", "she kept",
        "she made me", "she would",
    ]
    score += sum(1 for s in soft_male if s in t)

    # Personal narrative signals (+2 each)
    personal = [
        "i used to", "i was in a relationship", "i realized", "i struggled",
        "i gave", "i loved her", "i trusted", "i thought we",
        "i put her first", "i sacrificed", "i gave everything",
        "my experience", "my story", "after my divorce", "after my breakup",
        "after she left", "after she cheated", "i went through",
        "this happened to me", "i can speak from experience",
        "let me tell you", "i'll share my experience",
    ]
    score += sum(2 for s in personal if s in t)

    # Disappointment / damage signals (+2 each)
    disappointment = [
        "gave everything", "gave my all", "one-sided", "she cheated",
        "she used me", "abandoned", "betrayed", "drained me",
        "destroyed me", "broke me", "trust issues", "walls up",
        "afraid to love", "never again", "sworn off", "better off alone",
        "given up", "don't trust", "can't trust", "stopped caring",
        "stopped trying", "swore off relationships", "never want to",
        "done with dating", "done with women", "done with relationships",
    ]
    score += sum(2 for s in disappointment if s in t)

    # Length bonus
    if len(text) > 300:  score += 1
    if len(text) > 700:  score += 1
    if len(text) > 1200: score += 2

    # Determine segment
    segment = "General / Disappointed in Love"
    if any(s in t for s in ["cheated", "infidelity", "unfaithful", "betrayed", "she lied"]):
        segment = "Betrayed / Cheated On"
    elif any(s in t for s in ["divorce", "married", "marriage", "ex-wife", "after my divorce"]):
        segment = "Post-Divorce Rebuilder"
    elif any(s in t for s in ["gave everything", "one-sided", "not reciprocated", "gave my all"]):
        segment = "One-Sided Giver / Depleted"
    elif any(s in t for s in ["drained", "lost myself", "became a shell", "emotionally exhausted"]):
        segment = "Emotionally Drained / Lost Self"
    elif any(s in t for s in ["done with", "sworn off", "never again", "given up", "swore off"]):
        segment = "Resigned / Sworn Off Love"
    elif any(s in t for s in ["can't trust", "walls up", "afraid to love", "numb", "closed off"]):
        segment = "Guarded / Can't Trust Again"
    elif any(s in t for s in ["used me", "she only wanted", "taken advantage", "she was using"]):
        segment = "Used / Taken Advantage Of"

    return score, segment


def main():
    records = []
    seen_texts: set[str] = set()

    # Load existing results to avoid duplicates
    if os.path.exists(OUTPUT_FILE):
        existing = pd.read_csv(OUTPUT_FILE)
        for t in existing.get("answer_text", []):
            seen_texts.add(str(t)[:80])
        print(f"Loaded {len(existing)} existing answers from {os.path.basename(OUTPUT_FILE)}", flush=True)
        records = existing.to_dict("records")

    valid_urls = []

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
        page = ctx.new_page()

        # ── Phase 1: test candidates to find valid URLs ───────────────────────
        print(f"\nPhase 1: Testing {len(CANDIDATE_SLUGS)} question slugs...\n", flush=True)
        for i, slug in enumerate(CANDIDATE_SLUGS):
            url = f"https://www.quora.com/{slug}"
            try:
                page.goto(url + "?share=1", wait_until="domcontentloaded", timeout=15000)
                time.sleep(2)
                body = page.inner_text("body")
                title = page.title()
                if page_has_answers(body) and len(body) > 1000:
                    valid_urls.append((title, url))
                    print(f"  ✓ [{i+1}/{len(CANDIDATE_SLUGS)}] {slug[:60]}", flush=True)
                else:
                    if (i + 1) % 10 == 0:
                        print(f"  ... [{i+1}/{len(CANDIDATE_SLUGS)}] tested, {len(valid_urls)} valid so far", flush=True)
            except Exception:
                pass
            time.sleep(1.2)

        print(f"\n✓ Found {len(valid_urls)} valid question pages.\n", flush=True)

        # ── Phase 2: scrape each valid question for answers ───────────────────
        print("Phase 2: Extracting answers...\n", flush=True)
        for i, (title, url) in enumerate(valid_urls):
            print(f"[{i+1}/{len(valid_urls)}] {title[:70]}", flush=True)
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
            print(f"  → {len(answers)} blocks, {kept} kept", flush=True)
            time.sleep(1.5)

        browser.close()

    if not records:
        print("\nNo relevant answers found.", flush=True)
        return

    df = pd.DataFrame(records)
    df.drop_duplicates(subset="answer_text", inplace=True)
    df.sort_values("relevance_score", ascending=False, inplace=True)
    df.reset_index(drop=True, inplace=True)
    df.to_csv(OUTPUT_FILE, index=False, encoding="utf-8-sig")

    print(f"\n{'='*60}")
    print(f"✓ Saved {len(df)} answers to quora_answers.csv")
    print(f"\nSegment distribution:")
    print(df["segment_tag"].value_counts().to_string())
    print(f"\nTop 10 by relevance:")
    for _, row in df.head(10).iterrows():
        print(f"\n  [score {row.relevance_score}] {row.question_title[:65]}")
        print(f"  {row.answer_text[:180]}")


if __name__ == "__main__":
    main()
