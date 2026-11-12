"""SEEDU:ON Rubric 3.0 - stable OpenRouter semantic analyzer.

Replace ONLY repository-root ai_semantic.py with this file.
No extra environment variables. Requires OPENROUTER_API_KEY already configured.
Keeps request_semantics(sources, candidates, *, call_fn=None) interface.
"""
from __future__ import annotations

import json
import logging
import os
import re
import urllib.request
from typing import Any

from rubric_v2 import COMPETENCY_NAMES

LOGGER = logging.getLogger('seedu.semantic')
API_BASE = 'https://openrouter.ai/api/v1'
# Verified from OpenRouter public catalog on 2026-11-13. Availability can change.
PREFERRED_MODELS = (
    'google/gemma-4-31b-it:free',
    'google/gemma-4-26b-a4b-it:free',
)
MAX_OUTPUT_TOKENS = 2800
TAGS = frozenset('learning career question method result validation revision collaboration leadership reflection planning interdisciplinary comparison application continuity concept'.split())

SYSTEM = '''당신은 고등학교 학생부 평가를 위한 한국어 근거 추출기다.
텍스트 내용에 근거해 수행 행동과 결과를 구별한다. 키워드 반복만으로 점수를 높이지 않는다.
원문에서 글자 그대로 인용한다. 추론으로 활동 사실을 만들지 않는다.
JSON 객체 하나만 반환하고 마크다운, 긴 설명, 추가 키를 쓰지 않는다.
정확한 JSON 모양: {"f":[[0,"원문에서 그대로 복사한 문장",["method","result"]]],"c":[[2,[0]],[null,[]],[2,[0]],[null,[]],[null,[]]],"m":[[0],[],[]]}
f는 2~4개. 각 항목 [sources의 i, 글자 그대로 인용한 12자 이상 구절, 태그 배열].
c는 정확히 5개 [0~4 정수 또는 null, f의 근거번호 배열]. 순서는 학업역량, 진로역량, 탐구역량, 공동체역량, 성장가능성.
m은 candidate_majors 3개에 대한 근거번호 배열. 무관하면 [].
태그: learning, career, question, method, result, validation, revision, collaboration, leadership, reflection, planning, interdisciplinary, comparison, application, continuity, concept.
등급: 1=참여/관심, 2=구체적 수행, 3=방법·결과 연결, 4=실질적인 검증·개선까지 근거가 충분함. 정보 없으면 null.
짧고 유효한 JSON만 출력하라.'''


