#!/usr/bin/env python3
"""
Propaganda Pulse — FastAPI Edition
────────────────────────────────────
pip install fastapi uvicorn
python main.py
Open: http://localhost:8000
"""
from __future__ import annotations
import hashlib, re, time
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import uvicorn

app = FastAPI(title="Propaganda Pulse", docs_url=None, redoc_url=None)


# ══════════════════════════════════════════════════════════════════════════════
#  ANALYSIS ENGINE  (deterministic, URL-hash seeded — no external APIs needed)
# ══════════════════════════════════════════════════════════════════════════════

TECHNIQUES = [
    "Loaded Language", "Appeal to Fear", "Ad Hominem", "Repetition",
    "False Dichotomy", "Bandwagon", "Glittering Generalities", "Card Stacking",
    "Name Calling", "Transfer", "Testimonial", "Plain Folks",
    "Scapegoating", "Emotional Appeal", "Cherry Picking", "Straw Man",
    "Whataboutism", "Dog Whistle", "Euphemism", "Dehumanization",
]

COUNTRIES = [
    {"name": "United States",   "code": "US", "lat":  39.0,  "lng":  -98.0},
    {"name": "United Kingdom",  "code": "GB", "lat":  55.0,  "lng":   -3.0},
    {"name": "Russia",          "code": "RU", "lat":  61.0,  "lng":  105.0},
    {"name": "China",           "code": "CN", "lat":  35.0,  "lng":  105.0},
    {"name": "France",          "code": "FR", "lat":  46.0,  "lng":    2.0},
    {"name": "Germany",         "code": "DE", "lat":  51.0,  "lng":   10.0},
    {"name": "Iran",            "code": "IR", "lat":  32.0,  "lng":   53.0},
    {"name": "Israel",          "code": "IL", "lat":  31.5,  "lng":   34.8},
    {"name": "Brazil",          "code": "BR", "lat": -10.0,  "lng":  -55.0},
    {"name": "India",           "code": "IN", "lat":  20.0,  "lng":   77.0},
    {"name": "Turkey",          "code": "TR", "lat":  39.0,  "lng":   35.0},
    {"name": "Australia",       "code": "AU", "lat": -25.0,  "lng":  133.0},
    {"name": "Canada",          "code": "CA", "lat":  56.0,  "lng": -106.0},
    {"name": "Japan",           "code": "JP", "lat":  36.0,  "lng":  138.0},
    {"name": "South Korea",     "code": "KR", "lat":  37.0,  "lng":  127.5},
    {"name": "Qatar",           "code": "QA", "lat":  25.3,  "lng":   51.2},
    {"name": "Saudi Arabia",    "code": "SA", "lat":  24.0,  "lng":   45.0},
    {"name": "Ukraine",         "code": "UA", "lat":  49.0,  "lng":   31.0},
]

DOMAIN_COUNTRY = {
    "bbc.co.uk":       "United Kingdom", "bbc.com":         "United Kingdom",
    "reuters.com":     "United Kingdom", "theguardian.com": "United Kingdom",
    "independent.co.uk": "United Kingdom",
    "nytimes.com":     "United States",  "washingtonpost.com": "United States",
    "foxnews.com":     "United States",  "cnn.com":         "United States",
    "theatlantic.com": "United States",  "breitbart.com":   "United States",
    "apnews.com":      "United States",  "npr.org":         "United States",
    "rt.com":          "Russia",         "sputniknews.com": "Russia",
    "tass.com":        "Russia",         "pravda.ru":       "Russia",
    "xinhuanet.com":   "China",          "chinadaily.com.cn": "China",
    "globaltimes.cn":  "China",
    "aljazeera.com":   "Qatar",
    "dw.com":          "Germany",        "spiegel.de":      "Germany",
    "lemonde.fr":      "France",         "lefigaro.fr":     "France",
    "presstv.ir":      "Iran",
    "haaretz.com":     "Israel",         "timesofisrael.com": "Israel",
    "thehindu.com":    "India",          "ndtv.com":        "India",
    "kyivindependent.com": "Ukraine",
}

