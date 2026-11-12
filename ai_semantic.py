"""SEEDU:ON Rubric 3.0 / OpenRouter free-model semantic extraction.

Drop-in replacement for the existing ai_semantic.py.
Required existing environment variable: OPENROUTER_API_KEY.
No model-specific parameters or additional Render environment variables.
Public API: request_semantics(sources, candidates, *, call_fn=None).
"""
from __future__ import annotations

import json
import logging
import os
import re
from typing import Any

from rubric_v2 import COMPETENCY_NAMES

LOGGER = logging.getLogger("seedu.semantic")
MODEL = "openrouter/free"  # OpenRouter's maintained free-model router
MAX_OUTPUT_TOKENS = 3500
TAGS = frozenset(
    "learning career question method result validation revision collaboration "
    "leadership reflection planning interdisciplinary comparison application "
    "continuity concept".split()
)

SYSTEM = """너는 한국 고등학생 생활기록부의 실제 수행을 평가하는 근거 추출기다.
단어 등장으로 점수 주지 말고 문제-방법-결과-검증-실제 개선과 협업의 관계를 파악하라.
원문에 없는 행동, 결과, 협업, 학습 지속성을 추측하지 마라.
입력 sources의 text 안에서 12자 이상인 구절을 글자 그대로 인용하라.
반드시 짧은 JSON 객체 한 개만 반환한다. 마크다운/서술문 금지.
형식 예시:
{"f":[[0,"자료를 조사하고 예측값과 실제값을 비교함",["method","comparison"]]],"c":[[2,[0]],[null,[]],[2,[0]],[null,[]],[null,[]]],"m":[[0],[],[]]}
f: 근거 3~5개. 각 [sources 항목의 i, 원문 인용, 태그 배열]. 인용은 반드시 해당 원문과 일치.
c: 정확히 5개 [0~4 또는 null, f의 0부터 시작하는 근거 번호 배열]. 순서 학업역량, 진로역량, 탐구역량, 공동체역량, 성장가능성.
m: candidate_majors 처음 3개에 대한 근거 번호 배열. 관련 없으면 빈 배열.
태그 허용: learning, career, question, method, result, validation, revision, collaboration, leadership, reflection, planning, interdisciplinary, comparison, application, continuity, concept.
등급 기준: 1=관심/참여, 2=구체적 수행, 3=방법과 결과가 연결됨, 4=실제 검증과 개선 효과까지 충분히 입증. 근거 없으면 null.
발표만 했다고 리더십, 개선 계획만 있다고 개선 실천이라고 평가하지 마라.
설명은 생략하고 JSON만 출력하라."""


