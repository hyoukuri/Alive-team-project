"""SEEDU:ON 3.1 — quote-safe semantic analysis with one OpenRouter request.

Drop-in replacement for the repository-root ai_semantic.py.
The Python code chooses verbatim source excerpts BEFORE the model call; the model
only supplies excerpt IDs, behavioral tags, levels, and major links. This avoids
failing all evidence because an LLM paraphrases a quotation.

No student record contents or API credentials are written to logs.
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
THINKING_OPTION_MODEL = "inclusionai/ling-3.2-flash:free"
TAGS = set("learning career question method result validation revision collaboration leadership reflection planning interdisciplinary comparison application continuity concept".split())

SYSTEM = (
    "당신은 학생부의 실제 수행 내용을 해석하는 평가 보조자다. 제공된 s의 각 항목은 Python이 원문에서 직접 추출한 근거이며 n은 근거 ID다. "
    "원문 인용문을 재작성하지 마라. 근거 ID로만 답하라. 단어 등장만으로 높은 평가를 내리지 마라. "
    "반드시 JSON 객체 하나만 출력하라. 형식: "
    '{"e":[[0,["method","result"]],[2,["revision"]]],'
    '"c":[[3,[0,2]],[null,[]],[3,[0,2]],[null,[]],[2,[2]]],'
    '"m":[[0,2],[0],[]]}. '
    "e는 원문 근거 ID와 의미 태그 배열, 최대 6개. 근거 번호는 입력 s의 n에서만 고른다. "
    "태그는 learning,career,question,method,result,validation,revision,collaboration,leadership,reflection,planning,interdisciplinary,comparison,application,continuity,concept 중 선택. "
    "c는 학업·진로·탐구·공동체·성장 순서로 정확히 5개 [0~4 또는 null, 근거 ID 배열]. "
    "1=참여·관심, 2=구체적 수행, 3=문제·방법·결과의 연결, 4=독립적인 검증과 실질적인 개선을 확인한 경우만. "
    "m은 입력한 전공 후보 3개의 관련 근거 ID 배열. 원문에 없는 근거와 허위 성과를 만들지 마라."
)


def _source_spans(sources: list[dict]) -> list[dict]:
    """Produce short, exact excerpts with stable source indexes; no AI quotation."""
    if not sources:
        raise ValueError("학생부 기록 없음")
    spans = []
    # Up to 6 records, two excerpts each. Keeps prompt short and retains multiple facts.
    for source_idx, item in enumerate(sources[:6]):
        raw = str(item.get("text") or "").strip()
        if not raw:
            continue
        # A sentence is copied exactly from its source. Do not synthesize text.
        sentences = [s.strip() for s in re.split(r"(?<=[.!?。])\s+|\n+", raw) if s.strip()]
        if not sentences:
            sentences = [raw]
        used = set()
        for part in sentences:
            if len(used) >= 2:
                break
            # Keep the verbatim prefix for unusually long source sentences.
            quote = part[:220].strip()
            if len(quote) < 12 or quote in used:
                continue
            used.add(quote)
            spans.append({"n": len(spans), "i": source_idx, "t": quote})
        if not used and len(raw) >= 12:
            spans.append({"n": len(spans), "i": source_idx, "t": raw[:220]})
    if not spans:
        raise ValueError("학생부 기록에서 분석할 문장을 추출하지 못함")
    return spans


def _payload(sources: list[dict], candidates: list[str]):
    spans = _source_spans(sources)
    user = json.dumps({"s": spans, "m": list(candidates[:3])}, ensure_ascii=False, separators=(",", ":"))
    return user, spans


def _json_object(content: Any) -> dict:
    if not isinstance(content, str) or not content.strip():
        raise ValueError("빈 AI 응답")
    data = re.sub(r"^```(?:json)?\s*", "", content.strip(), flags=re.I)
    data = re.sub(r"\s*```$", "", data)
    start, end = data.find("{"), data.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("완성된 JSON 객체가 없음")
    try:
        obj = json.loads(data[start:end + 1])
    except json.JSONDecodeError as exc:
        raise ValueError("AI JSON 형식 오류: 위치=" + str(exc.pos)) from exc
    if not isinstance(obj, dict):
        raise ValueError("AI JSON 최상위 구조 오류")
    if not isinstance(obj.get("e"), list) or not isinstance(obj.get("c"), list) or len(obj["c"]) != 5:
        raise ValueError("AI JSON 구조 오류: e 배열, c 배열 5개 필요")
    return obj


def _normalize(raw: dict, candidates: list[str], spans: list[dict], sources: list[dict]) -> dict:
    by_id = {span["n"]: span for span in spans}
    facts = []
    span_to_fact = {}
    for row in raw["e"][:6]:
        if not isinstance(row, list) or len(row) < 2 or type(row[0]) is not int or not isinstance(row[1], list):
            continue
        segment_id = row[0]
        if segment_id not in by_id or segment_id in span_to_fact:
            continue
        seg = by_id[segment_id]
        source_idx = seg["i"]
        quote = seg["t"]
        # This is deterministic validation, not a fuzzy AI quote match.
        if source_idx >= len(sources) or len(quote) < 12 or quote not in str(sources[source_idx].get("text") or ""):
            continue
        tags = list(dict.fromkeys(t for t in row[1] if isinstance(t, str) and t in TAGS))
        if not tags:
            continue
        span_to_fact[segment_id] = len(facts)
        facts.append({"source_index": source_idx, "quote": quote, "tags": tags})

    def linked(ids: Any) -> list[int]:
        if not isinstance(ids, list):
            return []
        return list(dict.fromkeys(span_to_fact[i] for i in ids if type(i) is int and i in span_to_fact))

    competencies = []
    for idx, name in enumerate(COMPETENCY_NAMES):
        row = raw["c"][idx]
        rating = row[0] if isinstance(row, list) and row else None
        ids = linked(row[1] if isinstance(row, list) and len(row) > 1 else [])
        if type(rating) is not int or not 0 <= rating <= 4 or not ids:
            rating = None
        competencies.append({"name": name, "rating": rating, "evidence_ids": ids})

    major_links = []
    raw_m = raw.get("m", [])
    for idx, major in enumerate(candidates[:3]):
        ids = raw_m[idx] if isinstance(raw_m, list) and idx < len(raw_m) else []
        major_links.append({"major": major, "evidence_ids": linked(ids)})
    return {"facts": facts, "competencies": competencies, "major_links": major_links}


def _configured_model() -> str:
    model = os.getenv("OPENROUTER_MODEL", "").strip()
    if not model:
        raise ValueError("Render OPENROUTER_MODEL 미설정")
    return model


def _usage(reply):
    usage = getattr(reply, "usage", None)
    details = getattr(usage, "completion_tokens_details", None)
    return (str(getattr(reply, "model", "unknown"))[:100],
            getattr(usage, "completion_tokens", None), getattr(details, "reasoning_tokens", None))


def request_semantics(sources, candidates, *, call_fn=None):
    payload, spans = _payload(sources, candidates)
    if call_fn is not None:
        result = _normalize(_json_object(call_fn(SYSTEM, payload)), candidates, spans, sources)
    else:
        key = os.getenv("OPENROUTER_API_KEY", "").strip()
        if not key:
            raise ValueError("Render OPENROUTER_API_KEY 미설정")
        model = _configured_model()
        from openai import OpenAI
        params = {
            "model": model,
            "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": payload}],
            "max_tokens": 1400,
            "temperature": 0,
            "response_format": {"type": "json_object"},
        }
        if model == THINKING_OPTION_MODEL:
            params["extra_body"] = {"reasoning": {"enabled": False}}
        try:
            with OpenAI(base_url=BASE_URL, api_key=key, timeout=40.0, max_retries=0) as client:
                reply = client.chat.completions.create(**params)
        except Exception as exc:
            LOG.warning("SEEDU semantic API failure: model=%s error=%s status=%s",
                        model, type(exc).__name__, getattr(exc, "status_code", None))
            raise
        selected_model, completion, reasoning = _usage(reply)
        choices = getattr(reply, "choices", []) or []
        if not choices:
            raise ValueError("AI 응답 없음")
        if getattr(choices[0], "finish_reason", None) == "length":
            LOG.warning("SEEDU semantic length: model=%s completion=%s reasoning=%s",
                        selected_model, completion, reasoning)
            raise ValueError("AI 출력 토큰 한도 초과")
        parsed = _json_object(getattr(getattr(choices[0], "message", None), "content", None))
        result = _normalize(parsed, candidates, spans, sources)
        LOG.info("SEEDU semantic parsed: model=%s spans=%d valid_facts=%d linked_scores=%d",
                 selected_model, len(spans), len(result["facts"]),
                 sum(c["rating"] is not None for c in result["competencies"]))

    if not result["facts"] or not any(c["rating"] is not None for c in result["competencies"]):
        LOG.warning("SEEDU semantic evidence invalid: spans=%d facts=%d graded=%d",
                    len(spans), len(result["facts"]),
                    sum(c["rating"] is not None for c in result["competencies"]))
        raise ValueError("AI가 유효한 근거 ID와 등급 연결을 반환하지 않음")
    return result
