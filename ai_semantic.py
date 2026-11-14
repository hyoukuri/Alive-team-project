"""SEEDU:ON 3.1 — lightweight OpenRouter semantics with safe 429 diagnostics.

One completion request, no automatic retries, no model-specific reasoning options.
Logs safe error metadata (never API keys, prompts or student-record text).
"""
from __future__ import annotations

import json
import logging
import os
import re
import time
import urllib.request
from typing import Any

from rubric_v2 import COMPETENCY_NAMES

LOG = logging.getLogger('seedu.semantic')
_model_id = None
_model_checked_at = 0.0
URL = 'https://openrouter.ai/api/v1'
TAGS = set('learning career question method result validation revision collaboration leadership reflection planning interdisciplinary comparison application continuity concept'.split())

SYSTEM = ("학생부 근거 추출기다. 아래 학생부에서 실제 수행·결과·개선 행동을 이해하고 "
          "원문 그대로 짧게 인용해 JSON만 출력한다. 키워드만으로 우수하다고 판단하지 마라. "
          "없는 근거를 만들지 마라. 반드시 한 줄 JSON: "
          '{"f":[[0,"학생부에서 그대로 인용한 12자 이상 구절",["method","result"]]],'
          '"c":[[2,[0]],[null,[]],[2,[0]],[null,[]],[null,[]]],"m":[[0],[],[]]}. '
          'f는 최대 4개이며 각 항목은 [자료번호,원문인용,태그]. '
          'c는 학업,진로,탐구,공동체,성장 순서로 정확히 5개 [0~4 또는 null, 근거번호배열]. '
          '1은 참여,2는 구체적 수행,3은 방법과 결과 연결,4는 뚜렷한 검증과 실질적 개선. '
          'm은 제시된 전공 후보 3개와 관련된 근거번호 배열. 설명문 없이 JSON만 반환.')


