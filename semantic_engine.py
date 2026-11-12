"""SEEDU:ON 3.0: evidence-first semantic scoring.

AI reads context and identifies actions. Python validates verbatim evidence, applies
conservative ceilings, and calculates the 16 weighted scores. No keyword hits
can increase the scored aptitude. Research-informed design, NOT a validated
university admissions score.
"""
from __future__ import annotations

import re
from collections import defaultdict
from rubric_v2 import INDICATORS, MAJOR_FIT_RUBRIC, COMPETENCY_NAMES
from rubric_engine import MAJORS, LEARNING_VALUE, _record_chunks

VERSION = "rubric-3.0-semantic"
TAGS = {"learning", "career", "question", "method", "result", "validation", "revision", "collaboration", "leadership", "reflection", "planning", "interdisciplinary", "comparison", "application", "continuity", "concept"}
# action-level semantics from AI, not keyword matches
HIGH_ACTIONS = {"validation", "revision"}


def prepare(records, text, grade):
    chunks = _record_chunks(records, text)
    if not chunks:
        raise ValueError("분석할 학생부 기록이 없습니다.")
    # Exact text excerpts are kept with grade + source, so bogus quotes are rejected.
    sources = []
    seen = set()
    for chunk in chunks:
        key = (chunk["grade"], chunk["source"])
        if key not in seen:
            seen.add(key)
            sources.append({"grade": key[0], "source": key[1], "text": ""})
        index = next(i for i, v in enumerate(sources) if (v["grade"], v["source"]) == key)
        sources[index]["text"] += (" " if sources[index]["text"] else "") + chunk["text"]
    return sources


def candidates_from_sources(sources):
    # Preselection only; never used for the final score.
    full = " ".join(x["text"].lower() for x in sources)
    scored = []
    for major, terms in MAJORS.items():
        hits = sum(1 for term in terms if term.lower() in full)
        if hits:
            scored.append((major, hits))
    scored.sort(key=lambda x: (-x[1], x[0]))
    options = [name for name, _ in scored[:5]]
    # Students can have a new field; AI may not invent unlisted majors in this version.
    if not options:
        options = ["컴퓨터공학과", "데이터사이언스학과", "사회학과"]
    for name in MAJORS:
        if len(options) >= 3:
            break
        if name not in options:
            options.append(name)
    return options[:5]


def _norm(s):
    return re.sub(r"\s+", "", str(s or "")).casefold()


def clean_facts(raw, sources):
    """Accept facts only if quote is verbatim within its designated source."""
    facts = []
    seen = set()
    if not isinstance(raw, list):
        return facts
    for original_id, obj in enumerate(raw[:16]):
        if not isinstance(obj, dict):
            continue
        try:
            index = int(obj.get("source_index"))
        except (ValueError, TypeError):
            continue
        if not 0 <= index < len(sources):
            continue
        quote = str(obj.get("quote") or "").strip()
        if len(quote) < 12 or len(quote) > 550 or _norm(quote) not in _norm(sources[index]["text"]):
            continue
        key = (index, _norm(quote))
        if key in seen:
            continue
        seen.add(key)
        tags = [s for s in obj.get("tags", []) if isinstance(s, str) and s in TAGS] if isinstance(obj.get("tags"), list) else []
        if not tags:
            continue
        facts.append({"id":original_id, "source_index":index, "grade":sources[index]["grade"],
                      "source":sources[index]["source"], "quote":quote,
                      "tags":tags, "interpretation":str(obj.get("interpretation") or "")[:150]})
    return facts


def _valid_ids(value, facts):
    if not isinstance(value, list):
        return []
    position = {fact["id"]: idx for idx, fact in enumerate(facts)}
    return list(dict.fromkeys(position[v] for v in value if type(v) is int and v in position))[:12]


def _find_quote_facts(facts, quote):
    q = _norm(quote)
    return [f for f in facts if q and (_norm(f["quote"]) == q or q in _norm(f["quote"]))]


