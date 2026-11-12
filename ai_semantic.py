"""One bounded OpenRouter request: semantic evidence, not 48 verbose scores."""
from __future__ import annotations
import json
import os
import re
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from rubric_v2 import COMPETENCY_NAMES

SYSTEM = """당신은 한국 고등학생 생활기록부 기록을 읽는 의미 평가자다. 키워드 출현이 아니라 실제 행동과 결과를 판단한다.
입력 sources에서 원문 구절을 정확히 복사해서 JSON 객체 하나만 반환한다. 설명/코드블록은 금지한다.
형식: {"facts":[{"source_index":0,"quote":"원문 연속 구절","tags":["method","result"]}],"competencies":[{"name":"학업역량","rating":2,"evidence_ids":[0]}],"major_links":[{"major":"후보 학과명","evidence_ids":[0]}]}
- facts는 3~7개. quote는 입력 sources[source_index].text에 존재하는 12~180자 원문 그대로. 근거가 없는 항목을 꾸며내지 말 것.
- tags: learning, career, question, method, result, validation, revision, collaboration, leadership, reflection, planning, interdisciplinary, comparison, application, continuity, concept 중 실제 수행 행동인 것만.
- competencies는 학업역량, 진로역량, 탐구역량, 공동체역량, 성장가능성 정확히 5개. rating은 0~4 또는 null. evidence_ids는 facts의 0부터 시작하는 번호 배열. 0은 기록에서 수행이 확인되지 않을 때, null은 판단 자료 부족.
- 1 단순 참여/관심, 2 실제 수행, 3 구체적 방법·결과 연결, 4 충분히 입증된 검증·실질적 개선과 효과. 4점 남발 금지.
- major_links는 candidate_majors 중 앞의 3개 학과에 대해서만 작성. 관련된 facts의 번호만 인용. 억지로 관련짓지 말 것.
- 발표=리더십, 관심=지속성, 개선 계획=개선 실행이라고 추정 금지.
- 짧고 유효한 JSON만 출력. 이유 장문 설명, 반복, 추가 필드 불필요.
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
    budget = int(os.getenv("SEMANTIC_MAX_CHARS", "6000"))
    budget = max(1500, min(12000, budget))
    items = []
    for idx, entry in enumerate(sources):
        if budget <= 0:
            break
        content = entry["text"][:min(1800,budget)]
        items.append({"source_index":idx,"grade":entry["grade"],"source":entry["source"],"text":content})
        budget -= len(content)
    if not items:
        raise ValueError("AI가 읽을 기록이 없습니다")
    payload = json.dumps({"sources":items,"candidate_majors":candidates[:3]},ensure_ascii=False)
    if call_fn is not None:
        return _parse(call_fn(SYSTEM,payload))
    key = os.getenv("OPENROUTER_API_KEY", "").strip()
    if not key:
        raise ValueError("OPENROUTER_API_KEY 미설정")
    from openai import OpenAI
    timeout = float(os.getenv("SEMANTIC_AI_TIMEOUT", "35"))
    timeout = max(5.0,min(60.0,timeout))
    with OpenAI(base_url="https://openrouter.ai/api/v1",api_key=key,timeout=timeout,max_retries=0) as client:
        response = client.chat.completions.create(
            model=os.getenv("OPENROUTER_MODEL","openrouter/free"),
            temperature=0,
            max_tokens=int(os.getenv("SEMANTIC_MAX_OUTPUT_TOKENS","3500")),
            messages=[{"role":"system","content":SYSTEM},{"role":"user","content":payload}],
        )
        if not response.choices:
            raise ValueError("AI 응답 선택지가 없습니다")
        message = response.choices[0].message
        finish_reason = response.choices[0].finish_reason
        if finish_reason == "length":
            raise ValueError("AI 출력 길이 제한에 도달했습니다 (max_tokens 또는 모델 변경 필요)")
        if not isinstance(message.content, str) or not message.content.strip():
            print(f"Semantic AI empty: model={response.model}, finish_reason={finish_reason}, usage={response.usage}")
            raise ValueError(f"AI가 텍스트를 반환하지 않았습니다 (종료 사유: {finish_reason})")
        return _parse(message.content)
