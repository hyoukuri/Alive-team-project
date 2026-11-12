"""SEEDU:ON 로그인 / 분석 기록 API

프론트엔드는 Vercel의 /api/* 경로로 요청하고, Vercel이 이 서버의 /api/*로 그대로 넘긴다.
그래서 브라우저 입장에서는 같은 사이트 요청이 되어 httpOnly 쿠키가 안정적으로 동작한다.

규칙
- 아이디: 영문/숫자 4~16자 (소문자로 통일해 저장)
- 비밀번호: 6~64자, bcrypt 해시로만 저장
- 아이디가 없으면 새 계정을 만들고, 있으면 비밀번호를 확인한다
- 실패 메시지는 아이디/비밀번호 중 무엇이 틀렸는지 알려주지 않는다
- 로그인 실패 횟수 제한(아이디 기준, IP 기준), 계정 생성 횟수 제한(IP 기준)
- 기록은 항상 로그인한 사용자 소유인지 서버에서 확인한다
- 비밀번호 / 세션 토큰 / 생기부 원문은 로그에 남기지 않는다
"""

import hashlib
import json
import os
import re
import secrets
import threading
import time
from datetime import datetime, timedelta, timezone

import bcrypt
from fastapi import APIRouter, Cookie, HTTPException, Request, Response
from pydantic import BaseModel, Field

import storage

router = APIRouter(prefix="/api")

SESSION_COOKIE = "seeduon_session"
SESSION_DAYS = 7
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "true").lower() != "false"

USERNAME_RE = re.compile(r"^[A-Za-z0-9]{4,16}$")
PASSWORD_MIN, PASSWORD_MAX = 6, 64
MAX_RESULT_BYTES = 200_000
MAX_RECORDS_PER_USER = 200

GENERIC_LOGIN_ERROR = "아이디 또는 비밀번호가 올바르지 않아요."


# =========================================
# 시도 횟수 제한 (서버 메모리 기준, 재시작 시 초기화)
# =========================================

class RateLimiter:
    def __init__(self):
        self._events = {}
        self._lock = threading.Lock()

    def _recent(self, key, window):
        now = time.monotonic()
        events = [t for t in self._events.get(key, []) if now - t < window]
        self._events[key] = events
        return events

    def blocked(self, key, limit, window):
        with self._lock:
            return len(self._recent(key, window)) >= limit

    def hit(self, key):
        with self._lock:
            self._events.setdefault(key, []).append(time.monotonic())

    def clear(self, key):
        with self._lock:
            self._events.pop(key, None)


limiter = RateLimiter()
FAIL_WINDOW = 15 * 60          # 15분
FAILS_PER_USERNAME = 5         # 같은 아이디로 15분에 5번 실패하면 잠시 차단
FAILS_PER_IP = 20              # 같은 IP에서 15분에 20번 실패하면 잠시 차단
SIGNUP_WINDOW = 60 * 60        # 1시간
SIGNUPS_PER_IP = 10            # 같은 IP에서 1시간에 새 계정 10개까지


def client_ip(request: Request):
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


# =========================================
# 공통 도우미
# =========================================

def now_utc():
    return datetime.now(timezone.utc)


def to_datetime(value):
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    text = str(value).replace("Z", "+00:00")
    parsed = datetime.fromisoformat(text)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def to_iso(value):
    return to_datetime(value).astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def db_time(value: datetime):
    """Postgres는 datetime 그대로, SQLite는 ISO 문자열로 저장한다."""
    return value if storage.IS_POSTGRES else to_iso(value)


def hash_token(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def set_session_cookie(response: Response, token):
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=SESSION_DAYS * 24 * 60 * 60,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="lax",
        path="/api",
    )


def clear_session_cookie(response: Response):
    response.delete_cookie(SESSION_COOKIE, path="/api", secure=COOKIE_SECURE, httponly=True, samesite="lax")


def current_user(token):
    """세션 쿠키로 사용자를 찾는다. 없거나 만료되면 None."""
    if not token:
        return None
    row = storage.fetch_one(
        "SELECT s.user_id, s.expires_at, u.username FROM sessions s "
        "JOIN users u ON u.id = s.user_id WHERE s.token_hash = ?",
        (hash_token(token),),
    )
    if row is None:
        return None
    if to_datetime(row["expires_at"]) <= now_utc():
        storage.execute("DELETE FROM sessions WHERE token_hash = ?", (hash_token(token),))
        return None
    return {"id": row["user_id"], "username": row["username"]}


