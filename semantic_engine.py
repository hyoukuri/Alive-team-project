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

VERSION = "rubric-3.2-behavior-anchors"
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
            # Upper bounds are guardrails. Several tags spread across unrelated
            # activities must not be merged into a fabricated causal process.
            same_source = defaultdict(list)
            for fact in facts_for:
                same_source[(fact['grade'],fact['source_index'])].append(fact)
            cap=1
            for activity in same_source.values():
                t=set().union(*(set(f['tags']) for f in activity))
                n=len(activity)
                activity_cap=1
                if name == '학업역량':
                    if t & {'learning','concept'} and t & {'application','method'}:
                        activity_cap=2
                    if activity_cap>=2 and 'result' in t and n>=2:
                        activity_cap=3
                    if activity_cap>=3 and {'validation','revision'} <= t and n>=3:
                        activity_cap=4
                elif name == '진로역량':
                    if 'career' in t and t & {'planning','comparison','method','application'}:
                        activity_cap=2
                    if activity_cap>=2 and 'continuity' in t and t & {'method','application'} and n>=2:
                        activity_cap=3
                    if activity_cap>=3 and {'revision','result'} <= t and n>=3:
                        activity_cap=4
                elif name == '탐구역량':
                    if 'method' in t and t & {'question','comparison','result'}:
                        activity_cap=2
                    if activity_cap>=2 and 'result' in t and t & {'comparison','validation','question'} and n>=2:
                        activity_cap=3
                    if activity_cap>=3 and {'validation','revision'} <= t and n>=3:
                        activity_cap=4
                elif name == '공동체역량':
                    if 'collaboration' in t and t & {'method','result','leadership'}:
                        activity_cap=2
                    if activity_cap>=2 and {'leadership','result'} <= t and n>=2:
                        activity_cap=3
                    if activity_cap>=3 and {'revision','validation'} <= t and n>=3:
                        activity_cap=4
                elif name == '성장가능성':
                    if 'reflection' in t and t & {'planning','revision'}:
                        activity_cap=2
                    if activity_cap>=2 and {'revision','result'} <= t and n>=2:
                        activity_cap=3
                    if activity_cap>=3 and {'validation','continuity'} <= t and n>=3:
                        activity_cap=4
                cap=max(cap,activity_cap)
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
    """Conservative per-activity evidence for the existing 16 indicators.

    A tag from an unrelated source must not complete another source's method,
    result or follow-up. No missing indicator becomes a zero.
    """
    if not linked:
        return None
    level2, level3, level4 = REQUIREMENTS[indicator]
    by_source = defaultdict(list)
    for fact in linked:
        by_source[(fact['grade'], fact['source_index'])].append(fact)
    ratings=[]
    for actions in by_source.values():
        tags=set().union(*(set(f['tags']) for f in actions))
        if not tags & level2:
            continue
        rating=1
        if tags & {'method','application','collaboration','revision','result'}:
            rating=2
        if (rating>=2 and tags & level3 and 'result' in tags
                and tags & {'method','application','comparison','question'}):
            rating=3
        if (rating>=3 and len(actions)>=3 and tags & level4
                and 'validation' in tags and 'revision' in tags):
            rating=4
        ratings.append(rating)
    if not ratings:
        return None
    best=max(ratings)
    # Activity linkage and sustained interest cannot be evidenced by one source.
    if indicator in {'활동 간 연계성','관심 주제의 반복·유지','관심의 발전 과정'}:
        if len(by_source)<2:
            best=min(best,2)
        # A repeated keyword is not demonstrated development.
        if not any('continuity' in f['tags'] for f in linked):
            best=min(best,1)
    return best

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


# --- Evidence-grounded strengths and improvements (presentation only). ---
# This section must not modify ratings or invent student actions.
STRENGTH_INTERPRETATION = {
    "학업역량": "교과 학습과 과제 수행에서 확인된 활동입니다.",
    "진로역량": "관심 분야를 탐색하거나 전공과 연결한 활동입니다.",
    "탐구역량": "문제를 조사하고 탐구 과정을 수행한 근거입니다.",
    "공동체역량": "공동 활동에서 참여하거나 맡은 역할을 수행한 근거입니다.",
    "성장가능성": "학습을 점검하거나 조정한 행동에 관한 근거입니다.",
}
IMPROVEMENT_NEXT = {
    "학업역량": "개념을 적용한 결과와 오류를 확인하고, 수정 후 결과를 다시 비교한 기록을 보완해 보세요.",
    "진로역량": "탐색한 관심 분야를 후속 학습·체험으로 연결하고, 실행 결과를 남겨 보세요.",
    "탐구역량": "문제 설정부터 방법·결과·재검증까지 이어지는 과정을 구체적으로 기록해 보세요.",
    "공동체역량": "본인의 역할뿐 아니라 공동 문제 해결과 협력 과정에서의 구체적인 기여를 기록해 보세요.",
    "성장가능성": "피드백을 반영해 무엇을 바꾸었고, 변화의 효과를 어떻게 확인했는지 기록해 보세요.",
}


def _visible_evidence(item):
    """Only verified input quotes are eligible; no invented evidence."""
    src = item.get("evidence_source") or {}
    if isinstance(src, dict) and src.get("verified") is True:
        quote = str(src.get("quote") or "").strip()
        if quote:
            return f"{src.get('grade', '?')}학년 {src.get('category', '학생부')} — \"{quote[:180]}{'…' if len(quote)>180 else ''}\""
    return None