GEO_SUMMARIES = {
    True: [
        "This piece exhibits strong geopolitical framing, positioning the subject nation as a defensive actor in a hostile international order. Narrative techniques suggest a deliberate attempt to shape perception of regional power dynamics.",
        "Classic sovereignty-threat framing pervades this article, invoking historical grievances to justify present-day positioning. The geopolitical subtext elevates national interest over multilateral consensus-building.",
        "The text deploys alliance-signaling rhetoric, reinforcing in-group solidarity while casting rival powers as inherently destabilizing. Selective citation of international law suggests instrumental rather than principled engagement.",
    ],
    False: [
        "This piece maintains relatively neutral geopolitical framing, presenting multiple state perspectives without overt allegiance to a particular power bloc. Minor editorial biases are detectable through source selection.",
        "Geopolitical content appears balanced in its surface presentation, though structural omissions — notably the absence of counter-hegemonic perspectives — suggest mild editorial alignment.",
    ],
}
INST_SUMMARIES = {
    True: [
        "The article consistently undermines institutional credibility, framing governmental bodies, expert consensus, and mainstream media as corrupt or captured. This anti-establishment posture is a hallmark of populist media operations.",
        "Strong anti-institutional sentiment pervades this piece. Scientific consensus, judicial authority, and international bodies are cast as adversarial forces opposing the legitimate will of ordinary citizens.",
        "Elite-capture framing is deployed throughout: institutions are portrayed not as imperfect but as systematically corrupted — a rhetorical move that forecloses reform in favour of replacement.",
    ],
    False: [
        "Institutional framing appears largely conventional, citing established authorities and maintaining deference to official narratives. Dissenting expert opinion is acknowledged but positioned as minority view.",
        "The piece operates within mainstream institutional discourse, reinforcing rather than challenging established power structures. Credentialist sourcing patterns suggest deep trust in formal expertise.",
    ],
}
SOCIO_SUMMARIES = {
    True: [
        "Clear ideological polarization detected. The article deploys economic grievance narratives alongside cultural identity markers to activate base sentiment. Left-right framing is prominent and structural.",
        "Strong socio-political signaling detected. Language patterns suggest deliberate audience segmentation along cultural and economic fault lines, with little rhetorical space allocated to synthesis or compromise.",
        "The text performs ideological sorting: issues that might be framed as technical or economic are systematically recast as moral and identity-laden, maximizing the emotional stakes of political disagreement.",
    ],
    False: [
        "Socio-political framing appears relatively centrist, avoiding overt ideological positioning while maintaining standard editorial conventions around balance.",
        "The piece maintains moderate ideological positioning, drawing from both progressive and traditional value frameworks without strong polarization. Rhetorical moderation may mask deeper editorial assumptions.",
    ],
}


def _hash(url: str) -> int:
    return int(hashlib.md5(url.encode()).hexdigest(), 16)

def _flt(seed: int, idx: int) -> float:
    h = hashlib.md5(f"{seed}:{idx}".encode()).hexdigest()
    return int(h[:8], 16) / 0xFFFF_FFFF

def _rng(seed: int, idx: int, lo: float, hi: float) -> float:
    return lo + _flt(seed, idx) * (hi - lo)

def _pick(seed: int, idx: int, items: list):
    i = int(_flt(seed, idx) * len(items))
    return items[min(i, len(items) - 1)]

def _shuffle_n(seed: int, offset: int, items: list, n: int) -> list:
    items = list(items)
    for i in range(len(items) - 1, 0, -1):
        j = int(_flt(seed, offset + i) * (i + 1))
        items[i], items[j] = items[j], items[i]
    return items[:n]

def _alignment(score: float) -> str:
    if score < -55: return "far-left"
    if score < -20: return "center-left"
    if score <  20: return "center"
    if score <  55: return "center-right"
    return "far-right"

def _domain(url: str) -> str:
    m = re.search(r'(?:https?://)?(?:www\.)?([^/\s]+)', url)
    return m.group(1).lower() if m else url.lower()


def analyze_url(url: str) -> dict:
    seed = _hash(url)
    domain = _domain(url)

    country_name = next(
        (c for d, c in DOMAIN_COUNTRY.items() if d in domain), None
    ) or _pick(seed, 0, [c["name"] for c in COUNTRIES])

    country = next(c for c in COUNTRIES if c["name"] == country_name)
    lat = country["lat"] + _rng(seed, 1, -2, 2)
    lng = country["lng"] + _rng(seed, 2, -2, 2)

    geo_score   = round(_rng(seed, 10, -92, 92), 1)
    inst_score  = round(_rng(seed, 20, -92, 92), 1)
    socio_score = round(_rng(seed, 30, -92, 92), 1)
    bias_score  = round((geo_score * 0.4 + inst_score * 0.3 + socio_score * 0.3), 1)

    source_types = ["state-media", "mainstream", "tabloid", "independent", "think-tank", "wire", "partisan"]
    source_type = _pick(seed, 5, source_types)

    return {
        "id":                 hashlib.md5(f"{url}:{seed}".encode()).hexdigest()[:12],
        "url":                url,
        "domain":             domain,
        "biasScore":          bias_score,
        "alignment":          _alignment(bias_score),
        "sourceType":         source_type,
        "primaryCountry":     country_name,
        "primaryCountryCode": country["code"],
        "primaryLat":         round(lat, 4),
        "primaryLng":         round(lng, 4),
        "analyzedAt":         int(time.time() * 1000),
        "lenses": {
            "geopolitical": {
                "score":      geo_score,
                "alignment":  _alignment(geo_score),
                "techniques": _shuffle_n(seed, 100, TECHNIQUES, 4),
                "summary":    _pick(seed, 6, GEO_SUMMARIES[abs(geo_score) > 40]),
            },
            "institutional": {
                "score":      inst_score,
                "alignment":  _alignment(inst_score),
                "techniques": _shuffle_n(seed, 200, TECHNIQUES, 4),
                "summary":    _pick(seed, 7, INST_SUMMARIES[abs(inst_score) > 40]),
            },
            "sociopolitical": {
                "score":      socio_score,
                "alignment":  _alignment(socio_score),
                "techniques": _shuffle_n(seed, 300, TECHNIQUES, 4),
                "summary":    _pick(seed, 8, SOCIO_SUMMARIES[abs(socio_score) > 40]),
            },
        },
    }


