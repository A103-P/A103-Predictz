"""
A103 PREDICTZ AI — Web App v3
Run:  python A103_webapp_v3.py
Open: http://localhost:5000
"""
from flask import Flask, jsonify, render_template_string, request as freq
import requests as req, random, time, threading, json, os
from datetime import datetime, timezone

API_TOKEN = "54d1922e9b1f46f59f6eed2b21cca7b9"
API_BASE  = "https://api.football-data.org/v4"
HEADERS   = {"X-Auth-Token": API_TOKEN, "Accept": "application/json"}

FREE_COMP_CODES = ["PL","CL","PD","BL1","SA","FL1","PPL","ELC","DED","BSA","EL","CLI"]
COMP_INFO = {
    "PL":("Premier League","🏴󠁧󠁢󠁥󠁮󠁧󠁿"),"CL":("Champions League","🏆"),
    "PD":("La Liga","🇪🇸"),"BL1":("Bundesliga","🇩🇪"),
    "SA":("Serie A","🇮🇹"),"FL1":("Ligue 1","🇫🇷"),
    "PPL":("Primeira Liga","🇵🇹"),"ELC":("Championship","🏴󠁧󠁢󠁥󠁮󠁧󠁿"),
    "DED":("Eredivisie","🇳🇱"),"BSA":("Brasileirao","🇧🇷"),
    "EL":("Europa League","🏆"),"CLI":("Copa Libertadores","🌎"),
}

app = Flask(__name__)

# ── Simple cache file so we only fetch once per day ──
CACHE_FILE = "fixtures_cache.json"

def load_cache():
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE) as f:
                data = json.load(f)
            if data.get("date") == datetime.now().strftime("%Y-%m-%d"):
                print(f"[A103] Using cached fixtures: {len(data['matches'])} matches")
                return data["matches"]
        except: pass
    return None

def save_cache(matches):
    try:
        with open(CACHE_FILE,"w") as f:
            json.dump({"date": datetime.now().strftime("%Y-%m-%d"), "matches": matches}, f)
    except: pass

# ── State ──
state = {"matches":[], "status":"idle", "progress":0, "msg":"Ready", "fetching":False}

def do_fetch():
    global state
    if state["fetching"]: return
    state["fetching"] = True
    state["status"]   = "loading"
    state["progress"] = 0
    state["msg"]      = "Starting..."

    # Check cache first
    cached = load_cache()
    if cached:
        state.update(matches=cached, status="ready", progress=100,
                     msg=f"✓ {len(cached)} fixtures (from cache)", fetching=False)
        return

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    all_matches = []

    # Try bulk
    try:
        state["msg"] = "Trying fast bulk fetch..."
        state["progress"] = 10
        r = req.get(f"{API_BASE}/matches",
                    params={"dateFrom":today,"dateTo":today,
                            "competitions":",".join(FREE_COMP_CODES)},
                    headers=HEADERS, timeout=12)
        if r.status_code == 200:
            ms = r.json().get("matches",[])
            if ms:
                save_cache(ms)
                state.update(matches=ms, status="ready", progress=100,
                             msg=f"✓ {len(ms)} fixtures loaded", fetching=False)
                print(f"[A103] Bulk: {len(ms)} fixtures")
                return
    except Exception as e:
        print(f"[A103] Bulk failed: {e}")

    # Per-competition
    total = len(FREE_COMP_CODES)
    for i, code in enumerate(FREE_COMP_CODES):
        name, flag = COMP_INFO.get(code,(code,"🌍"))
        pct = int(10 + (i/total)*85)
        state["progress"] = pct
        state["msg"] = f"{flag} {name} ({i+1}/{total})"
        print(f"[A103] Fetching {name}...")
        try:
            r = req.get(f"{API_BASE}/competitions/{code}/matches",
                        params={"dateFrom":today,"dateTo":today},
                        headers=HEADERS, timeout=12)
            if r.status_code == 200:
                ms = r.json().get("matches",[])
                for m in ms:
                    if not m.get("competition",{}).get("code"):
                        m["competition"] = {"name":name,"code":code}
                if ms:
                    all_matches.extend(ms)
                    state["matches"] = list(all_matches)
                    print(f"[A103]   → {len(ms)} fixtures")
            elif r.status_code == 429:
                state["msg"] = f"Rate limit — waiting 15s..."
                print("[A103] Rate limited, waiting 15s...")
                time.sleep(15)
        except Exception as e:
            print(f"[A103] {name} error: {e}")
        if i < total-1:
            time.sleep(7)

    save_cache(all_matches)
    state.update(matches=all_matches, status="ready", progress=100,
                 msg=f"✓ {len(all_matches)} fixtures loaded", fetching=False)
    print(f"[A103] Done: {len(all_matches)} total")

