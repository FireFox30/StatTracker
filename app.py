from flask import Flask, render_template, jsonify
import requests

app = Flask(__name__)
API = "https://overfast-api.tekrop.fr"
ROLES = {"tank", "damage", "support"}
RANKS = {"bronze", "silver", "gold", "platinum", "diamond", "master", "grandmaster", "champion"}

def extract_competitive(raw):
    if not raw:
        return {}
    # Roles at top level
    if set(raw.keys()) & ROLES:
        return raw
    # Roles nested under a platform key (pc/console)
    for v in raw.values():
        if isinstance(v, dict) and set(v.keys()) & ROLES:
            return v
    return {}

def normalise_role(data):
    tier, division = "", None
    for val in data.values():
        if isinstance(val, str) and val.lower() in RANKS:
            tier = val.capitalize()
        elif isinstance(val, int) and division is None:
            division = val
    return {"tier": tier, "division": division}

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/player/<path:tag>")
def get_player(tag):
    try:
        h = {"User-Agent": "OWTracker/1.0"}
        r = requests.get(f"{API}/players/{tag}/summary", headers=h, timeout=10)
        if r.status_code == 404:
            return jsonify({"error": "Player not found or profile is private."}), 404
        if r.status_code != 200:
            return jsonify({"error": f"API returned {r.status_code}."}), r.status_code

        s = r.json()
        comp_raw = extract_competitive(s.get("competitive") or {})
        competitive = {role: normalise_role(data)
                       for role, data in comp_raw.items()
                       if isinstance(data, dict)}

        stats = None
        try:
            sr = requests.get(f"{API}/players/{tag}/stats/summary", headers=h, timeout=10)
            if sr.ok:
                stats = sr.json()
        except Exception:
            pass

        return jsonify({
            "username": s.get("username", tag),
            "avatar":   s.get("avatar"),
            "title":    s.get("title"),
            "endorsement": s.get("endorsement"),
            "competitive": competitive,
            "stats": stats,
        })
    except requests.exceptions.Timeout:
        return jsonify({"error": "Request timed out."}), 504
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True, port=5000)