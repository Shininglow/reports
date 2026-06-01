import pandas as pd
import re

INPUT_FILE = "male_loneliness_threads.csv"
OUTPUT_FILE = "male_loneliness_filtered.csv"

# Title/body must contain at least one of these to pass
MUST_MATCH = [
    r"\blonely\b",
    r"\bloneliness\b",
    r"\balone\b",
    r"\bisolat",
    r"\bno friends\b",
    r"\bno one to talk\b",
    r"\bno one cares\b",
    r"\bfeel invisible\b",
    r"\bsocially isolated\b",
    r"\bfriend group\b",
    r"\bmale connection\b",
    r"\bmen.{0,20}friend",
]

# If title/body contains these it's probably not about loneliness
NOISE_PATTERNS = [
    r"\bpregnant\b",
    r"\bdisinformation\b",
    r"\bweight loss\b",
    r"\bLuigi\b",
    r"\bwedding\b",
    r"\bdivorce\b",
    r"\bcheating\b",
]

def is_relevant(row):
    text = f"{row['title']} {row['post_body']}".lower()
    has_signal = any(re.search(p, text, re.IGNORECASE) for p in MUST_MATCH)
    is_noise = any(re.search(p, text, re.IGNORECASE) for p in NOISE_PATTERNS)
    return has_signal and not is_noise

df = pd.read_csv(INPUT_FILE)
print(f"Raw posts: {len(df)}")

df["relevant"] = df.apply(is_relevant, axis=1)
filtered = df[df["relevant"]].drop(columns=["relevant"]).reset_index(drop=True)

print(f"Filtered posts: {len(filtered)}")
filtered.to_csv(OUTPUT_FILE, index=False, encoding="utf-8-sig")
print(f"Saved to '{OUTPUT_FILE}'")

print("\nTop 10 by score:")
for _, row in filtered.head(10).iterrows():
    print(f"  [{row['score']:>5}] r/{row['subreddit']:<20} {row['title'][:70]}")
