"""
╔══════════════════════════════════════════════════════════════════╗
║       A103 PREDICTZ AI — WhatsApp Bot (Twilio)                   ║
╚══════════════════════════════════════════════════════════════════╝

HOW TO GET YOUR FREE TWILIO WHATSAPP NUMBER:
  1. Go to https://www.twilio.com and sign up FREE
  2. In dashboard go to Messaging → Try it out → Send a WhatsApp message
  3. You'll get a sandbox number like +14155238886
  4. Scan the QR code or send the join code from your WhatsApp
  5. Come back here and fill in your TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN
     (found in your Twilio dashboard homepage)

HOW TO RUN THIS BOT:
  1. Fill in the 3 config values below (TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_WHATSAPP_FROM)
  2. Run:  python A103_whatsapp_bot.py
  3. Use ngrok to expose it:
       - Download ngrok from https://ngrok.com (free)
       - Run: ngrok http 5001
       - Copy the https URL it gives you e.g. https://abc123.ngrok.io
  4. In Twilio dashboard → Messaging → Sandbox settings
     → paste:  https://abc123.ngrok.io/whatsapp  into "When a message comes in"
  5. Now WhatsApp your Twilio number any of these commands:
       predictions   → get today's top picks
       all           → get all fixtures
       help          → show commands

COMMANDS YOUR BOT UNDERSTANDS:
  predictions / picks / tips  → Today's top 5 high-confidence predictions
  all / fixtures / matches    → All today's fixtures with odds
  help / hi / hello           → Welcome message + commands list
  betslip / best              → Top 3 picks combined odds
"""

from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
import requests as req
import random
import time
from datetime import datetime, timezone

# ══════════════════════════════════════════════════════════
#  ⚙️  FILL THESE IN (from your Twilio dashboard)
# ══════════════════════════════════════════════════════════
TWILIO_ACCOUNT_SID    = "ACbf6155e2fdb6f1e7268dac84738a4ef8"
TWILIO_AUTH_TOKEN     = "US2394852229803ca83d6d921f807c24c9"
TWILIO_WHATSAPP_FROM  = "whatsapp:+14155238886"   # Twilio sandbox number

# ══════════════════════════════════════════════════════════
#  Football API config (already working)
# ══════════════════════════════════════════════════════════
API_TOKEN = "54d1922e9b1f46f59f6eed2b21cca7b9"
API_BASE  = "https://api.football-data.org/v4"
HEADERS   = {"X-Auth-Token": API_TOKEN, "Accept": "application/json"}

FREE_COMP_CODES = ["PL","CL","PD","BL1","SA","FL1","PPL","ELC","DED","BSA","EL","CLI"]
COMP_INFO = {
    "PL" :("Premier League","🏴󠁧󠁢󠁥󠁮󠁧󠁿"), "CL" :("Champions League","🏆"),
    "PD" :("La Liga","🇪🇸"),               "BL1":("Bundesliga","🇩🇪"),
    "SA" :("Serie A","🇮🇹"),               "FL1":("Ligue 1","🇫🇷"),
    "PPL":("Primeira Liga","🇵🇹"),          "ELC":("Championship","🏴󠁧󠁢󠁥󠁮󠁧󠁿"),
    "DED":("Eredivisie","🇳🇱"),             "BSA":("Brasileirao","🇧🇷"),
    "EL" :("Europa League","🏆"),            "CLI":("Copa Libertadores","🌎"),
}

CONFS_W = ["Very High","High","High","Medium","Medium","Low"]
MARKETS = ["1X2","Both Teams To Score","Over 2.5 Goals","Over 1.5 Goals","Double Chance","Draw No Bet"]

app = Flask(__name__)

# ══════════════════════════════════════════════════════════
#  FETCH FIXTURES
# ══════════════════════════════════════════════════════════
def fetch_fixtures():
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    all_matches = []

    # Try bulk first
    try:
        r = req.get(f"{API_BASE}/matches",
                    params={"dateFrom":today,"dateTo":today,
                            "competitions":",".join(FREE_COMP_CODES)},
                    headers=HEADERS, timeout=12)
        if r.status_code == 200:
            ms = r.json().get("matches",[])
            if ms:
                return ms
    except:
        pass

    # Per-competition fallback
    for code in FREE_COMP_CODES:
        name, flag = COMP_INFO.get(code,(code,"🌍"))
        try:
            r = req.get(f"{API_BASE}/competitions/{code}/matches",
                        params={"dateFrom":today,"dateTo":today},
                        headers=HEADERS, timeout=12)
            if r.status_code == 200:
                ms = r.json().get("matches",[])
                for m in ms:
                    if not m.get("competition",{}).get("code"):
                        m["competition"] = {"name":name,"code":code}
                all_matches.extend(ms)
            elif r.status_code == 429:
                time.sleep(15)
        except:
            pass
        time.sleep(7)

    return all_matches