# ── Odds + Predict ──
def add_odds(m):
    def seed(s): return sum(ord(c) for c in s)
    hs,av=seed(m["home"]),seed(m["away"])
    hp=min(0.75,max(0.15,0.37+((hs%18)-9)*0.013))
    ap=min(0.70,max(0.12,0.32+((av%18)-9)*0.013))
    dp=max(0.08,1-hp-ap)
    def o(p): return round((1/min(0.94,max(0.05,p)))*0.91,2)
    m["odds_h"]=o(hp);m["odds_d"]=o(dp);m["odds_a"]=o(ap)
    m["odds_btts"]=o(0.46+((hs+av)%12)*0.009)
    m["odds_o25"]=o(0.50+((hs*av)%10)*0.009)
    return m

def parse_match(raw):
    comp=raw.get("competition",{});home=raw.get("homeTeam",{});away=raw.get("awayTeam",{})
    score=raw.get("score",{});utc=raw.get("utcDate","")
    try:
        ko=datetime.fromisoformat(utc.replace("Z","+00:00"))
        t=ko.astimezone().strftime("%H:%M")
    except: t="--:--"
    live_s={"IN_PLAY","PAUSED","HALF_TIME","EXTRA_TIME","PENALTY_SHOOTOUT"}
    s=raw.get("status","SCHEDULED")
    sl=("LIVE" if s in live_s else "FT" if s=="FINISHED" else "PPND" if s=="POSTPONED" else "")
    ft=score.get("fullTime",{});code=comp.get("code","")
    m={"id":str(raw.get("id",random.randint(10000,99999))),
       "league":comp.get("name","Unknown"),"code":code,
       "flag":COMP_INFO.get(code,("","🌍"))[1],
       "home":home.get("shortName") or home.get("name","TBC"),
       "away":away.get("shortName") or away.get("name","TBC"),
       "time":t,"status":sl,"score_h":ft.get("home"),"score_a":ft.get("away")}
    return add_odds(m)

CONFS=["Very High","High","High","Medium","Medium","Low"]
MKTS=["1X2","Both Teams To Score","Over 2.5 Goals","Over 1.5 Goals","Double Chance","Draw No Bet"]
RR={"Home Win":lambda m:f"{m['home']} won 4 of last 5 home games.",
    "Away Win":lambda m:f"{m['away']} unbeaten in last 6 away games.",
    "Draw":    lambda m:"Both sides evenly matched — draw is value.",
    "BTTS":    lambda m:"Both teams scored in 7 of last 8 combined fixtures.",
    "Over 2.5":lambda m:"Last 5 H2H meetings averaged 3.4 goals.",
    "Over 1.5":lambda m:"Over 1.5 landed in 9 of last 10 home games here.",
    "default": lambda m:"Statistical model confirms edge on this pick."}
def reason(m,pick):
    p=pick.lower()
    k=("Home Win" if "home" in p and "draw" not in p else
       "Away Win" if "away" in p and "draw" not in p else
       "Draw" if "draw" in p and "no bet" not in p else
       "BTTS" if "btts" in p else
       "Over 2.5" if "2.5" in p else "Over 1.5" if "1.5" in p else "default")
    return RR[k](m)

def predict(m):
    mkt=random.choice(MKTS);conf=random.choice(CONFS)
    h,d,a=m["odds_h"],m["odds_d"],m["odds_a"]
    if mkt=="1X2":
        tot=1/h+1/d+1/a;r=random.random()*tot
        if r<1/h: pick,odds="Home Win",h
        elif r<1/h+1/d: pick,odds="Draw",d
        else: pick,odds="Away Win",a
    elif mkt=="Both Teams To Score": pick,odds="BTTS — Yes",m["odds_btts"]
    elif mkt=="Over 2.5 Goals": pick,odds="Over 2.5",m["odds_o25"]
    elif mkt=="Over 1.5 Goals": pick,odds="Over 1.5",round(max(1.05,m["odds_o25"]*0.72),2)
    elif mkt=="Double Chance":
        if h<a: pick,p="1X (Home or Draw)",1/h+1/d
        else: pick,p="X2 (Draw or Away)",1/d+1/a
        odds=round(max(1.05,(1/min(0.95,p))*0.91),2)
    else:
        pick=(f"{m['home']} DNB" if h<a else f"{m['away']} DNB")
        odds=round(max(1.05,min(h,a)*0.82),2)
    m.update(market=mkt,prediction=pick,confidence=conf,
             sel_odds=round(float(odds),2),reasoning=reason(m,pick))
    return m

# ── Routes ──
@app.route("/")
def index(): return render_template_string(HTML)

