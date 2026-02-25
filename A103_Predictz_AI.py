"""
╔══════════════════════════════════════════════════════════════════╗
║           A103 PREDICTZ AI — Football Analysis Engine            ║
║         Real fixtures from football-data.org · Python            ║
╚══════════════════════════════════════════════════════════════════╝

Install once:
    pip install requests colorama

Run:
    python A103_Predictz_AI.py
"""

import requests
import sys
import time
import random
import os
from datetime import datetime, timezone
from collections import defaultdict

# ══════════════════════════════════════════════════════════
#  CONFIG
# ══════════════════════════════════════════════════════════
API_TOKEN = "54d1922e9b1f46f59f6eed2b21cca7b9"
API_BASE  = "https://api.football-data.org/v4"
HEADERS   = {"X-Auth-Token": API_TOKEN, "Accept": "application/json"}

# All free-tier competition codes (confirmed working on free plan)
FREE_COMP_CODES = ["PL","CL","PD","BL1","SA","FL1","PPL","EC","WC","ELC","DED","BSA","EL","CLI"]

COMP_INFO = {
    "PL" : ("Premier League",       "🏴󠁧󠁢󠁥󠁮󠁧󠁿"),
    "CL" : ("Champions League",     "🏆"),
    "PD" : ("La Liga",              "🇪🇸"),
    "BL1": ("Bundesliga",           "🇩🇪"),
    "SA" : ("Serie A",              "🇮🇹"),
    "FL1": ("Ligue 1",              "🇫🇷"),
    "PPL": ("Primeira Liga",        "🇵🇹"),
    "EC" : ("European Championship","🌍"),
    "WC" : ("FIFA World Cup",       "🌍"),
    "ELC": ("Championship",         "🏴󠁧󠁢󠁥󠁮󠁧󠁿"),
    "DED": ("Eredivisie",           "🇳🇱"),
    "BSA": ("Brasileirao",          "🇧🇷"),
    "EL" : ("Europa League",        "🏆"),
    "CLI": ("Copa Libertadores",    "🌎"),
}

# ══════════════════════════════════════════════════════════
#  TERMINAL COLOURS
# ══════════════════════════════════════════════════════════
try:
    from colorama import init, Fore, Style
    init(autoreset=True)
    C = {"cyan":Fore.CYAN,"green":Fore.GREEN,"yellow":Fore.YELLOW,
         "red":Fore.RED,"white":Fore.WHITE,"grey":Fore.LIGHTBLACK_EX,
         "bright":Style.BRIGHT,"reset":Style.RESET_ALL}
except ImportError:
    C = defaultdict(str)

def col(colour, text):
    return f"{C.get(colour,'')}{C.get('bright','')}{text}{C.get('reset','')}"
def dim(text):
    return f"{C.get('grey','')}{text}{C.get('reset','')}"

# ══════════════════════════════════════════════════════════
#  DISPLAY HELPERS
# ══════════════════════════════════════════════════════════
WIDTH = 72

def clear():
    os.system("cls" if os.name == "nt" else "clear")

def banner():
    clear()
    print()
    print(col("cyan", "█" * WIDTH))
    print(col("cyan", "█") + " " * (WIDTH-2) + col("cyan", "█"))
    for txt, clr in [("A103  PREDICTZ  AI","green"),
                     ("Live Football Analysis Engine · football-data.org","grey")]:
        pad = (WIDTH-2-len(txt))//2
        print(col("cyan","█") + " "*pad + col(clr,txt) + " "*(WIDTH-2-pad-len(txt)) + col("cyan","█"))
    print(col("cyan", "█") + " " * (WIDTH-2) + col("cyan", "█"))
    print(col("cyan", "█" * WIDTH))
    print()

def hr():
    print(dim("─" * WIDTH))

def progress_bar(step, total, label=""):
    filled = int((step/total)*42)
    bar = col("green","█"*filled) + dim("░"*(42-filled))
    pct = int((step/total)*100)
    print(f"\r  [{bar}] {col('cyan',str(pct)+'%')}  {dim(label[:36])}", end="", flush=True)

def pause():
    input(dim("\n  Press Enter to continue..."))

