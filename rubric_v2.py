"""SEEDU:ON Rubric 2.0 — 프로젝트 자체 설계 평가 기준.

연구 참고: Cha et al. (2024) 추천의사결정 지원,
Jin et al. (2023) 자기조절학습 단계, Park et al. (2025) 점수 일치도 검증.
이 논문들이 본 파일의 0~4 등급·가중치를 제시했다는 뜻이 아니다.
"""
from __future__ import annotations

import re
from typing import Any

VERSION = "rubric-2.0.1"
MAJOR_FIT_RUBRIC = {
    "전공 관련 활동": {"전공 주제 관련성": 10, "활동의 구체성": 10, "활동 간 연계성": 10},
    "학업 역량": {"전공 기초 교과 역량": 10, "지식의 실제 적용": 10, "학습 태도와 개선": 5},
    "관심의 지속성": {"관심 주제의 반복·유지": 8, "관심의 발전 과정": 8, "자기주도적 확장": 4},
    "탐구 심화도": {"탐구 문제 설정": 4, "탐구 방법 설계": 4, "결과 분석 및 검증": 4, "개선 및 후속 탐구": 3},
    "융합 역량": {"타 분야 지식 활용": 4, "융합적 문제해결": 4, "융합 결과의 타당성": 2},
}
INDICATORS = [(cat, label, weight) for cat, group in MAJOR_FIT_RUBRIC.items() for label, weight in group.items()]
COMPETENCY_NAMES = ["학업역량", "진로역량", "탐구역량", "공동체역량", "성장가능성"]

# 실제 사용 중인 백엔드의 지표 명칭과 배점을 그대로 유지한다.
INDICATOR_FOCUS = {
    "전공 주제 관련성": "희망 전공의 핵심 질문·지식과 활동 내용의 구체적 연결",
    "활동의 구체성": "수행 역할·방법·결과물·수정이 학생 기록에 있는가",
    "활동 간 연계성": "서로 다른 기록 또는 동일 학년의 후속 활동에 실제 연결이 있는가",
    "전공 기초 교과 역량": "관련 교과 개념의 이해와 정확한 응용",
    "지식의 실제 적용": "지식을 실제 문제나 산출물에 적용한 행동",
    "학습 태도와 개선": "오류·피드백을 반영한 구체적 학습 조정",
    "관심 주제의 반복·유지": "기록된 시점들에서 공통 관심의 지속 (미입력 미래 학년 감점 금지)",
    "관심의 발전 과정": "초기 활동에서 후속 활동으로 탐색 수준이 발전했는가",
    "자기주도적 확장": "추가 질문·활동·탐색을 학생이 실제로 수행했는가",
    "탐구 문제 설정": "구체적 질문 및 연구 필요성·범위",
    "탐구 방법 설계": "조사·실험·분석 방법 선택과 이유·개선",
    "결과 분석 및 검증": "자료-결론 연결 및 결과 검증",
    "개선 및 후속 탐구": "한계 진단 이후 실제 개선 또는 후속 탐구",
    "타 분야 지식 활용": "서로 다른 교과·분야 개념의 실질적 연결",
    "융합적 문제해결": "다른 분야의 방법을 결합한 문제 해결",
    "융합 결과의 타당성": "융합 산출물의 결과·한계 또는 효과 검증",
}
COMPETENCY_ANCHORS = {
    "학업역량": ["관련 학습 기록에 이해·적용 행동 없음", "개념 학습·정리", "개념의 구체적 과제 적용", "문제 해결과 논리적 설명", "복합 문제 응용 및 오류·한계 검토와 개선"],
    "진로역량": ["진로 탐색 행동 없음", "관심 분야 언급·정보 조사", "관련 학습·체험 수행", "전공 이해의 구체적 확장", "여러 탐색 비교·판단 및 후속 활동 실행"],
    "탐구역량": ["탐구 수행 행동 없음", "주제 관심·단순 조사", "질문 설정 및 조사·실험 수행", "방법·결과 분석 및 근거 있는 결론", "한계 검토 후 재검증 또는 실제 방법 개선"],
    "공동체역량": ["협력·기여 행동 없음", "공동 활동 참여", "역할 수행 또는 자료·의견 공유", "의견 조율·공동 성과 기여", "협력 문제 해결과 협업 방식 개선"],
    "성장가능성": ["성찰·조정 행동 없음", "목표·어려움 인식", "계획 수립 또는 수행 점검", "성찰·피드백에 따른 행동 수정", "개선 효과 확인 후 다음 활동 전략 재조정"],
}


