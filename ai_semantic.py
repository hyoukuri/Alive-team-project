"""SEEDU:ON 3.1 — compact, evidence-first OpenRouter semantic adapter.

Drop-in replacement for the repository-root ai_semantic.py.
Contract: request_semantics(sources, candidates, *, call_fn=None) returns:
  {'facts': [...], 'competencies': [...], 'major_links': [...]}

Only ONE API request per analysis. The model is controlled exclusively by the
Render OPENROUTER_MODEL environment variable. No automatic model discovery or
mandatory-reasoning toggles. API failures are surfaced to main.py, which shows
an explicitly unverified rule-based preview.

Do not send identifiable student records to third-party AI providers without
an appropriate lawful basis and consent/notice, as applicable.
"""
from __future__ import annotations

import json
import logging
import os
import re
from typing import Any

from rubric_v2 import COMPETENCY_NAMES

LOG = logging.getLogger("seedu.semantic")
BASE_URL = "https://openrouter.ai/api/v1"
TAGS = set(
    "learning career question method result validation revision collaboration "
    "leadership reflection planning interdisciplinary comparison application "
    "continuity concept".split()
)

# Four facts and five compact assessments deliberately keep the visible answer short.
# No examples containing invented evidence: the model must copy from source text.
SYSTEM = (
    "너는 고등학생 생활기록부의 행동 근거 추출기다. 의미와 수행 맥락을 판단하되 "
    "과장하거나 추정하지 마라. 입력 s의 t에서 연속된 문구를 정확히 복사해라. "
    "원문에 실제로 없는 인용이나 점수는 금지한다. "
    "오직 짧은 JSON 객체 하나만 출력한다. 키는 f,c,m 세 개뿐이다. "
    "f는 최대 4개: [자료 i, 원문 그대로 12자 이상 인용, 영어 태그 배열]. "
    "태그는 learning,career,question,method,result,validation,revision,"
    "collaboration,leadership,reflection,planning,interdisciplinary,comparison,"
    "application,continuity,concept 중에서만 선택. "
    "c는 학업,진로,탐구,공동체,성장 순서로 정확히 5개 [등급, f의 인덱스 배열]. "
    "등급은 0~4 또는 null. 근거가 없으면 [null,[]]. "
    "1=참여,2=구체적 수행,3=방법과 결과의 연결,4=검증과 실제 개선이 명확함. "
    "m은 입력 m의 첫 3개 학과별로 관련 f 인덱스 배열, 총 3개. "
    "출력 예시(내용은 복사 금지): "
    '{"f":[[0,"학생부의 실제 행동과 결과를 그대로 인용한 문구",["method","result"]]],'
    '"c":[[2,[0]],[null,[]],[2,[0]],[null,[]],[null,[]]],"m":[[0],[],[]]}. '
    "설명, 줄바꿈, 마크다운 없이 JSON만 출력."
)