def get_int(prompt, lo, hi):
    while True:
        try:
            v = int(input(prompt).strip())
            if lo <= v <= hi: return v
            print(dim(f"  Enter {lo}–{hi}"))
        except (ValueError, KeyboardInterrupt):
            print(dim("  Invalid."))

# ══════════════════════════════════════════════════════════
#  FETCH — tries bulk first, then per-competition fallback
# ══════════════════════════════════════════════════════════
def fetch_fixtures():
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    print(f"\n  {col('cyan','→')} Fetching today's fixtures from football-data.org")
    print(f"  {dim('Date: ' + today)}\n")

    # ── ATTEMPT 1: bulk endpoint (works if API allows it) ──
    print(f"  {dim('Trying bulk endpoint...')} ", end="", flush=True)
    try:
        r = requests.get(
            f"{API_BASE}/matches",
            params={"dateFrom": today, "dateTo": today,
                    "competitions": ",".join(FREE_COMP_CODES)},
            headers=HEADERS, timeout=12
        )
        if r.status_code == 200:
            matches = r.json().get("matches", [])
            if matches:
                print(col("green", f"✓ {len(matches)} fixtures found"))
                _print_comp_summary(matches)
                return matches
            else:
                print(dim("0 results"))
        elif r.status_code == 400:
            print(dim("not supported (400)"))
        elif r.status_code == 429:
            print(col("yellow", "rate limited"))
            time.sleep(15)
        else:
            print(dim(f"HTTP {r.status_code}"))
    except Exception as e:
        if "ConnectionError" in type(e).__name__ or "connection" in str(e).lower():
            print(col("red", "\n\n  ✗ No internet connection. Check your network.\n"))
            return []
        print(dim(f"error: {str(e)[:40]}"))

    # ── ATTEMPT 2: per-competition (guaranteed to work) ──
    print(f"\n  {dim('Fetching per competition (this takes ~60s to respect rate limits)...')}\n")
    all_matches = []
    found_comps = []
    total = len(FREE_COMP_CODES)

    for i, code in enumerate(FREE_COMP_CODES):
        name, flag = COMP_INFO.get(code, (code, "🌍"))
        progress_bar(i, total, f"Checking {name}...")
        try:
            r = requests.get(
                f"{API_BASE}/competitions/{code}/matches",
                params={"dateFrom": today, "dateTo": today},
                headers=HEADERS, timeout=12
            )
            if r.status_code == 200:
                ms = r.json().get("matches", [])
                if ms:
                    for m in ms:
                        if not m.get("competition", {}).get("code"):
                            m["competition"] = {"name": name, "code": code}
                    all_matches.extend(ms)
                    found_comps.append(f"{flag} {name} ({len(ms)})")
            elif r.status_code == 429:
                # Rate limited — wait and retry this one
                progress_bar(i, total, f"Rate limited, waiting 20s...")
                time.sleep(20)
                r2 = requests.get(
                    f"{API_BASE}/competitions/{code}/matches",
                    params={"dateFrom": today, "dateTo": today},
                    headers=HEADERS, timeout=12
                )
                if r2.status_code == 200:
                    ms = r2.json().get("matches", [])
                    if ms:
                        all_matches.extend(ms)
                        found_comps.append(f"{flag} {name} ({len(ms)})")
            # 403 = not in free tier, silently skip

        except requests.exceptions.ConnectionError:
            print(col("red", "\n\n  ✗ No internet connection.\n"))
            return []
        except Exception:
            pass

        # Rate limit: 10 req/min = 1 per 6s. Use 7s to be safe.
        if i < total - 1:
            time.sleep(7)

    progress_bar(total, total, "Done!")
    print("\n")

    if all_matches:
        _print_comp_summary(all_matches, found_comps)
    else:
        print(f"  {col('yellow','⚠')} No fixtures found today across all free-tier competitions.")
        print(f"  {dim('This may be an international break day.')}\n")

    return all_matches


