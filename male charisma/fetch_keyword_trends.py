"""
Fetch Google Trends data for all High Value Man keywords.
Uses pytrends (no API key needed).
Outputs: keyword_trends.csv with interest scores, trend direction, peak month.
"""

# Fix urllib3 v2 compatibility (method_whitelist → allowed_methods)
import urllib3.util.retry as _retry_mod
_orig_retry_init = _retry_mod.Retry.__init__
def _compat_retry_init(self, *args, method_whitelist=None, allowed_methods=None, **kwargs):
    if method_whitelist is not None and allowed_methods is None:
        allowed_methods = method_whitelist
    _orig_retry_init(self, *args, allowed_methods=allowed_methods, **kwargs)
_retry_mod.Retry.__init__ = _compat_retry_init

import time
import pandas as pd
from datetime import datetime, timedelta
from pytrends.request import TrendReq

# ── Keywords by cluster — broader terms with proven search demand ─────────────
CLUSTERS = {
    "Identity & Archetypes": [
        "high value man",
        "alpha male",
        "sigma male",
        "how to be an alpha male",
        "alpha male traits",
        "beta male",
        "what is alpha male",
        "sigma male meaning",
        "high value man traits",
    ],
    "Charisma & Confidence": [
        "how to be more confident",
        "how to build confidence",
        "how to be more charismatic",
        "how to be charming",
        "how to talk to people",
        "how to be more likeable",
        "self confidence tips",
        "how to be outgoing",
        "social confidence",
    ],
    "Mindset & Discipline": [
        "stoicism",
        "stoic philosophy",
        "how to be disciplined",
        "growth mindset",
        "how to stop caring what people think",
        "mental toughness",
        "how to be more motivated",
        "morning routine",
        "discipline habits",
    ],
    "Status & Success": [
        "financial independence",
        "how to be successful",
        "how to build wealth",
        "how to make more money",
        "passive income",
        "how to find your purpose",
        "how to be productive",
        "success mindset",
        "how to level up in life",
    ],
    "Social Dynamics": [
        "how to be more assertive",
        "how to set boundaries",
        "how to be a better leader",
        "how to gain respect",
        "leadership skills",
        "how to network",
        "how to be more dominant",
        "how to command respect",
        "social skills",
    ],
    "Physical Presence": [
        "body language tips",
        "how to look more attractive men",
        "men's grooming tips",
        "men's style tips",
        "how to dress well men",
        "how to improve posture",
        "how to look more masculine",
        "eye contact attraction",
        "how to be physically attractive",
    ],
    "Attraction & Dating": [
        "how to attract women",
        "dating advice for men",
        "what women find attractive in men",
        "how to talk to women",
        "dating tips for men",
        "how to get a girlfriend",
        "how to be more attractive to women",
        "red pill dating",
        "masculine energy attraction",
    ],
    "Self-Improvement": [
        "self improvement",
        "how to improve yourself",
        "personal development",
        "how to be a better man",
        "how to be the best version of yourself",
        "self help for men",
        "how to reinvent yourself",
        "how to change your life",
        "men self improvement",
    ],
    "Masculinity & Culture": [
        "masculinity",
        "toxic masculinity",
        "modern masculinity",
        "red pill",
        "what is masculinity",
        "how to be more masculine",
        "masculine men",
        "masculinity crisis",
        "Andrew Tate",
    ],
}

# ── Helpers ───────────────────────────────────────────────────────────────────

def chunks(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i:i+n]

def trend_direction(series: pd.Series) -> str:
    """Compare first-quarter avg vs last-quarter avg."""
    if len(series) < 6:
        return "Insufficient data"
    first = series.iloc[:3].mean()
    last  = series.iloc[-3:].mean()
    if first == 0 and last == 0:
        return "No data"
    if first == 0:
        return "Rising"
    pct = (last - first) / (first + 1) * 100
    if pct > 25:
        return "Rising"
    if pct < -25:
        return "Declining"
    return "Stable"

def classify_volume(avg_score: float) -> str:
    """Estimate search volume tier from Google Trends 0-100 score."""
    if avg_score >= 60:  return "High (>10k/mo)"
    if avg_score >= 35:  return "Medium (1k-10k/mo)"
    if avg_score >= 12:  return "Low (100-1k/mo)"
    if avg_score > 0:    return "Very low (<100/mo)"
    return "No data"

def trend_emoji(direction: str) -> str:
    return {"Rising": "↑ Rising", "Declining": "↓ Declining",
            "Stable": "→ Stable"}.get(direction, "— N/A")

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    pytrends = TrendReq(hl="en-US", tz=360, timeout=(10, 25),
                        retries=3, backoff_factor=0.5)

    timeframe = "today 12-m"
    geo       = "US"

    all_kws = []
    for cluster, kws in CLUSTERS.items():
        for kw in kws:
            all_kws.append((cluster, kw))

    # Fetch each keyword individually — scores become self-relative (0-100 vs own peak).
    # Batching multiple keywords normalizes them against each other, crushing lower-volume
    # terms to near-zero even when they have real search demand.
    print(f"Fetching Google Trends for {len(all_kws)} keywords (1 per request)...")

    rows = []

    for i, (cluster, kw) in enumerate(all_kws):
        print(f"  [{i+1}/{len(all_kws)}] {kw}", flush=True)
        series = None
        try:
            pytrends.build_payload([kw], cat=0, timeframe=timeframe, geo=geo)
            iot = pytrends.interest_over_time()
            time.sleep(4)
            if not iot.empty and kw in iot.columns:
                series = iot[kw]
        except Exception as e:
            print(f"    Error: {e}")
            time.sleep(12)

        if series is None or (hasattr(series, 'sum') and series.sum() == 0):
            rows.append({
                "cluster":         cluster,
                "keyword":         kw,
                "avg_interest":    0,
                "peak_interest":   0,
                "peak_month":      "—",
                "trend_direction": "No data",
                "est_volume":      "No data",
                "is_trending":     "No",
            })
            continue

        avg   = round(series.mean(), 1)
        peak  = int(series.max())
        pidx  = series.idxmax()
        pmth  = pidx.strftime("%b %Y") if hasattr(pidx, "strftime") else str(pidx)
        direc = trend_direction(series)

        rows.append({
            "cluster":         cluster,
            "keyword":         kw,
            "avg_interest":    avg,
            "peak_interest":   peak,
            "peak_month":      pmth,
            "trend_direction": direc,
            "est_volume":      classify_volume(avg),
            "is_trending":     "Yes" if direc == "Rising" else "No",
        })

    df = pd.DataFrame(rows)
    df.sort_values(["cluster", "avg_interest"], ascending=[True, False], inplace=True)
    df.to_csv("keyword_trends.csv", index=False, encoding="utf-8-sig")

    print(f"\n✓ Saved {len(df)} keywords → keyword_trends.csv")
    print(f"\nTrend summary:")
    print(df["trend_direction"].value_counts().to_string())
    print(f"\nTop 15 by avg interest:")
    print(df[["keyword","cluster","avg_interest","trend_direction","est_volume"]]
          .head(15).to_string(index=False))


if __name__ == "__main__":
    main()