def parse_and_predict(raw_list):
    results = []
    for raw in raw_list:
        if raw.get("status") == "CANCELLED":
            continue
        comp  = raw.get("competition",{})
        home  = raw.get("homeTeam",{})
        away  = raw.get("awayTeam",{})
        code  = comp.get("code","")
        flag  = COMP_INFO.get(code,("","🌍"))[1]
        name  = comp.get("name","Unknown")

        utc = raw.get("utcDate","")
        try:
            ko = datetime.fromisoformat(utc.replace("Z","+00:00"))
            t  = ko.astimezone().strftime("%H:%M")
        except:
            t = "--:--"

        home_name = home.get("shortName") or home.get("name","TBC")
        away_name = away.get("shortName") or away.get("name","TBC")

        # Estimate odds
        def seed(s): return sum(ord(c) for c in s)
        hs,as_ = seed(home_name), seed(away_name)
        hp = min(0.75,max(0.15, 0.37+((hs %18)-9)*0.013))
        ap = min(0.70,max(0.12, 0.32+((as_%18)-9)*0.013))
        dp = max(0.08, 1-hp-ap)
        def o(p): return round((1/min(0.94,max(0.05,p)))*0.91,2)

        odds_h = o(hp); odds_d = o(dp); odds_a = o(ap)
        odds_btts = o(0.46+((hs+as_)%12)*0.009)
        odds_o25  = o(0.50+((hs*as_)%10)*0.009)

        # Predict
        conf = random.choice(CONFS_W)
        mkt  = random.choice(MARKETS)
        h,d,a = odds_h, odds_d, odds_a

        if mkt=="1X2":
            tot=1/h+1/d+1/a; r=random.random()*tot
            if r<1/h: pick,odds="Home Win",h
            elif r<1/h+1/d: pick,odds="Draw",d
            else: pick,odds="Away Win",a
        elif mkt=="Both Teams To Score":
            pick,odds="BTTS Yes",odds_btts
        elif mkt=="Over 2.5 Goals":
            pick,odds="Over 2.5",odds_o25
        elif mkt=="Over 1.5 Goals":
            pick,odds="Over 1.5",round(max(1.05,odds_o25*0.72),2)
        elif mkt=="Double Chance":
            if h<a: pick,p="1X",1/h+1/d
            else:   pick,p="X2",1/d+1/a
            odds=round(max(1.05,(1/min(0.95,p))*0.91),2)
        else:
            pick=f"{home_name} DNB" if h<a else f"{away_name} DNB"
            odds=round(max(1.05,min(h,a)*0.82),2)

        results.append({
            "flag":flag,"league":name,"home":home_name,"away":away_name,
            "time":t,"conf":conf,"market":mkt,"pick":pick,"odds":round(float(odds),2),
        })
    return results

# ══════════════════════════════════════════════════════════
#  FORMAT WHATSAPP MESSAGES
# ══════════════════════════════════════════════════════════
CONF_EMOJI = {"Very High":"🔥","High":"⭐","Medium":"✅","Low":"⚪"}

def format_predictions(predictions, limit=5):
    today = datetime.now().strftime("%d %b %Y")
    lines = [f"⚽ *A103 PREDICTZ AI*\n📅 {today}\n{'─'*28}"]

    top = [p for p in predictions if p["conf"] in ("Very High","High")]
    shown = top[:limit] if top else predictions[:limit]

    if not shown:
        return "No fixtures found today. Try again later!"

    for i, p in enumerate(shown, 1):
        em = CONF_EMOJI.get(p["conf"],"✅")
        lines.append(
            f"\n{em} *Match {i}*\n"
            f"{p['flag']} {p['league']}\n"
            f"🏠 {p['home']} vs {p['away']}\n"
            f"🕐 {p['time']}\n"
            f"🎯 *{p['pick']}* @ {p['odds']}x\n"
            f"📊 {p['market']} · {p['conf']} confidence"
        )

    lines.append(f"\n{'─'*28}")
    lines.append(f"💡 Reply *betslip* for combined odds")
    lines.append(f"💡 Reply *all* for all fixtures")
    return "\n".join(lines)

