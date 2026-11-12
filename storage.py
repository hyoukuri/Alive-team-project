"""SEEDU:ON 저장소 (계정 / 세션 / 분석 기록)

- 배포: 환경변수 DATABASE_URL(postgres://...)이 있으면 Postgres(Neon)를 사용한다.
- 로컬 개발: DATABASE_URL이 없거나 sqlite:/// 로 시작하면 SQLite 파일을 사용한다.
- 테이블은 서버 시작 시 자동으로 만든다(CREATE TABLE IF NOT EXISTS).
- 비밀번호, 세션 토큰, 생기부 원문은 절대 로그에 남기지 않는다.
"""

import os
import sqlite3
from contextlib import contextmanager

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
IS_POSTGRES = DATABASE_URL.startswith(("postgres://", "postgresql://"))

if IS_POSTGRES:
    SQLITE_PATH = None
elif DATABASE_URL.startswith("sqlite:///"):
    SQLITE_PATH = DATABASE_URL[len("sqlite:///"):]
else:
    SQLITE_PATH = os.getenv("SQLITE_PATH", "seeduon_local.db")


POSTGRES_SCHEMA = [
    """CREATE TABLE IF NOT EXISTS users (
        id BIGSERIAL PRIMARY KEY,
        username TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )""",
    """CREATE TABLE IF NOT EXISTS sessions (
        token_hash TEXT PRIMARY KEY,
        user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        expires_at TIMESTAMPTZ NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS analyses (
        id BIGSERIAL PRIMARY KEY,
        user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        grade INTEGER NOT NULL,
        subjects TEXT NOT NULL,
        top_major TEXT NOT NULL,
        top_fit_level TEXT NOT NULL,
        keywords TEXT NOT NULL,
        result TEXT NOT NULL
    )""",
    "CREATE INDEX IF NOT EXISTS analyses_user_created ON analyses (user_id, created_at DESC)",
]

SQLITE_SCHEMA = [
    """CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
    )""",
    """CREATE TABLE IF NOT EXISTS sessions (
        token_hash TEXT PRIMARY KEY,
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        expires_at TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS analyses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
        grade INTEGER NOT NULL,
        subjects TEXT NOT NULL,
        top_major TEXT NOT NULL,
        top_fit_level TEXT NOT NULL,
        keywords TEXT NOT NULL,
        result TEXT NOT NULL
    )""",
    "CREATE INDEX IF NOT EXISTS analyses_user_created ON analyses (user_id, created_at DESC)",
]


def _connect():
    if IS_POSTGRES:
        # Postgres 드라이버는 배포 환경에서만 불러온다
        import psycopg
        from psycopg.rows import dict_row
        return psycopg.connect(DATABASE_URL, row_factory=dict_row, connect_timeout=15)

    conn = sqlite3.connect(SQLITE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _sql(query):
    """쿼리는 ? 자리표시자로 쓰고, Postgres일 때만 %s로 바꾼다."""
    return query.replace("?", "%s") if IS_POSTGRES else query


@contextmanager
def connection():
    conn = _connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def fetch_one(query, params=()):
    with connection() as conn:
        row = conn.execute(_sql(query), params).fetchone()
        return dict(row) if row is not None else None


def fetch_all(query, params=()):
    with connection() as conn:
        return [dict(row) for row in conn.execute(_sql(query), params).fetchall()]


def execute(query, params=()):
    """INSERT ... RETURNING / UPDATE / DELETE 실행. RETURNING이 있으면 첫 행을 돌려준다."""
    with connection() as conn:
        cursor = conn.execute(_sql(query), params)
        row = cursor.fetchone() if "RETURNING" in query.upper() else None
        affected = cursor.rowcount
        return (dict(row) if row is not None else None), affected


def init_db():
    with connection() as conn:
        for statement in POSTGRES_SCHEMA if IS_POSTGRES else SQLITE_SCHEMA:
            conn.execute(statement)


def backend_name():
    return "postgres" if IS_POSTGRES else "sqlite"