def _payload(sources: list[dict], candidates: list[str]) -> str:
    """Use up to six source entries, keeping their original indices."""
    if not sources:
        raise ValueError("학생부 기록 없음")
    # A bounded student record limits input cost; the full source remains available
    # to semantic_engine.clean_facts for quote verification.
    total_budget = 1700
    nonempty = [(i, str(item.get("text") or "").strip()) for i, item in enumerate(sources)]
    nonempty = [(i, text) for i, text in nonempty if text][:6]
    if not nonempty:
        raise ValueError("학생부 기록에 텍스트가 없음")
    per_item = max(160, total_budget // len(nonempty))
    selected = []
    for index, text in nonempty:
        excerpt = text[: min(per_item, total_budget)]
        if excerpt:
            selected.append({"i": index, "t": excerpt})
            total_budget -= len(excerpt)
        if total_budget <= 0:
            break
    return json.dumps({"s": selected, "m": list(candidates[:3])}, ensure_ascii=False, separators=(",", ":"))


def _json_object(content: str) -> dict:
    if not isinstance(content, str) or not content.strip():
        raise ValueError("빈 AI 응답")
    body = re.sub(r"^```(?:json)?\s*", "", content.strip(), flags=re.I)
    body = re.sub(r"\s*```$", "", body)
    first, last = body.find("{"), body.rfind("}")
    if first < 0 or last <= first:
        raise ValueError("AI가 완성된 JSON 객체를 반환하지 않음")
    try:
        parsed = json.loads(body[first:last + 1])
    except json.JSONDecodeError as exc:
        raise ValueError(f"AI JSON 형식 오류 (위치={exc.pos})") from exc
    if (not isinstance(parsed, dict)
            or not isinstance(parsed.get("f"), list)
            or not isinstance(parsed.get("c"), list)
            or len(parsed["c"]) != 5):
        raise ValueError("AI 출력 구조 오류: f 목록과 c 5개가 필요합니다")
    return parsed


def _normalize(parsed: dict, candidates: list[str]) -> dict:
    facts = []
    # Convert model fact indices to normalized fact indices; malformed facts
    # never shift references to the wrong quote.
    remap = {}
    for old_index, item in enumerate(parsed["f"][:4]):
        if (not isinstance(item, list) or len(item) < 3
                or type(item[0]) is not int or item[0] < 0
                or not isinstance(item[1], str)
                or not isinstance(item[2], list)):
            continue
        tags = list(dict.fromkeys(x for x in item[2] if isinstance(x, str) and x in TAGS))
        if len(item[1].strip()) < 12 or not tags:
            continue
        remap[old_index] = len(facts)
        facts.append({
            "source_index": item[0],
            "quote": item[1].strip(),
            "tags": tags,
        })

    def valid_links(links: Any) -> list[int]:
        if not isinstance(links, list):
            return []
        return list(dict.fromkeys(remap[i] for i in links if type(i) is int and i in remap))

    competencies = []
    for i, name in enumerate(COMPETENCY_NAMES):
        row = parsed["c"][i]
        grade = row[0] if isinstance(row, list) and row else None
        links = row[1] if isinstance(row, list) and len(row) > 1 else []
        if type(grade) is not int or not 0 <= grade <= 4:
            grade = None
        ids = valid_links(links)
        if not ids:
            grade = None
        competencies.append({"name": name, "rating": grade, "evidence_ids": ids})

    raw_major_links = parsed.get("m", [])
    major_links = []
    for i, name in enumerate(candidates[:3]):
        ids = raw_major_links[i] if isinstance(raw_major_links, list) and i < len(raw_major_links) else []
        major_links.append({"major": name, "evidence_ids": valid_links(ids)})
    return {"facts": facts, "competencies": competencies, "major_links": major_links}


def _model() -> str:
    name = os.getenv("OPENROUTER_MODEL", "").strip()
    if not name:
        raise ValueError("Render 환경변수 OPENROUTER_MODEL이 비어 있습니다")
    return name


def _safe_api_error(exc: Exception) -> tuple[str, str]:
    status = str(getattr(exc, "status_code", "-") or "-")
    limit_source = "-"
    body = getattr(exc, "body", None)
    if isinstance(body, dict):
        detail = body.get("error", body)
        if isinstance(detail, dict):
            metadata = detail.get("metadata", {})
            if isinstance(metadata, dict):
                limit_source = str(metadata.get("limit_source", "-") or "-")[:80]
    return status, limit_source


def _usage_info(response: Any) -> tuple[str, str, str]:
    usage = getattr(response, "usage", None)
    details = getattr(usage, "completion_tokens_details", None)
    return (
        str(getattr(usage, "completion_tokens", "-") or "-"),
        str(getattr(details, "reasoning_tokens", "-") or "-"),
        str(getattr(response, "model", "-") or "-")[:120],
    )


def request_semantics(sources, candidates, *, call_fn=None):
    payload = _payload(sources, candidates)
    if call_fn is not None:
        return _normalize(_json_object(call_fn(SYSTEM, payload)), candidates)

    key = os.getenv("OPENROUTER_API_KEY", "").strip()
    if not key:
        raise ValueError("OPENROUTER_API_KEY 미설정")
    model = _model()
    from openai import OpenAI
    try:
        # JSON mode lets OpenRouter route to a compatible free provider.
        # No model-specific reasoning override: some endpoints require reasoning.
        # Single request; the existing main.py controls cooldown and cache.
        with OpenAI(base_url=BASE_URL, api_key=key, timeout=35.0, max_retries=0) as client:
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "system", "content": SYSTEM},
                          {"role": "user", "content": payload}],
                response_format={"type": "json_object"},
                max_tokens=2800,
            )
    except Exception as exc:
        status, source = _safe_api_error(exc)
        LOG.warning("SEEDU semantic API error: model=%s type=%s status=%s limit_source=%s",
                    model, type(exc).__name__, status, source)
        raise

    choices = getattr(response, "choices", None) or []
    if not choices:
        raise ValueError("AI 응답 선택지 없음")
    choice = choices[0]
    finish_reason = getattr(choice, "finish_reason", None)
    completion, reasoning, actual_model = _usage_info(response)
    if finish_reason == "length":
        LOG.warning("SEEDU semantic length: selected_model=%s completion_tokens=%s reasoning_tokens=%s",
                    actual_model, completion, reasoning)
        raise ValueError("AI 출력 토큰 한도 초과 (선택 모델의 추론 토큰 소모 가능)")
    if finish_reason not in ("stop", None):
        raise ValueError(f"AI 비정상 종료: {str(finish_reason)[:50]}")

    content = getattr(getattr(choice, "message", None), "content", None)
    output = _normalize(_json_object(content), candidates)
    if not output["facts"]:
        raise ValueError("AI 응답에 확인 가능한 근거가 없음")
    LOG.info("SEEDU semantic success: selected_model=%s facts=%s completion_tokens=%s reasoning_tokens=%s",
             actual_model, len(output["facts"]), completion, reasoning)
    return output
