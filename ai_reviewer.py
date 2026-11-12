"""Bounded optional OpenRouter review: never needed for a successful baseline.
AI can propose one conservative adjustment only when an exact input quote supports it.
"""
import json
import os
import re
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout

REVIEW_TIMEOUT = 7.0


def should_review(result, full_text, mode="hybrid"):
    if mode == "fast" or os.getenv("HYBRID_AI_ENABLED", "true").lower() in ("false", "0", "off"):
        return False, "fast_mode_or_disabled"
    if not os.getenv("OPENROUTER_API_KEY"):
        return False, "no_api_key"
    if len(full_text.strip()) < 220:
        return False, "short_record"
    majors = result.get("recommended_majors", [])
    if len(majors) < 2:
        return False, "insufficient_candidates"
    # Top candidates whose evidence counts are too similar require contextual comparison.
    # Do not ask AI to invent a major when nothing in the record matches.
    relevant = [m for m in majors[:2] if m.get("related_term_count", 0) >= 2]
    if len(relevant) == 2 and abs(relevant[0]["related_term_count"] - relevant[1]["related_term_count"]) <= 1:
        return True, "close_major_candidates"
    # A record may provide many activities but an evidence gap for one competence.
    if len(full_text) >= 380 and sum(c.get("rating") is None for c in result["competencies"]) >= 2 and len(relevant) >= 1:
        return True, "competency_evidence_ambiguous"
    return False, "no_review_needed"


def _call(prompt, timeout):
    from openai import OpenAI
    client = OpenAI(base_url="https://openrouter.ai/api/v1",
                    api_key=os.environ["OPENROUTER_API_KEY"],
                    timeout=timeout, max_retries=0)
    try:
        response = client.chat.completions.create(
            model=os.getenv("OPENROUTER_MODEL", "openrouter/free"),
            messages=[
                {"role": "system", "content": (
                    "당신은 학생부 평가 보조자다. 전체 채점이나 학과 추천을 새로 하지 마라. "
                    "입력 원문에서 정확하게 복사한 한 문장으로 근거를 제시해라. "
                    "JSON 한 개만 반환: {\"target_major\":\"\",\"quote\":\"\",\"reason\":\"\",\"next_step\":\"\"}. "
                    "target_major는 제공 후보 중 하나. quote는 입력 원문에 정확히 나타난 부분 문자열이어야 한다. "
                    "근거가 없으면 quote와 reason을 빈 문자열로 반환." )},
                {"role": "user", "content": prompt},
            ], temperature=0, max_tokens=350,
        )
        content = response.choices[0].message.content or ""
        if not content.strip():
            return None
        content = re.sub(r"^```(?:json)?\s*|\s*```$", "", content.strip(), flags=re.I)
        return json.loads(content)
    finally:
        client.close()


def run_review(result, full_text, mode="hybrid", call_fn=None):
    trigger, reason = should_review(result, full_text, mode)
    status = {"requested": bool(trigger), "used": False, "status": "skipped", "reason": reason}
    if not trigger:
        return status
    major_names = [x["major"] for x in result["recommended_majors"][:3]]
    # Keep user text bounded to reduce latency and cost; never return an unsupported quote.
    prompt = json.dumps({
        "candidate_majors": major_names,
        "existing_reasons": [x.get("reason", "") for x in result["recommended_majors"][:3]],
        "student_record": full_text[:3300],
    }, ensure_ascii=False)
    func = call_fn or _call
    # Executor context manager waits for hung tasks; avoid that by shutting down without waiting.
    pool = ThreadPoolExecutor(max_workers=1)
    future = pool.submit(func, prompt, REVIEW_TIMEOUT)
    try:
        response = future.result(timeout=REVIEW_TIMEOUT + 0.5)
    except (FutureTimeout, Exception):
        status["status"] = "fallback"
        status["reason"] = "review_timeout_or_invalid_response"
        return status
    finally:
        pool.shutdown(wait=False, cancel_futures=True)
    if not isinstance(response, dict):
        status["status"] = "fallback"
        status["reason"] = "invalid_review"
        return status
    quote = str(response.get("quote") or "").strip()
    target = str(response.get("target_major") or "").strip()
    explanation = str(response.get("reason") or "").strip()[:260]
    next_step = str(response.get("next_step") or "").strip()[:240]
    if len(quote) < 12 or quote not in full_text or target not in major_names or not explanation:
        status["status"] = "fallback"
        status["reason"] = "unverified_quote_or_major"
        return status
    # AI never changes numerical ratings. It supplies only verified contextual interpretation.
    for item in result["recommended_majors"]:
        if item["major"] == target:
            item["ai_context"] = {"quote":quote, "reason":explanation,
                                  "next_step":next_step, "verified":True}
            item["reason"] = item["reason"] + " AI 보조 해석: " + explanation
            break
    status.update({"used":True, "status":"reviewed", "reason":reason})
    return status