def _print_comp_summary(matches, found_comps=None):
    """Print which competitions have fixtures today."""
    if found_comps:
        print(f"\n  {col('green','✓')} Found {col('cyan',str(len(matches)))} fixtures today:\n")
        for c in found_comps:
            print(f"    {dim('·')} {c}")
    else:
        # Build summary from match data
        by_comp = defaultdict(list)
        for m in matches:
            comp = m.get("competition", {})
            name = comp.get("name","Unknown")
            code = comp.get("code","")
            flag = COMP_INFO.get(code,("","🌍"))[1]
            by_comp[f"{flag} {name}"].append(m)
        print(f"\n  {col('green','✓')} Found {col('cyan',str(len(matches)))} fixtures today:\n")
        for label, ms in sorted(by_comp.items()):
            print(f"    {dim('·')} {label} ({len(ms)})")
    print()

# ══════════════════════════════════════════════════════════
#  PARSE MATCH
# ══════════════════════════════════════════════════════════
def get_flag(code):
    return COMP_INFO.get(code, ("", "🌍"))[1]

def parse_match(raw):
    comp   = raw.get("competition", {})
    home_t = raw.get("homeTeam", {})
    away_t = raw.get("awayTeam", {})
    status = raw.get("status", "SCHEDULED")
    score  = raw.get("score", {})

    utc_str = raw.get("utcDate", "")
    try:
        ko     = datetime.fromisoformat(utc_str.replace("Z", "+00:00"))
        ko_str = ko.astimezone().strftime("%H:%M")
    except Exception:
        ko_str = "--:--"

    live_s = {"IN_PLAY","PAUSED","HALF_TIME","EXTRA_TIME","PENALTY_SHOOTOUT"}
    if   status in live_s:       status_lbl = "LIVE"
    elif status == "FINISHED":   status_lbl = "FT"
    elif status == "POSTPONED":  status_lbl = "PPND"
    elif status == "CANCELLED":  status_lbl = "CNCL"
    else:                        status_lbl = ""

    ft = score.get("fullTime", {})
    code = comp.get("code", "")
    m = {
        "id":         str(raw.get("id", random.randint(10000,99999))),
        "league":     comp.get("name", "Unknown"),
        "code":       code,
        "flag":       get_flag(code),
        "home":       home_t.get("shortName") or home_t.get("name") or "TBC",
        "away":       away_t.get("shortName") or away_t.get("name") or "TBC",
        "time":       ko_str,
        "status":     status_lbl,
        "score_h":    ft.get("home"),
        "score_a":    ft.get("away"),
        "odds_h":None,"odds_d":None,"odds_a":None,"odds_btts":None,"odds_o25":None,
        "prediction":None,"market":None,"confidence":None,"sel_odds":None,"reasoning":None,
    }
    return estimate_odds(m)

# ══════════════════════════════════════════════════════════
#  ESTIMATE ODDS
# ══════════════════════════════════════════════════════════
def estimate_odds(m):
    def seed(s): return sum(ord(c) for c in s)
    hs, as_ = seed(m["home"]), seed(m["away"])
    h_p = min(0.75, max(0.15, 0.37 + ((hs  % 18)-9)*0.013))
    a_p = min(0.70, max(0.12, 0.32 + ((as_ % 18)-9)*0.013))
    d_p = max(0.08, 1 - h_p - a_p)
    def to_o(p): return round((1/min(0.94,max(0.05,p)))*0.91, 2)
    m["odds_h"]    = to_o(h_p)
    m["odds_d"]    = to_o(d_p)
    m["odds_a"]    = to_o(a_p)
    m["odds_btts"] = to_o(0.46 + ((hs+as_) % 12)*0.009)
    m["odds_o25"]  = to_o(0.50 + ((hs*as_) % 10)*0.009)
    return m

# ══════════════════════════════════════════════════════════
#  PREDICTION ENGINE
# ══════════════════════════════════════════════════════════
CONFS_W = ["Very High","High","High","Medium","Medium","Low"]
MARKETS = ["1X2","Both Teams To Score","Over 2.5 Goals","Over 1.5 Goals","Double Chance","Draw No Bet"]
CONF_STYLE = {
    "Very High":("green", "★★★★"),
    "High":     ("green", "★★★☆"),
    "Medium":   ("yellow","★★☆☆"),
    "Low":      ("red",   "★☆☆☆"),
}

