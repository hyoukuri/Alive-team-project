"""SEEDU:ON Rubric 3.0 - OpenRouter AI semantic extraction (deployment replacement).

- No NVIDIA-specific options; no reasoning-disable request.
- Uses two explicit free *instruction* models rather than old OPENROUTER_MODEL.
- Fast model fallback, conservative validation, exact quotes, current scorer interface.
- Existing OPENROUTER_API_KEY is the only required configuration.
"""
from __future__ import annotations

import json
import logging
import os
import re
from typing import Any

from rubric_v2 import COMPETENCY_NAMES

LOG = logging.getLogger('seedu.semantic')

# These are model IDs, NOT providers. Neither requires a vendor-specific setting.
# They can be changed here when OpenRouter's free catalog changes; no Render edits.
MODELS = (
    'google/gemma-3-27b-it:free',
    'meta-llama/llama-3.3-70b-instruct:free',
)

TAGS = set(('learning career question method result validation revision collaboration '
            'leadership reflection planning interdisciplinary comparison application '
            'continuity concept').split())

SYSTEM = '''당신은 고등학교 학생부 평가를 보조하는 근거 추출기다.
입력 기록의 구체적인 수행 행동, 방법, 결과, 검증, 수정 실행, 협업의 의미를 이해하라.
활동을 하지 않았는데 했다고 추정하지 말고, 키워드의 존재만으로 고득점 주지 마라.
원문 인용은 제공된 sources[i].text에 있는 연속 문장을 그대로 복사하라. 인용 내용을 창작하거나 바꾸지 마라.
반드시 아래 형태의 JSON 객체 하나만 출력하라. 마크다운, 해설, 추가 문자 금지.
{"f":[[0,"원문 그대로 인용한 12자 이상 구절",["method","result"]]],"c":[[2,[0]],[2,[0]],[3,[0]],[1,[0]],[2,[0]]],"m":[[0],[],[]]}
f: 핵심적인 근거 4~7개. 각 원소는 [sources 번호(0부터), 실제 원문 그대로의 구절(12~160자), 영문 태그 배열].
c: 정확히 다섯 개, 순서는 학업역량/진로역량/탐구역량/공동체역량/성장가능성. 각 [0~4의 평가제안 또는 null, f의 증거번호 배열].
m: candidate_majors 앞 3개 순서로 각각 관련된 f의 증거번호 배열. 없으면 [].
허용 태그: learning,career,question,method,result,validation,revision,collaboration,leadership,reflection,planning,interdisciplinary,comparison,application,continuity,concept.
1=관심이나 단순 참여; 2=구체적 수행; 3=방법과 결과가 연결됨; 4=검증과 실행한 개선의 효과까지 충분히 확인됨.
발표=리더십, 관심=지속성, 개선 계획=개선 실천으로 간주하지 마라. 증거가 없으면 null.
짧게 작성하되 근거의 원문 인용 정확성을 우선하라.'''


def _parse(content: str) -> dict[str, Any]:
    if not isinstance(content, str) or not content.strip():
        raise ValueError('AI 응답이 비어 있습니다')
    clean = content.strip().lstrip('\ufeff')
    clean = re.sub(r'^```(?:json)?\s*', '', clean, flags=re.I)
    clean = re.sub(r'\s*```\s*$', '', clean)
    # Some providers preface JSON despite the instruction. Isolate a single object.
    first, last = clean.find('{'), clean.rfind('}')
    if first < 0 or last <= first:
        raise ValueError('AI 응답에 JSON 객체가 없습니다')
    clean = clean[first:last + 1]
    # Safe, syntax-only cleanup; never invent missing evaluations/evidence.
    clean = re.sub(r',\s*([}\]])', r'\1', clean)
    parsed = json.loads(clean)
    if not isinstance(parsed, dict):
        raise ValueError('AI 응답이 JSON 객체가 아닙니다')
    if not isinstance(parsed.get('f'), list) or not isinstance(parsed.get('c'), list):
        raise ValueError('AI JSON 필수 필드가 없습니다')
    if not parsed['f'] or len(parsed['c']) != 5:
        raise ValueError('AI가 필수 근거/역량 평가를 완성하지 않았습니다')
    return parsed


