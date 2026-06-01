"""Generate hvm_segments.html from hvm_segments.csv"""
import pandas as pd
from pathlib import Path
import html as html_lib

CSV = "hvm_segments.csv"
OUT = "hvm_segments.html"

df = pd.read_csv(CSV)

CLR = {
    "A": dict(hex="#D97706", bg="#15110a", border="#382800", text="#fbbf24", dim="#7a5a20"),
    "B": dict(hex="#7C3AED", bg="#0e0a18", border="#241650", text="#a78bfa", dim="#4a3580"),
    "C": dict(hex="#DC2626", bg="#140808", border="#360e0e", text="#f87171", dim="#7a2020"),
    "D": dict(hex="#2563EB", bg="#080e1c", border="#102050", text="#60a5fa", dim="#1e3a80"),
    "E": dict(hex="#059669", bg="#060e0c", border="#0c2820", text="#34d399", dim="#155a40"),
}

SEG_META = {
    "A": dict(name="The Invisible Provider", share="35%", num=1),
    "B": dict(name="The Man Without a Mission", share="25%", num=2),
    "C": dict(name="The Nice Guy Awakening", share="20%", num=3),
    "D": dict(name="The Rebuilder", share="15%", num=4),
    "E": dict(name="The Optimizer", share="5%", num=5),
}

def e(s):
    return html_lib.escape(str(s)) if s and str(s) != "nan" else ""

def jtbd_items(row):
    parts = []
    for i in range(1, 6):
        t = e(row.get(f"jtbd_type_{i}", ""))
        j = e(row.get(f"jtbd_{i}", ""))
        if j:
            badge = f'<span class="jtbd-badge">{t}</span>' if t else ""
            parts.append(f'<li>{badge} {j}</li>')
    return "\n".join(parts)

def blocker_items(row):
    parts = []
    for i in range(1, 6):
        b = e(row.get(f"blocker_{i}", ""))
        if b:
            parts.append(f'<li>{b}</li>')
    return "\n".join(parts)

def split_tags(val, cls):
    val = str(val) if val and str(val) != "nan" else ""
    if not val:
        return ""
    tags = [t.strip() for t in val.split(",") if t.strip()]
    return " ".join(f'<span class="{cls}">{html_lib.escape(t)}</span>' for t in tags)

# ── build sidebar nav ──────────────────────────────────────────────────────────
def sidebar_nav():
    parts = ['<nav class="sidebar">',
             '<div class="sidebar-logo"><h2>High Value Man</h2><p>Audience segments · 5 triggers · Reddit-validated</p></div>']
    for sid, meta in SEG_META.items():
        c = CLR[sid]
        triggers = df[df["segment_id"] == sid]["trigger_type"].tolist()
        parts.append(f'''
  <div class="nav-section">
    <div class="nav-cat" onclick="location.href=\'#seg-{sid}\'">
      <div class="nav-dot" style="background:{c['hex']}"></div>
      <span style="color:{c['text']}">{meta['num']} · {meta['name']}</span>
      <span class="nav-share">{meta['share']}</span>
    </div>''')
        for ti, trig in enumerate(triggers):
            parts.append(f'    <a class="nav-sub" href="#t-{sid}{ti+1}">{html_lib.escape(trig)}</a>')
        parts.append('  </div>\n  <div class="nav-divider"></div>')
    parts.append('</nav>')
    return "\n".join(parts)

