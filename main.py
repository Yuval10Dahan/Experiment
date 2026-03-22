from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

import sqlite3
import uuid
import random
import datetime

def get_israel_time():
    return datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=2))).isoformat()

app = FastAPI()

# Allow browser requests freely (fine for simple experiment)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")

DB = "experiment.db"


def db():
    return sqlite3.connect(DB, check_same_thread=False)


# ---------- INIT DB ----------
with db() as con:
    con.execute("""
    CREATE TABLE IF NOT EXISTS experiment_results (
        participant_id TEXT PRIMARY KEY,

        consent_given INTEGER,   -- 1 = agree, 0 = disagree

        speak_english TEXT,      -- "yes"/"no"
        age INTEGER,
        gender TEXT,             -- "male"/"female"/"other"
        residence TEXT,          -- "north"/"central"/"south"
        socioeconomic TEXT,      -- "low"/"medium"/"high"
        marital_status TEXT,     -- "single"/"married"
        education TEXT,          -- "until_high_school"/"high_school"/"ba"/"masters_or_higher"

        repression_q1  INTEGER,
        repression_q2  INTEGER,
        repression_q3  INTEGER,
        repression_q4  INTEGER,
        repression_q5  INTEGER,
        repression_q6  INTEGER,
        repression_q7  INTEGER,
        repression_q8  INTEGER,
        repression_q9  INTEGER,
        repression_q10 INTEGER,
        repression_q11 INTEGER,
        repression_q12 INTEGER,
        repression_q13 INTEGER,
        repression_q14 INTEGER,
        repression_q15 INTEGER,

        stress_condition INTEGER NOT NULL,
        stress_level INTEGER,

        created_at TEXT NOT NULL,
        completed_at TEXT
    )
    """)
    con.commit()


# ---------- ROUTES ----------
@app.get("/", response_class=HTMLResponse)
def index():
    with open("static/index.html", encoding="utf-8") as f:
        return f.read()


@app.post("/start")
async def start():
    pid = str(uuid.uuid4())
    stress = random.choice([0, 1])
    return {
        "participant_id": pid,
        "stress_condition": stress,
        "start_time": get_israel_time()
    }


def ensure_participant_exists(con, participant_id: str):
    cur = con.cursor()
    cur.execute(
        "SELECT participant_id FROM experiment_results WHERE participant_id=?",
        (participant_id,),
    )
    if not cur.fetchone():
        raise HTTPException(status_code=404, detail="participant_id not found")


@app.post("/save/consent")
async def save_consent(req: Request):
    body = await req.json()
    participant_id = body.get("participant_id")
    data = body.get("data") or {}

    if not participant_id:
        raise HTTPException(status_code=400, detail="Missing participant_id")

    consent_given = data.get("consent_given")
    if consent_given not in (0, 1):
        raise HTTPException(status_code=400, detail="consent_given must be 0 or 1")

    with db() as con:
        ensure_participant_exists(con, participant_id)

        con.execute(
            "UPDATE experiment_results SET consent_given=? WHERE participant_id=?",
            (consent_given, participant_id),
        )
        con.commit()

    return {"ok": True}


@app.post("/save/demo")
async def save_demo(req: Request):
    body = await req.json()
    participant_id = body.get("participant_id")
    data = body.get("data") or {}

    if not participant_id:
        raise HTTPException(status_code=400, detail="Missing participant_id")

    speak_english = data.get("speak_english")
    age = data.get("age")
    gender = data.get("gender")
    residence = data.get("residence")
    socioeconomic = data.get("socioeconomic")
    marital_status = data.get("marital_status")
    education = data.get("education")

    # ---- validations ----
    if speak_english not in ("yes", "no"):
        raise HTTPException(status_code=400, detail="speak_english must be yes/no")

    if not isinstance(age, int) or age < 18 or age > 99:
        raise HTTPException(status_code=400, detail="Invalid age (must be integer 18-99)")

    if gender not in ("male", "female", "other"):
        raise HTTPException(status_code=400, detail="gender must be male/female/other")

    if residence not in ("north", "central", "south"):
        raise HTTPException(status_code=400, detail="residence must be north/central/south")

    if socioeconomic not in ("low", "medium", "high"):
        raise HTTPException(status_code=400, detail="socioeconomic must be low/medium/high")

    if marital_status not in ("single", "married"):
        raise HTTPException(status_code=400, detail="marital_status must be single/married")

    if education not in ("until_high_school", "high_school", "ba", "masters_or_higher"):
        raise HTTPException(
            status_code=400,
            detail="education must be until_high_school/high_school/ba/masters_or_higher",
        )

    with db() as con:
        ensure_participant_exists(con, participant_id)

        con.execute(
            """
            UPDATE experiment_results
            SET speak_english=?,
                age=?,
                gender=?,
                residence=?,
                socioeconomic=?,
                marital_status=?,
                education=?
            WHERE participant_id=?
            """,
            (
                speak_english,
                age,
                gender,
                residence,
                socioeconomic,
                marital_status,
                education,
                participant_id,
            ),
        )
        con.commit()

    return {"ok": True}


