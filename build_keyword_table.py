"""
Read keyword_trends.csv → generate keyword_trends_table.html
Interactive table: sortable, filterable by cluster, color-coded by volume.
"""
import pandas as pd, json, sys
from pathlib import Path

CSV = "keyword_trends.csv"
OUT = "keyword_trends_table.html"

if not Path(CSV).exists():
    print(f"CSV not found: {CSV}")
    sys.exit(1)

df = pd.read_csv(CSV)

CLUSTER_COLORS = {
    "Identity & Archetypes":   "#F59E0B",
    "Charisma & Confidence":   "#6366F1",
    "Mindset & Discipline":    "#8B5CF6",
    "Status & Success":        "#10B981",
    "Social Dynamics":         "#3B82F6",
    "Physical Presence":       "#EF4444",
    "Attraction & Dating":     "#EC4899",
    "Self-Improvement":        "#06B6D4",
    "Masculinity & Culture":   "#F97316",
}

def msv_bar(msv_val, avg_interest, est_volume):
    """Visual bar + volume label. Uses msv_monthly if present, else avg_interest as proxy."""
    try:
        msv = int(float(msv_val))
        pct = min(100, int(msv / 5500))   # 550K → 100%
        label = est_volume
    except (ValueError, TypeError):
        pct = min(100, int(float(avg_interest)))
        label = str(est_volume)
    return (
        f'<div class="bar-wrap">'
        f'<div class="bar" style="width:{pct}%;background:var(--clr)"></div>'
        f'<span class="bar-val">{label}</span>'
        f'</div>'
    )

def trend_badge(direction):
    maps = {
        "Rising":    ('<span class="badge badge-up">↑ Rising</span>',   1),
        "Stable":    ('<span class="badge badge-st">→ Stable</span>',   2),
        "Declining": ('<span class="badge badge-dn">↓ Declining</span>',3),
    }
    return maps.get(str(direction).strip(), ('<span class="badge badge-na">— N/A</span>', 4))

def volume_tier(msv_val, est_volume_val):
    """Color tier badge based on actual MSV."""
    try:
        msv = int(float(msv_val))
        if msv >= 100_000: return f'<span class="vol vol-xl">{est_volume_val}</span>'
        if msv >= 20_000:  return f'<span class="vol vol-h">{est_volume_val}</span>'
        if msv >= 5_000:   return f'<span class="vol vol-m">{est_volume_val}</span>'
        if msv >= 1_000:   return f'<span class="vol vol-l">{est_volume_val}</span>'
        return f'<span class="vol vol-vl">{est_volume_val}</span>'
    except (ValueError, TypeError):
        v = str(est_volume_val)
        if "High"     in v: return f'<span class="vol vol-h">{v}</span>'
        if "Medium"   in v: return f'<span class="vol vol-m">{v}</span>'
        if "Low"      in v: return f'<span class="vol vol-l">{v}</span>'
        return f'<span class="vol vol-vl">{v}</span>'

# Use msv_monthly column if present, else fall back to avg_interest
has_msv = "msv_monthly" in df.columns

rows_html = []
for _, r in df.iterrows():
    clr = CLUSTER_COLORS.get(r["cluster"], "#888")
    tbadge, _ = trend_badge(r["trend_direction"])
    is_trending = str(r.get("is_trending","No")).strip().lower() == "yes"
    msv_val = r["msv_monthly"] if has_msv else r["avg_interest"]
    est_vol = r["est_volume"]

    rows_html.append(f"""
    <tr data-cluster="{r['cluster']}" data-trend="{r['trend_direction']}" data-msv="{msv_val}" style="--clr:{clr}">
      <td class="td-cluster"><span class="dot" style="background:{clr}"></span>{r['cluster']}</td>
      <td class="td-keyword">{r['keyword']}{"<span class='fire'>🔥</span>" if is_trending else ""}</td>
      <td>{msv_bar(msv_val, r['avg_interest'], est_vol)}</td>
      <td><span class="peak-mo">{r['peak_month']}</span></td>
      <td>{tbadge}</td>
    </tr>""")

# Stats
total = len(df)
rising = len(df[df['trend_direction'] == 'Rising'])
stable = len(df[df['trend_direction'] == 'Stable'])
declining = len(df[df['trend_direction'] == 'Declining'])
if has_msv:
    high_vol = len(df[df['msv_monthly'] >= 20_000])
    total_msv = df['msv_monthly'].sum()
    total_msv_str = f"{total_msv//1_000_000}M" if total_msv >= 1_000_000 else f"{total_msv//1000}K"
