import pandas as pd
import re

INPUT_FILE = "male_dating_threads.csv"
OUTPUT_FILE = "male_dating_filtered.csv"

MUST_MATCH = [
    r"\bcan.t find.{0,20}girlfriend\b",
    r"\bnever had.{0,20}girlfriend\b",
    r"\bno girlfriend\b",
    r"\balways single\b",
    r"\bforever alone\b",
    r"\bforever single\b",
    r"\bdating.{0,20}(struggle|hard|difficult|hopeless|impossible)\b",
    r"\b(struggle|struggling).{0,20}dating\b",
    r"\bcan.t date\b",
    r"\bcan.t get.{0,15}(date|girl|woman)\b",
    r"\bno woman.{0,20}want\b",
    r"\bwomen.{0,20}don.t want\b",
    r"\bunlovable\b",
    r"\bundesirable\b",
    r"\bno one wants me\b",
    r"\bdie alone\b",
    r"\balone forever\b",
    r"\bnever been in.{0,20}relationship\b",
    r"\bnever dated\b",
    r"\bcan.t get.{0,10}laid\b",
    r"\bincel\b",
    r"\bblackpill\b",
    r"\blow value man\b",
    r"\bsingle.{0,20}lonely\b",
    r"\blonely.{0,20}single\b",
    r"\bno dates\b",
    r"\bgetting rejected\b",
    r"\brejected by women\b",
    r"\bdating app.{0,20}(hopeless|depressing|useless|broken)\b",
    r"\btinder.{0,20}(hopeless|no matches|useless|broken)\b",
    r"\bno matches\b",
    r"\b(25|26|27|28|29|30|31|32|33|34|35).{0,10}(never|no).{0,10}(girlfriend|relationship|dated)\b",
]

NOISE_PATTERNS = [
    r"\bpregnant\b",
    r"\bdisinformation\b",
    r"\bdivorce\b",
    r"\bcheating\b",
    r"\bweight loss\b",
    r"\bmy (ex-)?wife\b",
    r"\bmy husband\b",
    r"\bI.m a woman\b",
    r"\bas a woman\b",
    r"\bI.m female\b",
    r"\bI.m a girl\b",
    r"\bI \(F\b",        # "I (F25)" style
    r"\b\d+F\b",         # "25F" style
]


def is_relevant(row):
    text = f"{row['title']} {str(row['post_body'] or '')}".lower()
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