def _payload(sources: list[dict], candidates: list[str]) -> str:
    if not isinstance(sources, list) or not sources:
        raise ValueError('학생부 기록이 비어 있습니다')
    budget = 3100
    per_item = max(200, min(820, budget // len(sources)))
    items = []
    for i, source in enumerate(sources):
        if budget <= 0:
            break
        excerpt = str(source.get('text') or '').strip()[:min(per_item, budget)]
        if excerpt:
            items.append({'i': i, 'source': str(source.get('source') or '')[:45],
                          'grade': source.get('grade', 1), 'text': excerpt})
            budget -= len(excerpt)
    if not items:
        raise ValueError('학생부에서 분석할 문장을 찾을 수 없습니다')
    return json.dumps({'sources': items, 'candidate_majors': list(candidates[:3])},
                      ensure_ascii=False, separators=(',', ':'))


def _parse(content: str) -> dict[str, Any]:
    if not isinstance(content, str) or not content.strip():
        raise ValueError('AI의 텍스트 출력이 비어 있습니다')
    raw = content.strip().lstrip('\ufeff')
    raw = re.sub(r'^```(?:json)?\s*', '', raw, flags=re.I)
    raw = re.sub(r'\s*```$', '', raw)
    start, end = raw.find('{'), raw.rfind('}')
    if start < 0 or end < start:
        raise ValueError('AI JSON 객체가 없습니다')
    try:
        obj = json.loads(raw[start:end + 1])
    except json.JSONDecodeError as exc:
        raise ValueError(f'AI JSON 문법 오류: {exc.msg} (위치 {exc.pos})') from exc
    if not isinstance(obj, dict) or not isinstance(obj.get('f'), list) or not isinstance(obj.get('c'), list):
        raise ValueError('AI JSON 필수 항목 f/c가 없습니다')
    if len(obj['c']) != 5 or not obj['f']:
        raise ValueError('AI JSON의 5대 역량 또는 근거가 비어 있습니다')
    return obj


def _normalize(parsed: dict[str, Any], candidates: list[str]) -> dict[str, Any]:
    if isinstance(parsed.get('facts'), list) and isinstance(parsed.get('competencies'), list):
        return parsed
    facts = []
    for item in parsed.get('f', [])[:12]:
        if (not isinstance(item, list) or len(item) < 3 or type(item[0]) is not int
                or not isinstance(item[1], str) or not isinstance(item[2], list)):
            facts.append({'source_index': -1, 'quote': '', 'tags': []})
            continue
        facts.append({'source_index': item[0], 'quote': item[1],
                      'tags': [x for x in item[2] if isinstance(x, str) and x in TAGS]})
    competencies = []
    for i, name in enumerate(COMPETENCY_NAMES):
        row = parsed['c'][i]
        rating = row[0] if isinstance(row, list) and row else None
        refs = row[1] if isinstance(row, list) and len(row) > 1 else []
        if type(rating) is not int or not 0 <= rating <= 4:
            rating = None
        if not isinstance(refs, list):
            refs = []
        competencies.append({'name': name, 'rating': rating,
                             'evidence_ids': [k for k in refs if type(k) is int and 0 <= k < len(facts)]})
    raw_major_links = parsed.get('m') if isinstance(parsed.get('m'), list) else []
    links = []
    for i, major in enumerate(candidates[:3]):
        refs = raw_major_links[i] if i < len(raw_major_links) else []
        if not isinstance(refs, list):
            refs = []
        links.append({'major': major,
                      'evidence_ids': [k for k in refs if type(k) is int and 0 <= k < len(facts)]})
    return {'facts': facts, 'competencies': competencies, 'major_links': links}


def _response_text(response: Any) -> str:
    choices = getattr(response, 'choices', None) or []
    if not choices:
        raise ValueError('AI 선택 응답이 없습니다')
    choice = choices[0]
    if getattr(choice, 'finish_reason', None) == 'length':
        usage = getattr(response, 'usage', None)
        # Do not log private student records.
        LOGGER.warning('SEEDU semantic length: model=%s usage=%s', getattr(response, 'model', '?'), usage)
        raise ValueError('AI 응답의 출력 길이가 제한에 도달했습니다')
    body = getattr(getattr(choice, 'message', None), 'content', None)
    if not isinstance(body, str) or not body.strip():
        raise ValueError('AI가 응답 본문을 반환하지 않았습니다')
    return body


def _discover_models() -> list[str]:
    """Ask public OpenRouter catalog for currently listed free text models.

    Never route to random free models; exclude mandatory reasoning when advertised.
    Discovery failure falls back to recently verified model IDs, which may also expire.
    """
    req = urllib.request.Request(API_BASE + '/models', headers={'Accept': 'application/json', 'User-Agent': 'SEEDU-ON/3.0'})
    try:
        with urllib.request.urlopen(req, timeout=7) as r:
            entries = json.load(r).get('data', [])
    except Exception as exc:
        LOGGER.warning('SEEDU model catalog unavailable: %s', type(exc).__name__)
        return list(PREFERRED_MODELS)
    available = {}
    for m in entries:
        if not isinstance(m, dict):
            continue
        ident = m.get('id')
        if not isinstance(ident, str) or not ident.endswith(':free'):
            continue
        output_mods = (m.get('architecture') or {}).get('output_modalities') or ['text']
        if 'text' not in output_mods:
            continue
        reasoning = m.get('reasoning') or {}
        if isinstance(reasoning, dict) and reasoning.get('mandatory') is True:
            continue
        available[ident] = m
    # Explicitly prioritize instruction-following models with familiar Korean support.
    preferred = [x for x in PREFERRED_MODELS if x in available]
    rest = [x for x in available if x not in preferred and any(y in x for y in ('gemma', 'instruct', 'chat'))]
    return (preferred + sorted(rest))[:5] or list(PREFERRED_MODELS)


def request_semantics(sources, candidates, *, call_fn=None):
    """Return compact evidence and ratings for semantic_engine.build_analysis."""
    payload = _payload(sources, candidates)
    if call_fn is not None:
        return _normalize(_parse(call_fn(SYSTEM, payload)), candidates)
    key = os.getenv('OPENROUTER_API_KEY', '').strip()
    if not key:
        raise ValueError('OPENROUTER_API_KEY가 없습니다')
    from openai import OpenAI
    messages = [{'role': 'system', 'content': SYSTEM}, {'role': 'user', 'content': payload}]
    errors = []
    models = _discover_models()
    with OpenAI(base_url=API_BASE, api_key=key, timeout=45.0, max_retries=0) as client:
        for model in models[:3]:
            # These Gemma instruction models expose configurable reasoning; avoid spending
            # all completion tokens on unbounded thinking. If provider rejects this
            # optional setting, retry without it once using the NEXT model.
            kwargs = {'model': model, 'messages': messages,
                      'max_tokens': MAX_OUTPUT_TOKENS,
                      'temperature': 0.1}
            if model.startswith('google/gemma-4-'):
                kwargs['extra_body'] = {'reasoning': {'effort': 'none'}}
            try:
                response = client.chat.completions.create(**kwargs)
                result = _normalize(_parse(_response_text(response)), candidates)
                if not any(f['quote'] and f['tags'] for f in result['facts']):
                    raise ValueError('인용 근거가 없습니다')
                LOGGER.info('SEEDU semantic success: model=%s facts=%d',
                            getattr(response, 'model', model), len(result['facts']))
                return result
            except Exception as exc:
                status = getattr(exc, 'status_code', None)
                LOGGER.warning('SEEDU semantic attempt failed: model=%s type=%s status=%s error=%s',
                               model, type(exc).__name__, status, str(exc)[:170])
                errors.append(f'{model}: {type(exc).__name__}')
                if status in (401, 402, 403, 429):
                    break
    raise ValueError('OpenRouter 의미 분석 실패 (모델을 바꿔 재시도함): ' + '; '.join(errors))