def _rating(value: Any, *, permit_none: bool = False) -> int | None:
    if permit_none and value is None:
        return None
    if isinstance(value, bool):
        raise ValueError("참/거짓은 점수가 아닙니다.")
    if isinstance(value, str) and value.strip() in {"0", "1", "2", "3", "4"}:
        value = int(value)
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    if not isinstance(value, int) or not 0 <= value <= 4:
        raise ValueError(f"0~4의 정수 등급이 필요합니다: {value!r}")
    return value


def _norm(text: str) -> str:
    return re.sub(r"\s+", "", text).casefold()


def _evidence(quote: Any, source: str, rating: int | None) -> dict:
    """인용은 실제 입력의 문자(공백 차이 허용)와 일치해야 한다."""
    quote = str(quote or "").strip()
    if rating is not None and rating > 0 and not quote:
        raise ValueError("1점 이상에는 학생부 원문 인용이 필요합니다.")
    if quote and (len(quote) < 4 or _norm(quote) not in _norm(source)):
        raise ValueError(f"학생부 입력에 없는 인용: {quote[:70]}")
    return {"quote": quote, "verified": bool(quote)}


def _source_text(records: Any, text: str) -> str:
    if isinstance(records, dict):
        available = "\n".join(str(value or "") for value in records.values())
        return available or text
    return text


def scoring_guidance() -> str:
    return (
        "당신은 학생부에 실제 작성된 행동만 평가한다. 아래 0~4점은 SEEDU:ON 자체 기준이다. "
        "교사 수식어(우수·탁월)만으로 고득점을 주지 않는다. "
        "각 영역의 공통 원칙: 0=평가 가능한 활동에서 해당 행동이 없음을 확인, "
        "1=관심·참여, 2=구체적 수행, 3=수행 과정과 결과·근거, "
        "4=심화·검증·방법 개선이 실제 나타남. "
        "관찰 자료 자체가 없거나 판단 불가능하면 rating=null로 반환한다. "
        "rating>0이면 반드시 사용자 입력 중 실제 연속된 문구를 evidence_quote로 복사한다. "
        "rating=0 또는 null이면 인용이 없을 수 있다. "
        "같은 인용을 여러 지표에 쓰더라도 각기 다른 관련 행동을 설명해야 한다. "
        "미입력 상위 학년, 입력되지 않은 영역을 이유로 등급을 낮추지 않는다. "
        "전공 적합도는 추천 학과별로 독립 평가하고 AI가 총점을 임의로 정하지 않는다.\n"
        + "5대 역량 0~4 등급 기준: "
        + str(COMPETENCY_ANCHORS) + "\n"
        + "16개 세부 지표의 초점 및 배점: "
        + str([(cat, label, weight, INDICATOR_FOCUS[label]) for cat, label, weight in INDICATORS])
    )