def competencies_from_ai(raw, facts):
    by_name = {x.get("name"):x for x in raw if isinstance(x, dict)} if isinstance(raw, list) else {}
    result = []
    for name in COMPETENCY_NAMES:
        item = by_name.get(name, {})
        value = item.get("rating")
        rating = value if type(value) is int and 0 <= value <= 4 else None
        ids = _valid_ids(item.get("evidence_ids"), facts)
        # High ratings need multiple distinct behavioral facts; a mere claimed score is insufficient.
        facts_for = [facts[i] for i in ids]
        tags = set().union(*(set(f["tags"]) for f in facts_for)) if facts_for else set()
        if not facts_for:
            rating = None
        elif rating is not None:
            # Upper bounds are guardrails, not automated semantic grading.
            cap = 2
            if len(facts_for) >= 2 and "result" in tags and ("method" in tags or "application" in tags):
                cap = 3
            if (len(facts_for) >= 3 and "result" in tags and
                "validation" in tags and "revision" in tags and
                name in {"학업역량", "탐구역량", "성장가능성"}):
                cap = 4
            if name == "공동체역량":
                cap = 2
                if "collaboration" in tags and "leadership" in tags and "result" in tags:
                    cap = 3
                if cap == 3 and "revision" in tags and len(facts_for) >= 3:
                    cap = 4
            if name == "진로역량" and cap == 4 and "continuity" not in tags:
                cap = 3
            rating = min(rating, cap)
        evidence = (f"{facts_for[0]['grade']}학년 {facts_for[0]['source']}: {facts_for[0]['quote']}" if facts_for else
                    "근거를 확인하지 못했습니다. 평가를 보류합니다.")
        result.append({"name":name,"rating":rating,"score":rating*25 if rating is not None else None,
                       "status":"rated" if rating is not None else "insufficient_evidence",
                       "evidence":evidence,
                       "reason":str(item.get("reason") or "")[:220],
                       "evidence_source": {"grade": facts_for[0]["grade"], "category": facts_for[0]["source"],
                                            "quote":facts_for[0]["quote"], "verified":True} if facts_for else {"verified":False,"quote":""}})
    return result

# Need BOTH semantic evidence and several related actions for high marks.
# Values are requirements for levels 2, 3 and 4 respectively; no keyword triggers.
REQUIREMENTS = {
    "전공 주제 관련성": ({"career"}, {"method"}, {"concept","application"}),
    "활동의 구체성": ({"method"}, {"result"}, {"validation","revision"}),
    "활동 간 연계성": ({"continuity"}, {"method"}, {"revision"}),
    "전공 기초 교과 역량": ({"learning","concept"}, {"application"}, {"validation"}),
    "지식의 실제 적용": ({"application"}, {"result"}, {"validation","revision"}),
    "학습 태도와 개선": ({"reflection"}, {"revision"}, {"validation"}),
    "관심 주제의 반복·유지": ({"career"}, {"continuity"}, {"revision"}),
    "관심의 발전 과정": ({"career"}, {"continuity"}, {"revision","result"}),
    "자기주도적 확장": ({"planning"}, {"method"}, {"result","revision"}),
    "탐구 문제 설정": ({"question"}, {"method"}, {"validation"}),
    "탐구 방법 설계": ({"method"}, {"question"}, {"validation","revision"}),
    "결과 분석 및 검증": ({"result"}, {"comparison","validation"}, {"revision"}),
    "개선 및 후속 탐구": ({"revision"}, {"method"}, {"validation","result"}),
    "타 분야 지식 활용": ({"interdisciplinary"}, {"application"}, {"result"}),
    "융합적 문제해결": ({"interdisciplinary"}, {"question","method"}, {"result"}),
    "융합 결과의 타당성": ({"interdisciplinary"}, {"result"}, {"validation"}),
}


def _indicator_score(indicator, linked):
    if not linked:
        return None
    tags = set().union(*(set(x["tags"]) for x in linked))
    level2, level3, level4 = REQUIREMENTS[indicator]
    if not tags.intersection(level2):
        return None
    rating = 1
    if len(linked) >= 1 and (tags & level2) and ("method" in tags or "application" in tags):
        rating = 2
    if len(linked) >= 2 and (tags & level3) and (tags & level2):
        rating = 3
    if (len(linked) >= 3 and (tags & level4) and
        "result" in tags and ("validation" in tags or "revision" in tags)):
        rating = 4
    if indicator in {"활동 간 연계성", "관심 주제의 반복·유지", "관심의 발전 과정"}:
        if len({(f["grade"], f["source_index"]) for f in linked}) < 2:
            rating = min(rating, 2)
    return rating


