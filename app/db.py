"""Couche SQLite minimaliste (thread-safe via une connexion par appel)."""
from __future__ import annotations

import json
import sqlite3
import threading
import time
import uuid
from contextlib import contextmanager
from typing import Any

from .config import DB_PATH, DEFAULT_SETTINGS

_lock = threading.RLock()

SCHEMA = """
CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY,
    title TEXT,
    source_url TEXT,
    source_kind TEXT,
    status TEXT,
    progress REAL DEFAULT 0,
    message TEXT,
    error TEXT,
    options TEXT,
    meta TEXT,
    created_at REAL
);
CREATE TABLE IF NOT EXISTS clips (
    id TEXT PRIMARY KEY,
    project_id TEXT,
    rank INTEGER,
    start REAL,
    end REAL,
    score INTEGER,
    scores TEXT,
    category TEXT,
    title TEXT,
    hook TEXT,
    description TEXT,
    hashtags TEXT,
    reason TEXT,
    transcript TEXT,
    file TEXT,
    thumb TEXT,
    status TEXT,
    error TEXT,
    overrides TEXT,
    created_at REAL
);
CREATE TABLE IF NOT EXISTS accounts (
    id TEXT PRIMARY KEY,
    platform TEXT,
    name TEXT,
    avatar TEXT,
    external_id TEXT,
    tokens TEXT,
    created_at REAL
);
CREATE TABLE IF NOT EXISTS posts (
    id TEXT PRIMARY KEY,
    clip_id TEXT,
    platform TEXT,
    account_id TEXT,
    scheduled_at REAL,
    caption TEXT,
    privacy TEXT,
    status TEXT,
    result TEXT,
    error TEXT,
    created_at REAL,
    published_at REAL
);
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT
);
"""

JSON_FIELDS = {"options", "meta", "scores", "hashtags", "tokens", "result", "overrides"}


def new_id() -> str:
    return uuid.uuid4().hex[:12]


@contextmanager
def conn():
    with _lock:
        c = sqlite3.connect(DB_PATH, timeout=30)
        c.row_factory = sqlite3.Row
        try:
            yield c
            c.commit()
        finally:
            c.close()


def init() -> None:
    with conn() as c:
        c.executescript(SCHEMA)
        # Au redémarrage, les traitements interrompus repartent en file d'attente
        c.execute(
            "UPDATE projects SET status='queued', message='Reprise après redémarrage' "
            "WHERE status NOT IN ('done','error','queued')"
        )
        c.execute("UPDATE clips SET status='queued' WHERE status='rendering'")
        c.execute("UPDATE posts SET status='scheduled' WHERE status='publishing'")


def _decode(row: sqlite3.Row | None) -> dict | None:
    if row is None:
        return None
    d = dict(row)
    for k in JSON_FIELDS & d.keys():
        if d[k]:
            try:
                d[k] = json.loads(d[k])
            except (TypeError, ValueError):
                pass
    return d


def _encode(values: dict) -> dict:
    out = {}
    for k, v in values.items():
        out[k] = json.dumps(v, ensure_ascii=False) if k in JSON_FIELDS and v is not None else v
    return out


def insert(table: str, values: dict) -> dict:
    values = dict(values)
    values.setdefault("id", new_id())
    values.setdefault("created_at", time.time())
    enc = _encode(values)
    cols = ",".join(enc)
    qs = ",".join("?" for _ in enc)
    with conn() as c:
        c.execute(f"INSERT INTO {table} ({cols}) VALUES ({qs})", list(enc.values()))
    return values


def update(table: str, id_: str, **values: Any) -> None:
    if not values:
        return
    enc = _encode(values)
    sets = ",".join(f"{k}=?" for k in enc)
    with conn() as c:
        c.execute(f"UPDATE {table} SET {sets} WHERE id=?", [*enc.values(), id_])


def get(table: str, id_: str) -> dict | None:
    with conn() as c:
        return _decode(c.execute(f"SELECT * FROM {table} WHERE id=?", (id_,)).fetchone())


def query(sql: str, params: tuple | list = ()) -> list[dict]:
    with conn() as c:
        return [_decode(r) for r in c.execute(sql, params).fetchall()]


def delete(table: str, id_: str) -> None:
    with conn() as c:
        c.execute(f"DELETE FROM {table} WHERE id=?", (id_,))


# ---------- Réglages ----------

def get_settings() -> dict:
    s = json.loads(json.dumps(DEFAULT_SETTINGS))
    with conn() as c:
        for row in c.execute("SELECT key, value FROM settings"):
            try:
                val = json.loads(row["value"])
            except ValueError:
                continue
            if row["key"] == "brand" and isinstance(val, dict):
                s["brand"].update(val)
            else:
                s[row["key"]] = val
    return s


def set_settings(values: dict) -> None:
    with conn() as c:
        for k, v in values.items():
            if k not in DEFAULT_SETTINGS:
                continue
            c.execute(
                "INSERT INTO settings(key,value) VALUES(?,?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (k, json.dumps(v, ensure_ascii=False)),
            )