# ── trigger card ──────────────────────────────────────────────────────────────
def trigger_card(row, sid, ti):
    c = CLR[sid]
    anchor = f"t-{sid}{ti}"
    trigger_type = e(row.get("trigger_type", ""))
    trigger_desc = e(row.get("trigger_description", ""))
    timing = e(row.get("timing_window", ""))
    buyable = e(row.get("buyable_window", ""))
    sweet = e(row.get("sweet_spot_months_post_event", ""))
    hook = e(row.get("converting_hook", ""))
    testimonial = e(row.get("testimonial_type", ""))
    ad_angle = e(row.get("ad_campaign_angle", ""))
    lp_angle = e(row.get("landing_page_angle", ""))
    product_fit = e(row.get("product_fit", ""))
    special = e(row.get("special_notes", ""))
    reddit = split_tags(row.get("reddit_communities", ""), "comm-tag")
    queries = split_tags(row.get("search_queries", ""), "search-tag")
    channels = split_tags(row.get("content_channels", ""), "chan-tag")

    jhtml = jtbd_items(row)
    bhtml = blocker_items(row)

    warning = ""
    if "⚠" in str(row.get("special_notes", "")) or "HIGHEST" in str(row.get("special_notes", "")):
        warning = f'<div class="warning-bar">⚠ {special}</div>'
        special = ""

    return f"""
    <div class="trigger-card" id="{anchor}">
      <div class="trigger-header" style="border-left:4px solid {c['hex']}">
        <span class="trigger-type-badge" style="background:{c['bg']};color:{c['text']};border-color:{c['border']}">{trigger_type}</span>
        <span class="trigger-title">{trigger_desc}</span>
      </div>
      <div class="seg-grid">
        <div class="seg-col">
          <div class="col-label" style="color:{c['text']}">Timing Window</div>
          <div class="timing-block">
            <div class="timing-row"><span class="t-key">Enters market</span><span class="t-val">{timing}</span></div>
            <div class="timing-row"><span class="t-key">Buyable window</span><span class="t-val">{buyable}</span></div>
            <div class="timing-row"><span class="t-key">Sweet spot</span><span class="t-val">{sweet}</span></div>
          </div>
          <div class="col-label" style="color:{c['text']};margin-top:16px">Jobs to Be Done</div>
          <ul class="list-items jtbd">{jhtml}</ul>
        </div>
        <div class="seg-col">
          <div class="col-label" style="color:{c['text']}">Purchase Blockers</div>
          <ul class="list-items blk">{bhtml}</ul>
          <div class="col-label" style="color:{c['text']};margin-top:14px">Reddit Communities</div>
          <div class="tag-row">{reddit}</div>
          <div class="col-label" style="color:{c['text']};margin-top:10px">Search Queries</div>
          <div class="tag-row">{queries}</div>
          <div class="col-label" style="color:{c['text']};margin-top:10px">Content Channels</div>
          <div class="tag-row">{channels}</div>
        </div>
        <div class="seg-col">
          <div class="col-label" style="color:{c['text']}">Converting Hook</div>
          <p class="hook-text">&ldquo;{hook}&rdquo;</p>
          <div class="col-label" style="color:{c['text']};margin-top:14px">Ad Campaign Angle</div>
          <p class="seg-desc">{ad_angle}</p>
          <div class="col-label" style="color:{c['text']};margin-top:14px">Landing Page Angle</div>
          <p class="seg-desc">{lp_angle}</p>
          <div class="col-label" style="color:{c['text']};margin-top:14px">Testimonial Type</div>
          <p class="seg-desc">{testimonial}</p>
        </div>
      </div>
      {warning}
      <div class="insight-bar" style="border-left-color:{c['hex']}">
        <strong>Product fit:</strong> {product_fit}{(' — <em>' + special + '</em>') if special else ''}
      </div>
    </div>"""

# ── segment section ───────────────────────────────────────────────────────────
def segment_section(sid):
    c = CLR[sid]
    meta = SEG_META[sid]
    rows = df[df["segment_id"] == sid]
    first = rows.iloc[0]
    baseline = e(first.get("baseline_description", ""))
    core_q = e(first.get("core_question", ""))
    share_pct = int(meta["share"].replace("%", ""))

    cards = ""
    for ti, (_, row) in enumerate(rows.iterrows(), 1):
        cards += trigger_card(row, sid, ti)

    return f"""
  <div class="cat-section" id="seg-{sid}" style="--seg-clr:{c['hex']};--seg-bg:{c['bg']};--seg-border:{c['border']};--seg-text:{c['text']}">
    <div class="cat-header">
      <div class="cat-header-inner" style="background:{c['bg']};border-color:{c['border']}">
        <div class="cat-num" style="background:{c['hex']};color:#fff">{meta['num']}</div>
        <div>
          <div class="cat-name">{meta['name']}</div>
          <div class="cat-baseline">{baseline}</div>
        </div>
        <div class="cat-right">
          <div class="share-circle" style="--share:{share_pct}%;color:{c['text']}">{meta['share']}</div>
          <div class="core-q">&ldquo;{core_q}&rdquo;</div>
        </div>
      </div>
    </div>
    <div class="seg-section">{cards}</div>
  </div>"""