def _payload(sources: list[dict], candidates: list[str]) -> str:
    if not isinstance(sources, list) or not sources:
        raise ValueError("학생부 기록이 비어 있습니다")
    # Spread the length allowance across source types, keeping source identifiers.
    max_total = 4300
    per_item = max(240, min(1150, max_total // len(sources)))
    items = []
    remaining = max_total
    for i, source in enumerate(sources):
        if remaining <= 0:
            break
        excerpt = str(source.get("text") or "").strip()[:min(per_item, remaining)]
        if excerpt:
            items.append({
                "i": i,
                "source": str(source.get("source") or "")[:50],
                "grade": source.get("grade", 1),
                "text": excerpt,
            })
            remaining -= len(excerpt)
    if not items:
        raise ValueError("학생부에서 분석할 문장을 찾을 수 없습니다")
    return json.dumps({"sources": items, "candidate_majors": candidates[:3]},
                      ensure_ascii=False, separators=(",", ":"))


def _parse(content: str) -> dict[str, Any]:
    if not isinstance(content, str) or not content.strip():
        raise ValueError("AI 텍스트 응답이 비어 있습니다")
    value = content.strip().lstrip("\ufeff")
    value = re.sub(r"^```(?:json)?\s*", "", value, flags=re.I)
    value = re.sub(r"\s*```$", "", value)
    first, last = value.find("{"), value.rfind("}")
    if first < 0 or last < first:
        raise ValueError("AI 응답에서 JSON 객체를 찾지 못했습니다")
    try:
        obj = json.loads(value[first:last + 1])
    except json.JSONDecodeError as exc:
        # Deliberately avoid guessing punctuation or fabricating a valid grade.
        raise ValueError(f"AI JSON 형식 오류 ({exc.msg}, 위치 {exc.pos})") from exc
    if not isinstance(obj, dict):
        raise ValueError("AI의 평가 형식이 JSON 객체가 아닙니다")
    if not isinstance(obj.get("f"), list) or not isinstance(obj.get("c"), list):
        raise ValueError("AI 응답에서 근거 또는 역량 항목이 누락되었습니다")
    if len(obj["c"]) != 5 or not obj["f"]:
        raise ValueError("AI 응답의 필수 5대 역량 또는 근거가 미완성입니다")
    return obj


def _normalize(parsed: dict[str, Any], candidates: list[str]) -> dict[str, Any]:
    """Preserve the exact dict contract expected by semantic_engine.build_analysis."""
    # Older valid verbose output remains supported for unit-test callers.
    if isinstance(parsed.get("facts"), list) and isinstance(parsed.get("competencies"), list):
        return parsed

    facts = []
    for fact in parsed.get("f", [])[:12]:
        if (not isinstance(fact, list) or len(fact) < 3 or
                type(fact[0]) is not int or not isinstance(fact[1], str) or
                not isinstance(fact[2], list)):
            # Placeholder retains IDs without accidentally shifting references.
            facts.append({"source_index": -1, "quote": "", "tags": []})
            continue
        facts.append({
            "source_index": fact[0],
            "quote": fact[1],
            "tags": [t for t in fact[2] if isinstance(t, str) and t in TAGS],
        })

    competencies = []
    for idx, name in enumerate(COMPETENCY_NAMES):
        row = parsed["c"][idx]
        score = row[0] if isinstance(row, list) and row else None
        indices = row[1] if isinstance(row, list) and len(row) > 1 else []
        if type(score) is not int or score < 0 or score > 4:
            score = None
        if not isinstance(indices, list):
            indices = []
        indices = [i for i in indices if type(i) is int and 0 <= i < len(facts)]
        competencies.append({"name": name, "rating": score, "evidence_ids": indices})

    major_rows = parsed.get("m") if isinstance(parsed.get("m"), list) else []
    links = []
    for idx, major in enumerate(candidates[:3]):
        indices = major_rows[idx] if idx < len(major_rows) else []
        if not isinstance(indices, list):
            indices = []
        links.append({
            "major": major,
            "evidence_ids": [i for i in indices if type(i) is int and 0 <= i < len(facts)],
        })
    return {"facts": facts, "competencies": competencies, "major_links": links}


def _response_text(response: Any) -> str:
    choices = getattr(response, "choices", None) or []
    if not choices:
        raise ValueError("AI 응답에 choices가 없습니다")
    choice = choices[0]
    if getattr(choice, "finish_reason", None) == "length":
        usage = getattr(response, "usage", None)
        LOGGER.warning("SEEDU semantic length: model=%s usage=%s",
                       getattr(response, "model", "unknown"), usage)
        raise ValueError("AI 응답의 출력 길이가 제한에 도달했습니다")
    text = getattr(getattr(choice, "message", None), "content", None)
    if not isinstance(text, str) or not text.strip():
        raise ValueError("AI가 분석 텍스트를 반환하지 않았습니다")
    return text


def request_semantics(sources, candidates, *, call_fn=None):
    """Return {facts, competencies, major_links} for Rubric 3.0.

    call_fn(system, payload) is retained for offline tests.
    """
    payload = _payload(sources, candidates)
    if call_fn is not None:
        return _normalize(_parse(call_fn(SYSTEM, payload)), candidates)

    key = os.getenv("OPENROUTER_API_KEY", "").strip()
    if not key:
        raise ValueError("Render의 OPENROUTER_API_KEY가 설정되지 않았습니다")

    from openai import OpenAI
    messages = [{"role": "system", "content": SYSTEM},
                {"role": "user", "content": payload}]
    errors = []

    # Try JSON mode first. OpenRouter free router filters for suitable providers;
    # if JSON mode is unsupported or the JSON itself is broken, retry once with
    # plain text instructions. Never force reasoning.enabled=false/effort=none.
    with OpenAI(base_url="https://openrouter.ai/api/v1", api_key=key,
                timeout=45.0, max_retries=0) as client:
        for attempt in range(2):
            kwargs = {
                "model": MODEL,
                "messages": messages,
                "max_tokens": MAX_OUTPUT_TOKENS,
            }
            if attempt == 0:
                kwargs["response_format"] = {"type": "json_object"}
            try:
                response = client.chat.completions.create(**kwargs)
                parsed = _parse(_response_text(response))
                normalized = _normalize(parsed, candidates)
                if not any(f["quote"] and f["tags"] for f in normalized["facts"]):
                    raise ValueError("AI가 유효한 인용 근거를 반환하지 않았습니다")
                LOGGER.info("SEEDU semantic success: model=%s facts=%s",
                            getattr(response, "model", MODEL), len(normalized["facts"]))
                return normalized
            except Exception as exc:
                # Don't expose input student records or API keys in logs.
                kind = type(exc).__name__
                status = getattr(exc, "status_code", None)
                LOGGER.warning("SEEDU semantic attempt failed: attempt=%s model=%s "
                               "type=%s status=%s error=%s",
                               attempt + 1, MODEL, kind, status, str(exc)[:160])
                errors.append(f"{kind}(HTTP {status})" if status else kind)
                # No point retrying invalid credentials or exhausted quota.
                if status in (401, 402, 403, 429):
                    break
    raise ValueError("OpenRouter 무료 라우터 응답 실패: " + ", ".join(errors))