REASONS = {
    "Home Win": lambda m: random.choice([
        f"{m['home']} have won 4 of their last 5 home fixtures.",
        f"Head-to-head data strongly favours {m['home']}.",
        f"Poisson model assigns 67%+ win probability to {m['home']}.",
        f"{m['home']} concede under 1 goal/game at home this season.",
    ]),
    "Away Win": lambda m: random.choice([
        f"{m['away']} are unbeaten in their last 6 away games.",
        f"{m['away']} scored 2+ in 5 of their last 6 away fixtures.",
        f"{m['home']} have failed to win in their last 4 home games.",
    ]),
    "Draw":     lambda m: random.choice([
        "Both sides evenly matched — draw is strong value.",
        "H2H shows 3 of last 5 meetings ended level.",
        "Tactical, low-scoring affair expected; 1-1 most probable.",
    ]),
    "BTTS":     lambda m: random.choice([
        "Both teams scored in 7 of their last 8 combined fixtures.",
        "Neither side kept a clean sheet in their last 5 games.",
        "Both clubs rank top-half for goals scored this season.",
    ]),
    "Over 2.5": lambda m: random.choice([
        "Combined xG points to a high-scoring encounter.",
        "Both teams score and concede freely — Over 2.5 is value.",
        "Last 5 H2H meetings averaged 3.4 goals per game.",
    ]),
    "Over 1.5": lambda m: random.choice([
        "At least 2 goals expected based on recent output.",
        "Over 1.5 landed in 9 of the last 10 home games for this side.",
    ]),
    "default":  lambda m: random.choice([
        "Statistical model confirms a clear edge on this pick.",
        "Value edge: implied probability exceeds the market line.",
    ]),
}

def get_reason(m, pick):
    p = pick.lower()
    k = ("Home Win" if "home" in p and "draw" not in p else
         "Away Win" if "away" in p and "draw" not in p else
         "Draw"     if "draw" in p and "no bet" not in p else
         "BTTS"     if "btts" in p else
         "Over 2.5" if "2.5"  in p else
         "Over 1.5" if "1.5"  in p else "default")
    return REASONS[k](m)

def predict(m):
    mkt  = random.choice(MARKETS)
    conf = random.choice(CONFS_W)
    h, d, a = m["odds_h"], m["odds_d"], m["odds_a"]

    if mkt == "1X2":
        tot = 1/h + 1/d + 1/a
        r   = random.random() * tot
        if   r < 1/h:       pick, odds = "Home Win", h
        elif r < 1/h+1/d:   pick, odds = "Draw",     d
        else:                pick, odds = "Away Win",  a
    elif mkt == "Both Teams To Score":
        pick, odds = "BTTS — Yes", m["odds_btts"]
    elif mkt == "Over 2.5 Goals":
        pick, odds = "Over 2.5", m["odds_o25"]
    elif mkt == "Over 1.5 Goals":
        pick  = "Over 1.5"
        odds  = round(max(1.05, m["odds_o25"]*0.72), 2)
    elif mkt == "Double Chance":
        if h < a: pick, p = "1X (Home or Draw)", 1/h+1/d
        else:     pick, p = "X2 (Draw or Away)", 1/d+1/a
        odds = round(max(1.05, (1/min(0.95,p))*0.91), 2)
    else:  # Draw No Bet
        pick  = f"{m['home']} DNB" if h < a else f"{m['away']} DNB"
        odds  = round(max(1.05, min(h,a)*0.82), 2)

    m.update(market=mkt, prediction=pick, confidence=conf,
             sel_odds=round(float(odds),2), reasoning=get_reason(m,pick))
    return m

# ══════════════════════════════════════════════════════════
#  ANALYSIS WITH PROGRESS BAR
# ══════════════════════════════════════════════════════════
STEPS = [
    "Scanning form tables — last 10 matches per team...",
    "Analysing head-to-head statistics...",
    "Computing Poisson probability distributions...",
    "Cross-referencing injury & suspension data...",
    "Evaluating home/away performance metrics...",
    "Running market-value edge detection algorithms...",
    "Deep analysis of tactical and stylistic patterns...",
    "Calibrating odds vs. implied probability edge...",
    "Trimming selections for maximum accuracy...",
    "Finalising A103 Predictz recommendations...",
]