def _normalize(raw: dict[str, Any], candidates: list[str]) -> dict[str, Any]:
    # Preserve compatibility with semantic_engine.build_analysis.
    if 'facts' in raw and isinstance(raw['facts'], list):
        return raw
    facts: list[dict[str, Any]] = []
    for entry in raw.get('f', [])[:12]:
        if (not isinstance(entry, list) or len(entry) < 3 or
                type(entry[0]) is not int or not isinstance(entry[1], str) or
                not isinstance(entry[2], list)):
            # Keep exact f positions for evidence IDs: discard invalid facts but
            # do NOT renumber references used by c/m.
            facts.append({'source_index': -1, 'quote': '', 'tags': []})
            continue
        facts.append({'source_index': entry[0], 'quote': entry[1],
                      'tags': [t for t in entry[2] if isinstance(t, str) and t in TAGS]})
    competencies = []
    for i, name in enumerate(COMPETENCY_NAMES):
        entries = raw.get('c', [])
        entry = entries[i] if i < len(entries) else []
        rating = entry[0] if isinstance(entry, list) and len(entry) > 0 else None
        ids = entry[1] if isinstance(entry, list) and len(entry) > 1 and isinstance(entry[1], list) else []
        # Reject booleans, strings, out-of-range numbers; no inferred scores.
        if type(rating) is not int or not 0 <= rating <= 4:
            rating = None
        ids = [x for x in ids if type(x) is int and 0 <= x < len(facts)]
        competencies.append({'name': name, 'rating': rating, 'evidence_ids': ids})
    links = []
    major_links = raw.get('m') if isinstance(raw.get('m'), list) else []
    for i, major in enumerate(candidates[:3]):
        ids = major_links[i] if i < len(major_links) else []
        if not isinstance(ids, list):
            ids = []
        links.append({'major': major,
                      'evidence_ids': [x for x in ids if type(x) is int and 0 <= x < len(facts)]})
    return {'facts': facts, 'competencies': competencies, 'major_links': links}


def _request_payload(sources: list[dict], candidates: list[str]) -> str:
    # Across distinct school subjects, divide budget fairly: avoid losing last categories.
    budget = 4600
    count = max(1, len(sources))
    per_record = max(350, min(1100, budget // count))
    items = []
    for i, entry in enumerate(sources):
        excerpt = str(entry.get('text') or '').strip()[:per_record]
        if excerpt:
            items.append({'i': i, 'grade': entry.get('grade', 1),
                          'source': str(entry.get('source', ''))[:80], 'text': excerpt})
    if not items:
        raise ValueError('AI가 읽을 학생부 내용이 없습니다')
    return json.dumps({'sources': items, 'candidate_majors': candidates[:3]},
                      ensure_ascii=False, separators=(',', ':'))


def _extract_completion(response, model: str) -> str:
    choices = getattr(response, 'choices', None) or []
    if not choices:
        raise ValueError('AI 선택지 없음')
    choice = choices[0]
    finish = getattr(choice, 'finish_reason', None)
    content = getattr(getattr(choice, 'message', None), 'content', None)
    if finish == 'length':
        raise ValueError('AI 출력 길이 제한 도달')
    if not isinstance(content, str) or not content.strip():
        raise ValueError('AI 텍스트 응답 없음')
    return content


def request_semantics(sources, candidates, *, call_fn=None):
    """Return {facts,competencies,major_links}, unchanged Rubric 3.0 interface.

    call_fn(system, payload) remains available to offline tests.
    """
    payload = _request_payload(sources, candidates)
    if call_fn is not None:
        return _normalize(_parse(call_fn(SYSTEM, payload)), candidates)

    api_key = os.getenv('OPENROUTER_API_KEY', '').strip()
    if not api_key:
        raise ValueError('OPENROUTER_API_KEY가 설정되지 않았습니다')

    from openai import OpenAI, BadRequestError
    failures = []
    # Important: intentionally DO NOT use old OPENROUTER_MODEL. It may still
    # contain the NVIDIA mandatory-reasoning model; no Render env edit needed.
    with OpenAI(base_url='https://openrouter.ai/api/v1', api_key=api_key,
                timeout=40.0, max_retries=0) as client:
        messages = [{'role': 'system', 'content': SYSTEM},
                    {'role': 'user', 'content': payload}]
        for model in MODELS:
            for json_mode in (True, False):
                kwargs = {'model': model, 'messages': messages, 'max_tokens': 2400,
                          'temperature': 0}
                if json_mode:
                    kwargs['response_format'] = {'type': 'json_object'}
                try:
                    response = client.chat.completions.create(**kwargs)
                    raw = _parse(_extract_completion(response, model))
                    result = _normalize(raw, candidates)
                    # At least one real fact must be verified by semantic_engine.
                    if not any(f['quote'] for f in result['facts']):
                        raise ValueError('AI 원문 인용 누락')
                    LOG.info('SEEDU semantic success: model=%s facts=%d', model, len(result['facts']))
                    return result
                except BadRequestError as exc:
                    msg = str(exc).lower()
                    # Only remove JSON mode if API says it does not support it.
                    if json_mode and any(term in msg for term in
                        ('response_format', 'json_object', 'structured output', 'unsupported parameter')):
                        LOG.warning('SEEDU semantic JSON-mode unsupported: model=%s', model)
                        continue
                    failures.append((model, type(exc).__name__, str(exc)[:110]))
                    break
                except Exception as exc:
                    failures.append((model, type(exc).__name__, str(exc)[:110]))
                    # Retry without JSON mode only if the first answer was malformed.
                    if json_mode and isinstance(exc, (json.JSONDecodeError, ValueError)):
                        continue
                    break
    # Do not log secrets, student input, or full model response.
    for model, kind, info in failures:
        LOG.warning('SEEDU semantic attempt failed: model=%s type=%s reason=%s', model, kind, info)
    summary = '; '.join(f'{model}: {kind}' for model, kind, _ in failures)
    raise ValueError('OpenRouter AI 분석 실패 (모든 후보 모델): ' + summary[:260])
