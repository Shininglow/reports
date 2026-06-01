import pandas as pd
import re

INPUT_FILE = "male_loneliness_filtered.csv"
CLASSIFIED_FILE = "male_loneliness_classified.csv"
FINAL_FILE = "male_loneliness_final.csv"
SCORE_THRESHOLD = 0.5

# Each pattern carries a weight (higher = stronger signal of male loneliness)
WEIGHTED_PATTERNS = [
    # Core loneliness signals — high weight
    (r"\bmale loneliness\b",            1.0),
    (r"\bmen.{0,10}lonely\b",           1.0),
    (r"\bman.{0,10}lonely\b",           1.0),
    (r"\blonely man\b",                 0.9),
    (r"\blonely men\b",                 0.9),
    (r"\bmale isolation\b",             0.9),
    (r"\bsocially isolated\b",          0.8),
    (r"\bno male friends\b",            0.9),
    (r"\bcan.t make friends\b",         0.8),
    (r"\bno friends\b",                 0.7),
    (r"\bfeel invisible\b",             0.7),
    (r"\bno one to talk\b",             0.7),
    (r"\bno one cares\b",               0.7),
    (r"\bemotionally alone\b",          0.8),
    (r"\bemotional connection\b",       0.6),
    (r"\bdeep loneliness\b",            0.9),
    (r"\bchronic loneliness\b",         0.9),
    (r"\bloneliness epidemic\b",        0.9),

    # General loneliness — medium weight
    (r"\blonely\b",                     0.5),
    (r"\bloneliness\b",                 0.5),
    (r"\bisolat(ed|ion)\b",             0.4),
    (r"\balone\b",                      0.3),

    # Male friendship / connection context — medium weight
    (r"\bmale.{0,15}friend",            0.6),
    (r"\bmen.{0,15}friend",             0.6),
    (r"\bman.{0,15}friend",             0.6),
    (r"\bfriend group\b",               0.4),
    (r"\bmale connection\b",            0.7),
    (r"\bmen.{0,15}connect",            0.6),
    (r"\bbromance\b",                   0.5),
    (r"\bmen don.t",                    0.5),
    (r"\bguys don.t",                   0.5),

    # Gendered suffering signals
    (r"\bmen suffer\b",                 0.6),
    (r"\bmen struggle\b",               0.6),
    (r"\bmen.{0,20}mental health\b",    0.6),
    (r"\bmen.{0,20}depress",            0.5),
    (r"\bmen.{0,20}suicid",             0.7),
    (r"\bforever alone\b",              0.7),
    (r"\bno girlfriend\b",              0.4),
    (r"\bno relationship\b",            0.3),
]

# Posts matching any of these get a strong score penalty
PENALTY_PATTERNS = [
    r"\bpregnant\b",
    r"\bweight loss\b",
    r"\bdisinformation\b",
    r"\bwedding\b",
    r"\bcheating\b",
    r"\bdivorce\b",
    r"\bLuigi\b",
]

# Posts explicitly about a woman's experience get penalized
FEMALE_FOCUS = [
    r"\bI.m a woman\b",
    r"\bas a woman\b",
    r"\bI.m female\b",
    r"\bmy husband\b",
    r"\bmy boyfriend\b",
    r"\bmy son\b",
]


def score_post(row) -> float:
    text = f"{row['title']} {str(row['post_body'] or '')}".lower()

    # Penalty patterns — strong down-weight
    if any(re.search(p, text, re.IGNORECASE) for p in PENALTY_PATTERNS):
        return 0.0

    # Female-focus penalty (halve the score)
    female_penalty = 0.5 if any(re.search(p, text, re.IGNORECASE) for p in FEMALE_FOCUS) else 1.0

    # Accumulate weighted keyword matches (cap each pattern at 1 hit)
    raw_score = 0.0
    for pattern, weight in WEIGHTED_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            raw_score += weight

    # Normalize to 0–1 range (max possible raw is ~15+, so cap at 3.0 → 1.0)
    normalized = min(raw_score / 3.0, 1.0)

    # Small upvote boost (more upvotes = more resonance with community)
    upvote_boost = min(row["score"] / 50000, 0.1)

    return round(min(normalized + upvote_boost, 1.0) * female_penalty, 3)


def main():
    df = pd.read_csv(INPUT_FILE)
    print(f"Loaded {len(df)} posts from '{INPUT_FILE}'")

    df["relevance_score"] = df.apply(score_post, axis=1)
    df.sort_values("relevance_score", ascending=False, inplace=True)
    df.reset_index(drop=True, inplace=True)

    df.to_csv(CLASSIFIED_FILE, index=False, encoding="utf-8-sig")
    print(f"Saved all {len(df)} scored posts to '{CLASSIFIED_FILE}'")

    final = df[df["relevance_score"] >= SCORE_THRESHOLD].reset_index(drop=True)
    final.to_csv(FINAL_FILE, index=False, encoding="utf-8-sig")
    print(f"Saved {len(final)} high-relevance posts (score >= {SCORE_THRESHOLD}) to '{FINAL_FILE}'")

    print("\nTop 15 by relevance score:")
    for _, row in final.head(15).iterrows():
        print(f"  [{row['relevance_score']:.2f}] r/{row['subreddit']:<20} {row['title'][:65]}")

    print(f"\nScore distribution:")
    bins = [0.0, 0.2, 0.4, 0.6, 0.8, 1.01]
    labels = ["0.0–0.2", "0.2–0.4", "0.4–0.6", "0.6–0.8", "0.8–1.0"]
    df["band"] = pd.cut(df["relevance_score"], bins=bins, labels=labels, right=False)
    print(df["band"].value_counts().sort_index().to_string())


if __name__ == "__main__":
    main()