def majors_from_ai(raw_links, facts, candidates):
    links = {x.get("major"):x for x in raw_links if isinstance(x, dict) and x.get("major") in candidates} if isinstance(raw_links,list) else {}
    ranked = []
    for major in candidates:
        item = links.get(major, {})
        ids = _valid_ids(item.get("evidence_ids"), facts)
        # semantic link must be explicit, otherwise no scored fit
        ranked.append((major, ids, str(item.get("reason") or "")[:200]))
    ranked.sort(key=lambda x:(-len(x[1]), candidates.index(x[0])))
    selected = ranked[:3]
    recommends, fits = [], []
    for major, ids, reason in selected:
        linked = [facts[i] for i in ids]
        categories = {cat:0.0 for cat in MAJOR_FIT_RUBRIC}
        details, nested = [], {cat:{} for cat in MAJOR_FIT_RUBRIC}
        coverage = 0
        for cat, indicator, weight in INDICATORS:
            # Do not allow unrelated activities to inflate all 16 scores.
            rating = _indicator_score(indicator, linked)
            nested[cat][indicator] = rating
            if rating is not None:
                coverage += weight
                categories[cat] += weight * rating / 4
            details.append({"category":cat,"indicator":indicator,"weight":weight,"rating":rating,
                            "status":"rated" if rating is not None else "insufficient_evidence",
                            "quote":linked[0]["quote"] if rating is not None else "",
                            "grade":linked[0]["grade"] if rating is not None else None,
                            "source":linked[0]["source"] if rating is not None else "",
                            "verified":rating is not None})
        partial = round(sum(categories.values()),2)
        explain = reason if ids else "입력 기록만으로 이 전공과의 연관성을 충분히 확인하지 못했습니다."
        recommends.append({"major":major,"reason":explain,
                           "learning_value":LEARNING_VALUE.get(major,"해당 전공의 교과 구조와 학습 내용을 탐색해 보세요."),
                           "exploration":"활동의 이유·수행 과정·검증 결과를 기록해 보세요."})
        fits.append({"major":major,"ratings":nested,"category_scores":{k:round(v,2) for k,v in categories.items()},
                     "total_score":partial if coverage == 100 else None,"partial_score":partial,
                     "coverage_weight":coverage,"score_status":"complete" if coverage==100 else "insufficient_evidence",
                     "indicator_details":details,"evidence":explain,
                     "improvement":"평가되지 않은 지표는 낮은 능력의 증거가 아니라 추가 검토가 필요한 항목입니다."})
    return recommends, fits


def build_analysis(raw, records, text, grade, sources, candidates):
    facts = clean_facts(raw.get("facts"), sources)
    if not facts:
        raise ValueError("AI가 확인 가능한 원문 근거를 반환하지 않았습니다.")
    comps = competencies_from_ai(raw.get("competencies"), facts)
    majors, fits = majors_from_ai(raw.get("major_links"), facts, candidates)
    if not any(c["rating"] is not None for c in comps):
        raise ValueError("AI가 근거에 연결된 역량 평가를 반환하지 않았습니다.")
    strong = [f"{c['name']}: {c['reason'] or c['evidence']}" for c in comps if c["rating"] is not None and c["rating"] >= 3][:3]
    weak = [f"{c['name']}: 구체적 수행 수준을 판단할 근거가 부족합니다." for c in comps if c["rating"] is None]
    growth = [{"grade":g,"summary":f"{g}학년 기록에서 확인된 활동 근거 {sum(f['grade']==g for f in facts)}개. 활동 간 성장 여부는 별도 검토가 필요합니다."} for g in range(1,grade+1) if any(f["grade"]==g for f in facts)]
    return {"rubric_version":VERSION,"analysis_mode":"semantic_ai_python_scoring",
            "competencies":comps,"recommended_majors":majors,"major_fit":fits,
            "strengths":strong or ["추가적인 근거 확인이 필요합니다."],
            "weaknesses":weak or ["루브릭은 학생부에 기록된 행동만 평가하므로 외부 평가와 비교가 필요합니다."],
            "growth":growth,"facts_verified":len(facts),
            "assessment_notice":"AI 의미 해석과 Python 규칙의 참고 평가입니다. 공식 입학 평가·합격 확률이 아니며, N/E 지표는 종합점수에서 제외합니다."}


def safe_fallback(records, text, grade, reason="ai_unavailable"):
    # No lexical scoring as authoritative! Return neutral N/E grades and useful source/candidate info.
    sources = prepare(records,text,grade)
    candidates = candidates_from_sources(sources)[:3]
    return {"rubric_version":VERSION,"analysis_mode":"evidence_pending",
            "competencies":[{"name":n,"rating":None,"score":None,"status":"insufficient_evidence",
                             "evidence":"AI 의미 검토를 완료하지 못해 평가를 보류했습니다."} for n in COMPETENCY_NAMES],
            "recommended_majors":[{"major":m,"reason":"추가 의미 검토가 필요한 탐색 후보입니다. 적합도 순위가 아닙니다."} for m in candidates],
            "major_fit":[{"major":m,"ratings":{},"category_scores":{},"total_score":None,"partial_score":0,
                         "coverage_weight":0,"score_status":"insufficient_evidence", "evidence":"AI 의미 검토 미완료", "improvement":"재분석 후 평가를 확인하세요."} for m in candidates],
            "strengths":["학생부 기록은 정상적으로 접수되었습니다."],
            "weaknesses":["AI 평가가 완료되지 않아 역량 점수는 제공하지 않습니다."],
            "growth":[{"grade":g,"summary":"입력 기록이 존재하지만 의미 평가는 보류되었습니다."} for g in range(1,grade+1) if any(s["grade"]==g for s in sources)],
            "assessment_notice":"AI 검토 실패: 실제 근거 확인 없이 키워드만으로 점수를 부여하지 않았습니다.",
            "fallback_reason":reason}