# ══════════════════════════════════════════════════════════════════════════════
#  IN-MEMORY STORE
# ══════════════════════════════════════════════════════════════════════════════

_analyses: list[dict] = []


# ══════════════════════════════════════════════════════════════════════════════
#  ROUTES
# ══════════════════════════════════════════════════════════════════════════════

class AnalyzeRequest(BaseModel):
    url: str

@app.get("/", response_class=HTMLResponse)
async def index():
    return HTMLResponse(content=HTML)

@app.post("/analyze")
async def analyze(req: AnalyzeRequest):
    result = analyze_url(req.url.strip())
    _analyses.insert(0, result)
    if len(_analyses) > 50:
        _analyses.pop()
    return result

@app.get("/history")
async def history():
    return _analyses

@app.get("/stats")
async def stats():
    if not _analyses:
        return {"count": 0, "avgBias": 0.0, "countries": 0, "topTechniques": []}
    avg = sum(a["biasScore"] for a in _analyses) / len(_analyses)
    countries = len({a["primaryCountryCode"] for a in _analyses})
    tc: dict[str, int] = {}
    for a in _analyses:
        for t in a.get("lenses", {}).get("geopolitical", {}).get("techniques", []):
            tc[t] = tc.get(t, 0) + 1
    top = sorted(tc.items(), key=lambda x: x[1], reverse=True)[:4]
    return {
        "count": len(_analyses),
        "avgBias": round(avg, 1),
        "countries": countries,
        "topTechniques": [{"name": n, "count": c} for n, c in top],
    }


# ══════════════════════════════════════════════════════════════════════════════
#  FRONTEND  (single-file, CDN-driven)
# ══════════════════════════════════════════════════════════════════════════════

HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Propaganda Pulse — OSINT Terminal</title>

<!-- Fonts -->
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Lora:ital,wght@0,500;0,700;1,400;1,500&family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">

<!-- Leaflet -->
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>

<style>
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}

html,body{
  height:100%;overflow:hidden;
  background:#060810;
  color:#e2e2e6;
  font-family:'Inter',system-ui,sans-serif;
  -webkit-font-smoothing:antialiased;
}

/* ── Map ── */
#map{position:fixed;inset:0;z-index:0}
.leaflet-tile-pane{
  filter:sepia(.9) hue-rotate(185deg) saturate(3.5) brightness(.72) contrast(1.2);
}
.leaflet-container{background:#060810!important}

/* ── Glass ── */
.glass{
  background:rgba(8,9,20,.75);
  border:1px solid rgba(255,255,255,.08);
  backdrop-filter:blur(22px);
  -webkit-backdrop-filter:blur(22px);
}
.glass-light{
  background:rgba(14,15,28,.65);
  border:1px solid rgba(255,255,255,.07);
  backdrop-filter:blur(14px);
  -webkit-backdrop-filter:blur(14px);
}

/* ── Header ── */
#header{
  position:fixed;top:0;left:0;right:0;
  z-index:8;
  pointer-events:none;
  text-align:center;
  padding:1.25rem 0 .5rem;
  background:linear-gradient(to bottom,rgba(6,8,16,.88) 0%,rgba(6,8,16,0) 100%);
}
#header h1{
  font-family:'Inter',sans-serif;
  font-size:1.45rem;font-weight:700;
  letter-spacing:.42em;
  color:rgba(226,226,230,.42);
  text-transform:uppercase;
}
#header h1 em{font-style:normal;color:#eebc06}
#header p{
  margin-top:.25rem;
  font-size:.56rem;font-weight:500;
  letter-spacing:.28em;
  color:rgba(226,226,230,.25);
  text-transform:uppercase;
}