@app.post("/save/rep")
async def save_rep(req: Request):
    body = await req.json()
    participant_id = body.get("participant_id")
    data = body.get("data")

    if not participant_id:
        raise HTTPException(status_code=400, detail="Missing participant_id")
    if not isinstance(data, list):
        raise HTTPException(status_code=400, detail="Repression data must be a list")

    scores = {}
    for item in data:
        if not isinstance(item, dict):
            continue
        q_idx = item.get("qIndex")
        score = item.get("score")
        if (
            isinstance(q_idx, int)
            and 1 <= q_idx <= 15
            and isinstance(score, int)
            and 1 <= score <= 5
        ):
            scores[q_idx] = score

    missing = [i for i in range(1, 16) if i not in scores]
    if missing:
        raise HTTPException(status_code=400, detail=f"Missing repression answers: {missing}")

    cols = [f"repression_q{i}=?" for i in range(1, 16)]
    values = [scores[i] for i in range(1, 16)]
    values.append(participant_id)

    with db() as con:
        ensure_participant_exists(con, participant_id)
        con.execute(
            f"UPDATE experiment_results SET {', '.join(cols)} WHERE participant_id=?",
            values,
        )
        con.commit()

    return {"ok": True}


@app.post("/save/rating")
async def save_rating(req: Request):
    body = await req.json()
    participant_id = body.get("participant_id")
    data = body.get("data") or {}

    if not participant_id:
        raise HTTPException(status_code=400, detail="Missing participant_id")

    rating = data.get("rating")
    if not isinstance(rating, int) or rating < 0 or rating > 100:
        raise HTTPException(status_code=400, detail="Invalid rating (must be integer 0-100)")

    with db() as con:
        ensure_participant_exists(con, participant_id)

        con.execute(
            "UPDATE experiment_results SET stress_level=? WHERE participant_id=?",
            (rating, participant_id),
        )
        con.commit()

    return {"ok": True}

@app.post("/submit_disagree")
async def submit_disagree(req: Request):
    body = await req.json()
    participant_id = body.get("participant_id")
    stress_condition = body.get("stress_condition")
    start_time = body.get("start_time") or get_israel_time()
    completed_at = get_israel_time()
    
    with db() as con:
        con.execute(
            """
            INSERT INTO experiment_results (
                participant_id, stress_condition, created_at, completed_at, consent_given
            ) VALUES (?,?,?,?,?)
            """,
            (participant_id, stress_condition, start_time, completed_at, 0),
        )
        con.commit()
    return {"ok": True}