def strengths_and_weaknesses(competencies):
    """Explain confirmed scores without changing the scoring rubric.

    A high relative rank is not claimed to be excellent. N/E is not treated as 0.
    """
    evaluated = [(index, item) for index, item in enumerate(competencies)
                 if type(item.get('rating')) is int and _visible_evidence(item)]
    pending = [item for item in competencies if item.get('rating') is None]
    best = sorted(evaluated, key=lambda pair: (-pair[1]['rating'], pair[0]))[:2]
    # Low-scoring dimensions first. Even a 3/4 score may have an actionable next step.
    needs = sorted(evaluated, key=lambda pair: (pair[1]['rating'], pair[0]))[:2]

    strengths = []
    for _, item in best:
        rating, name = item['rating'], item['name']
        level = ("상대적으로 높은 평가" if rating >= 3 else
                 "기록에서 확인된 수행" if rating == 2 else "기초적인 활동 확인")
        strengths.append(f"{name} ({rating}/4, {level}): {_visible_evidence(item)}. "
                         f"{STRENGTH_INTERPRETATION.get(name, '평가 근거가 확인된 활동입니다.')}")

    weaknesses = []
    for _, item in needs:
        name, rating = item['name'], item['rating']
        prefix = ("현재 기록에서는 기본적인 참여·수행만 확인됩니다." if rating <= 1 else
                  "구체적인 수행은 확인되지만 심화·재검증까지 충분히 확인된 것은 아닙니다." if rating == 2 else
                  "상대적으로 높은 평가를 받았지만 후속 심화 여부는 별도 확인이 필요합니다." if rating == 3 else
                  "현재 평가에서 높은 수준의 근거가 확인되었습니다. 다음 단계의 지속성은 별도로 확인할 수 있습니다.")
        weaknesses.append(f"{name} ({rating}/4): {prefix} "
                          f"확인된 근거: {_visible_evidence(item)}. "
                          f"다음 단계: {IMPROVEMENT_NEXT.get(name, '후속 활동의 과정과 결과를 기록해 보세요.')}")

    # N/E is a request for evidence, not a statement that the student lacks ability.
    for item in pending[:max(0, 3-len(weaknesses))]:
        name = item['name']
        weaknesses.append(f"{name} (N/E): 현재 입력된 자료에서 채점에 필요한 근거를 연결하지 못했습니다. "
                          f"{IMPROVEMENT_NEXT.get(name, '관련 활동 기록을 추가로 확인해 보세요.')}")

    if not strengths:
        strengths = ["검증된 역량 근거가 없어 개인별 강점을 판단할 수 없습니다. 입력 자료와 AI 근거 연결을 확인해 주세요."]
    if not weaknesses:
        weaknesses = ["이번 입력에서 확인된 수행을 토대로 다음 학년의 후속 활동과 검증 결과를 기록해 보세요."]
    return strengths, weaknesses


def build_analysis(raw, records, text, grade, sources, candidates):
    facts = clean_facts(raw.get("facts"), sources)
    if not facts:
        raise ValueError("AI가 확인 가능한 원문 근거를 반환하지 않았습니다.")
    comps = competencies_from_ai(raw.get("competencies"), facts)
    majors, fits = majors_from_ai(raw.get("major_links"), facts, candidates)
    if not any(c["rating"] is not None for c in comps):
        raise ValueError("AI가 근거에 연결된 역량 평가를 반환하지 않았습니다.")
    strong, weak = strengths_and_weaknesses(comps)
    growth = [{"grade":g,"summary":f"{g}학년 기록에서 확인된 활동 근거 {sum(f['grade']==g for f in facts)}개. 활동 간 성장 여부는 별도 검토가 필요합니다."} for g in range(1,grade+1) if any(f["grade"]==g for f in facts)]
    return {"rubric_version":VERSION,"analysis_mode":"semantic_ai_python_scoring",
            "competencies":comps,"recommended_majors":majors,"major_fit":fits,
            "strengths":strong,
            "weaknesses":weak,
            "growth":growth,"facts_verified":len(facts),
            "assessment_notice":"AI 의미 해석과 Python 규칙의 참고 평가입니다. 공식 입학 평가·합격 확률이 아니며, N/E 지표는 종합점수에서 제외합니다."}


def safe_fallback(records, text, grade, reason="ai_unavailable"):
    # System outage is not an evaluation of student evidence. Never label outage as N/E.
    sources = prepare(records,text,grade)
    candidates = candidates_from_sources(sources)[:3]
    return {"rubric_version":VERSION,"analysis_mode":"evidence_pending",
            "competencies":[{"name":n,"rating":None,"score":None,"status":"analysis_unavailable",
                             "evidence":"분석 서비스 오류로 평가가 실행되지 않았습니다. 학생부 근거 부족 판정이 아닙니다."} for n in COMPETENCY_NAMES],
            "recommended_majors":[{"major":m,"reason":"추가 의미 검토가 필요한 탐색 후보입니다. 적합도 순위가 아닙니다."} for m in candidates],
            "major_fit":[{"major":m,"ratings":{},"category_scores":{},"total_score":None,"partial_score":0,
                         "coverage_weight":0,"score_status":"insufficient_evidence", "evidence":"AI 의미 검토 미완료", "improvement":"재분석 후 평가를 확인하세요."} for m in candidates],
            "strengths":["학생부 기록은 정상적으로 접수되었습니다."],
            "weaknesses":["AI 평가가 완료되지 않아 역량 점수는 제공하지 않습니다."],
            "growth":[{"grade":g,"summary":"입력 기록은 접수되었지만 AI 서비스 오류로 평가하지 못했습니다."} for g in range(1,grade+1) if any(s["grade"]==g for s in sources)],
            "assessment_notice":"학생부 평가 미실행: AI 서비스 오류가 발생했습니다. 근거 부족(N/E) 판정이 아닙니다.",
            "fallback_reason":reason}