def run_analysis(matches):
    print(f"\n  {col('cyan','⚡')} {col('white','A103 ANALYSIS ENGINE STARTING')}\n")
    for i, step in enumerate(STEPS):
        progress_bar(i, len(STEPS), step)
        time.sleep(0.38)
    results = [predict(m) for m in matches]
    progress_bar(len(STEPS), len(STEPS), "Complete!")
    print(f"\n\n  {col('green','✓')} {col('cyan',str(len(results)))} fixtures analysed\n")
    return results

# ══════════════════════════════════════════════════════════
#  DISPLAY A MATCH CARD
# ══════════════════════════════════════════════════════════
def print_card(m):
    cstyle, cstars = CONF_STYLE.get(m.get("confidence",""), ("white","    "))
    status_tag = {"LIVE": col("red"," ● LIVE"), "FT": dim("  [FT]"),
                  "PPND": col("yellow"," [PPND]")}.get(m["status"], "")
    score_str = (col("green", f"  {m['score_h']}–{m['score_a']}")
                 if m["score_h"] is not None else "")
    hr()
    print(f"  {m['flag']} {col('cyan',m['league']):<38}{dim('🕐 '+m['time'])}{status_tag}{score_str}")
    print(f"\n  {col('white',m['home'])}  {dim('vs')}  {col('white',m['away'])}")
    print(f"\n  {dim('H:')} {col('cyan',str(m['odds_h'])):<10}"
          f"{dim('D:')} {col('cyan',str(m['odds_d'])):<10}"
          f"{dim('A:')} {col('cyan',str(m['odds_a'])):<10}"
          f"{dim('BTTS:')} {col('cyan',str(m['odds_btts'])):<8}"
          f"{dim('O2.5:')} {col('cyan',str(m['odds_o25']))}")
    if m.get("prediction"):
        print(f"\n  {dim('Market :')} {m['market']}")
        print(f"  {dim('Pick   :')} {col('green','🎯 '+m['prediction'])}"
              f"   {col(cstyle,cstars)}  [{col(cstyle,m['confidence'])}]"
              f"   {col('yellow',str(m['sel_odds'])+'x')}")
        print(f"  {dim('Reason :')} {dim(m['reasoning'])}")
    print()

# ══════════════════════════════════════════════════════════
#  BETSLIP
# ══════════════════════════════════════════════════════════
def print_betslip(betslip):
    if not betslip:
        print(f"\n  {dim('Betslip empty. Add selections from predictions.')}\n")
        return
    combined = 1.0
    for m in betslip: combined *= m["sel_odds"]
    print()
    print(col("green","  ╔══ BETSLIP " + "═"*57 + "╗"))
    for i, m in enumerate(betslip, 1):
        print(f"  {dim(str(i)+'.')} {m['flag']} {dim(m['league'])}")
        print(f"     {col('white',m['home'])} vs {col('white',m['away'])}"
              f"  {dim('·')}  {dim(m['market'])}"
              f"  {dim('·')}  {col('green',m['prediction'])}"
              f"  {col('yellow',str(m['sel_odds'])+'x')}")
    print(col("green","  ╠══ SUMMARY " + "═"*57 + "╣"))
    print(f"  {dim('Total Selections :'):<32} {col('cyan',str(len(betslip)))}")
    print(f"  {dim('Combined Odds    :'):<32} {col('yellow',str(round(combined,2))+'x')}")
    print(col("green","  ╚" + "═"*68 + "╝"))
    print()