/* ── URL Bar ── */
#url-bar{
  position:fixed;top:5rem;
  left:50%;transform:translateX(-50%);
  z-index:20;
  width:min(620px,calc(100vw - 600px));
  display:flex;gap:.5rem;
  transition:opacity .3s;
}
#url-input{
  flex:1;
  background:rgba(8,9,20,.9);
  border:1px solid rgba(255,255,255,.12);
  border-radius:.375rem;
  padding:.6rem 1rem;
  font-family:'Inter',sans-serif;font-size:.82rem;
  color:#e2e2e6;outline:none;
  backdrop-filter:blur(20px);
  transition:border-color .2s;
}
#url-input::placeholder{color:rgba(226,226,230,.32)}
#url-input:focus{border-color:rgba(238,188,6,.5)}
#analyze-btn{
  background:#eebc06;color:#06080f;
  border:none;border-radius:.375rem;
  padding:.6rem 1.1rem;
  font-family:'Inter',sans-serif;font-size:.7rem;font-weight:700;
  letter-spacing:.1em;text-transform:uppercase;
  cursor:pointer;white-space:nowrap;
  transition:opacity .15s,transform .1s;
}
#analyze-btn:hover{opacity:.88;transform:scale(1.02)}
#analyze-btn:active{transform:scale(.97)}
#analyze-btn:disabled{opacity:.45;cursor:not-allowed}

/* ── Scanning Badge ── */
#scan-badge{
  position:fixed;top:5rem;
  left:50%;transform:translateX(-50%);
  z-index:21;
  background:rgba(238,188,6,.1);
  border:1px solid rgba(238,188,6,.35);
  border-radius:2rem;
  padding:.3rem 1rem;
  font-size:.6rem;font-weight:600;letter-spacing:.2em;
  color:#eebc06;text-transform:uppercase;
  display:none;
  animation:pulseBadge 1.4s ease-in-out infinite;
}
@keyframes pulseBadge{0%,100%{opacity:.55}50%{opacity:1}}

/* ── Stats Panel (left) ── */
#stats{
  position:fixed;top:1.25rem;left:1.25rem;
  z-index:15;width:196px;
  border-radius:.625rem;
  padding:.875rem;
  display:flex;flex-direction:column;gap:.7rem;
}
.stat-lbl{
  font-size:.52rem;font-weight:600;
  letter-spacing:.14em;text-transform:uppercase;
  color:rgba(226,226,230,.38);
}
.stat-val{
  font-size:1.45rem;font-weight:700;color:#e2e2e6;line-height:1.1;
}
.stat-val small{font-size:.7rem;font-weight:500;color:rgba(226,226,230,.38)}
.hr{height:1px;background:rgba(255,255,255,.055)}

/* ── Analysis Panel (right) ── */
#analysis{
  position:fixed;top:1.25rem;right:1.25rem;
  z-index:15;width:310px;
  max-height:calc(100vh - 130px);
  border-radius:.625rem;
  padding:1.1rem;
  overflow-y:auto;scrollbar-width:none;
  display:flex;flex-direction:column;gap:.9rem;
  opacity:0;transition:opacity .45s;
}
#analysis::-webkit-scrollbar{display:none}
#analysis.show{opacity:1}

/* ── Gauge ── */
#gauge-wrap{display:flex;flex-direction:column;align-items:center}
#gauge-svg{width:100%;max-width:270px;overflow:visible}

/* ── Lens buttons ── */
.lens-btns{display:flex;gap:.3rem}
.lbtn{
  flex:1;padding:.38rem .2rem;
  background:transparent;
  border:1px solid rgba(255,255,255,.1);
  border-radius:.25rem;
  color:rgba(226,226,230,.45);
  font-family:'Inter',sans-serif;font-size:.53rem;font-weight:600;
  letter-spacing:.07em;text-transform:uppercase;
  cursor:pointer;transition:all .2s;
}
.lbtn.on{
  background:rgba(238,188,6,.1);
  border-color:rgba(238,188,6,.6);
  color:#eebc06;
}
.lbtn:hover:not(.on){
  border-color:rgba(255,255,255,.2);
  color:rgba(226,226,230,.7);
}

/* ── Lens content ── */
#lens-content{display:flex;flex-direction:column;gap:.85rem;transition:opacity .22s,transform .22s}
#lens-content.fade{opacity:0;transform:translateY(4px)}

.sec-hdr{
  font-size:.52rem;font-weight:600;
  letter-spacing:.17em;text-transform:uppercase;
  color:rgba(226,226,230,.32);margin-bottom:.4rem;
}

