"""One bounded OpenRouter request: semantic evidence, not 48 verbose scores."""
from __future__ import annotations
import json
import os
import re
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from rubric_v2 import COMPETENCY_NAMES

SYSTEM = """당신은 한국 고등학생 학교생활기록부의 '행동과 의미'를 읽는 평가 보조자입니다.
입력은 학생부 기록과 후보 학과 목록입니다. 단어 출현 횟수로 평가하지 말고, 학생이 실제로 한 행동의 문제-방법-결과-검증-개선의 연결 관계를 해석합니다.
원문에 없는 활동, 능력, 결과, 인과관계는 절대 만들지 않습니다.
특히 '발표'만으로 협업 주도성을, '관심'만으로 지속성을, '계획'만으로 실행을 추정하지 마세요.
반복 없이 짧은 JSON 객체 하나만 출력하세요. 마크다운 금지.

facts: 4~12개의 독립적으로 의미 있는 행동 근거. 각 항목은 {"source_index":0,"quote":"원문에서 연속으로 복사한 구절","tags":["method","result"],"interpretation":"짧은 해석"}.
quote는 지정된 source_index의 text 안에서 반드시 글자 그대로 연속된 문자열이어야 함. 원문을 바꾸거나 서로 다른 문장을 합치면 무효.
tags는 다음 값만 사용: learning, career, question, method, result, validation, revision, collaboration, leadership, reflection, planning, interdisciplinary, comparison, application, continuity, concept.
단어 자체가 아니라 실제 수행 행동이 근거일 때만 tags 부여. 후속 계획은 실제 실행된 revision이 아님.

competencies: 정확히 5개. {"name":"학업역량","rating":2,"evidence_ids":[0,1],"reason":"짧은 채점 이유"}.
name 순서: 학업역량, 진로역량, 탐구역량, 공동체역량, 성장가능성.
rating은 0,1,2,3,4 혹은 null (판단 근거 자체가 부족하면 null).
0=평가 가능한 기록에서 관련 수행 없음, 1=관심·단순 참여, 2=직접 수행, 3=방법과 결과를 설명하고 근거로 연결, 4=문제 해결·재검증·실질적 개선과 그 효과가 충분히 입증됨.
4점은 드물게, 기록으로 확증될 때만 사용. 3점도 단순 수식어로 부여 금지.
evidence_ids는 위 facts 배열의 0부터 시작하는 인덱스. 없으면 []와 null을 사용.

major_links: 제공된 candidate_majors 각각에 대해 {"major":"후보 학과명","evidence_ids":[0,2],"reason":"전공 관련 구체적 이유"}.
해당 전공과 직접적으로 관련되는 facts만 연결. 전공 명칭을 말한 것만으로 높은 적합도 주장 금지. 각 이유는 짧게.
전체 스키마: {"facts":[],"competencies":[],"major_links":[]}.
숫자 총점, 16개 가중 점수, 학과별 장문 평가는 생성하지 마세요.
"""

def _parse(content):
    if not isinstance(content,str) or not content.strip():
        raise ValueError("AI 응답이 비어 있습니다")
    clean = re.sub(r"^```(?:json)?\s*|\s*```$", "", content.strip(), flags=re.I)
    try:
        raw = json.loads(clean)
    except json.JSONDecodeError:
        start, end = clean.find("{"), clean.rfind("}")
        if start < 0 or end <= start:
            raise ValueError("AI JSON 형식 오류")
        raw = json.loads(clean[start:end+1])
    if not isinstance(raw,dict):
        raise ValueError("AI 응답 객체 형식 오류")
    return raw


def request_semantics(sources, candidates, *, call_fn=None):
    # Context bound: enforce per-source length and total text, avoid token blowups.
    budget = int(os.getenv("SEMANTIC_MAX_CHARS", "9000"))
    budget = max(1500, min(16000, budget))
    items = []
    for idx, entry in enumerate(sources):
        if budget <= 0:
            break
        content = entry["text"][:min(2600,budget)]
        items.append({"source_index":idx,"grade":entry["grade"],"source":entry["source"],"text":content})
        budget -= len(content)
    if not items:
        raise ValueError("AI가 읽을 기록이 없습니다")
    payload = json.dumps({"sources":items,"candidate_majors":candidates},ensure_ascii=False)
    if call_fn is not None:
        return _parse(call_fn(SYSTEM,payload))
    key = os.getenv("OPENROUTER_API_KEY", "").strip()
    if not key:
        raise ValueError("OPENROUTER_API_KEY 미설정")
    from openai import OpenAI
    timeout = float(os.getenv("SEMANTIC_AI_TIMEOUT", "18"))
    timeout = max(5.0,min(40.0,timeout))
    with OpenAI(base_url="https://openrouter.ai/api/v1",api_key=key,timeout=timeout,max_retries=0) as client:
        response = client.chat.completions.create(
            model=os.getenv("OPENROUTER_MODEL","openrouter/free"),
            temperature=0,
            max_tokens=int(os.getenv("SEMANTIC_MAX_OUTPUT_TOKENS","2400")),
            messages=[{"role":"system","content":SYSTEM},{"role":"user","content":payload}],
        )
        if not response.choices:
            raise ValueError("AI 응답 선택지가 없습니다")
        message = response.choices[0].message
        if response.choices[0].finish_reason == "length":
            raise ValueError("AI 출력 길이 제한에 도달했습니다")
        return _parse(message.content)