# ── build full HTML ────────────────────────────────────────────────────────────
nav_html = sidebar_nav()
segments_html = "".join(segment_section(sid) for sid in SEG_META)
total_triggers = len(df)
total_segs = len(SEG_META)

css = """
*{box-sizing:border-box;margin:0;padding:0}
html{scroll-behavior:smooth}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#0d0d12;color:#dddde8;line-height:1.65;display:flex}

/* sidebar */
.sidebar{width:240px;min-height:100vh;background:#0a0a10;border-right:1px solid #1a1a28;position:fixed;top:0;left:0;overflow-y:auto;padding:24px 0 60px;z-index:100;flex-shrink:0}
.sidebar-logo{padding:0 18px 20px;border-bottom:1px solid #1a1a28;margin-bottom:16px}
.sidebar-logo h2{font-size:.82rem;font-weight:700;color:#fff;line-height:1.4}
.sidebar-logo p{font-size:.7rem;color:#444466;margin-top:3px}
.nav-section{margin-bottom:4px}
.nav-cat{display:flex;align-items:center;gap:8px;padding:9px 18px;font-size:.74rem;font-weight:700;text-transform:uppercase;letter-spacing:.6px;cursor:pointer;transition:background .15s}
.nav-cat:hover{background:rgba(255,255,255,.04)}
.nav-dot{width:8px;height:8px;border-radius:50%;flex-shrink:0}
.nav-share{margin-left:auto;font-size:.68rem;color:#444466;font-weight:400;font-style:normal}
.nav-sub{display:block;padding:5px 18px 5px 34px;font-size:.74rem;color:#444466;text-decoration:none;transition:color .15s,background .15s;border-left:2px solid transparent;margin-left:18px}
.nav-sub:hover{color:#aaaacc;background:rgba(255,255,255,.03)}
.nav-sub.active{color:#aaaaee;border-left-color:#4444aa}
.nav-divider{height:1px;background:#1a1a28;margin:8px 0}

/* main */
.main{margin-left:240px;flex:1;min-width:0;padding-bottom:100px}

/* hero */
.hero{background:linear-gradient(135deg,#141424 0%,#0e1830 60%,#0a2040 100%);padding:48px 40px 40px;border-bottom:1px solid #1a1a30}
.hero h1{font-size:1.7rem;font-weight:700;color:#fff;letter-spacing:-.4px;margin-bottom:6px}
.hero p{color:#6666aa;font-size:.88rem;max-width:640px;line-height:1.6}
.hero .stats{display:flex;gap:14px;margin-top:20px;flex-wrap:wrap}
.stat{background:rgba(255,255,255,.05);border:1px solid rgba(255,255,255,.08);border-radius:9px;padding:9px 16px}
.stat-num{font-size:1.3rem;font-weight:700;color:#fff}
.stat-label{font-size:.68rem;color:#6666aa;text-transform:uppercase;letter-spacing:.5px}

/* overview bar */
.overview{padding:24px 40px;border-bottom:1px solid #1a1a28}
.overview h2{font-size:.78rem;font-weight:700;text-transform:uppercase;letter-spacing:.8px;color:#444466;margin-bottom:14px}
.share-bar{display:flex;height:10px;border-radius:6px;overflow:hidden;gap:2px}
.share-seg{height:100%;border-radius:3px;transition:opacity .2s;cursor:pointer}
.share-seg:hover{opacity:.8}
.share-legend{display:flex;flex-wrap:wrap;gap:12px 20px;margin-top:12px}
.share-item{display:flex;align-items:center;gap:6px;font-size:.76rem;color:#8888aa}
.share-dot{width:8px;height:8px;border-radius:50%}

/* segment section */
.cat-section{padding-top:8px}
.cat-header{padding:28px 40px 0;position:sticky;top:0;z-index:10}
.cat-header-inner{display:flex;align-items:flex-start;gap:16px;padding:16px 20px;border-radius:12px 12px 0 0;border:1px solid}
.cat-num{width:36px;height:36px;min-width:36px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:1rem;font-weight:800;flex-shrink:0;margin-top:2px}
.cat-name{font-size:1.05rem;font-weight:700;color:#fff;margin-bottom:4px}
.cat-baseline{font-size:.78rem;color:#7777aa;line-height:1.55;max-width:480px}
.cat-right{margin-left:auto;text-align:right;flex-shrink:0;max-width:280px}
.share-circle{font-size:1.8rem;font-weight:800;line-height:1}
.core-q{font-size:.74rem;color:#5555aa;margin-top:6px;font-style:italic;line-height:1.45}

/* segment + trigger cards */
.seg-section{padding:0 40px 56px}
.trigger-card{background:#101015;border:1px solid #1e1e2a;border-radius:14px;overflow:hidden;margin-top:16px}
.trigger-header{display:flex;align-items:flex-start;gap:12px;padding:14px 20px;border-bottom:1px solid #1a1a24;background:rgba(255,255,255,.02)}
.trigger-type-badge{font-size:.68rem;font-weight:700;padding:3px 10px;border-radius:5px;border:1px solid;white-space:nowrap;flex-shrink:0;margin-top:2px;letter-spacing:.3px;text-transform:uppercase}
.trigger-title{font-size:.9rem;color:#c8c8e0;line-height:1.5}

.seg-grid{display:grid;grid-template-columns:1fr 1.1fr 1fr}
@media(max-width:900px){.seg-grid{grid-template-columns:1fr 1fr}}
@media(max-width:580px){.seg-grid{grid-template-columns:1fr}}
.seg-col{padding:18px 20px;border-right:1px solid #1a1a24}
.seg-col:last-child{border-right:none}
.col-label{font-size:.62rem;font-weight:700;text-transform:uppercase;letter-spacing:1.1px;margin-bottom:8px}

/* timing block */
.timing-block{background:rgba(255,255,255,.025);border:1px solid rgba(255,255,255,.06);border-radius:8px;padding:10px 12px;margin-bottom:4px}
.timing-row{display:flex;gap:8px;margin-bottom:4px;font-size:.76rem}
.timing-row:last-child{margin-bottom:0}
.t-key{color:#555577;min-width:90px;flex-shrink:0}
.t-val{color:#9999bb}

/* jtbd + blockers */
.list-items{list-style:none;display:flex;flex-direction:column;gap:7px}
.list-items li{font-size:.79rem;color:#9999bb;padding-left:18px;position:relative;line-height:1.5}
.list-items.jtbd li::before{content:'→';position:absolute;left:0;opacity:.4;font-size:.72rem}
.list-items.blk li::before{content:'✕';position:absolute;left:0;opacity:.3;font-size:.7rem}
.jtbd-badge{font-size:.58rem;font-weight:700;text-transform:uppercase;letter-spacing:.4px;padding:1px 5px;border-radius:3px;background:rgba(255,255,255,.07);color:#7777aa;margin-right:4px;vertical-align:middle}

/* tags */
.tag-row{display:flex;flex-wrap:wrap;gap:5px;margin-top:4px;margin-bottom:6px}
.comm-tag{font-size:.68rem;padding:2px 7px;border-radius:4px;background:rgba(59,130,246,.1);color:#60a5fa;border:1px solid rgba(59,130,246,.2)}
.search-tag{font-size:.68rem;padding:2px 7px;border-radius:4px;background:rgba(16,185,129,.1);color:#34d399;border:1px solid rgba(16,185,129,.2)}
.chan-tag{font-size:.68rem;padding:2px 7px;border-radius:4px;background:rgba(245,158,11,.1);color:#fbbf24;border:1px solid rgba(245,158,11,.2)}

/* messaging col */
.hook-text{font-size:.85rem;color:#ddddf0;font-style:italic;line-height:1.55;border-left:3px solid rgba(255,255,255,.15);padding-left:12px}
.seg-desc{font-size:.8rem;color:#8888aa;line-height:1.6}

/* warning bar */
.warning-bar{background:rgba(220,38,38,.08);border-top:1px solid rgba(220,38,38,.2);padding:10px 20px;font-size:.78rem;color:#f87171;line-height:1.55}

/* insight bar */
.insight-bar{padding:11px 22px;background:rgba(255,255,255,.02);border-top:1px solid #1a1a24;font-size:.8rem;color:#8888aa;border-left:4px solid;line-height:1.55}
.insight-bar strong{color:#ddd}
.insight-bar em{color:#9999bb;font-style:normal}
"""