/* Technique rows */
.t-row{display:flex;align-items:center;gap:.45rem;margin-bottom:.3rem}
.t-name{font-size:.7rem;color:rgba(226,226,230,.72);font-weight:500;flex:1}
.t-bar-bg{width:44px;height:2px;background:rgba(255,255,255,.06);border-radius:1px;overflow:hidden}
.t-bar{height:100%;background:#eebc06;border-radius:1px;transition:width .55s ease}
.t-cnt{font-size:.58rem;font-weight:700;color:#eebc06;width:14px;text-align:right}

/* Summary */
.summary{
  font-family:'Lora',serif;font-style:italic;
  font-size:.76rem;line-height:1.68;
  color:rgba(226,226,230,.72);
}

/* Meta pills */
.pill{
  display:inline-flex;align-items:center;gap:.25rem;
  font-size:.58rem;font-weight:500;
  background:rgba(255,255,255,.04);
  border:1px solid rgba(255,255,255,.07);
  padding:.12rem .42rem;border-radius:2rem;
  letter-spacing:.04em;text-transform:uppercase;
  color:rgba(226,226,230,.5);
}

/* ── History strip ── */
#history{
  position:fixed;bottom:0;left:0;right:0;
  z-index:15;
  padding:.65rem 1.25rem .75rem;
  background:linear-gradient(to top,rgba(6,8,16,.97) 0%,rgba(6,8,16,0) 100%);
}
#h-lbl{
  font-size:.52rem;font-weight:600;
  letter-spacing:.2em;color:rgba(226,226,230,.28);
  text-transform:uppercase;margin-bottom:.45rem;
}
#h-scroll{display:flex;gap:.6rem;overflow-x:auto;scrollbar-width:none;padding-bottom:.2rem}
#h-scroll::-webkit-scrollbar{display:none}
.hcard{
  flex-shrink:0;width:172px;
  padding:.55rem .65rem;
  border-radius:.375rem;cursor:pointer;
  border:1px solid rgba(255,255,255,.07);
  transition:border-color .2s,transform .15s;
}
.hcard:hover{border-color:rgba(238,188,6,.3)!important;transform:translateY(-2px)}
.hcard-domain{
  font-size:.7rem;font-weight:600;color:#e2e2e6;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:110px;
}
.hbadge{
  font-size:.62rem;font-weight:700;
  padding:.08rem .32rem;border-radius:.2rem;
}

/* ── Fade-in ── */
@keyframes fadeUp{from{opacity:0;transform:translateY(5px)}to{opacity:1;transform:none}}
.fade-in{animation:fadeUp .3s ease}
</style>
</head>
<body>

<div id="map"></div>
<div id="scan-badge">&#11044; Scanning Narrative DNA...</div>

<!-- Header -->
<div id="header">
  <h1>PROPAGANDA<em>PULSE</em></h1>
  <p>Narrative Analysis Engine &nbsp;//&nbsp; OSINT Terminal</p>
</div>

<!-- URL Bar -->
<div id="url-bar">
  <input id="url-input" type="url" placeholder="Paste article URL to analyze narrative..." autocomplete="off" spellcheck="false">
  <button id="analyze-btn" onclick="doAnalyze()">ANALYZE</button>
</div>

<!-- Stats (left) -->
<div id="stats" class="glass">
  <div class="stat-lbl">Global Pulse</div>
  <div style="display:flex;gap:.75rem">
    <div><div class="stat-lbl">Analyses</div><div class="stat-val" id="s-count">0</div></div>
    <div><div class="stat-lbl">Avg Bias</div><div class="stat-val" id="s-avg">—</div></div>
  </div>
  <div class="hr"></div>
  <div>
    <div class="stat-lbl" style="display:flex;align-items:center;gap:.3rem">
      <svg width="9" height="9" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="12" cy="12" r="10"/><path d="M2 12h20M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/></svg>
      Countries Tracked
    </div>
    <div class="stat-val" id="s-countries">0</div>
  </div>
  <div class="hr"></div>
  <div>
    <div class="stat-lbl">Top Techniques</div>
    <div id="s-techniques" style="margin-top:.35rem;display:flex;flex-direction:column;gap:.28rem">
      <div style="color:rgba(226,226,230,.28);font-size:.68rem">No data yet</div>
    </div>
  </div>
</div>