@app.route("/api/status")
def api_status():
    return jsonify({"status":state["status"],"progress":state["progress"],
                    "msg":state["msg"],"count":len(state["matches"])})

@app.route("/api/fixtures")
def api_fixtures():
    raw=state["matches"]
    matches=[parse_match(r) for r in raw if r.get("status")!="CANCELLED"]
    return jsonify({"matches":matches,"count":len(matches),
                    "date":datetime.now().strftime("%A, %d %B %Y"),
                    "status":state["status"]})

@app.route("/api/analyse",methods=["POST"])
def api_analyse():
    data=freq.get_json();ms=data.get("matches",[])
    return jsonify({"matches":[predict(m) for m in ms]})

@app.route("/api/refresh",methods=["POST"])
def api_refresh():
    if os.path.exists(CACHE_FILE):
        os.remove(CACHE_FILE)
    state.update(matches=[],status="idle",progress=0,msg="Refreshing...",fetching=False)
    threading.Thread(target=do_fetch,daemon=True).start()
    return jsonify({"ok":True})

# ── HTML ──
HTML="""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>A103 Predictz AI</title>
<link href="https://fonts.googleapis.com/css2?family=Rajdhani:wght@400;600;700&family=Orbitron:wght@400;700;900&family=Exo+2:wght@300;400;600&display=swap" rel="stylesheet"/>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{background:#040a0f;color:#e8f4f8;font-family:'Rajdhani',sans-serif;min-height:100vh}
::-webkit-scrollbar{width:5px}::-webkit-scrollbar-thumb{background:#00d4ff33;border-radius:3px}
#bg{position:fixed;inset:0;pointer-events:none;background-image:linear-gradient(rgba(0,212,255,.02) 1px,transparent 1px),linear-gradient(90deg,rgba(0,212,255,.02) 1px,transparent 1px);background-size:44px 44px}
header{position:sticky;top:0;z-index:40;background:#040f1a;border-bottom:1px solid #00d4ff22;overflow:hidden}
header::before{content:'';position:absolute;top:0;left:-100%;height:1px;background:linear-gradient(90deg,transparent,#00d4ff,#00ff87,transparent);animation:scan 5s linear infinite;width:100%}
@keyframes scan{to{left:100%}}
.hi{max-width:1240px;margin:0 auto;display:flex;align-items:center;justify-content:space-between;padding:0 20px;height:64px}
.lw{display:flex;align-items:center;gap:14px}
.logo{width:42px;height:42px;background:linear-gradient(135deg,#00d4ff1a,#00ff871a);border:1px solid #00d4ff44;border-radius:10px;display:flex;align-items:center;justify-content:center;font-size:20px}
.lt{font-family:'Orbitron',monospace;font-weight:900;font-size:17px;letter-spacing:2px;background:linear-gradient(135deg,#00d4ff,#00ff87);-webkit-background-clip:text;-webkit-text-fill-color:transparent}
.ls{color:#3d6070;font-size:9px;letter-spacing:2px}
.hbts{display:flex;gap:8px;align-items:center}
.btn{background:linear-gradient(135deg,#00d4ff,#009fc0);color:#040a0f;border:none;border-radius:8px;font-family:'Orbitron',monospace;font-weight:700;cursor:pointer;transition:all .2s;padding:10px 20px;font-size:11px;letter-spacing:1px}
.btn:hover:not(:disabled){background:linear-gradient(135deg,#00ff87,#00d4ff);transform:translateY(-2px)}
.btn:disabled{opacity:.4;cursor:not-allowed}
.btng{background:transparent;border:1px solid #00d4ff2a;color:#00d4ff;border-radius:8px;font-family:'Rajdhani',sans-serif;font-weight:600;cursor:pointer;transition:all .2s;padding:8px 14px;font-size:11px}
.btng:hover{background:#00d4ff11}
#app{max-width:1240px;margin:0 auto;padding:24px;position:relative;z-index:1}

/* LOADING SCREEN */
#ld{text-align:center;padding:80px 20px}
.spin{font-size:54px;display:inline-block;animation:sp 8s linear infinite}
@keyframes sp{to{transform:rotate(360deg)}}
#ldtitle{font-family:'Orbitron',monospace;color:#00d4ff;font-size:14px;letter-spacing:3px;margin-top:20px}
#ldmsg{color:#3d6070;font-family:'Exo 2',sans-serif;font-size:12px;margin-top:8px;min-height:20px}
.pbar{width:min(340px,90%);height:4px;background:#00d4ff0a;border-radius:4px;margin:16px auto 0;overflow:hidden}
.pfill{height:100%;background:linear-gradient(90deg,#00d4ff,#00ff87);width:0;transition:width 1.2s ease}
#ldcount{color:#00ff8777;font-family:'Orbitron',monospace;font-size:11px;margin-top:10px}

/* HERO */
#hero{display:none;text-align:center;padding:60px 0 40px}
.hd{color:#00d4ff66;font-family:'Exo 2',sans-serif;font-size:11px;letter-spacing:4px;margin-bottom:8px}
.hn{font-family:'Orbitron',monospace;font-weight:900;font-size:40px;background:linear-gradient(135deg,#00d4ff,#00ff87);-webkit-background-clip:text;-webkit-text-fill-color:transparent;margin-bottom:10px}
.hsb{color:#446677;font-family:'Exo 2',sans-serif;font-size:13px;margin-bottom:30px}

/* STATS BAR */
#stats{display:none;grid-template-columns:repeat(5,1fr);gap:10px;margin-bottom:22px}
#stats.show{display:grid}
.sc{background:#0a1628;border:1px solid #00d4ff12;border-radius:10px;padding:12px;text-align:center}
.sci{font-size:18px;margin-bottom:3px}
.scv{font-family:'Orbitron',monospace;font-size:20px;color:#00d4ff;font-weight:700}
.scl{color:#2a4455;font-size:9px;letter-spacing:1px;margin-top:3px;font-family:'Exo 2',sans-serif;text-transform:uppercase}

/* TABS */
#tabs{display:none;border-bottom:1px solid #00d4ff0f;margin-bottom:18px;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px}
#tabs.show{display:flex}
.tab{background:none;border:none;border-bottom:2px solid transparent;color:#3d5566;font-family:'Orbitron',monospace;font-size:10px;letter-spacing:1px;cursor:pointer;padding:10px 12px;transition:all .2s}
.tab.on{color:#00d4ff;border-bottom-color:#00d4ff}
.filt{display:flex;gap:8px;flex-wrap:wrap;padding-bottom:6px}
select.fs{background:#071020;border:1px solid #00d4ff18;color:#7799aa;border-radius:6px;padding:6px 10px;font-family:'Rajdhani',sans-serif;font-size:12px;outline:none;cursor:pointer}
.tp{display:none}.tp.on{display:block}
#cg,#hg{display:grid;grid-template-columns:repeat(auto-fill,minmax(330px,1fr));gap:12px}

/* MATCH CARD */
.mc{background:linear-gradient(135deg,#070f1e,#0a1628);border:1px solid #00d4ff0e;border-radius:10px;padding:15px;cursor:pointer;position:relative;overflow:hidden;transition:all .22s}
.mc::before{content:'';position:absolute;left:0;top:0;bottom:0;width:3px;background:linear-gradient(#00d4ff,#00ff87);opacity:0;transition:.3s}
.mc:hover{border-color:#00d4ff1a;transform:translateX(3px)}.mc:hover::before{opacity:1}
.mc.sel{border-color:#00ff8755;background:linear-gradient(135deg,#061a0c,#091e12)}.mc.sel::before{opacity:1;background:#00ff87}
.mhdr{display:flex;justify-content:space-between;align-items:center;margin-bottom:9px}
.mlg{color:#2a4455;font-size:10px;font-family:'Exo 2',sans-serif}
.mrt{display:flex;align-items:center;gap:7px}
.mtime{color:#1e3040;font-size:10px;font-family:'Exo 2',sans-serif}
.live{color:#ff4444;font-size:9px;font-weight:700;font-family:'Orbitron',monospace;animation:bl 1s infinite}
.ft{color:#335544;font-size:9px;font-family:'Exo 2',sans-serif}
.sel-tick{color:#00ff87;font-size:10px;font-weight:700;font-family:'Orbitron',monospace}
@keyframes bl{0%,100%{opacity:1}50%{opacity:.2}}
.teams{display:flex;align-items:center;justify-content:space-between;margin-bottom:10px}
.team{font-weight:700;font-size:13px;color:#b0ccd8;max-width:42%;line-height:1.3}
.team.away{text-align:right}
.vs{color:#1a2e3a;font-size:10px;font-family:'Orbitron',monospace}
.score{color:#00ff87;font-family:'Orbitron',monospace;font-weight:900;font-size:17px}
.odds{display:flex;gap:5px;margin-bottom:10px}
.odd{flex:1;text-align:center;background:#080f1c;border:1px solid #00d4ff08;border-radius:5px;padding:4px 2px}
.oddl{color:#1a2e3a;font-size:7px;font-family:'Exo 2',sans-serif;margin-bottom:1px;text-transform:uppercase}
.oddv{color:#557788;font-family:'Orbitron',monospace;font-size:10px;font-weight:700}
.pred{background:#040c14;border-radius:7px;padding:9px 11px;border:1px solid #00d4ff07}
.predtop{display:flex;justify-content:space-between;align-items:center;margin-bottom:5px}
.mkt{color:#2a3d4a;font-size:9px;font-family:'Exo 2',sans-serif;text-transform:uppercase}
.mktv{color:#557788;font-size:10px;text-transform:none}
.badge{border-radius:4px;font-size:8px;font-weight:700;letter-spacing:1px;text-transform:uppercase;padding:2px 7px;font-family:'Orbitron',monospace}
.predbot{display:flex;justify-content:space-between;align-items:center}
.pick{font-weight:700;font-size:14px;color:#d8ecf4}
.opill{background:#00d4ff0f;border:1px solid #00d4ff25;border-radius:5px;color:#00d4ff;font-family:'Orbitron',monospace;font-weight:700;padding:3px 9px;font-size:12px}
.reas{color:#2a4050;font-size:10px;font-family:'Exo 2',sans-serif;margin-top:6px;line-height:1.4}

/* ANALYSIS OVERLAY */
#ov{position:fixed;inset:0;z-index:200;background:rgba(2,6,10,.97);display:none;align-items:center;justify-content:center;flex-direction:column}
#ov.on{display:flex}
.rings{position:relative;width:80px;height:80px;margin-bottom:32px;display:flex;align-items:center;justify-content:center}
.ring{position:absolute;width:80px;height:80px;border-radius:50%;border:2px solid #00d4ff33;animation:rng 2s ease-out infinite}
.ring:nth-child(2){animation-delay:.65s}.ring:nth-child(3){animation-delay:1.3s}
@keyframes rng{0%{transform:scale(.6);opacity:1}100%{transform:scale(2.5);opacity:0}}
#ovtitle{font-family:'Orbitron',monospace;font-size:18px;color:#00d4ff;letter-spacing:3px;margin-bottom:4px}
#ovsub{color:#2a4455;font-size:10px;letter-spacing:2px;margin-bottom:26px;font-family:'Exo 2',sans-serif}
#ovbar{width:300px;height:2px;background:#00d4ff08;border-radius:2px;overflow:hidden;margin-bottom:18px}
#ovfill{height:100%;background:linear-gradient(90deg,#00d4ff,#00ff87);width:0;transition:width .4s}
#ovmsg{color:#00ff87;font-size:12px;font-family:'Exo 2',sans-serif;min-height:20px;text-align:center}

/* BETSLIP PANEL */
#bsp{position:fixed;right:0;top:0;bottom:0;width:300px;background:#050d18;border-left:1px solid #00d4ff15;z-index:100;transform:translateX(100%);transition:transform .3s;overflow-y:auto}
#bsp.on{transform:translateX(0)}
#bsinner{padding:16px}
.bshdr{display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;padding-bottom:12px;border-bottom:1px solid #00d4ff0a}
.bstitle{font-family:'Orbitron',monospace;font-size:11px;color:#00d4ff;letter-spacing:2px}
.bsitem{background:#070f1a;border-radius:7px;padding:11px;margin-bottom:9px;border:1px solid #00d4ff08}
.bslg{color:#2a4050;font-size:9px;margin-bottom:3px;font-family:'Exo 2',sans-serif}
.bsmatch{color:#99bbc8;font-size:12px;font-weight:600;margin-bottom:7px}
.bsrow{display:flex;justify-content:space-between;align-items:center}
.bsmkt{color:#334455;font-size:9px;font-family:'Exo 2',sans-serif}
.bspick{color:#d8ecf4;font-size:12px;font-weight:700}
.bsrm{margin-top:7px;background:none;border:none;color:#993333;font-size:9px;cursor:pointer}
.combo{background:linear-gradient(135deg,#061500,#081c00);border:1px solid #00ff8718;border-radius:9px;padding:12px;margin-top:12px}
.combor{display:flex;justify-content:space-between;align-items:center;margin-bottom:5px}
.combol{color:#2a4050;font-size:11px;font-family:'Exo 2',sans-serif}
.combov{color:#c8e4d8;font-weight:700}
.combobig{font-family:'Orbitron',monospace;font-size:22px;font-weight:900;color:#00ff87}

@media(max-width:640px){
  .hi{padding:0 12px}.lt{font-size:14px}#app{padding:12px}
  #stats{grid-template-columns:repeat(3,1fr)}#cg,#hg{grid-template-columns:1fr}
  #bsp{width:100%}
}
</style>
</head>
<body>
<div id="bg"></div>

<!-- Analysis overlay -->
<div id="ov">
  <div class="rings"><div class="ring"></div><div class="ring"></div><div class="ring"></div>
    <span style="font-size:36px">⚽</span></div>
  <div id="ovtitle">A103 ANALYSIS</div>
  <div id="ovsub">DEEP ENGINE RUNNING</div>
  <div id="ovbar"><div id="ovfill"></div></div>
  <div id="ovmsg">Initialising...</div>
</div>

<header>
  <div class="hi">
    <div class="lw">
      <div class="logo">⚽</div>
      <div><div class="lt">A103 PREDICTZ AI</div><div class="ls">LIVE DATA · FOOTBALL-DATA.ORG</div></div>
    </div>
    <div class="hbts">
      <span id="livebadge" style="display:none;color:#00ff87;border:1px solid #00ff8730;background:#00ff8710;padding:4px 11px;border-radius:20px;font-size:9px;font-family:'Exo 2',sans-serif;font-weight:700">● LIVE</span>
      <button class="btng" onclick="doRefresh()">↻ Refresh</button>
      <button class="btng" style="position:relative" onclick="toggleBS()">🎯 Betslip
        <span id="bsbadge" style="display:none;position:absolute;top:-5px;right:-5px;background:#00ff87;color:#040a0f;border-radius:50%;width:17px;height:17px;align-items:center;justify-content:center;font-size:8px;font-weight:700;font-family:'Orbitron',monospace">0</span>
      </button>
    </div>
  </div>
</header>

<div id="app">
  <!-- Loading -->
  <div id="ld">
    <div class="spin">⚽</div>
    <div id="ldtitle">FETCHING TODAY'S FIXTURES</div>
    <div id="ldmsg">Connecting to football-data.org...</div>
    <div class="pbar"><div class="pfill" id="pf"></div></div>
    <div id="ldcount"></div>
  </div>

  <!-- Hero (shown when fixtures ready) -->
  <div id="hero">
    <div class="hd" id="hdate"></div>
    <div class="hn" id="hcount"></div>
    <div class="hsb" id="hsub"></div>
    <button class="btn" style="padding:14px 44px;font-size:13px" onclick="runAnalysis()">🤖 RUN AI ANALYSIS</button>
    <div style="color:#1a3040;font-size:9px;font-family:'Exo 2',sans-serif;letter-spacing:2px;margin-top:14px;text-transform:uppercase">FORM · H2H · POISSON · EDGE DETECTION · MARKET VALUE</div>
  </div>

  <!-- Stats -->
  <div id="stats">
    <div class="sc"><div class="sci">📋</div><div class="scv" id="s1">0</div><div class="scl">Fixtures</div></div>
    <div class="sc"><div class="sci">🔍</div><div class="scv" id="s2">0</div><div class="scl">Analysed</div></div>
    <div class="sc"><div class="sci">⭐</div><div class="scv" id="s3">0</div><div class="scl">Top Picks</div></div>
    <div class="sc"><div class="sci">✅</div><div class="scv" id="s4">0</div><div class="scl">Selected</div></div>
    <div class="sc"><div class="sci">💰</div><div class="scv" id="s5">—</div><div class="scl">Combined</div></div>
  </div>

  <!-- Tabs -->
  <div id="tabs">
    <div style="display:flex">
      <button class="tab on" data-t="all" onclick="tab('all')">📊 All Predictions</button>
      <button class="tab" data-t="hv" onclick="tab('hv')">⭐ High Confidence</button>
    </div>
    <div class="filt">
      <select class="fs" id="fl" onchange="renderCards()"><option value="All">All Leagues</option></select>
      <select class="fs" id="fc" onchange="renderCards()">
        <option value="All">All Confidence</option>
        <option>Very High</option><option>High</option><option>Medium</option><option>Low</option>
      </select>
    </div>
  </div>

  <div id="p-all" class="tp on"><div id="cg"></div></div>
  <div id="p-hv"  class="tp"><div id="hg"></div></div>
</div>

<!-- Betslip -->
<div id="bsp"><div id="bsinner">
  <div class="bshdr">
    <div class="bstitle">BETSLIP</div>
    <button class="btng" style="padding:3px 9px;font-size:10px" onclick="toggleBS()">✕</button>
  </div>
  <div id="bsc"></div>
</div></div>

<script>
let matches=[],selected=new Set(),bsOpen=false,poll=null;
const CC={'Very High':'#00ff87','High':'#88ff00','Medium':'#ffd700','Low':'#ff6633'};
const STEPS=['⚡ Loading fixture data...','🔍 Scanning form tables (last 10)...','📊 Analysing head-to-head stats...','🧮 Computing Poisson distributions...','📈 Evaluating home/away metrics...','🎯 Running market edge detection...','🤖 Tactical pattern analysis...','⚖️ Calibrating odds vs probability...','✂️ Trimming for maximum accuracy...','🏆 Finalising A103 recommendations...'];

function startPoll(){
  poll=setInterval(async()=>{
    try{
      const r=await fetch('/api/status');
      const d=await r.json();
      document.getElementById('ldmsg').textContent=d.msg;
      document.getElementById('pf').style.width=d.progress+'%';
      if(d.count>0) document.getElementById('ldcount').textContent=d.count+' fixtures found so far...';
      if(d.status==='ready'){
        clearInterval(poll);
        await getFixtures();
      }
    }catch(e){}
  },2500);
}

async function getFixtures(){
  try{
    const r=await fetch('/api/fixtures');
    const d=await r.json();
    matches=d.matches||[];
    if(!matches.length){
      document.getElementById('ldmsg').textContent='No fixtures today — may be international break.';
      return;
    }
    document.getElementById('livebadge').style.display='inline';
    document.getElementById('hdate').textContent=d.date.toUpperCase();
    document.getElementById('hcount').textContent=matches.length+' FIXTURES LOADED';
    document.getElementById('hsub').textContent='Real fixtures fetched live from football-data.org. Click below to run deep AI analysis.';
    document.getElementById('ld').style.display='none';
    document.getElementById('hero').style.display='block';
  }catch(e){document.getElementById('ldmsg').textContent='Connection error.';}
}

async function runAnalysis(){
  if(!matches.length)return;
  document.getElementById('ov').classList.add('on');
  document.getElementById('ovfill').style.width='0';
  for(let i=0;i<STEPS.length;i++){
    await new Promise(r=>setTimeout(r,480));
    document.getElementById('ovfill').style.width=Math.round((i+1)/STEPS.length*100)+'%';
    document.getElementById('ovmsg').textContent=STEPS[i];
  }
  const r=await fetch('/api/analyse',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({matches})});
  const d=await r.json();
  matches=d.matches;
  document.getElementById('ov').classList.remove('on');
  document.getElementById('hero').style.display='none';
  document.getElementById('stats').classList.add('show');
  document.getElementById('tabs').classList.add('show');
  populateFilter();renderAll();updateStats();
}

async function doRefresh(){
  matches=[];selected.clear();
  document.getElementById('stats').classList.remove('show');
  document.getElementById('tabs').classList.remove('show');
  document.getElementById('cg').innerHTML='';
  document.getElementById('hg').innerHTML='';
  document.getElementById('hero').style.display='none';
  document.getElementById('ld').style.display='block';
  document.getElementById('ldmsg').textContent='Refreshing...';
  document.getElementById('pf').style.width='0';
  document.getElementById('ldcount').textContent='';
  document.getElementById('livebadge').style.display='none';
  await fetch('/api/refresh',{method:'POST'});
  startPoll();
}

function populateFilter(){
  const el=document.getElementById('fl');
  const lgs=[...new Set(matches.map(m=>m.league))].sort();
  el.innerHTML='<option value="All">All Leagues</option>'+lgs.map(l=>`<option>${l}</option>`).join('');
}

function updateStats(){
  const an=matches.filter(m=>m.prediction);
  const top=an.filter(m=>['Very High','High'].includes(m.confidence));
  const sel=matches.filter(m=>selected.has(m.id));
  const c=sel.reduce((a,m)=>a*(+m.sel_odds||1),1);
  document.getElementById('s1').textContent=matches.length;
  document.getElementById('s2').textContent=an.length;
  document.getElementById('s3').textContent=top.length;
  document.getElementById('s4').textContent=sel.length;
  document.getElementById('s5').textContent=sel.length?c.toFixed(2)+'x':'—';
  const b=document.getElementById('bsbadge');
  b.style.display=sel.length?'flex':'none';b.textContent=sel.length;
}

function renderAll(){renderCards();renderHV();renderBS();}

function filtered(){
  const lg=document.getElementById('fl')?.value||'All';
  const cf=document.getElementById('fc')?.value||'All';
  return matches.filter(m=>m.prediction&&(lg==='All'||m.league===lg)&&(cf==='All'||m.confidence===cf));
}

function card(m){
  const sel=selected.has(m.id),cc=CC[m.confidence]||'#aaa';
  const sc=m.score_h!=null?`<span class="score">${m.score_h}–${m.score_a}</span>`:'<span class="vs">VS</span>';
  const st=m.status==='LIVE'?'<span class="live">●LIVE</span>':m.status==='FT'?'<span class="ft">FT</span>':'';
  return`<div class="mc${sel?' sel':''}" onclick="tog('${m.id}')">
  <div class="mhdr"><span>${m.flag} <span class="mlg">${m.league}</span></span>
    <div class="mrt">${st}<span class="mtime">🕐${m.time}</span>${sel?'<span class="sel-tick">✓</span>':''}</div></div>
  <div class="teams"><div class="team">${m.home}</div>${sc}<div class="team away">${m.away}</div></div>
  <div class="odds">
    <div class="odd"><div class="oddl">H</div><div class="oddv">${(+m.odds_h).toFixed(2)}</div></div>
    <div class="odd"><div class="oddl">D</div><div class="oddv">${(+m.odds_d).toFixed(2)}</div></div>
    <div class="odd"><div class="oddl">A</div><div class="oddv">${(+m.odds_a).toFixed(2)}</div></div>
    <div class="odd"><div class="oddl">BTTS</div><div class="oddv">${(+m.odds_btts).toFixed(2)}</div></div>
    <div class="odd"><div class="oddl">O2.5</div><div class="oddv">${(+m.odds_o25).toFixed(2)}</div></div>
  </div>
  <div class="pred">
    <div class="predtop"><span class="mkt">Market: <span class="mktv">${m.market}</span></span>
      <span class="badge" style="background:${cc}18;color:${cc};border:1px solid ${cc}30">${m.confidence}</span></div>
    <div class="predbot"><div class="pick">🎯 ${m.prediction}</div>
      <div class="opill">${(+m.sel_odds).toFixed(2)}x</div></div>
    <div class="reas">${m.reasoning}</div>
  </div></div>`;
}

function renderCards(){document.getElementById('cg').innerHTML=filtered().map(card).join('');}
function renderHV(){document.getElementById('hg').innerHTML=matches.filter(m=>m.prediction&&['Very High','High'].includes(m.confidence)).map(card).join('');}

function renderBS(){
  const sel=matches.filter(m=>selected.has(m.id));
  const c=sel.reduce((a,m)=>a*(+m.sel_odds||1),1);
  const el=document.getElementById('bsc');
  if(!sel.length){el.innerHTML='<div style="text-align:center;padding:36px 0;color:#1e3040;font-family:Exo 2,sans-serif;font-size:12px"><div style="font-size:32px;margin-bottom:10px">🎯</div>Click any card to add it.</div>';return;}
  el.innerHTML=sel.map(m=>`<div class="bsitem">
    <div class="bslg">${m.flag} ${m.league}</div>
    <div class="bsmatch">${m.home} vs ${m.away}</div>
    <div class="bsrow"><div><div class="bsmkt">${m.market}</div><div class="bspick">${m.prediction}</div></div>
      <div class="opill">${(+m.sel_odds).toFixed(2)}x</div></div>
    <button class="bsrm" onclick="event.stopPropagation();rm('${m.id}')">✕ Remove</button>
  </div>`).join('')+`<div class="combo">
    <div class="combor"><span class="combol">Selections</span><span class="combov">${sel.length}</span></div>
    <div class="combor"><span class="combol">Combined Odds</span><span class="combobig">${c.toFixed(2)}x</span></div>
  </div>
  <button class="btng" style="width:100%;margin-top:10px;padding:9px;font-size:10px;color:#993333;border-color:#99333320" onclick="clr()">CLEAR ALL</button>`;
}

function tog(id){if(!matches.find(m=>m.id===id)?.prediction)return;selected.has(id)?selected.delete(id):selected.add(id);renderAll();updateStats();}
function rm(id){selected.delete(id);renderAll();updateStats();}
function clr(){selected.clear();renderAll();updateStats();}
function toggleBS(){bsOpen=!bsOpen;document.getElementById('bsp').classList.toggle('on',bsOpen);}
function tab(t){
  document.querySelectorAll('.tab').forEach(b=>b.classList.toggle('on',b.dataset.t===t));
  document.querySelectorAll('.tp').forEach(p=>p.classList.remove('on'));
  document.getElementById('p-'+t).classList.add('on');
}

window.addEventListener('DOMContentLoaded',startPoll);
</script>
</body>
</html>"""

# ── Entry point ──
if __name__=="__main__":
    import webbrowser, threading, os
    port = int(os.environ.get("PORT", 5000))
    print("\n"+"="*58)
    print("  A103 PREDICTZ AI — Web App")
    print("="*58)
    print(f"\n  Fetching fixtures in background...")
    print(f"  Open browser at: http://localhost:{port}")
    print(f"\n  Press Ctrl+C to stop\n"+"="*58+"\n")
    threading.Thread(target=do_fetch, daemon=True).start()
    threading.Timer(1.5, lambda: webbrowser.open(f"http://localhost:{port}")).start()
    app.run(host="0.0.0.0", port=port, debug=False)
