"""SEEDU:ON Rubric 3.2 API — full-record semantic analysis.

All student-record segments must be processed successfully before returning an
AI-scored result. No API keys or student text are logged.
"""
from __future__ import annotations

import copy
import hashlib
import json
import logging
import os
import re
import threading
import time
from collections import OrderedDict
from typing import Any, Literal

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

load_dotenv()
app = FastAPI(title='SEEDU:ON Rubric 3.2 API')
app.add_middleware(
    CORSMiddleware,
    allow_origins=['https://alive-team-project.vercel.app'],
    allow_origin_regex=r'https://.*\.vercel\.app',
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

from accounts import router as accounts_router
app.include_router(accounts_router)
from rubric_engine import make_roadmap, analyze_records, MAJORS
from semantic_engine import prepare, candidates_from_sources
from full_record_analysis import analyze_all_sources

LOG = logging.getLogger('seedu.main')
VERSION = 'rubric-3.2-major-evidence-ui-20261115'
CACHE_TTL = 6 * 60 * 60
CACHE_MAX = 128
LIMIT_COOLDOWN = 120
_cache = OrderedDict()
_inflight = {}
_last_limited_until = 0.0
_lock = threading.Lock()


class AnalyzeRequest(BaseModel):
    grade: int = Field(default=1, ge=1, le=2)
    records: Any = None
    text: str = ''
    subjects: list[str] = Field(default_factory=list)
    analysis_mode: Literal['hybrid', 'fast'] = 'hybrid'
    model_config = {'extra': 'allow'}


class RoadmapRequest(BaseModel):
    grade: int = Field(default=1, ge=1, le=2)
    major: str = ''
    records: Any = None
    text: str = ''
    analysis: Any = None
    model_config = {'extra': 'allow'}


@app.get('/')
def home():
    return {'message': 'SEEDU:ON Rubric 3.2 running', 'rubric_version': VERSION}


@app.get('/majors')
def list_majors():
    """Available exploration fields; not an aptitude ranking."""
    return {'count': len(MAJORS), 'majors': sorted(MAJORS)}


@app.get('/health')
def health():
    return {'status': 'ok', 'rubric_version': VERSION}


def _cache_key(req):
    data = {
        'grade': req.grade,
        'records': req.records,
        'text': req.text,
        'subjects': req.subjects,
        'mode': req.analysis_mode,
        'version': VERSION,
    }
    return hashlib.sha256(
        json.dumps(data, sort_keys=True, ensure_ascii=False, default=str).encode()
    ).hexdigest()


def _preview(req, why):
    """Conservative rule preview; not verified semantic-AI analysis."""
    result = analyze_records(req.records, req.text, req.grade)
    for c in result.get('competencies', []):
        if type(c.get('rating')) is int:
            c['rating'] = min(c['rating'], 2)
            c['score'] = c['rating'] * 25
            c['status'] = 'provisional_rule'
    for fit in result.get('major_fit', []):
        scores = {}
        covered = 0
        for d in fit.get('indicator_details', []):
            r = d.get('rating')
            d['rating'] = min(r, 2) if type(r) is int else None
            if type(d['rating']) is int:
                covered += d.get('weight', 0)
                d['status'] = 'provisional_rule'
                scores[d['category']] = (
                    scores.get(d['category'], 0) + d['weight'] * d['rating'] / 4
                )
        fit['category_scores'] = {k: round(v, 2) for k, v in scores.items()}
        fit['coverage_weight'] = covered
        fit['partial_score'] = round(sum(scores.values()), 2)
        fit['total_score'] = None
        fit['score_status'] = 'provisional_rule'
        fit['evidence'] = (
            'AI 미검증: 어휘 기반 탐색 참고 결과이며 전공 적합도 점수는 확정되지 않았습니다.'
        )
    result['rubric_version'] = VERSION
    result['analysis_mode'] = 'rule_preview_unverified'
    result['assessment_notice'] = (
        'AI 의미 분석이 완료되지 않았습니다. 아래 점수는 키워드 기반의 '
        '제한적 참고치이며 정식 평가가 아닙니다.'
    )
    result['ai_review'] = {'used': False, 'status': 'unverified', 'reason': why}
    return result


def _safe_error_message(exc: Exception) -> str:
    if not isinstance(exc, ValueError):
        return '-'
    message = str(exc).replace('\r', ' ').replace('\n', ' ')
    key = os.getenv('OPENAI_API_KEY', '').strip()
    if key:
        message = message.replace(key, '[REDACTED_API_KEY]')
    message = re.sub(r'sk-[A-Za-z0-9_-]+', '[REDACTED_API_KEY]', message)
    if len(message) > 240:
        return '[validation message truncated; inspect ai_semantic.py]'
    return message or '-'


def _log_error(exc):
    status = getattr(exc, 'status_code', None)
    code = getattr(exc, 'code', None)
    if not isinstance(code, (str, int)):
        code = '-'
    response = getattr(exc, 'response', None)
    request_id = '-'
    retry_after = '-'
    if response is not None:
        headers = getattr(response, 'headers', None)
        if headers:
            request_id = str(headers.get('x-request-id') or headers.get('X-Request-ID') or '-')[:80]
            retry_after = str(headers.get('retry-after') or '-')[:40]
    LOG.warning(
        'SEEDU official OpenAI failure: type=%s status=%s code=%s '
        'reason=%s retry_after=%s request_id=%s',
        type(exc).__name__, status, code, _safe_error_message(exc),
        retry_after, request_id,
    )
    return status


@app.post('/analyze')
def analyze(req: AnalyzeRequest):
    global _last_limited_until
    try:
        sources = prepare(req.records, req.text, req.grade)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if req.analysis_mode == 'fast':
        return _preview(req, 'fast_mode')
    key = _cache_key(req)
    now = time.monotonic()
    with _lock:
        for k, (expiry, _) in list(_cache.items()):
            if expiry <= now:
                _cache.pop(k, None)
        cached = _cache.get(key)
        if cached:
            _cache.move_to_end(key)
            result = copy.deepcopy(cached[1])
            result['ai_review'] = {**result['ai_review'], 'cached': True}
            return result
        limited = now < _last_limited_until
        existing = _inflight.get(key)
        if not existing and not limited:
            existing = threading.Event()
            _inflight[key] = existing
            owner = True
        else:
            owner = False
    if limited:
        raise HTTPException(status_code=503, detail={
            'code': 'AI_COOLDOWN',
            'message': 'AI 사용량 제한으로 전체 세특 분석을 시작할 수 없습니다. 잠시 후 다시 시도해 주세요.',
        })
    if not owner:
        existing.wait(timeout=240)
        with _lock:
            cached = _cache.get(key)
            if cached and cached[0] > time.monotonic():
                result = copy.deepcopy(cached[1])
                result['ai_review'] = {**result['ai_review'], 'cached': True}
                return result
        raise HTTPException(status_code=503, detail='전체 세특 분석 대기 시간이 초과되었습니다. 다시 시도해 주세요.')
    try:
        candidates = candidates_from_sources(sources)
        result = analyze_all_sources(sources, req.records, req.text, req.grade, candidates)
        result['rubric_version'] = VERSION
        result['ai_review'] = {
            'used': True, 'status': 'reviewed',
            'reason': 'full_record_semantic_extraction', 'cached': False,
        }
        with _lock:
            _cache[key] = (time.monotonic() + CACHE_TTL, copy.deepcopy(result))
            _cache.move_to_end(key)
            while len(_cache) > CACHE_MAX:
                _cache.popitem(last=False)
        return result
    except Exception as exc:
        status = _log_error(exc)
        if status == 429:
            with _lock:
                _last_limited_until = time.monotonic() + LIMIT_COOLDOWN
        raise HTTPException(
            status_code=503,
            detail={
                'code': 'FULL_ANALYSIS_INCOMPLETE',
                'message': '전체 세특 분석이 완료되지 않았습니다. 잠시 후 다시 시도해 주세요.',
                'retryable': status in (429, 500, 502, 503, 504),
            },
        ) from exc
    finally:
        with _lock:
            event = _inflight.pop(key, None)
            if event:
                event.set()


@app.post('/roadmap')
def roadmap(req: RoadmapRequest):
    if not req.major.strip():
        raise HTTPException(status_code=400, detail='희망 학과를 입력해 주세요.')
    return make_roadmap(req.major.strip(), req.grade, req.records, req.text)
