"""My Festival REST API — M10 MALLIRATKAISU / REFERENCE SOLUTION (teacher only).

Based on the starter:

FI: Tämä on M10-tehtävän lähtöpohja. GET /api/artists on valmiina mallina;
    toteuta loput TODO-kohdat. Aja paikallisesti:  python app.py
    ja testaa:  python test_endpoints.py http://localhost:8080
EN: This is the M10 starter. GET /api/artists is done as an example;
    implement the remaining TODOs. Run locally:  python app.py
    and test:  python test_endpoints.py http://localhost:8080
"""
import os
import sqlite3
from datetime import datetime, timedelta

from flask import Flask, jsonify, request

app = Flask(__name__)

# FI: Kanta kulkee kontin mukana. Polun voi vaihtaa ympäristömuuttujalla.
# EN: The database ships inside the container. Override the path with an env var.
DB_PATH = os.environ.get("DB_PATH", os.path.join(os.path.dirname(__file__), "myfestival.db"))


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")  # M8: sqlite3 ei valvo FK:ita oletuksena / FKs are off by default
    conn.row_factory = sqlite3.Row
    return conn


@app.get("/")
def health():
    """FI: Rahti ja selain näkevät, että sovellus on pystyssä.
    EN: Lets Rahti and your browser see the app is up."""
    return jsonify(status="ok", endpoints=["/api/artists", "/api/days", "/api/stages",
                                           "/api/artists/<id>/events", "/api/timetable?day=YYYY-MM-DD",
                                           "POST /api/events", "DELETE /api/events/<id>"])


@app.get("/api/artists")
def get_artists():
    conn = get_db()
    rows = conn.execute("SELECT artist_id, name, country FROM Artist ORDER BY name").fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.get("/api/days")
def get_days():
    """FI: Apuendpoint: festivaalipäivät (tarkistin hakee tästä day_id:n).
    EN: Helper endpoint: festival days (the checker reads day_id from here)."""
    conn = get_db()
    rows = conn.execute("SELECT day_id, date FROM Day ORDER BY date").fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.get("/api/stages")
def get_stages():
    """FI: Apuendpoint: lavat. EN: Helper endpoint: stages."""
    conn = get_db()
    rows = conn.execute("SELECT stage_id, name FROM Stage ORDER BY stage_id").fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.get("/api/artists/<int:artist_id>/events")
def get_artist_events(artist_id):
    conn = get_db()
    if conn.execute("SELECT 1 FROM Artist WHERE artist_id = ?", (artist_id,)).fetchone() is None:
        conn.close()
        return jsonify(error=f"artist {artist_id} not found"), 404
    rows = conn.execute("""
        SELECT e.event_id, d.date AS day, st.name AS stage, time(e.start_dt) AS starts
        FROM Event e JOIN Day d USING(day_id) JOIN Stage st USING(stage_id)
                     JOIN EventType et USING(event_type_id)
        WHERE e.artist_id = ? AND et.code = 'performance'
        ORDER BY e.start_dt""", (artist_id,)).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.get("/api/timetable")
def get_timetable():
    day = request.args.get("day")
    sql = "SELECT date, stage, artist, starts, ends FROM V_Schedule"
    params = ()
    if day is not None:
        try:
            datetime.strptime(day, "%Y-%m-%d")
        except ValueError:
            return jsonify(error="day must be YYYY-MM-DD"), 400
        sql += " WHERE date = ?"
        params = (day,)
    conn = get_db()
    rows = conn.execute(sql + " ORDER BY date, starts", params).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


REQUIRED = ("artist_id", "stage_id", "day_id", "start_dt")


@app.post("/api/events")
def create_event():
    body = request.get_json(silent=True) or {}
    missing = [k for k in REQUIRED if k not in body]
    if missing:
        return jsonify(error=f"missing fields: {', '.join(missing)}"), 400
    try:
        start = datetime.strptime(body["start_dt"], "%Y-%m-%d %H:%M:%S")
    except (TypeError, ValueError):
        return jsonify(error="start_dt must be 'YYYY-MM-DD HH:MM:SS'"), 400
    duration = int(body.get("duration_min", 45))
    end = start + timedelta(minutes=duration)
    conn = get_db()
    try:
        with conn:
            cur = conn.execute("""
                INSERT INTO Event(event_type_id, day_id, stage_id, artist_id, start_dt, end_dt, duration_min)
                VALUES ((SELECT event_type_id FROM EventType WHERE code = 'performance'), ?, ?, ?, ?, ?, ?)""",
                (body["day_id"], body["stage_id"], body["artist_id"],
                 start.strftime("%Y-%m-%d %H:%M:%S"), end.strftime("%Y-%m-%d %H:%M:%S"), duration))
        new_id = cur.lastrowid
    except sqlite3.IntegrityError as e:
        conn.close()
        return jsonify(error=f"constraint failed: {e}"), 400
    conn.close()
    return jsonify(event_id=new_id, artist_id=body["artist_id"], stage_id=body["stage_id"],
                   day_id=body["day_id"], start_dt=body["start_dt"], duration_min=duration), 201


@app.delete("/api/events/<int:event_id>")
def delete_event(event_id):
    conn = get_db()
    with conn:
        cur = conn.execute("DELETE FROM Event WHERE event_id = ?", (event_id,))
    conn.close()
    if cur.rowcount == 0:
        return jsonify(error=f"event {event_id} not found"), 404
    return "", 204


if __name__ == "__main__":
    # FI: Paikallinen kehityspalvelin. Rahdissa sovellusta ajaa gunicorn (ks. Dockerfile).
    # EN: Local dev server. On Rahti the app is run by gunicorn (see Dockerfile).
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)), debug=True)