@app.post("/submit_all")
async def submit_all(req: Request):
    body = await req.json()
    participant_id = body.get("participant_id")
    stress_condition = body.get("stress_condition")
    start_time = body.get("start_time") or get_israel_time()
    data = body.get("data") or {}

    if not participant_id:
        raise HTTPException(status_code=400, detail="Missing participant_id")

    consent_given = data.get("consent_given")
    demo = data.get("demo") or {}
    rep = data.get("rep") or []
    rating = data.get("rating")

    if consent_given != 1:
        raise HTTPException(status_code=400, detail="consent_given must be 1")

    speak_english = demo.get("speak_english")
    age = demo.get("age")
    gender = demo.get("gender")
    residence = demo.get("residence")
    socioeconomic = demo.get("socioeconomic")
    marital_status = demo.get("marital_status")
    education = demo.get("education")

    if speak_english not in ("yes", "no"):
        raise HTTPException(status_code=400, detail="speak_english must be yes/no")

    if not isinstance(age, int) or age < 18 or age > 99:
        raise HTTPException(status_code=400, detail="Invalid age (must be integer 18-99)")

    if gender not in ("male", "female", "other"):
        raise HTTPException(status_code=400, detail="gender must be male/female/other")

    if residence not in ("north", "central", "south"):
        raise HTTPException(status_code=400, detail="residence must be north/central/south")

    if socioeconomic not in ("low", "medium", "high"):
        raise HTTPException(status_code=400, detail="socioeconomic must be low/medium/high")

    if marital_status not in ("single", "married"):
        raise HTTPException(status_code=400, detail="marital_status must be single/married")

    if education not in ("until_high_school", "high_school", "ba", "masters_or_higher"):
        raise HTTPException(
            status_code=400,
            detail="education must be until_high_school/high_school/ba/masters_or_higher",
        )

    scores = {}
    for item in rep:
        if not isinstance(item, dict):
            continue
        q_idx = item.get("qIndex")
        score = item.get("score")
        if (
            isinstance(q_idx, int)
            and 1 <= q_idx <= 15
            and isinstance(score, int)
            and 1 <= score <= 5
        ):
            scores[q_idx] = score

    missing = [i for i in range(1, 16) if i not in scores]
    if missing:
        raise HTTPException(status_code=400, detail=f"Missing repression answers: {missing}")

    if not isinstance(rating, int) or rating < 0 or rating > 100:
        raise HTTPException(status_code=400, detail="Invalid rating (must be integer 0-100)")

    completed_at = get_israel_time()

    with db() as con:
        con.execute(
            """
            INSERT INTO experiment_results (
                participant_id,
                stress_condition,
                created_at,
                completed_at,
                consent_given,
                speak_english,
                age,
                gender,
                residence,
                socioeconomic,
                marital_status,
                education,
                repression_q1,
                repression_q2,
                repression_q3,
                repression_q4,
                repression_q5,
                repression_q6,
                repression_q7,
                repression_q8,
                repression_q9,
                repression_q10,
                repression_q11,
                repression_q12,
                repression_q13,
                repression_q14,
                repression_q15,
                stress_level
            ) VALUES (
                ?, ?, ?, ?,
                ?, ?, ?, ?, ?,
                ?, ?, ?,
                ?, ?, ?, ?,
                ?, ?, ?, ?,
                ?, ?, ?, ?,
                ?, ?, ?,
                ?
            )
            """,
            (
                participant_id,
                stress_condition,
                start_time,
                completed_at,
                consent_given,
                speak_english,
                age,
                gender,
                residence,
                socioeconomic,
                marital_status,
                education,
                scores[1],
                scores[2],
                scores[3],
                scores[4],
                scores[5],
                scores[6],
                scores[7],
                scores[8],
                scores[9],
                scores[10],
                scores[11],
                scores[12],
                scores[13],
                scores[14],
                scores[15],
                rating,
            ),
        )
        con.commit()

    return {"ok": True}


@app.post("/finish")
async def finish(req: Request):
    body = await req.json()
    participant_id = body.get("participant_id")

    if not participant_id:
        raise HTTPException(status_code=400, detail="Missing participant_id")

    with db() as con:
        ensure_participant_exists(con, participant_id)

        con.execute(
            "UPDATE experiment_results SET completed_at=? WHERE participant_id=?",
            (get_israel_time(), participant_id),
        )
        con.commit()

    return {"done": True}


@app.get("/admin/results", response_class=HTMLResponse)
def get_results():
    with db() as con:
        cur = con.cursor()
        # cur.execute("SELECT * FROM experiment_results ORDER BY created_at DESC")
        cur.execute("""
            SELECT * FROM experiment_results
            WHERE completed_at IS NOT NULL
            ORDER BY created_at DESC
        """)
        rows = cur.fetchall()
        cols = [description[0] for description in cur.description]
    
    html = "<html><head><meta charset='utf-8'><title>Results</title><style>table, th, td {border: 1px solid black; border-collapse: collapse; padding: 5px;}</style></head><body><h1>Experiment Results</h1><table>"
    html += "<tr>" + "".join(f"<th>{c}</th>" for c in cols) + "</tr>"
    for row in rows:
        html += "<tr>" + "".join(f"<td>{v}</td>" for v in row) + "</tr>"
    html += "</table></body></html>"
    return html


@app.get("/admin/download_db")
def download_db():
    import os
    if not os.path.exists(DB):
        raise HTTPException(status_code=404, detail="Database file not found.")
    return FileResponse(DB, filename="experiment.db")