<!-- Analysis Panel (right) -->
<div id="analysis" class="glass">

  <!-- Source -->
  <div>
    <div style="font-size:.88rem;font-weight:600;color:#e2e2e6;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" id="a-domain">—</div>
    <div style="display:flex;gap:.35rem;flex-wrap:wrap;margin-top:.38rem" id="a-meta"></div>
  </div>

  <div class="hr"></div>

  <!-- Gauge -->
  <div id="gauge-wrap">
    <svg id="gauge-svg" viewBox="0 0 270 158">
      <defs>
        <linearGradient id="gg" x1="0%" y1="0%" x2="100%" y2="0%">
          <stop offset="0%"   stop-color="#4a6fa5"/>
          <stop offset="28%"  stop-color="#2aaa8c"/>
          <stop offset="50%"  stop-color="#d4a204"/>
          <stop offset="72%"  stop-color="#e07a2f"/>
          <stop offset="100%" stop-color="#c64b4b"/>
        </linearGradient>
        <filter id="glow" x="-30%" y="-30%" width="160%" height="160%">
          <feGaussianBlur stdDeviation="3" result="b"/>
          <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
        </filter>
      </defs>
      <!-- Background track -->
      <path id="g-track" fill="none" stroke="rgba(255,255,255,0.06)" stroke-width="13" stroke-linecap="round"/>
      <!-- Gradient arc -->
      <path id="g-arc"   fill="none" stroke="url(#gg)" stroke-width="11" stroke-linecap="round" opacity=".92"/>
      <!-- Needle -->
      <line id="g-needle" stroke="#eebc06" stroke-width="2.5" stroke-linecap="round" filter="url(#glow)"/>
      <circle id="g-hub" r="5" fill="#eebc06"/>
      <!-- Score -->
      <text id="g-score"  text-anchor="middle" font-family="Inter,sans-serif" font-weight="700" font-size="22" fill="#e2e2e6"/>
      <text id="g-label"  text-anchor="middle" font-family="Lora,serif" font-size="7.5" fill="rgba(226,226,230,0.42)" letter-spacing="1.8"/>
    </svg>
  </div>

  <div class="hr"></div>

  <!-- Lens selector -->
  <div class="lens-btns">
    <button class="lbtn on" data-lens="geopolitical"  onclick="switchLens('geopolitical',this)">Geopolitical</button>
    <button class="lbtn"    data-lens="institutional" onclick="switchLens('institutional',this)">Institutional</button>
    <button class="lbtn"    data-lens="sociopolitical" onclick="switchLens('sociopolitical',this)">Socio-Political</button>
  </div>

  <!-- Lens content -->
  <div id="lens-content">
    <div>
      <div class="sec-hdr">Detected Techniques</div>
      <div id="l-techs"></div>
    </div>
    <div class="hr"></div>
    <div>
      <div class="sec-hdr">Narrative Assessment</div>
      <p id="l-summary" class="summary"></p>
    </div>
  </div>

</div>

<!-- History -->
<div id="history">
  <div id="h-lbl">Recent Intercepts</div>
  <div id="h-scroll"></div>
</div>

<script>
// ═══════════════════════════════════════════════════════════
// MAP
// ═══════════════════════════════════════════════════════════
const map = L.map('map',{center:[20,0],zoom:2,zoomControl:false,attributionControl:false});

L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_nolabels/{z}/{x}/{y}{r}.png',{
  subdomains:'abcd',maxZoom:20
}).addTo(map);

L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Reference/MapServer/tile/{z}/{y}/{x}',{
  pane:'overlayPane',maxZoom:16,opacity:.78
}).addTo(map);

// ═══════════════════════════════════════════════════════════
// GAUGE
// ═══════════════════════════════════════════════════════════
const GCX=135, GCY=142, GR=98;

function gaugeArc(r){
  return `M ${GCX-r} ${GCY} A ${r} ${r} 0 1 1 ${GCX+r} ${GCY}`;
}
function needlePt(score,r){
  const a = Math.PI*(100-score)/200;
  return {x:GCX+r*Math.cos(a), y:GCY-r*Math.sin(a)};
}

function drawGauge(score,lensLabel){
  const d = gaugeArc(GR);
  document.getElementById('g-track').setAttribute('d',d);
  document.getElementById('g-arc').setAttribute('d',d);

  const tip  = needlePt(score, GR-2);
  const hub  = {x:GCX, y:GCY};
  const n    = document.getElementById('g-needle');
  n.setAttribute('x1',hub.x); n.setAttribute('y1',hub.y);
  n.setAttribute('x2',tip.x.toFixed(2)); n.setAttribute('y2',tip.y.toFixed(2));

  const hc = document.getElementById('g-hub');
  hc.setAttribute('cx',hub.x); hc.setAttribute('cy',hub.y);

  const sign = score>0?'+':'';
  const gs   = document.getElementById('g-score');
  gs.setAttribute('x',GCX); gs.setAttribute('y',GCY-12);
  gs.textContent = sign+Math.round(score);
  gs.setAttribute('fill', score<-20?'#4a6fa5':score>20?'#c64b4b':'#d4a204');

  const gl = document.getElementById('g-label');
  gl.setAttribute('x',GCX); gl.setAttribute('y',GCY+5);
  gl.textContent = lensLabel.toUpperCase();
}

