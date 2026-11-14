"""SEEDU:ON 3.1 — minimal OpenRouter semantic extraction.

Model selection is explicitly controlled by OPENROUTER_MODEL in Render.
No auto-discovery, forced reasoning parameters, or automatic model retries.
Do not submit personal student data without an appropriate lawful basis/consent.
"""
from __future__ import annotations

import json
import logging
import os
import re

from rubric_v2 import COMPETENCY_NAMES

LOG = logging.getLogger('seedu.semantic')
URL = 'https://openrouter.ai/api/v1'
TAGS = set('learning career question method result validation revision collaboration leadership reflection planning interdisciplinary comparison application continuity concept'.split())

SYSTEM = (
    '학생부 근거 추출기다. 아래 학생부에서 실제 수행·결과·개선 행동을 이해하고 '
    '원문 그대로 짧게 인용해 JSON만 출력한다. 키워드만으로 우수하다고 판단하지 마라. '
    '없는 근거를 만들지 마라. 반드시 한 줄 JSON: '
    '{"f":[[0,"학생부에서 그대로 인용한 12자 이상 구절",["method","result"]]],'
    '"c":[[2,[0]],[null,[]],[2,[0]],[null,[]],[null,[]]],"m":[[0],[],[]]}. '
    'f는 최대 4개이며 각 항목은 [자료번호,원문인용,태그]. '
    'c는 학업,진로,탐구,공동체,성장 순서로 정확히 5개 [0~4 또는 null, 근거번호배열]. '
    '1은 참여,2는 구체적 수행,3은 방법과 결과 연결,4는 뚜렷한 검증과 실질적 개선. '
    'm은 제시된 전공 후보 3개와 관련된 근거번호 배열. 설명문 없이 JSON만 반환.'
)


def _payload(sources: list[dict], candidates: list[str]) -> str:
    if not sources:
        raise ValueError('학생부 기록 없음')
    budget = 1900
    count = min(len(sources), 7)
    per_item = max(140, budget // max(count, 1))
    selected = []
    for i, item in enumerate(sources[:7]):
        raw = str(item.get('text') or '').strip()
        value = raw[:min(per_item, budget)]
        if value:
            selected.append({'i': i, 't': value})
            budget -= len(value)
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
    try:
        parsed = json.loads(body[start:end + 1])
    except json.JSONDecodeError as exc:
        raise ValueError(f'AI 응답 JSON 형식 오류 (position={exc.pos})') from exc
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


def _configured_model() -> str:
    """Use the exact model explicitly configured by the operator."""
    model = os.getenv('OPENROUTER_MODEL', '').strip()
    if not model:
        raise ValueError('Render 환경변수 OPENROUTER_MODEL이 없습니다. OpenRouter 모델 ID를 설정해 주세요.')
    return model


def _safe_error_info(exc: Exception) -> tuple[str, str, str]:
    """Log diagnostics without student text, credentials, or raw provider responses."""
    status = str(getattr(exc, 'status_code', '-') or '-')
    code = '-'
    source = '-'
    body = getattr(exc, 'body', None)
    if isinstance(body, dict):
        error = body.get('error', body)
        if isinstance(error, dict):
            code = str(error.get('code', '-') or '-')[:80]
            metadata = error.get('metadata') or {}
            if isinstance(metadata, dict):
                source = str(metadata.get('limit_source', '-') or '-')[:100]
    return status, code, source


def request_semantics(sources, candidates, *, call_fn=None):
    payload = _payload(sources, candidates)
    if call_fn is not None:
        return _normalize(_json_object(call_fn(SYSTEM, payload)), candidates)

    key = os.getenv('OPENROUTER_API_KEY', '').strip()
    if not key:
        raise ValueError('OPENROUTER_API_KEY 미설정')
    model = _configured_model()

    from openai import OpenAI
    try:
        # Exactly one completion call, no SDK retry, no hidden model selection.
        with OpenAI(base_url=URL, api_key=key, timeout=35.0, max_retries=0) as client:
            response = client.chat.completions.create(
                model=model,
                messages=[{'role': 'system', 'content': SYSTEM}, {'role': 'user', 'content': payload}],
                max_tokens=1800,
                temperature=0.0,
            )
    except Exception as exc:
        status, code, limit_source = _safe_error_info(exc)
        LOG.warning('SEEDU semantic API error: model=%s type=%s status=%s error_code=%s limit_source=%s',
                    model, type(exc).__name__, status, code, limit_source)
        raise

    choices = getattr(response, 'choices', []) or []
    if not choices:
        raise ValueError('AI 응답 선택지 없음')
    choice = choices[0]
    if getattr(choice, 'finish_reason', None) == 'length':
        raise ValueError('AI 출력 토큰 한도 초과')
    content = getattr(getattr(choice, 'message', None), 'content', None)
    data = _normalize(_json_object(content), candidates)
    if not data['facts']:
        raise ValueError('AI가 근거 인용을 반환하지 않음')
    LOG.info('SEEDU semantic success: model=%s facts=%d', model, len(data['facts']))
    return data