def require_user(token):
    user = current_user(token)
    if user is None:
        raise HTTPException(status_code=401, detail="로그인이 필요해요.")
    return user


def create_session(user_id):
    token = secrets.token_urlsafe(32)
    storage.execute(
        "INSERT INTO sessions (token_hash, user_id, expires_at) VALUES (?, ?, ?)",
        (hash_token(token), user_id, db_time(now_utc() + timedelta(days=SESSION_DAYS))),
    )
    # 만료된 세션 정리
    storage.execute("DELETE FROM sessions WHERE expires_at < ?", (db_time(now_utc()),))
    return token


def ensure_db():
    try:
        storage.init_db()
    except Exception as exc:  # DB 설정 문제여도 분석 기능은 계속 동작해야 한다
        print(f"저장소 초기화 실패: {type(exc).__name__}")
        return False
    return True


DB_READY = ensure_db()


def require_db():
    global DB_READY
    if not DB_READY:
        DB_READY = ensure_db()
    if not DB_READY:
        raise HTTPException(status_code=503, detail="저장 기능을 잠시 사용할 수 없어요. 분석은 로그인 없이 계속할 수 있어요.")


# =========================================
# 인증 API
# =========================================

class LoginRequest(BaseModel):
    username: str = Field(default="", max_length=64)
    password: str = Field(default="", max_length=256)


@router.get("/health")
def accounts_health():
    return {"status": "ok", "storage": storage.backend_name(), "ready": DB_READY}


@router.post("/auth/login")
def login(body: LoginRequest, request: Request, response: Response):
    require_db()

    username = body.username.strip()
    password = body.password

    # 형식 오류는 구체적으로 알려준다
    if not USERNAME_RE.fullmatch(username):
        raise HTTPException(status_code=400, detail="아이디는 영문과 숫자로 4~16자여야 해요.")
    if not PASSWORD_MIN <= len(password) <= PASSWORD_MAX:
        raise HTTPException(status_code=400, detail=f"비밀번호는 {PASSWORD_MIN}자 이상 {PASSWORD_MAX}자 이하여야 해요.")

    username = username.lower()
    ip = client_ip(request)
    user_key, ip_key = f"fail:user:{username}", f"fail:ip:{ip}"

    if limiter.blocked(user_key, FAILS_PER_USERNAME, FAIL_WINDOW) or limiter.blocked(ip_key, FAILS_PER_IP, FAIL_WINDOW):
        raise HTTPException(status_code=429, detail="로그인 시도가 너무 많아요. 15분 뒤에 다시 시도해 주세요.")

    user = storage.fetch_one("SELECT id, password_hash FROM users WHERE username = ?", (username,))
    created = False

    if user is None:
        signup_key = f"signup:ip:{ip}"
        if limiter.blocked(signup_key, SIGNUPS_PER_IP, SIGNUP_WINDOW):
            raise HTTPException(status_code=429, detail="새 계정을 너무 많이 만들었어요. 잠시 뒤에 다시 시도해 주세요.")

        password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        try:
            user, _ = storage.execute(
                "INSERT INTO users (username, password_hash) VALUES (?, ?) RETURNING id",
                (username, password_hash),
            )
            created = True
            limiter.hit(signup_key)
        except Exception:
            # 거의 동시에 같은 아이디가 만들어진 경우: 기존 계정으로 확인
            user = storage.fetch_one("SELECT id, password_hash FROM users WHERE username = ?", (username,))
            if user is None:
                raise HTTPException(status_code=500, detail="계정을 만들지 못했어요. 다시 시도해 주세요.")

    if not created:
        if not bcrypt.checkpw(password.encode("utf-8"), user["password_hash"].encode("utf-8")):
            limiter.hit(user_key)
            limiter.hit(ip_key)
            raise HTTPException(status_code=401, detail=GENERIC_LOGIN_ERROR)
        limiter.clear(user_key)

    set_session_cookie(response, create_session(user["id"]))
    return {"username": username, "created": created}


@router.get("/auth/me")
def me(seeduon_session: str | None = Cookie(default=None)):
    require_db()
    user = current_user(seeduon_session)
    return {"loggedIn": user is not None, "username": user["username"] if user else None}


@router.post("/auth/logout")
def logout(response: Response, seeduon_session: str | None = Cookie(default=None)):
    require_db()
    if seeduon_session:
        storage.execute("DELETE FROM sessions WHERE token_hash = ?", (hash_token(seeduon_session),))
    clear_session_cookie(response)
    return {"ok": True}


# =========================================
# 분석 기록 API
# =========================================