html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1.0"/>
<title>High Value Man — Audience Segments</title>
<style>{css}</style>
</head>
<body>

{nav_html}

<div class="main">

  <div class="hero">
    <h1>High Value Man — Audience Segments</h1>
    <p>5 MECE segments built from 1,178 Reddit posts, 4,803 comments, and 81 validated keywords. Each segment defined by a core identity gap and mapped to the triggers that open the buying window.</p>
    <div class="stats">
      <div class="stat"><div class="stat-num">5</div><div class="stat-label">Segments</div></div>
      <div class="stat"><div class="stat-num">{total_triggers}</div><div class="stat-label">Buy triggers</div></div>
      <div class="stat"><div class="stat-num">81</div><div class="stat-label">Validated keywords</div></div>
      <div class="stat"><div class="stat-num">5,981</div><div class="stat-label">Reddit posts + comments</div></div>
    </div>
  </div>

  <div class="overview">
    <h2>Market share distribution</h2>
    <div class="share-bar">
      <div class="share-seg" style="width:35%;background:#D97706" onclick="location.href='#seg-A'" title="Invisible Provider 35%"></div>
      <div class="share-seg" style="width:25%;background:#7C3AED" onclick="location.href='#seg-B'" title="Man Without a Mission 25%"></div>
      <div class="share-seg" style="width:20%;background:#DC2626" onclick="location.href='#seg-C'" title="Nice Guy Awakening 20%"></div>
      <div class="share-seg" style="width:15%;background:#2563EB" onclick="location.href='#seg-D'" title="The Rebuilder 15%"></div>
      <div class="share-seg" style="width:5%;background:#059669" onclick="location.href='#seg-E'" title="The Optimizer 5%"></div>
    </div>
    <div class="share-legend">
      <div class="share-item"><div class="share-dot" style="background:#D97706"></div>A · Invisible Provider 35%</div>
      <div class="share-item"><div class="share-dot" style="background:#7C3AED"></div>B · Man Without a Mission 25%</div>
      <div class="share-item"><div class="share-dot" style="background:#DC2626"></div>C · Nice Guy Awakening 20%</div>
      <div class="share-item"><div class="share-dot" style="background:#2563EB"></div>D · The Rebuilder 15%</div>
      <div class="share-item"><div class="share-dot" style="background:#059669"></div>E · The Optimizer 5%</div>
    </div>
  </div>

{segments_html}

</div>

<script>
// Active nav on scroll
const sections = document.querySelectorAll('[id^="t-"]');
const navLinks = document.querySelectorAll('.nav-sub');
const obs = new IntersectionObserver((entries) => {{
  entries.forEach(e => {{
    if (e.isIntersecting) {{
      navLinks.forEach(l => l.classList.remove('active'));
      const active = document.querySelector('.nav-sub[href="#' + e.target.id + '"]');
      if (active) active.classList.add('active');
    }}
  }});
}}, {{rootMargin:'-20% 0px -70% 0px'}});
sections.forEach(s => obs.observe(s));
</script>
</body>
</html>"""

Path(OUT).write_text(html, encoding="utf-8")
print(f"✓ Saved → {OUT}")
print(f"  {total_segs} segments | {total_triggers} triggers")