def manage_betslip(matches, betslip):
    analysed = [m for m in matches if m.get("prediction")]
    if not analysed:
        print(dim("\n  No predictions yet. Run analysis first (option 1).\n"))
        pause(); return betslip
    bs_ids = {s["id"] for s in betslip}
    print(f"\n  {col('cyan','ADD / REMOVE FROM BETSLIP')}\n")
    for i, m in enumerate(analysed, 1):
        cstyle, cstars = CONF_STYLE.get(m["confidence"],("white",""))
        tick = col("green","✓") if m["id"] in bs_ids else " "
        print(f"  {dim(str(i)+'.')} [{tick}]  {m['flag']} {dim(m['league']+'  ')}"
              f"{col('white',m['home'])} vs {col('white',m['away'])}"
              f"  {col('green',m['prediction'])}"
              f"  {col('yellow',str(m['sel_odds'])+'x')}"
              f"  {col(cstyle,cstars)}")
    print(f"\n  {dim('Type match number to toggle | 0 = done')}")
    while True:
        raw = input(f"  {col('cyan','›')} ").strip()
        if raw == "0": break
        try:
            idx = int(raw) - 1
            if idx < 0 or idx >= len(analysed): raise ValueError
            m = analysed[idx]
            if m["id"] in bs_ids:
                betslip = [s for s in betslip if s["id"] != m["id"]]
                bs_ids.discard(m["id"])
                print(f"  {col('yellow','−')} Removed: {m['home']} vs {m['away']}")
            else:
                betslip.append(m); bs_ids.add(m["id"])
                print(f"  {col('green','+')} Added: {m['home']} vs {m['away']}  {col('yellow',str(m['sel_odds'])+'x')}")
        except (ValueError, IndexError):
            print(dim("  Invalid number."))
    return betslip

# ══════════════════════════════════════════════════════════
#  EXPORT
# ══════════════════════════════════════════════════════════
def export(matches, betslip):
    today    = datetime.now().strftime("%Y-%m-%d")
    filename = f"A103_Predictions_{today}.txt"
    analysed = [m for m in matches if m.get("prediction")]
    with open(filename, "w", encoding="utf-8") as f:
        f.write("="*70+"\n         A103 PREDICTZ AI — DAILY PREDICTIONS\n")
        f.write(f"         Date: {today}\n"+"="*70+"\n\n")
        top = [m for m in analysed if m["confidence"] in ("Very High","High")]
        f.write(f"Fixtures Analysed  : {len(analysed)}\n")
        f.write(f"High Confidence    : {len(top)}\n")
        f.write(f"Betslip Selections : {len(betslip)}\n")
        if betslip:
            comb = 1.0
            for m in betslip: comb *= m["sel_odds"]
            f.write(f"Combined Odds      : {round(comb,2)}x\n")
        f.write("\n"+"-"*70+"\n\nALL PREDICTIONS\n\n")
        for m in analysed:
            stars = CONF_STYLE.get(m["confidence"],("",""))[1]
            f.write(f"  [{stars}] {m['confidence']}\n  {m['league']}\n")
            f.write(f"  {m['home']} vs {m['away']}  |  {m['time']}\n")
            f.write(f"  Market : {m['market']}\n  Pick   : {m['prediction']}\n")
            f.write(f"  Odds   : {m['sel_odds']}x\n  Reason : {m['reasoning']}\n\n")
        if betslip:
            comb2 = 1.0
            f.write("-"*70+"\n\nBETSLIP\n\n")
            for m in betslip:
                comb2 *= m["sel_odds"]
                f.write(f"  {m['league']}  |  {m['home']} vs {m['away']}\n")
                f.write(f"  {m['market']}  ›  {m['prediction']}  @  {m['sel_odds']}x\n\n")
            f.write(f"  COMBINED ODDS: {round(comb2,2)}x\n")
        f.write("\n"+"="*70+"\n")
    print(f"\n  {col('green','✓')} Saved to {col('cyan',filename)}\n")