class RecordRequest(BaseModel):
    grade: int = Field(ge=1, le=3)
    subjects: list[str] = Field(default_factory=list, max_length=100)
    result: dict


def fit_level(score):
    if not isinstance(score, (int, float)):
        return "평가 점수 없음"
    if score >= 80:
        return "적합도 높음"
    if score >= 60:
        return "적합도 보통"
    return "적합도 낮음"


def summarize(result):
    """목록 화면용 요약: 1위 학과, 적합도 단계, 키워드(강점 앞 3개)."""
    majors = result.get("majors") if isinstance(result.get("majors"), list) else []
    top = majors[0] if majors and isinstance(majors[0], dict) else {}
    strengths = result.get("strengths") if isinstance(result.get("strengths"), list) else []
    keywords = [str(item)[:40] for item in strengths[:3]]
    return (
        str(top.get("name") or "추천 학과 없음")[:100],
        fit_level(top.get("fit")),
        keywords,
    )


def record_summary(row):
    return {
        "id": row["id"],
        "createdAt": to_iso(row["created_at"]),
        "grade": row["grade"],
        "subjects": json.loads(row["subjects"]),
        "topMajor": row["top_major"],
        "topFitLevel": row["top_fit_level"],
        "keywords": json.loads(row["keywords"]),
    }


@router.post("/records")
def save_record(body: RecordRequest, seeduon_session: str | None = Cookie(default=None)):
    require_db()
    user = require_user(seeduon_session)

    result_json = json.dumps(body.result, ensure_ascii=False)
    if len(result_json.encode("utf-8")) > MAX_RESULT_BYTES:
        raise HTTPException(status_code=413, detail="저장할 결과가 너무 커요.")

    count = storage.fetch_one("SELECT COUNT(*) AS n FROM analyses WHERE user_id = ?", (user["id"],))
    if count and count["n"] >= MAX_RECORDS_PER_USER:
        raise HTTPException(status_code=409, detail=f"기록은 {MAX_RECORDS_PER_USER}개까지 저장할 수 있어요. 오래된 기록을 삭제해 주세요.")

    subjects = [str(s).strip()[:40] for s in body.subjects if str(s).strip()]
    top_major, top_fit_level, keywords = summarize(body.result)

    row, _ = storage.execute(
        "INSERT INTO analyses (user_id, grade, subjects, top_major, top_fit_level, keywords, result) "
        "VALUES (?, ?, ?, ?, ?, ?, ?) RETURNING id, created_at",
        (user["id"], body.grade, json.dumps(subjects, ensure_ascii=False), top_major, top_fit_level,
         json.dumps(keywords, ensure_ascii=False), result_json),
    )
    return {"id": row["id"], "createdAt": to_iso(row["created_at"])}


@router.get("/records")
def list_records(seeduon_session: str | None = Cookie(default=None)):
    require_db()
    user = require_user(seeduon_session)
    rows = storage.fetch_all(
        "SELECT id, created_at, grade, subjects, top_major, top_fit_level, keywords "
        "FROM analyses WHERE user_id = ? ORDER BY created_at DESC, id DESC",
        (user["id"],),
    )
    return {"records": [record_summary(row) for row in rows]}


@router.get("/records/{record_id}")
def get_record(record_id: int, seeduon_session: str | None = Cookie(default=None)):
    require_db()
    user = require_user(seeduon_session)
    row = storage.fetch_one(
        "SELECT id, created_at, grade, subjects, top_major, top_fit_level, keywords, result "
        "FROM analyses WHERE id = ? AND user_id = ?",
        (record_id, user["id"]),
    )
    if row is None:
        # 다른 사람 기록인지 여부도 알려주지 않는다
        raise HTTPException(status_code=404, detail="기록을 찾을 수 없어요.")
    return {**record_summary(row), "result": json.loads(row["result"])}


@router.delete("/records/{record_id}")
def delete_record(record_id: int, seeduon_session: str | None = Cookie(default=None)):
    require_db()
    user = require_user(seeduon_session)
    _, affected = storage.execute("DELETE FROM analyses WHERE id = ? AND user_id = ?", (record_id, user["id"]))
    if not affected:
        raise HTTPException(status_code=404, detail="기록을 찾을 수 없어요.")
    return {"ok": True}


@router.delete("/records")
def delete_all_records(seeduon_session: str | None = Cookie(default=None)):
    require_db()
    user = require_user(seeduon_session)
    _, affected = storage.execute("DELETE FROM analyses WHERE user_id = ?", (user["id"],))
    return {"ok": True, "deleted": max(affected, 0)}
