"""SEEDU:ON 3.1 — deterministic model selection + concise semantic extraction.

Drop-in replacement for repository-root ai_semantic.py.
Contract: request_semantics(sources, candidates, *, call_fn=None) returns
{'facts': [...], 'competencies': [...], 'major_links': [...]}.

Privacy: do not transmit identifiable student records without an appropriate
lawful basis and necessary notice/consent. Never log API keys or record text.
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
# Verified on OpenRouter's model page (2026-11-14): this model supports switching thinking OFF.
TESTED_MODEL = "inclusionai/ling-3.2-flash:free"
TAGS = set("learning career question method result validation revision collaboration leadership reflection planning interdisciplinary comparison application continuity concept".split())

# Minimal response: 2-3 concise quotes plus 5 rubric assessments and 3 major links.
# The model handles meaning; rubric_engine/semantic_engine validate evidence and scoring.
SYSTEM = (
    "고등학생 학생부에서 수행 행동의 의미를 판단하고 JSON만 반환하라. "
    "원문(s의 t)에서 12~75자의 연속된 문구를 정확히 복사해 근거 2~3개를 뽑아라. "
    "관심·참여만 한 활동과 문제해결·검증·개선 활동을 구별하라. 추측하거나 과장하지 마라. "
    "JSON 키는 f,c,m만 사용한다. "
    "f=[[원문자료 i,인용문,태그배열],...], 최대 3개. "
    "태그는 learning,career,question,method,result,validation,revision,collaboration,"
    "leadership,reflection,planning,interdisciplinary,comparison,application,continuity,concept 중 선택. "
    "c는 학업,진로,탐구,공동체,성장 순서의 5개 [등급,근거번호배열]. "
    "등급=0~4 또는 null. 1 참여,2 구체적 수행,3 방법-결과 연결,4 검증 후 실제 개선. "
    "근거가 없으면 [null,[]]. 높은 등급을 억지로 주지 마라. "
    "m은 입력된 3개 전공 순서의 관련 근거번호 배열 3개. "
    "반드시 완성된 JSON 객체 한 개만 출력. 설명 없이 끝내라."
)


def _payload(sources: list[dict], candidates: list[str]) -> str:
    if not sources:
        raise ValueError("학생부 기록 없음")
    nonempty = [(i, str(s.get("text") or "").strip()) for i, s in enumerate(sources)]
    nonempty = [(i, txt) for i, txt in nonempty if txt][:6]
    if not nonempty:
        raise ValueError("학생부에 분석할 텍스트가 없음")
    # Balanced per-record excerpts prevent a single long record from consuming all budget.
    per_item = min(390, max(180, 2000 // len(nonempty)))
    selection = [{"i": i, "t": txt[:per_item]} for i, txt in nonempty]
    return json.dumps({"s": selection, "m": list(candidates[:3])}, ensure_ascii=False, separators=(",", ":"))


def _json_object(content: Any) -> dict:
    if not isinstance(content, str) or not content.strip():
        raise ValueError("빈 AI 응답: 모델이 최종 답변을 생성하지 못함")
    body = content.strip()
    body = re.sub(r"^```(?:json)?\s*", "", body, flags=re.I)
    body = re.sub(r"\s*```$", "", body)
    begin, end = body.find("{"), body.rfind("}")
    if begin < 0 or end <= begin:
        raise ValueError("완성된 JSON 객체 없음")
    try:
        data = json.loads(body[begin:end + 1])
    except json.JSONDecodeError as exc:
        raise ValueError(f"AI JSON 파싱 실패 위치={exc.pos}") from exc
    if (not isinstance(data, dict) or not isinstance(data.get("f"), list)
            or not isinstance(data.get("c"), list) or len(data["c"]) != 5):
        raise ValueError("AI 데이터 구조 오류: f와 c(5개) 필요")
    return data


def _normalize(raw: dict, candidates: list[str], sources: list[dict] | None = None) -> dict:
    facts = []
    old_to_new = {}
    for old_i, item in enumerate(raw["f"][:3]):
        if (not isinstance(item, list) or len(item) < 3
                or type(item[0]) is not int or item[0] < 0
                or not isinstance(item[1], str) or not isinstance(item[2], list)):
            continue
        source_index, quote = item[0], item[1].strip()
        tags = list(dict.fromkeys(t for t in item[2] if isinstance(t, str) and t in TAGS))
        if not 12 <= len(quote) <= 550 or not tags:
            continue
        # Verify cited text is present in selected source, not fabricated by model.
        if sources is not None:
            if source_index >= len(sources):
                continue
            original = str(sources[source_index].get("text") or "")
            normalize_ws = lambda s: re.sub(r"\s+", "", s).casefold()
            if normalize_ws(quote) not in normalize_ws(original):
                continue
        old_to_new[old_i] = len(facts)
        facts.append({"source_index": source_index, "quote": quote, "tags": tags})

    def links(ids: Any) -> list[int]:
        if not isinstance(ids, list):
            return []
        return list(dict.fromkeys(old_to_new[x] for x in ids if type(x) is int and x in old_to_new))

    competencies = []
    for idx, name in enumerate(COMPETENCY_NAMES):
        c = raw["c"][idx]
        rating = c[0] if isinstance(c, list) and c else None
        evidence_ids = links(c[1]) if isinstance(c, list) and len(c) > 1 else []
        if type(rating) is not int or not 0 <= rating <= 4 or not evidence_ids:
            rating = None
        competencies.append({"name": name, "rating": rating, "evidence_ids": evidence_ids})

    major_links = []
    raw_m = raw.get("m")
    for idx, major in enumerate(candidates[:3]):
        ids = raw_m[idx] if isinstance(raw_m, list) and idx < len(raw_m) else []
        major_links.append({"major": major, "evidence_ids": links(ids)})
    return {"facts": facts, "competencies": competencies, "major_links": major_links}


def _configured_model() -> str:
    model = os.getenv("OPENROUTER_MODEL", "").strip()
    if not model:
        raise ValueError("Render OPENROUTER_MODEL 설정이 비어 있습니다")
    if model == "openrouter/free":
        # Fail *before* sending any student record/token. Random router repeatedly
        # selected mandatory-reasoning models that consumed the whole output budget.
        raise ValueError(
            "openrouter/free는 추론 모델이 무작위 선택되어 출력 초과가 반복됩니다. "
            "Render OPENROUTER_MODEL을 inclusionai/ling-3.2-flash:free로 변경하세요."
        )
    return model


def _usage(reply: Any) -> tuple[str, str, str]:
    usage = getattr(reply, "usage", None)
    details = getattr(usage, "completion_tokens_details", None)
    def val(o, field):
        v = getattr(o, field, None)
        return str(v) if v is not None else "-"
    return val(reply, "model")[:120], val(usage, "completion_tokens"), val(details, "reasoning_tokens")


def request_semantics(sources, candidates, *, call_fn=None):
    payload = _payload(sources, candidates)
    if call_fn is not None:
        return _normalize(_json_object(call_fn(SYSTEM, payload)), candidates, sources)

    api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
    if not api_key:
        raise ValueError("OPENROUTER_API_KEY 미설정")
    model = _configured_model()
    from openai import OpenAI

    params: dict[str, Any] = {
        "model": model,
        "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": payload}],
        "max_tokens": 1200,
        "temperature": 0,
        "response_format": {"type": "json_object"},
    }
    if model == TESTED_MODEL:
        # Only THIS exact model has explicitly documented optional thinking.
        # Never send this to Nemotron, openrouter/free, or an unknown model.
        params["extra_body"] = {"reasoning": {"enabled": False}}

    try:
        with OpenAI(base_url=BASE_URL, api_key=api_key, timeout=40.0, max_retries=0) as client:
            reply = client.chat.completions.create(**params)
    except Exception as exc:
        status = getattr(exc, "status_code", None)
        # Do not expose key, raw request or student data.
        LOG.warning("SEEDU semantic API error: model=%s type=%s status=%s", model, type(exc).__name__, status)
        raise

    actual_model, completion, reasoning = _usage(reply)
    choices = getattr(reply, "choices", None) or []
    if not choices:
        raise ValueError("AI 응답에 선택지가 없음")
    first = choices[0]
    finish = getattr(first, "finish_reason", None)
    if finish == "length":
        LOG.warning("SEEDU semantic length: model=%s completion_tokens=%s reasoning_tokens=%s",
                    actual_model, completion, reasoning)
        raise ValueError("AI 출력 토큰 한도 초과")
    if finish not in (None, "stop"):
        raise ValueError("AI 비정상 종료: " + str(finish)[:50])

    raw = _json_object(getattr(getattr(first, "message", None), "content", None))
    data = _normalize(raw, candidates, sources)
    if not data["facts"] or not any(c["rating"] is not None for c in data["competencies"]):
        raise ValueError("AI가 검증 가능한 학생부 근거와 등급 연결을 반환하지 않음")
    LOG.info("SEEDU semantic success: model=%s facts=%d completion_tokens=%s reasoning_tokens=%s",
             actual_model, len(data["facts"]), completion, reasoning)
    return data
