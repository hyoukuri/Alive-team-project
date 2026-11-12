"""Compact semantic evidence extraction, compatible with the rubric 3.0 scorer.

Only the language model judges meaning; Python validates quotes and computes scores.
The compact wire format reduces completion tokens and free-tier failures.
"""
from __future__ import annotations

import json
import os
import re
from rubric_v2 import COMPETENCY_NAMES

TAGS = (
    'learning career question method result validation revision collaboration '
    'leadership reflection planning interdisciplinary comparison application '
    'continuity concept'
).split()

SYSTEM = """한국 고등학생의 학생부를 의미 분석하라. 행동의 실제 수행 수준을 평가하고 단어 출현만으로 고득점을 주지 마라.
원문에 있는 연속 구절만 증거로 인용하라. 한국어 설명 없이 짧은 JSON 하나만 출력하라.
출력 JSON 형식(키를 그대로 사용):
{"f":[[원문번호,"원문구절",["태그"]]],"c":[[등급,[증거번호]]],"m":[[증거번호]]}
f: 핵심 증거 3~5개. 원문번호는 sources의 번호(0부터), 인용은 12~120자 원문 그대로. 증거번호는 f의 배열 위치(0부터).
c: 반드시 5개이며 순서는 학업역량,진로역량,탐구역량,공동체역량,성장가능성. 등급은 0~4 또는 null.
m: 반드시 candidate_majors 순서대로 최대 3개, 각각 관련된 증거번호 목록. 무관하면 빈 배열.
태그는 learning,career,question,method,result,validation,revision,collaboration,leadership,reflection,planning,interdisciplinary,comparison,application,continuity,concept 중 선택.
평가 기준: 1=관심/참여, 2=실제 수행, 3=방법과 결과 연결, 4=검증 및 실행한 개선의 효과가 충분히 확인됨. 자료 부족은 null.
발표를 리더십으로, 관심을 지속성으로, 개선계획을 개선실행으로 추측 금지. 추정·장문·추가 필드 금지."""


def _parse(content):
    if not isinstance(content, str) or not content.strip():
        raise ValueError('AI 응답이 비어 있습니다')
    clean = re.sub(r'^```(?:json)?\s*|\s*```$', '', content.strip(), flags=re.I)
    try:
        parsed = json.loads(clean)
    except json.JSONDecodeError:
        start, end = clean.find('{'), clean.rfind('}')
        if start < 0 or end <= start:
            raise ValueError('AI JSON 형식 오류')
        parsed = json.loads(clean[start:end + 1])
    if not isinstance(parsed, dict):
        raise ValueError('AI 응답 객체 형식 오류')
    return parsed


def _normalize(raw, candidates):
    """Convert short-form model response to unchanged semantic_engine interface."""
    if 'facts' in raw:
        return raw   # Permit legacy models returning the previous wire schema.
    facts = []
    for item in (raw.get('f') or [])[:7]:
        if not isinstance(item, list) or len(item) < 3 or type(item[0]) is not int:
            continue
        if not isinstance(item[1], str) or not isinstance(item[2], list):
            continue
        facts.append({'source_index': item[0], 'quote': item[1],
                      'tags': [tag for tag in item[2] if tag in TAGS]})
    competencies = []
    entries = raw.get('c') or []
    for i, name in enumerate(COMPETENCY_NAMES):
        entry = entries[i] if isinstance(entries, list) and i < len(entries) else None
        if isinstance(entry, list) and len(entry) >= 2:
            rating, ids = entry[0], entry[1]
        else:
            rating, ids = None, []
        competencies.append({'name':name, 'rating':rating,
                             'evidence_ids':ids if isinstance(ids,list) else []})
    links = []
    entries = raw.get('m') or []
    for i, major in enumerate(candidates[:3]):
        ids = entries[i] if isinstance(entries, list) and i < len(entries) else []
        links.append({'major': major, 'evidence_ids': ids if isinstance(ids,list) else []})
    return {'facts': facts, 'competencies': competencies, 'major_links': links}


def request_semantics(sources, candidates, *, call_fn=None):
    budget = max(1200, min(9000, int(os.getenv('SEMANTIC_MAX_CHARS', '3800'))))
    items = []
    for idx, entry in enumerate(sources):
        if budget <= 0:
            break
        excerpt = entry['text'][:min(1200, budget)]
        if not excerpt:
            continue
        items.append({'i':idx, 'grade':entry['grade'], 'source':entry['source'], 'text':excerpt})
        budget -= len(excerpt)
    if not items:
        raise ValueError('AI가 읽을 기록이 없습니다')
    payload = json.dumps({'sources':items, 'candidate_majors':candidates[:3]}, ensure_ascii=False,
                         separators=(',',':'))
    if call_fn is not None:
        return _normalize(_parse(call_fn(SYSTEM, payload)), candidates)
    key = os.getenv('OPENROUTER_API_KEY', '').strip()
    if not key:
        raise ValueError('OPENROUTER_API_KEY 미설정')
    from openai import OpenAI
    timeout = max(5.0, min(90.0, float(os.getenv('SEMANTIC_AI_TIMEOUT', '40'))))
    max_tokens = max(500, min(10000, int(os.getenv('SEMANTIC_MAX_OUTPUT_TOKENS', '5000'))))
    with OpenAI(base_url='https://openrouter.ai/api/v1', api_key=key,
                timeout=timeout, max_retries=0) as client:
        response = client.chat.completions.create(
            model=os.getenv('OPENROUTER_MODEL', 'openrouter/free'),
            temperature=0, max_tokens=max_tokens,
            messages=[{'role':'system','content':SYSTEM},{'role':'user','content':payload}],
        )
    if not response.choices:
        raise ValueError('AI 응답 선택지가 없습니다')
    choice = response.choices[0]
    content = choice.message.content
    if choice.finish_reason == 'length':
        print(f'SEEDU semantic length: model={response.model}, max_tokens={max_tokens}, usage={response.usage}')
        raise ValueError('AI 출력 길이 제한 도달: 모델 출력량 또는 추론 토큰 한도 확인 필요')
    if not isinstance(content, str) or not content.strip():
        print(f'SEEDU semantic empty: model={response.model}, finish_reason={choice.finish_reason}, usage={response.usage}')
        raise ValueError(f'AI가 텍스트를 반환하지 않았습니다 (finish_reason={choice.finish_reason})')
    return _normalize(_parse(content), candidates)