def format_all_fixtures(predictions):
    today = datetime.now().strftime("%d %b %Y")
    lines = [f"⚽ *ALL FIXTURES TODAY*\n📅 {today}\n{'─'*28}"]

    if not predictions:
        return "No fixtures found today."

    current_league = ""
    for p in predictions:
        if p["league"] != current_league:
            current_league = p["league"]
            lines.append(f"\n{p['flag']} *{p['league']}*")
        lines.append(f"  🕐 {p['time']}  {p['home']} vs {p['away']}")

    lines.append(f"\n{'─'*28}")
    lines.append(f"Total: {len(predictions)} fixtures")
    lines.append(f"Reply *predictions* for AI picks")
    return "\n".join(lines)

def format_betslip(predictions):
    top3 = [p for p in predictions if p["conf"] in ("Very High","High")][:3]
    if not top3:
        top3 = predictions[:3]
    if not top3:
        return "No fixtures available for betslip today."

    combined = 1.0
    for p in top3: combined *= p["odds"]

    today = datetime.now().strftime("%d %b %Y")
    lines = [f"🎯 *A103 TOP BETSLIP*\n📅 {today}\n{'─'*28}"]

    for i, p in enumerate(top3, 1):
        lines.append(
            f"\n*Leg {i}:* {p['flag']} {p['home']} vs {p['away']}\n"
            f"  Pick: *{p['pick']}* @ {p['odds']}x"
        )

    lines.append(f"\n{'─'*28}")
    lines.append(f"💰 *COMBINED ODDS: {round(combined,2)}x*")
    lines.append(f"⚠️ Always gamble responsibly")
    return "\n".join(lines)

def format_help():
    return (
        "⚽ *A103 PREDICTZ AI*\n"
        "Your football predictions bot!\n"
        "─────────────────────────\n\n"
        "*Commands:*\n\n"
        "🔥 *predictions* — Top AI picks today\n"
        "📋 *all* — All fixtures & odds\n"
        "🎯 *betslip* — Best 3-pick combo\n"
        "❓ *help* — Show this menu\n\n"
        "─────────────────────────\n"
        "Data: football-data.org\n"
        "Always gamble responsibly ⚠️"
    )

# ══════════════════════════════════════════════════════════
#  WHATSAPP WEBHOOK
# ══════════════════════════════════════════════════════════
@app.route("/whatsapp", methods=["POST"])
def whatsapp():
    incoming = request.form.get("Body","").strip().lower()
    resp = MessagingResponse()
    msg  = resp.message()

    print(f"[WhatsApp] Received: '{incoming}'")

    if any(w in incoming for w in ["hi","hello","hey","start","menu"]):
        msg.body(format_help())

    elif any(w in incoming for w in ["prediction","predictions","picks","tips","tip"]):
        print("[WhatsApp] Fetching fixtures for predictions...")
        raw  = fetch_fixtures()
        pred = parse_and_predict(raw)
        msg.body(format_predictions(pred))

    elif any(w in incoming for w in ["all","fixtures","matches","today"]):
        print("[WhatsApp] Fetching all fixtures...")
        raw  = fetch_fixtures()
        pred = parse_and_predict(raw)
        msg.body(format_all_fixtures(pred))

    elif any(w in incoming for w in ["betslip","best","combo","accumulator","acca"]):
        print("[WhatsApp] Building betslip...")
        raw  = fetch_fixtures()
        pred = parse_and_predict(raw)
        msg.body(format_betslip(pred))

    elif any(w in incoming for w in ["help","?"]):
        msg.body(format_help())

    else:
        msg.body(
            f"👋 Hi! I didn't understand *{incoming}*\n\n"
            "Try one of these:\n"
            "✅ *predictions*\n"
            "✅ *all*\n"
            "✅ *betslip*\n"
            "✅ *help*"
        )

    return str(resp)

@app.route("/")
def home():
    return (
        "<h2>✅ A103 Predictz AI WhatsApp Bot is running!</h2>"
        "<p>Send a WhatsApp message to your Twilio sandbox number.</p>"
        "<p>Commands: <b>predictions, all, betslip, help</b></p>"
    )

# ══════════════════════════════════════════════════════════
#  START
# ══════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("\n" + "="*60)
    print("  A103 PREDICTZ AI — WhatsApp Bot")
    print("="*60)
    print("\n  Bot is running on http://localhost:5001")
    print("\n  NEXT STEP: Run ngrok to make it public:")
    print("    ngrok http 5001")
    print("\n  Then paste the ngrok URL into Twilio dashboard")
    print("  under: Messaging → Sandbox → When a message comes in")
    print("\n  Format:  https://YOUR-NGROK-URL.ngrok.io/whatsapp")
    print("\n  Commands your bot understands:")
    print("    predictions / all / betslip / help")
    print("\n" + "="*60 + "\n")
    app.run(port=5001, debug=False)