// ═══════════════════════════════════════════════════════════
// STATE
// ═══════════════════════════════════════════════════════════
let current=null, activeLens='geopolitical', circles=[], localHistory=[];

// ═══════════════════════════════════════════════════════════
// MARKERS
// ═══════════════════════════════════════════════════════════
function setMarkers(lat,lng,score){
  circles.forEach(c=>map.removeLayer(c));
  circles=[];
  const col = score<-20?'#4a6fa5':score>20?'#c64b4b':'#eebc06';
  [[36,.04,.4],[18,.09,.5],[6,1,1]].forEach(([r,fo,op])=>{
    const c=L.circleMarker([lat,lng],{
      radius:r, color:r===6?'#eebc06':col,
      fillColor:r===6?'#eebc06':col,
      fillOpacity:fo, weight:r===6?2:1, opacity:op
    }).addTo(map);
    circles.push(c);
  });
}

// ═══════════════════════════════════════════════════════════
// LENS RENDER
// ═══════════════════════════════════════════════════════════
const LENS_LABELS = {
  geopolitical:'Geopolitical Lens',
  institutional:'Institutional Lens',
  sociopolitical:'Socio-Political Lens'
};

function renderLens(data, key){
  const lc=document.getElementById('lens-content');
  lc.classList.add('fade');
  setTimeout(()=>{
    const maxW=[88,68,50,34];
    document.getElementById('l-techs').innerHTML =
      data.techniques.map((t,i)=>`
        <div class="t-row">
          <span class="t-name">${t}</span>
          <div class="t-bar-bg"><div class="t-bar" style="width:${maxW[i]||20}%"></div></div>
          <span class="t-cnt">${Math.round(maxW[i]||20/10)}</span>
        </div>`).join('');
    document.getElementById('l-summary').textContent = data.summary;
    lc.classList.remove('fade');
    lc.classList.add('fade-in');
    setTimeout(()=>lc.classList.remove('fade-in'),350);
  },190);
}

function switchLens(key,btn){
  activeLens=key;
  document.querySelectorAll('.lbtn').forEach(b=>b.classList.toggle('on',b===btn));
  if(current){
    renderLens(current.lenses[key],key);
    drawGauge(current.lenses[key].score, LENS_LABELS[key]);
  }
}

// ═══════════════════════════════════════════════════════════
// PANEL POPULATION
// ═══════════════════════════════════════════════════════════
function showPanel(r){
  current=r;

  document.getElementById('a-domain').textContent=r.domain;

  const ac=r.biasScore<-20?'#4a6fa5':r.biasScore>20?'#c64b4b':'#eebc06';
  document.getElementById('a-meta').innerHTML=`
    <span class="pill">
      <svg width="8" height="8" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
        <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/>
      </svg>${r.primaryCountry}
    </span>
    <span class="pill" style="color:${ac}">${r.alignment}</span>
    <span class="pill">${r.sourceType}</span>`;

  // Reset to geopolitical lens
  document.querySelectorAll('.lbtn').forEach(b=>b.classList.toggle('on',b.dataset.lens==='geopolitical'));
  activeLens='geopolitical';

  drawGauge(r.lenses.geopolitical.score,'Geopolitical Lens');
  renderLens(r.lenses.geopolitical,'geopolitical');

  document.getElementById('analysis').classList.add('show');
}

// ═══════════════════════════════════════════════════════════
// HISTORY
// ═══════════════════════════════════════════════════════════
function biasMeta(score){
  if(score<-40) return {bg:'rgba(74,111,165,.2)',c:'#4a6fa5',b:'rgba(74,111,165,.3)'};
  if(score<-10) return {bg:'rgba(74,111,165,.12)',c:'#7099c0',b:'rgba(74,111,165,.2)'};
  if(score>40)  return {bg:'rgba(198,75,75,.2)',c:'#c64b4b',b:'rgba(198,75,75,.3)'};
  if(score>10)  return {bg:'rgba(198,75,75,.12)',c:'#c97e7e',b:'rgba(198,75,75,.2)'};
  return {bg:'rgba(238,188,6,.15)',c:'#eebc06',b:'rgba(238,188,6,.28)'};
}

function renderHistory(){
  const wrap=document.getElementById('h-scroll');
  wrap.innerHTML=localHistory.map(r=>{
    const m=biasMeta(r.biasScore);
    const sign=r.biasScore>0?'+':'';
    return `<div class="hcard glass-light" onclick='pickHistory("${r.id}")'>
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:.28rem">
        <span class="hcard-domain">${r.domain}</span>
        <span class="hbadge" style="background:${m.bg};color:${m.c};border:1px solid ${m.b}">${sign}${r.biasScore.toFixed(1)}</span>
      </div>
      <div style="display:flex;gap:.3rem;align-items:center">
        <span style="font-size:.58rem;color:rgba(226,226,230,.38)">${r.primaryCountryCode}</span>
        <span style="color:rgba(255,255,255,.15);font-size:.58rem">·</span>
        <span style="font-size:.58rem;color:rgba(226,226,230,.38);text-transform:capitalize">${r.alignment}</span>
      </div>
    </div>`;
  }).join('');
}

