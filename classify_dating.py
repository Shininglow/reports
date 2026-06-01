import pandas as pd
import re

INPUT_FILE = "male_dating_filtered.csv"
CLASSIFIED_FILE = "male_dating_classified.csv"
FINAL_FILE = "male_dating_final.csv"
SCORE_THRESHOLD = 0.4

WEIGHTED_PATTERNS = [
    # Core signals — highest weight
    (r"\bcan.t find.{0,20}girlfriend\b",            1.0),
    (r"\bnever had.{0,20}girlfriend\b",             1.0),
    (r"\bnever been in.{0,20}relationship\b",       1.0),
    (r"\bnever dated\b",                            1.0),
    (r"\bforever alone\b",                          0.9),
    (r"\bforever single\b",                         0.9),
    (r"\bdie alone\b",                              0.9),
    (r"\balone forever\b",                          0.9),
    (r"\bunlovable\b",                              0.9),
    (r"\bundesirable\b",                            0.9),
    (r"\bno woman.{0,20}want(s)? me\b",             0.9),
    (r"\bno one wants me\b",                        0.9),
    (r"\bcan.t get.{0,15}(date|girl|woman)\b",      0.9),
    (r"\bgetting rejected\b",                       0.8),
    (r"\brejected by women\b",                      0.8),
    (r"\bno girlfriend\b",                          0.8),
    (r"\balways single\b",                          0.8),
    (r"\bno matches\b",                             0.7),

    # Dating struggle signals — medium-high weight
    (r"\bdating.{0,20}(impossible|hopeless|broken|rigged)\b", 0.8),
    (r"\b(impossible|hopeless).{0,20}dating\b",     0.8),
    (r"\btinder.{0,20}(no matches|hopeless|useless|broken|depressing)\b", 0.7),
    (r"\bdating app.{0,20}(hopeless|depressing|useless|broken)\b", 0.7),
    (r"\bmen.{0,20}dating (struggle|hard|difficult)\b", 0.7),
    (r"\b(struggle|struggling).{0,20}(to date|with dating|to find)\b", 0.7),
    (r"\bcan.t attract\b",                          0.7),
    (r"\blow value man\b",                          0.7),
    (r"\bblackpill\b",                              0.6),
    (r"\bincel\b",                                  0.6),

    # Loneliness + single context
    (r"\bsingle.{0,20}lonely\b",                   0.6),
    (r"\blonely.{0,20}single\b",                   0.6),
    (r"\bsingle man\b",                             0.5),
    (r"\bsingle men\b",                             0.5),
    (r"\bno dates\b",                               0.6),
    (r"\bnobody wants\b",                           0.6),
    (r"\bnever asked out\b",                        0.7),
    (r"\bnever been kissed\b",                      0.7),
    (r"\bvirgin.{0,20}(lonely|sad|embarrass|ashamed)\b", 0.7),
    (r"\b(25|26|27|28|29|30|31|32|33|34|35).{0,10}(never|no).{0,10}(girlfriend|relationship|dated)\b", 0.8),

    # Broader related signals — lower weight
    (r"\bdating\b",                                 0.2),
    (r"\brelationship\b",                           0.1),
    (r"\blonely\b",                                 0.2),
    (r"\bloneliness\b",                             0.2),
]

PENALTY_PATTERNS = [
    r"\bmy girlfriend\b",
    r"\bmy wife\b",
    r"\bmy husband\b",
    r"\bmy boyfriend\b",
    r"\bI.m a woman\b",
    r"\bas a woman\b",
    r"\bI.m female\b",
    r"\bI.m a girl\b",
    r"\bI \(F\b",
    r"\b\d+F\b",
    r"\bpregnant\b",
    r"\bdivorce\b",
    r"\bcheating\b",
    r"\bwedding\b",
    r"\bmod post\b",
    r"\bdisinformation\b",
]


def score_post(row) -> float:
    text = f"{row['title']} {str(row['post_body'] or '')}".lower()

    if any(re.search(p, text, re.IGNORECASE) for p in PENALTY_PATTERNS):
        return 0.0

    raw_score = 0.0
    for pattern, weight in WEIGHTED_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            raw_score += weight

    normalized = min(raw_score / 2.5, 1.0)
    upvote_boost = min(row["score"] / 100000, 0.05)
    return round(min(normalized + upvote_boost, 1.0), 3)


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

    print("\nTop 20 by relevance score:")
    for _, row in final.head(20).iterrows():
        print(f"  [{row['relevance_score']:.2f}] r/{row['subreddit']:<20} {row['title'][:65]}")

    print(f"\nScore distribution:")
    bins = [0.0, 0.2, 0.4, 0.6, 0.8, 1.01]
    labels = ["0.0–0.2", "0.2–0.4", "0.4–0.6", "0.6–0.8", "0.8–1.0"]
    df["band"] = pd.cut(df["relevance_score"], bins=bins, labels=labels, right=False)
    print(df["band"].value_counts().sort_index().to_string())


if __name__ == "__main__":
    main()
