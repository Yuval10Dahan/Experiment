from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

import sqlite3
import uuid
import random
import datetime
import json


app = FastAPI()

# (Optional but useful) Allow browser requests freely (same-origin still works fine)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # for local/simple experiment
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")

DB = "experiment.db"


def db():
    # check_same_thread=False helps sometimes on Windows with reload + SQLite
    return sqlite3.connect(DB, check_same_thread=False)


# ---------- INIT DB ----------
with db() as con:
    cur = con.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS participants (
        id TEXT PRIMARY KEY,
        stress_condition INTEGER,
        created_at TEXT,
        completed_at TEXT
    )
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS answers (
        participant_id TEXT,
        stage TEXT,
        data TEXT,
        created_at TEXT
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

    with db() as con:
        con.execute(
            "INSERT INTO participants (id, stress_condition, created_at, completed_at) VALUES (?,?,?,?)",
            (pid, stress, datetime.datetime.now().isoformat(), None)
        )
        con.commit()

    return {"participant_id": pid, "stress_condition": stress}


@app.post("/save/{stage}")
async def save(stage: str, req: Request):
    # Allowed stages (keep it simple + safe)
    allowed = {"demo", "rep", "exp", "rating"}
    if stage not in allowed:
        raise HTTPException(status_code=400, detail=f"Invalid stage '{stage}'")

    body = await req.json()
    participant_id = body.get("participant_id")
    data = body.get("data")

    if not participant_id:
        raise HTTPException(status_code=400, detail="Missing participant_id")

    # Ensure participant exists
    with db() as con:
        cur = con.cursor()
        cur.execute("SELECT id FROM participants WHERE id=?", (participant_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="participant_id not found")

        # Store as JSON string (supports arrays/objects cleanly)
        data_json = json.dumps(data, ensure_ascii=False)

        con.execute(
            "INSERT INTO answers (participant_id, stage, data, created_at) VALUES (?,?,?,?)",
            (participant_id, stage, data_json, datetime.datetime.now().isoformat())
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
        cur = con.cursor()
        cur.execute("SELECT id FROM participants WHERE id=?", (participant_id,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="participant_id not found")

        con.execute(
            "UPDATE participants SET completed_at=? WHERE id=?",
            (datetime.datetime.now().isoformat(), participant_id)
        )
        con.commit()

    return {"done": True}
