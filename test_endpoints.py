#!/usr/bin/env python3
"""M10 endpoint checker / M10 rajapintatarkistin.

Usage / Käyttö:
    python test_endpoints.py https://<osoitteesi>.rahtiapp.fi
    python test_endpoints.py http://localhost:8080

Valinnainen JSON-tulos (opettajan arviointiskripti) / optional JSON output:
    python test_endpoints.py URL --json
"""
import json
import random
import sys
import urllib.request
import urllib.error

PASS, FAIL = "\033[92mPASS\033[0m", "\033[91mFAIL\033[0m"
results = []


def call(base, path, method="GET", body=None):
    url = base.rstrip("/") + path
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()
    except Exception as e:
        return None, str(e)


JSON_MODE = "--json" in sys.argv
log = []


def check(name, ok, detail=""):
    results.append(ok)
    log.append({"check": name.strip(), "ok": bool(ok), "detail": detail})
    if JSON_MODE:
        return
    print(f"[{PASS if ok else FAIL}] {name}" + (f"  ({detail})" if detail and not ok else ""))


def main(base):
    if not JSON_MODE:
        print(f"Testing {base}\n")

    # 1. GET /api/artists
    status, text = call(base, "/api/artists")
    check("GET /api/artists returns 200", status == 200, f"status={status}")
    artists = []
    try:
        artists = json.loads(text)
        check("  response is a JSON list", isinstance(artists, list))
        check("  list is not empty", len(artists) > 0)
        keys = set(artists[0].keys()) if artists else set()
        check("  items have name field", "name" in keys, f"keys={keys}")
    except (json.JSONDecodeError, TypeError) as e:
        check("  response is valid JSON", False, str(e))

    # 2. GET /api/artists/{id}/events
    if artists:
        aid = artists[0].get("artist_id", artists[0].get("id", 1))
        status, text = call(base, f"/api/artists/{aid}/events")
        check(f"GET /api/artists/{aid}/events returns 200", status == 200, f"status={status}")
    status, _ = call(base, "/api/artists/999999/events")
    check("GET unknown artist returns 404", status == 404, f"status={status}")

    # 3. GET /api/timetable
    status, text = call(base, "/api/timetable")
    check("GET /api/timetable returns 200", status == 200, f"status={status}")
    status, _ = call(base, "/api/timetable?day=not-a-date")
    check("GET timetable with bad date returns 400", status == 400, f"status={status}")

    # 4. POST /api/events
    status, _ = call(base, "/api/events", "POST", {"artist_id": 1})
    check("POST with missing fields returns 400", status == 400, f"status={status}")
    status, _ = call(base, "/api/events", "POST",
                     {"artist_id": 999999, "stage_id": 1, "day_id": 1, "start_dt": "2025-07-05 12:00:00"})
    check("POST with bad foreign key returns 400", status == 400, f"status={status}")
    # Random small-hours start time so the checker can be re-run against the same
    # database without tripping the UNIQUE(day_id, stage_id, start_dt) constraint.
    start_dt = f"2025-07-05 0{random.randint(0, 4)}:{random.randint(0, 59):02d}:{random.randint(0, 59):02d}"
    status, text = call(base, "/api/events", "POST",
                        {"artist_id": 1, "stage_id": 1, "day_id": 1, "start_dt": start_dt})
    check("POST with valid body returns 201", status == 201, f"status={status}, body={text[:120]}")

    if JSON_MODE:
        print(json.dumps({"url": base, "passed": sum(results), "total": len(results), "checks": log}))
    else:
        print(f"\n{sum(results)}/{len(results)} checks passed")
    sys.exit(0 if all(results) else 1)


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "--json"]
    if len(args) != 1:
        print(__doc__)
        sys.exit(2)
    main(args[0])