else:
    high_vol = len(df[df['est_volume'].str.contains('High', na=False)])
    total_msv_str = "—"

html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>High Value Man — Keyword Search Demand</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{background:#080c14;font-family:'Segoe UI',system-ui,sans-serif;color:#D1D5DB;padding-bottom:60px}}

h1{{text-align:center;color:#F59E0B;font-size:17px;font-weight:700;letter-spacing:3px;
    text-transform:uppercase;padding:30px 0 6px}}
.subtitle{{text-align:center;color:#374151;font-size:11px;letter-spacing:1.5px;
           text-transform:uppercase;margin-bottom:24px}}

/* Controls */
.controls{{display:flex;flex-wrap:wrap;gap:10px;justify-content:center;
           padding:0 40px 20px;max-width:1500px;margin:0 auto}}
.controls button{{
  background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.1);
  color:#9CA3AF;font-size:11px;padding:7px 14px;border-radius:6px;cursor:pointer;
  transition:all 0.15s;letter-spacing:0.3px
}}
.controls button:hover,.controls button.active{{
  background:rgba(255,255,255,0.1);color:#F3F4F6;border-color:rgba(255,255,255,0.25)
}}
.controls button.active{{font-weight:600}}

/* Table */
.tbl-wrap{{max-width:1360px;margin:0 auto;padding:0 20px;overflow-x:auto}}
table{{width:100%;border-collapse:collapse}}
thead tr{{background:rgba(255,255,255,0.03);border-bottom:1px solid rgba(255,255,255,0.08)}}
th{{padding:11px 14px;font-size:10.5px;font-weight:700;text-transform:uppercase;
    letter-spacing:0.7px;color:#6B7280;text-align:left;cursor:pointer;white-space:nowrap}}
th:hover{{color:#9CA3AF}}
th .sort-arrow{{margin-left:4px;opacity:0.4}}
th.sorted{{color:#F59E0B}}
th.sorted .sort-arrow{{opacity:1}}

tbody tr{{border-bottom:1px solid rgba(255,255,255,0.04);transition:background 0.1s}}
tbody tr:hover{{background:rgba(255,255,255,0.03)}}
tbody tr.hidden{{display:none}}

td{{padding:10px 14px;vertical-align:middle;font-size:11px}}

.dot{{display:inline-block;width:8px;height:8px;border-radius:50%;
      margin-right:8px;flex-shrink:0;vertical-align:middle}}
.td-cluster{{font-size:10.5px;color:#9CA3AF;white-space:nowrap}}
.td-keyword{{font-size:12px;color:#E5E7EB;max-width:300px}}
.fire{{margin-left:5px;font-size:12px}}

/* Volume bar */
.bar-wrap{{display:flex;align-items:center;gap:10px;min-width:180px}}
.bar{{height:7px;border-radius:4px;min-width:2px;opacity:0.85;flex-shrink:0}}
.bar-val{{font-size:11.5px;font-weight:600;color:#E5E7EB;white-space:nowrap}}

/* Peak */
.peak-mo{{font-size:10px;color:#6B7280}}

/* Badges */
.badge{{display:inline-block;padding:3px 9px;border-radius:4px;
        font-size:10px;font-weight:600;letter-spacing:0.3px;white-space:nowrap}}
.badge-up{{background:rgba(16,185,129,0.15);color:#34D399}}
.badge-st{{background:rgba(59,130,246,0.15);color:#60A5FA}}
.badge-dn{{background:rgba(239,68,68,0.15);color:#F87171}}
.badge-na{{background:rgba(255,255,255,0.06);color:#6B7280}}

/* Stats bar */
.stats{{display:flex;justify-content:center;gap:40px;padding:0 0 26px;flex-wrap:wrap}}
.stat{{text-align:center}}
.stat-val{{font-size:24px;font-weight:700;color:#F59E0B}}
.stat-lbl{{font-size:10px;color:#6B7280;letter-spacing:0.5px;text-transform:uppercase;margin-top:3px}}

/* Search */
.search-wrap{{text-align:center;margin-bottom:16px}}
#search{{background:rgba(255,255,255,0.05);border:1px solid rgba(255,255,255,0.1);
         color:#E5E7EB;font-size:12px;padding:8px 16px;border-radius:7px;
         width:280px;outline:none}}
#search::placeholder{{color:#4B5563}}
#search:focus{{border-color:rgba(245,158,11,0.5)}}
</style>
</head>
<body>
<h1>High Value Man — Search Demand Map</h1>
<p class="subtitle">Monthly search volume estimates · US market · {total} keywords · market size validation</p>

<div class="stats">
  <div class="stat"><div class="stat-val">{total}</div><div class="stat-lbl">Keywords</div></div>
  <div class="stat"><div class="stat-val">{total_msv_str}</div><div class="stat-lbl">Total monthly searches</div></div>
  <div class="stat"><div class="stat-val">{high_vol}</div><div class="stat-lbl">20K+/mo keywords</div></div>
  <div class="stat"><div class="stat-val">{rising}</div><div class="stat-lbl">Rising trend</div></div>
  <div class="stat"><div class="stat-val">{stable}</div><div class="stat-lbl">Stable demand</div></div>
  <div class="stat"><div class="stat-val">{declining}</div><div class="stat-lbl">Declining</div></div>
</div>

<div class="search-wrap">
  <input id="search" type="text" placeholder="Filter keywords...">
</div>

<div class="controls">
  <button class="active" data-filter="all">All clusters</button>
  {''.join(f'<button data-filter="{c}">{c}</button>' for c in CLUSTER_COLORS)}
  <button data-trend="Rising">↑ Rising only</button>
  <button data-trend="Stable">→ Stable only</button>
  <button data-trend="Declining">↓ Declining only</button>
</div>

<div class="tbl-wrap">
<table id="tbl">
  <thead>
    <tr>
      <th onclick="sortBy(0)">Cluster <span class="sort-arrow">↕</span></th>
      <th onclick="sortBy(1)">Keyword <span class="sort-arrow">↕</span></th>
      <th onclick="sortBy(2)" class="sorted">Monthly Searches (US) <span class="sort-arrow">↓</span></th>
      <th onclick="sortBy(3)">Peak Month <span class="sort-arrow">↕</span></th>
      <th onclick="sortBy(4)">12-Month Trend <span class="sort-arrow">↕</span></th>
    </tr>
  </thead>
  <tbody id="tbody">
    {''.join(rows_html)}
  </tbody>
</table>
</div>

<script>
// Filter buttons
const btns = document.querySelectorAll('.controls button');
btns.forEach(btn => {{
  btn.addEventListener('click', () => {{
    btns.forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    applyFilters();
  }});
}});

document.getElementById('search').addEventListener('input', applyFilters);

function applyFilters() {{
  const activeBtn = document.querySelector('.controls button.active');
  const filter  = activeBtn?.dataset.filter;
  const tFilter = activeBtn?.dataset.trend;
  const q = document.getElementById('search').value.toLowerCase().trim();

  document.querySelectorAll('#tbody tr').forEach(row => {{
    const kw = row.cells[1]?.innerText.toLowerCase() || '';
    const matchCluster = !filter || filter === 'all' || row.dataset.cluster === filter;
    const matchTrend   = !tFilter || row.dataset.trend === tFilter;
    const matchSearch  = !q || kw.includes(q);
    row.classList.toggle('hidden', !(matchCluster && matchTrend && matchSearch));
  }});
}}

// Sort — table starts sorted by MSV (col 2, desc)
let sortDir = {{2: -1}};
function sortBy(col) {{
  const tbody = document.getElementById('tbody');
  const rows  = Array.from(tbody.querySelectorAll('tr'));
  const dir   = (sortDir[col] = -(sortDir[col] || -1));

  document.querySelectorAll('th').forEach((th, i) => {{
    th.classList.toggle('sorted', i === col);
    if (i === col) {{
      th.querySelector('.sort-arrow').textContent = dir === 1 ? '↑' : '↓';
    }} else {{
      th.querySelector('.sort-arrow').textContent = '↕';
    }}
  }});

  rows.sort((a, b) => {{
    if (col === 2) {{
      // Sort by data-msv attribute for accurate numeric sort
      const am = parseFloat(a.dataset.msv || 0);
      const bm = parseFloat(b.dataset.msv || 0);
      return dir * (am - bm);
    }}
    const at = a.cells[col]?.innerText.trim() || '';
    const bt = b.cells[col]?.innerText.trim() || '';
    const an = parseFloat(at), bn = parseFloat(bt);
    if (!isNaN(an) && !isNaN(bn)) return dir * (an - bn);
    return dir * at.localeCompare(bt);
  }});
  rows.forEach(r => tbody.appendChild(r));
}}

// Auto-sort by MSV on load
sortBy(2);
</script>
</body>
</html>
"""

Path(OUT).write_text(html, encoding="utf-8")
print(f"✓ Saved → {OUT}")
print(f"  {len(df)} rows | Rising: {rising} | Stable: {stable} | Declining: {declining} | 20K+ volume: {high_vol}")
