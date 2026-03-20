from flask import Flask, render_template, jsonify, request
import requests, sqlite3, os

app = Flask(__name__)
API = "https://overfast-api.tekrop.fr"
ROLES = {"tank", "damage", "support"}
RANKS = {"bronze", "silver", "gold", "platinum", "diamond", "master", "grandmaster", "champion"}
DB = os.path.join(os.path.dirname(__file__), "tracker.db")

def get_db():
    db = sqlite3.connect(DB)
    db.row_factory = sqlite3.Row
    return db

def init_db():
    with get_db() as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS searches (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                tag       TEXT NOT NULL,
                searched_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )""")
        db.execute("""
            CREATE TABLE IF NOT EXISTS favourites (
                id     INTEGER PRIMARY KEY AUTOINCREMENT,
                tag    TEXT NOT NULL UNIQUE,
                avatar TEXT,
                added_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )""")

def extract_competitive(raw):
    if not raw:
        return {}
    if set(raw.keys()) & ROLES:
        return raw
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

        # Log search to DB
        with get_db() as db:
            db.execute("INSERT INTO searches (tag) VALUES (?)", (tag,))

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

@app.route("/api/history")
def get_history():
    with get_db() as db:
        rows = db.execute(
            "SELECT tag, searched_at FROM searches ORDER BY searched_at DESC LIMIT 20"
        ).fetchall()
    return jsonify([dict(r) for r in rows])

@app.route("/api/favourites", methods=["GET"])
def get_favourites():
    with get_db() as db:
        rows = db.execute("SELECT tag, avatar FROM favourites ORDER BY added_at DESC").fetchall()
    return jsonify([dict(r) for r in rows])

@app.route("/api/favourites", methods=["POST"])
def add_favourite():
    body = request.get_json()
    tag, avatar = body.get("tag"), body.get("avatar")
    if not tag:
        return jsonify({"error": "No tag provided."}), 400
    try:
        with get_db() as db:
            db.execute("INSERT OR IGNORE INTO favourites (tag, avatar) VALUES (?,?)", (tag, avatar))
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/favourites/<path:tag>", methods=["DELETE"])
def remove_favourite(tag):
    with get_db() as db:
        db.execute("DELETE FROM favourites WHERE tag = ?", (tag,))
    return jsonify({"ok": True})

init_db()

if __name__ == "__main__":
    app.run(debug=True, port=5000)