def _payload(sources: list[dict], candidates: list[str]) -> str:
    if not sources:
        raise ValueError('학생부 기록 없음')
    budget = 1900
    count = min(len(sources), 7)
    per_item = max(140, budget // max(count, 1))
    selected = []
    for i, item in enumerate(sources[:7]):
        raw = str(item.get('text') or '').strip()
        excerpt = raw[:min(per_item, budget)]
        if excerpt:
            selected.append({'i': i, 't': excerpt})
            budget -= len(excerpt)
        if budget <= 0:
            break
    return json.dumps({'s': selected, 'm': list(candidates[:3])}, ensure_ascii=False, separators=(',', ':'))


def _json_object(content: str) -> dict:
    if not isinstance(content, str) or not content.strip():
        raise ValueError('빈 AI 응답')
    body = re.sub(r'^```(?:json)?\s*', '', content.strip(), flags=re.I)
    body = re.sub(r'\s*```$', '', body)
    start, end = body.find('{'), body.rfind('}')
    if start < 0 or end <= start:
        raise ValueError('완성된 JSON 객체 없음')
    parsed = json.loads(body[start:end + 1])
    if not isinstance(parsed, dict) or not isinstance(parsed.get('f'), list) or not isinstance(parsed.get('c'), list) or len(parsed['c']) != 5:
        raise ValueError('AI 출력 구조 오류')
    return parsed


def _normalize(parsed: dict, candidates: list[str]) -> dict:
    facts = []
    for item in parsed['f'][:5]:
        if not isinstance(item, list) or len(item) < 3 or type(item[0]) is not int or not isinstance(item[1], str) or not isinstance(item[2], list):
            continue
        facts.append({'source_index': item[0], 'quote': item[1], 'tags': [x for x in item[2] if isinstance(x, str) and x in TAGS]})
    competencies = []
    for i, name in enumerate(COMPETENCY_NAMES):
        row = parsed['c'][i]
        rating = row[0] if isinstance(row, list) and row else None
        links = row[1] if isinstance(row, list) and len(row) > 1 and isinstance(row[1], list) else []
        if type(rating) is not int or rating < 0 or rating > 4:
            rating = None
        competencies.append({'name': name, 'rating': rating, 'evidence_ids': [x for x in links if type(x) is int and 0 <= x < len(facts)]})
    raw_links = parsed.get('m', [])
    major_links = []
    for i, name in enumerate(candidates[:3]):
        ids = raw_links[i] if isinstance(raw_links, list) and len(raw_links) > i and isinstance(raw_links[i], list) else []
        major_links.append({'major': name, 'evidence_ids': [x for x in ids if type(x) is int and 0 <= x < len(facts)]})
    return {'facts': facts, 'competencies': competencies, 'major_links': major_links}


def _pick_free_chat_model() -> str:
    """Pick a listed free chat model; availability is not guaranteed."""
    global _model_id, _model_checked_at
    if _model_id and time.monotonic() - _model_checked_at < 3600:
        return _model_id
    try:
        req = urllib.request.Request(URL + '/models', headers={'Accept': 'application/json', 'User-Agent': 'SEEDU-ON/3.1'})
        with urllib.request.urlopen(req, timeout=5) as response:
            models = json.load(response).get('data', [])
        options = []
        for entry in models:
            ident = entry.get('id', '') if isinstance(entry, dict) else ''
            if not ident.endswith(':free'):
                continue
            architecture = entry.get('architecture') or {}
            if 'text' not in (architecture.get('input_modalities') or ['text']) or 'text' not in (architecture.get('output_modalities') or ['text']):
                continue
            name = ident.lower()
            if any(x in name for x in ('reasoning', 'thinking', 'nemotron', 'qwq', 'deepseek-r1', 'rerank', 'embedding', 'audio', 'vision', 'vl-', '-vl', 'ocr')):
                continue
            parameters = entry.get('supported_parameters') or []
            if parameters and 'max_tokens' not in parameters:
                continue
            score = 0
            if 'instruct' in name or '-it:' in name:
                score += 5
            if 'gemma' in name:
                score += 2
            if 'chat' in name:
                score += 2
            if 'flash' in name:
                score += 1
            if '70b' in name or '120b' in name:
                score -= 3
            options.append((score, ident))
        options.sort(key=lambda x: (-x[0], x[1]))
        _model_id = options[0][1] if options else 'openrouter/free'
    except Exception as exc:
        LOG.info('SEEDU catalog discovery skipped: %s', type(exc).__name__)
        _model_id = 'openrouter/free'
    _model_checked_at = time.monotonic()
    return _model_id


def _safe_token(value: Any, limit: int = 160) -> str:
    """Keep only unstructured metadata characters, never raw request/response text."""
    if not isinstance(value, (str, int, float, bool)):
        return '-'
    text = str(value).strip()[:limit]
    # The following is intended for machine-readable IDs/codes only.
    return re.sub(r'[^a-zA-Z0-9_./:+ -]', '_', text) or '-'


def _error_metadata(exc: Exception) -> dict:
    """Extract API error diagnostics without logging student data or credentials."""
    status = getattr(exc, 'status_code', None)
    response = getattr(exc, 'response', None)
    headers = getattr(response, 'headers', None) or {}
    result: dict[str, Any] = {
        'status': status,
        'retry_after': _safe_token(headers.get('retry-after')) if headers.get('retry-after') is not None else '-',
        'request_id': _safe_token(headers.get('x-request-id') or headers.get('x-openrouter-request-id')),
        'error_code': '-',
        'provider': '-',
        'upstream_status': '-',
        'limit_source': '-',
    }
    try:
        body = response.json() if response is not None else None
    except Exception:
        body = None
    if isinstance(body, dict):
        err = body.get('error', {})
        if isinstance(err, dict):
            result['error_code'] = _safe_token(err.get('code'))
            metadata = err.get('metadata')
            if isinstance(metadata, dict):
                result['provider'] = _safe_token(metadata.get('provider_name') or metadata.get('provider'))
                result['upstream_status'] = _safe_token(metadata.get('status_code') or metadata.get('upstream_status'))
                result['limit_source'] = _safe_token(metadata.get('limit_source'))
            if result['provider'] == '-':
                result['provider'] = _safe_token(err.get('provider'))
        elif isinstance(err, str):
            # Do not log arbitrary message: it can contain untrusted or sensitive content.
            pass
    return result


def request_semantics(sources, candidates, *, call_fn=None):
    payload = _payload(sources, candidates)
    if call_fn is not None:
        return _normalize(_json_object(call_fn(SYSTEM, payload)), candidates)
    key = os.getenv('OPENROUTER_API_KEY', '').strip()
    if not key:
        raise ValueError('OPENROUTER_API_KEY 미설정')
    from openai import OpenAI
    model = _pick_free_chat_model()
    LOG.info('SEEDU semantic request: model=%s', _safe_token(model))
    try:
        # No repeated requests, no model-specific reasoning controls.
        with OpenAI(base_url=URL, api_key=key, timeout=35.0, max_retries=0) as client:
            r = client.chat.completions.create(
                model=model,
                messages=[{'role': 'system', 'content': SYSTEM}, {'role': 'user', 'content': payload}],
                max_tokens=1800,
                temperature=0.0,
            )
    except Exception as exc:
        info = _error_metadata(exc)
        LOG.warning(
            'SEEDU semantic API error: model=%s type=%s status=%s error_code=%s '
            'provider=%s upstream_status=%s limit_source=%s retry_after=%s request_id=%s',
            _safe_token(model), type(exc).__name__, info['status'], info['error_code'],
            info['provider'], info['upstream_status'], info['limit_source'],
            info['retry_after'], info['request_id'],
        )
        raise
    choices = getattr(r, 'choices', []) or []
    if not choices:
        raise ValueError('AI 응답 선택지 없음')
    choice = choices[0]
    if getattr(choice, 'finish_reason', None) == 'length':
        raise ValueError('AI 출력 토큰 한도 초과')
    content = getattr(getattr(choice, 'message', None), 'content', None)
    data = _normalize(_json_object(content), candidates)
    if not data['facts']:
        raise ValueError('AI가 근거 인용을 반환하지 않음')
    LOG.info('SEEDU semantic success: model=%s facts=%d', _safe_token(getattr(r, 'model', 'unknown')), len(data['facts']))
    return data