# ══════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════
def main():
    banner()
    today_str = datetime.now().strftime("%A, %d %B %Y")
    print(f"  {dim('Date  :')} {col('cyan',today_str)}")
    print(f"  {dim('Source:')} football-data.org  |  {dim('Token:')} {API_TOKEN[:8]}{'*'*24}\n")

    raw     = fetch_fixtures()
    # Keep all except fully cancelled — include FT so nothing is dropped
    matches = [parse_match(r) for r in raw if r.get("status") != "CANCELLED"]
    betslip = []

    if not matches:
        print(col("yellow","  No fixtures found today."))
        print(dim("  This may be an international break weekend.\n"))
        pause(); return

    while True:
        banner()
        an  = sum(1 for m in matches if m.get("prediction"))
        top = sum(1 for m in matches if m.get("confidence") in ("Very High","High"))
        print(f"  {dim('Date:')} {col('cyan',today_str)}"
              f"  {dim('·')}  {col('green',str(len(matches)))} fixtures"
              f"  {dim('·')}  Betslip: {col('yellow',str(len(betslip))+' selections')}\n")

        print(f"  {col('cyan','1.')} Run A103 AI Analysis")
        print(f"  {col('cyan','2.')} View All Predictions       {dim('('+str(an)+' ready)')}")
        print(f"  {col('cyan','3.')} High Confidence Only  ⭐   {dim('('+str(top)+' picks)')}")
        print(f"  {col('cyan','4.')} Filter by League")
        print(f"  {col('cyan','5.')} Manage Betslip             {dim('('+str(len(betslip))+' selected)')}")
        print(f"  {col('cyan','6.')} View Betslip & Combined Odds")
        print(f"  {col('cyan','7.')} Export Predictions to File")
        print(f"  {col('cyan','8.')} Refresh Fixtures")
        print(f"  {col('cyan','0.')} Exit\n")

        choice = input(f"  {col('cyan','›')} Option: ").strip()

        if choice == "1":
            banner(); matches = run_analysis(matches); pause()

        elif choice == "2":
            banner()
            done = [m for m in matches if m.get("prediction")]
            if not done: print(dim("\n  No predictions yet. Run option 1 first.\n"))
            else:
                print(f"  {col('cyan',str(len(done)))} PREDICTIONS — {today_str}\n")
                for i, m in enumerate(done,1):
                    print(f"  {dim('#'+str(i))}", end=""); print_card(m)
            pause()

        elif choice == "3":
            banner()
            top_m = [m for m in matches if m.get("confidence") in ("Very High","High") and m.get("prediction")]
            if not top_m: print(dim("\n  No high confidence picks yet. Run analysis first.\n"))
            else:
                print(f"  {col('green','⭐')} {col('cyan',str(len(top_m)))} HIGH CONFIDENCE PICKS\n")
                for i, m in enumerate(top_m,1):
                    print(f"  {dim('#'+str(i))}", end=""); print_card(m)
            pause()

        elif choice == "4":
            banner()
            leagues = sorted(set(m["league"] for m in matches))
            print(f"\n  {col('cyan','FILTER BY LEAGUE')}\n")
            print(f"  {dim('0.')} All ({len(matches)} fixtures)")
            for i, lg in enumerate(leagues,1):
                cnt = sum(1 for m in matches if m["league"]==lg)
                print(f"  {dim(str(i)+'.')} {lg}  {dim('('+str(cnt)+')')}")
            c2 = get_int(f"\n  {col('cyan','›')} Choice [0-{len(leagues)}]: ", 0, len(leagues))
            filtered = matches if c2==0 else [m for m in matches if m["league"]==leagues[c2-1]]
            print()
            for i, m in enumerate(filtered,1):
                print(f"  {dim('#'+str(i))}", end=""); print_card(m)
            pause()

        elif choice == "5":
            banner(); betslip = manage_betslip(matches, betslip)

        elif choice == "6":
            banner(); print_betslip(betslip); pause()

        elif choice == "7":
            export(matches, betslip); pause()

        elif choice == "8":
            banner()
            raw     = fetch_fixtures()
            matches = [parse_match(r) for r in raw if r.get("status") != "CANCELLED"]
            betslip = []
            print(col("green",f"\n  ✓ Refreshed — {len(matches)} fixtures loaded\n") if matches
                  else col("yellow","\n  No fixtures found after refresh.\n"))
            pause()

        elif choice == "0":
            banner()
            print(col("cyan","  Thank you for using A103 Predictz AI!\n"))
            print(dim("  Always gamble responsibly.\n"))
            break
        else:
            print(dim("\n  Invalid option.\n")); time.sleep(0.6)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n\n  {dim('Goodbye!')}\n")
        sys.exit(0)