function pickHistory(id){
  const r=localHistory.find(h=>h.id===id);
  if(!r) return;
  showPanel(r);
  setMarkers(r.primaryLat,r.primaryLng,r.biasScore);
  map.flyTo([r.primaryLat,r.primaryLng],5,{duration:2.2,easeLinearity:.2});
}

// ═══════════════════════════════════════════════════════════
// STATS
// ═══════════════════════════════════════════════════════════
function updateStats(){
  const n=localHistory.length;
  document.getElementById('s-count').textContent=n;
  if(n>0){
    const avg=localHistory.reduce((s,r)=>s+r.biasScore,0)/n;
    const sign=avg>0?'+':'';
    document.getElementById('s-avg').innerHTML=`${sign}${avg.toFixed(1)}<small> ${avg>0?'R':'L'}</small>`;
  }
  const cx=new Set(localHistory.map(r=>r.primaryCountryCode));
  document.getElementById('s-countries').textContent=cx.size;

  const tc={};
  localHistory.forEach(r=>(r.lenses?.geopolitical?.techniques||[]).forEach(t=>{tc[t]=(tc[t]||0)+1}));
  const top=Object.entries(tc).sort((a,b)=>b[1]-a[1]).slice(0,4);
  const el=document.getElementById('s-techniques');
  el.innerHTML=top.length===0
    ?'<div style="color:rgba(226,226,230,.28);font-size:.68rem">No data yet</div>'
    :top.map(([t,c])=>`
      <div style="display:flex;justify-content:space-between;align-items:center">
        <span style="font-size:.66rem;color:rgba(226,226,230,.62)">${t}</span>
        <span style="font-size:.62rem;font-weight:700;color:#eebc06">${c}</span>
      </div>`).join('');
}

// ═══════════════════════════════════════════════════════════
// ANALYZE
// ═══════════════════════════════════════════════════════════
async function doAnalyze(){
  const inp=document.getElementById('url-input');
  const btn=document.getElementById('analyze-btn');
  const bar=document.getElementById('url-bar');
  const badge=document.getElementById('scan-badge');
  const url=inp.value.trim();
  if(!url){inp.focus();return;}

  btn.disabled=true;btn.textContent='...';
  bar.style.opacity='0';bar.style.pointerEvents='none';
  badge.style.display='block';

  try{
    const res=await fetch('/analyze',{
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({url})
    });
    if(!res.ok)throw new Error('fail');
    const r=await res.json();

    showPanel(r);
    setMarkers(r.primaryLat,r.primaryLng,r.biasScore);
    map.flyTo([r.primaryLat,r.primaryLng],5,{duration:2.2,easeLinearity:.2});

    localHistory.unshift(r);
    if(localHistory.length>20)localHistory.pop();
    renderHistory();
    updateStats();
    inp.value='';
  }catch(e){
    alert('Analysis failed — check the URL and try again.');
  }finally{
    btn.disabled=false;btn.textContent='ANALYZE';
    badge.style.display='none';
    bar.style.opacity='1';bar.style.pointerEvents='';
  }
}

document.getElementById('url-input').addEventListener('keydown',e=>{if(e.key==='Enter')doAnalyze()});

// ═══════════════════════════════════════════════════════════
// BOOT
// ═══════════════════════════════════════════════════════════
(async()=>{
  try{
    const r=await fetch('/history');
    localHistory=await r.json();
    renderHistory();
    updateStats();
    if(localHistory.length>0){
      const first=localHistory[0];
      showPanel(first);
      setMarkers(first.primaryLat,first.primaryLng,first.biasScore);
    }
  }catch(_){}
})();
</script>
</body>
</html>"""


# ══════════════════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print()
    print("  ██████╗ ██████╗  ██████╗ ██████╗ ")
    print("  ██╔══██╗██╔══██╗██╔═══██╗██╔══██╗")
    print("  ██████╔╝██████╔╝██║   ██║██████╔╝")
    print("  ██╔═══╝ ██╔═══╝ ██║   ██║██╔═══╝ ")
    print("  ██║     ██║     ╚██████╔╝██║     ")
    print("  ╚═╝     ╚═╝      ╚═════╝ ╚═╝     ")
    print()
    print("  Propaganda Pulse — OSINT Terminal")
    print("  ─────────────────────────────────")
    print("  http://localhost:8000")
    print()
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="warning")