def calculate_major_fit_v2(ratings: Any, quotes: Any, source: str) -> dict:
    if not isinstance(ratings, list) or len(ratings) != 16:
        raise ValueError("전공 적합도 등급 16개가 필요합니다.")
    if not isinstance(quotes, list) or len(quotes) != 16:
        raise ValueError("전공 적합도 원문 인용 16개가 필요합니다.")
    category_scores = {cat: 0.0 for cat in MAJOR_FIT_RUBRIC}
    nested = {cat: {} for cat in MAJOR_FIT_RUBRIC}
    details = []
    scored_weight = 0
    for (cat, label, weight), raw_rating, quote in zip(INDICATORS, ratings, quotes):
        rating = _rating(raw_rating, permit_none=True)
        verified = _evidence(quote, source, rating)
        nested[cat][label] = rating
        if rating is not None:
            category_scores[cat] += weight * rating / 4
            scored_weight += weight
        details.append({"category": cat, "indicator": label, "weight": weight, "rating": rating, "status": "insufficient_evidence" if rating is None else "rated", **verified})
    # 16개 중 평가 불가능한 지표가 있다면 총점은 보류하고, 점수 산출 범위만 제공한다.
    return {
        "ratings": nested,
        "indicator_details": details,
        "category_scores": {key: round(value, 2) for key, value in category_scores.items()},
        "total_score": round(sum(category_scores.values()), 2) if scored_weight == 100 else None,
        "partial_score": round(sum(category_scores.values()), 2),
        "coverage_weight": scored_weight,
        "score_status": "complete" if scored_weight == 100 else "insufficient_evidence",
    }


def validate_analysis_v2(result: dict, records: Any, source_text: str) -> dict:
    if not isinstance(result, dict):
        raise ValueError("AI 응답 객체가 필요합니다.")
    source = _source_text(records, source_text)
    if not source.strip():
        raise ValueError("분석할 기록이 없습니다.")
    comp = result.get("competencies")
    recommended = result.get("recommended_majors")
    fits = result.get("major_fit")
    if not isinstance(comp, list) or len(comp) != 5:
        raise ValueError("역량은 5개여야 합니다.")
    if not isinstance(recommended, list) or len(recommended) != 3 or not all(isinstance(x, dict) for x in recommended):
        raise ValueError("추천 학과 3개가 필요합니다.")
    if not isinstance(fits, list) or len(fits) != 3 or not all(isinstance(x, dict) for x in fits):
        raise ValueError("전공 적합도 평가 3개가 필요합니다.")
    names = [x.get("major") for x in recommended]
    if not all(isinstance(n, str) and n.strip() for n in names) or len(set(names)) != 3:
        raise ValueError("추천 학과명이 누락·중복되었습니다.")
    by_name = {}
    for item in comp:
        if not isinstance(item, dict) or item.get("name") not in COMPETENCY_NAMES:
            raise ValueError("역량 이름이 올바르지 않습니다.")
        name = item["name"]
        if name in by_name:
            raise ValueError("중복 역량이 있습니다.")
        rating = _rating(item.get("rating"), permit_none=True)
        verified = _evidence(item.get("evidence_quote"), source, rating)
        by_name[name] = {"name": name, "rating": rating, "score": rating * 25 if rating is not None else None,
                         "status": "insufficient_evidence" if rating is None else "rated",
                         "evidence": str(item.get("evidence") or (verified["quote"] or "평가할 기록이 충분하지 않습니다.")),
                         "evidence_source": verified}
    if set(by_name) != set(COMPETENCY_NAMES):
        raise ValueError("역량 누락")
    evaluated = {}
    for item in fits:
        major = item.get("major")
        if major not in names or major in evaluated:
            raise ValueError("전공 적합도 평가 학과명이 추천 학과와 일치하지 않습니다.")
        score = calculate_major_fit_v2(item.get("ratings"), item.get("evidence_quotes"), source)
        evaluated[major] = {"major": major, **score, "evidence": str(item.get("evidence") or ""),
                            "improvement": str(item.get("improvement") or "")}
    if set(evaluated) != set(names):
        raise ValueError("학과별 평가 누락")
    result["competencies"] = [by_name[name] for name in COMPETENCY_NAMES]
    result["major_fit"] = [evaluated[name] for name in names]
    for key in ("strengths", "weaknesses"):
        if not isinstance(result.get(key), list):
            result[key] = []
    if not isinstance(result.get("growth"), (dict, list, str)):
        result["growth"] = "입력된 자료에서 학년별 성장 근거를 확인하세요."
    result["rubric_version"] = VERSION
    result["rubric_research_note"] = "0~4 기준 및 가중치는 SEEDU:ON 자체 설계; 연구는 방법론 참고"
    return result

