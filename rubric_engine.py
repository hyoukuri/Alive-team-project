"""SEEDU:ON 2.1 — deterministic, evidence-grounded baseline.

This is NOT a validated assessment of actual student aptitude. It extracts
lexical indicators and produces conservative, explainable screening scores.
All excerpts are directly taken from the input. No network or LLM calls.
"""
from __future__ import annotations

import re
from collections import defaultdict
from rubric_v2 import MAJOR_FIT_RUBRIC, INDICATORS, COMPETENCY_NAMES

VERSION = "rubric-2.2-hybrid"

# Semantic interpretation is deliberately limited: each indicator needs an
# observed lexical cue, and higher levels require multiple distinct cues.
SIGNALS = {
    "interest": r"관심|희망|진로|탐색|알아보|조사|찾아보|관련 학과|교육과정|전공",
    "learning": r"학습|이해|개념|원리|정리|설명|풀이|해석|이론|공식|분석",
    "question": r"문제|질문|주제|목표|가설|원인|궁금|왜 |과제|연구|낮게|머무르|부족|어려움|차이",
    "method": r"수집|구현|제작|실험|조사|측정|분류|모델|설계|적용|계산|코딩|프로그래밍|사용|활용",
    "result": r"결과|산출|완성|도출|확인|성능|정확도|보고서|발표|예측|향상|감소|증가|성과|개선됨",
    "comparison": r"비교|전후|대조|차이|변화|보다 |대비|오차|%|퍼센트|평균|표준편차",
    "validation": r"검증|재실험|재검토|검토|타당|한계|오류|편향|혼동행렬|재현율|평가|점검",
    "revision": r"수정|보완|개선|조정|재구성|반영|바꾸|변경|다시 |재설계|추가 분석|후속",
    "collab": r"협업|협력|모둠|학급|구성원|팀|동아리|공동|역할|의견|공유|회의",
    "lead": r"조율|갈등|분담|재분배|통일|합의|지원|조정|이끌|제안|협의",
    "reflection": r"피드백|성찰|되돌아|부족|문제점|한계|개선점|자신의|스스로",
    "planning": r"계획|목표|후속|다음|확장|심화|예정|선정|실천",
    "application": r"적용|활용|구현|해결|제작|실험|분석|모델|프로젝트",
    "interdisciplinary": r"융합|연계|결합|통합|수학.*(과학|정보)|과학.*(수학|정보)|인문.*(기술|정보)|기술.*사회",
}
REGEX = {k: re.compile(v) for k, v in SIGNALS.items()}

MAJORS = {
    "인공지능학과": {"인공지능", "ai", "머신러닝", "딥러닝", "모델", "분류", "알고리즘", "데이터"},
    "컴퓨터공학과": {"프로그래밍", "코딩", "소프트웨어", "컴퓨터", "알고리즘", "파이썬", "python", "구현", "정보"},
    "데이터사이언스학과": {"데이터", "통계", "분석", "표본", "예측", "그래프", "모델", "정확도"},
    "수학과": {"수학", "함수", "미적분", "확률", "통계", "대수", "방정식", "수열"},
    "전자공학과": {"반도체", "전자", "회로", "센서", "전기", "로봇", "제어"},
    "기계공학과": {"기계", "물리", "역학", "로봇", "설계", "제작", "운동"},
    "화학과": {"화학", "물질", "반응", "분자", "촉매", "실험"},
    "생명과학과": {"생명", "생물", "유전", "세포", "생태", "바이오"},
    "환경공학과": {"환경", "기후", "재활용", "오염", "탄소", "에너지", "폐기물"},
    "경제학과": {"경제", "금융", "시장", "소비", "가격", "수요", "공급"},
    "경영학과": {"경영", "기업", "마케팅", "조직", "사업", "창업"},
    "심리학과": {"심리", "인지", "행동", "감정", "의사결정"},
    "교육학과": {"교육", "학습", "수업", "교수", "교사", "학생 지도"},
    "사회학과": {"사회", "공동체", "불평등", "정책", "문화", "사회문제"},
    "국어국문학과": {"국어", "문학", "독서", "언어", "소설", "비평"},
    "일어일문학과": {"일본어", "일본", "번역", "일본문학", "언어"},
}
LEARNING_VALUE = {
    "인공지능학과": "기계학습·모델 평가·AI 윤리를 체계적으로 학습",
    "컴퓨터공학과": "자료구조·알고리즘·소프트웨어 설계 학습",
    "데이터사이언스학과": "통계 분석·데이터 처리·예측 모델링 학습",
    "수학과": "수리적 증명·모델링·추론 심화 학습",
}


def _record_chunks(records, text):
    chunks = []
    if isinstance(records, dict) and any(str(v or "").strip() for v in records.values()):
        for grade in (1, 2, 3):
            raw = str(records.get(str(grade), records.get(grade, "")) or "")
            if raw.strip():
                chunks.extend(_split_activities(raw, grade))
    elif str(text or "").strip():
        blocks = re.split(r"(?=\[[123]학년\])", text)
        for block in blocks:
            found = re.match(r"\[([123])학년\]\s*", block)
            grade = int(found.group(1)) if found else 1
            body = block[found.end():] if found else block
            chunks.extend(_split_activities(body, grade))
    return chunks


def _split_activities(raw, grade):
    blocks = re.split(r"(?=\[(?:과목:|자율·자치활동:|동아리활동:|진로활동:|행동특성 및 종합의견:))", raw)
    found = []
    for block in blocks:
        if not block.strip():
            continue
        head = re.match(r"\[([^\]\n]+)\]\s*", block)
        label = head.group(1) if head else "기록"
        body = block[head.end():].strip() if head else block.strip()
        if not body:
            continue
        for sentence in re.split(r"(?<=[.!?。])\s+|(?<=함\.)\s*|(?<=됨\.)\s*", body):
            sentence = sentence.strip()
            if sentence:
                found.append({"grade": grade, "source": label, "quote": sentence[:650], "text": sentence})
    return found


def _signals(text):
    return {name for name, rx in REGEX.items() if rx.search(text)}


def _best(chunks, predicate):
    choices = [x for x in chunks if predicate(_signals(x["text"]))]
    return max(choices, key=lambda x: (len(_signals(x["text"])), len(x["text"])), default=None)


def _comp_rating(chunks, name):
    specs = {
        "학업역량": ("learning", "application", "result", "validation", "revision"),
        "진로역량": ("interest", "method", "result", "planning", "revision"),
        "탐구역량": ("question", "method", "result", "validation", "revision"),
        "공동체역량": ("collab", "method", "result", "lead", "revision"),
        "성장가능성": ("reflection", "planning", "method", "revision", "validation"),
    }
    a, b, c, d, e = specs[name]
    evidence = [x for x in chunks if a in _signals(x['text'])]
    if not evidence:
        return None, None
    # Related sentences in the same grade and activity may jointly establish
    # method/result/revision. Do not combine unrelated records or grades.
    clusters = defaultdict(set)
    for item in chunks:
        clusters[(item['grade'], item['source'])].update(_signals(item['text']))
    anchored = [clusters[(item['grade'], item['source'])] for item in evidence]
    combined = max(anchored, key=lambda group: len(group.intersection({a,b,c,d,e})))
    level = 1
    if b in combined:
        level = 2
    if b in combined and c in combined:
        level = 3
    if b in combined and c in combined and d in combined and e in combined:
        level = 4
    if name == "공동체역량":
        # Generic participation is not enough to certify leadership.
        if "lead" not in combined:
            level = min(level, 2)
        elif "revision" not in combined:
            level = min(level, 3)
    quote = _best(evidence, lambda s: a in s and (b in s or c in s)) or evidence[0]
    return level, quote


def _major_relevance(chunks, major):
    terms = MAJORS[major]
    matches = []
    unique = set()
    for x in chunks:
        words = {term for term in terms if term in x['text'].casefold()}
        if words:
            matches.append(x)
            unique.update(words)
    return matches, len(unique)


def _indicator_rating(label, chunks, matches):
    # Evaluate each domain indicator using independently visible lexical cues.
    selected = matches if label in {"전공 주제 관련성", "전공 기초 교과 역량", "관심 주제의 반복·유지", "관심의 발전 과정"} else chunks
    if not selected:
        return None, None
    sigs = set().union(*(_signals(x['text']) for x in selected))
    mapping = {
        "전공 주제 관련성": ("interest", "method", "result", "validation"),
        "활동의 구체성": ("method", "result", "comparison", "revision"),
        "활동 간 연계성": ("interest", "planning", "method", "revision"),
        "전공 기초 교과 역량": ("learning", "application", "result", "validation"),
        "지식의 실제 적용": ("application", "method", "result", "validation"),
        "학습 태도와 개선": ("learning", "reflection", "revision", "validation"),
        "관심 주제의 반복·유지": ("interest", "method", "planning", "revision"),
        "관심의 발전 과정": ("interest", "method", "result", "revision"),
        "자기주도적 확장": ("planning", "method", "result", "revision"),
        "탐구 문제 설정": ("question", "method", "result", "validation"),
        "탐구 방법 설계": ("method", "question", "result", "revision"),
        "결과 분석 및 검증": ("result", "comparison", "validation", "revision"),
        "개선 및 후속 탐구": ("revision", "result", "validation", "planning"),
        "타 분야 지식 활용": ("interdisciplinary", "application", "method", "result"),
        "융합적 문제해결": ("interdisciplinary", "question", "method", "result"),
        "융합 결과의 타당성": ("interdisciplinary", "result", "comparison", "validation"),
    }
    required = mapping[label]
    if required[0] not in sigs:
        return None, None
    count = sum(k in sigs for k in required)
    rating = min(4, count)
    # Continuity needs different activities / time markers, not just two keywords.
    if label in {"활동 간 연계성", "관심 주제의 반복·유지", "관심의 발전 과정"}:
        if len({(x['grade'],x['source']) for x in selected}) < 2:
            rating = min(2, rating)
    quote = _best(selected, lambda s: required[0] in s) or selected[0]
    return rating, quote


def analyze_records(records, text, grade):
    chunks = _record_chunks(records, text)
    if not chunks:
        raise ValueError("분석할 학생부 기록이 없습니다.")
    competencies = []
    for name in COMPETENCY_NAMES:
        rating, entry = _comp_rating(chunks, name)
        competencies.append({
            "name": name, "rating": rating, "score": None if rating is None else rating * 25,
            "status": "insufficient_evidence" if rating is None else "rated",
            "evidence": (f"{entry['grade']}학년 {entry['source']}: {entry['quote']}" if entry else "해당 역량은 입력 기록만으로 판단하기 어렵습니다."),
            "evidence_source": ({"grade":entry['grade'],"category":entry['source'],"quote":entry['quote'],"verified":True} if entry else {"quote":"","verified":False}),
        })
    ranked = []
    for major in MAJORS:
        matches, unique = _major_relevance(chunks, major)
        if matches:
            ranked.append((major, unique, len(matches), matches))
    ranked.sort(key=lambda e: (-e[1], -e[2], e[0]))
    if not ranked:
        # No domain evidence -> do not fabricate confident field-specific ranking.
        ranked = [(major, 0, 0, []) for major in ["컴퓨터공학과", "데이터사이언스학과", "사회학과"]]
    while len(ranked) < 3:
        fallback = next(m for m in MAJORS if m not in {x[0] for x in ranked})
        ranked.append((fallback, 0, 0, []))
    selected = ranked[:3]
    recommendations, fits = [], []
    for major, unique, count, matches in selected:
        categories = {cat:0.0 for cat in MAJOR_FIT_RUBRIC}
        nested = {cat:{} for cat in MAJOR_FIT_RUBRIC}
        details = []
        coverage = 0
        for cat, label, weight in INDICATORS:
            rating, entry = _indicator_rating(label, chunks, matches)
            nested[cat][label] = rating
            if rating is not None:
                categories[cat] += rating / 4 * weight
                coverage += weight
            details.append({"category":cat,"indicator":label,"weight":weight,"rating":rating,
                            "status":"rated" if rating is not None else "insufficient_evidence",
                            "quote":entry['quote'] if entry else "",
                            "grade":entry['grade'] if entry else None,
                            "source":entry['source'] if entry else "",
                            "verified":bool(entry)})
        raw_score = round(sum(categories.values()), 2)
        reason = (f"입력 기록에서 {unique}개 관련 용어와 {count}개 근거 문장이 확인되었습니다." if matches
                  else "관련 근거가 충분하지 않습니다. 이 학과는 탐색 예시이며 적합도 평가 대상이 아닙니다.")
        recommendations.append({"major":major,"reason":reason,"related_term_count":unique,
            "learning_value":LEARNING_VALUE.get(major, "전공 기초·심화 과목과 실무적 탐색 기회를 학습"),
            "exploration": "관심 분야 관련 활동을 비교하고 수행·검증 과정을 기록해 보세요."})
        fits.append({"major":major,"ratings":nested,"category_scores":{k:round(v,2) for k,v in categories.items()},
                     "total_score": raw_score if coverage==100 else None,"partial_score":raw_score,
                     "coverage_weight":coverage,
                     "score_status":"complete" if coverage==100 else "insufficient_evidence",
                     "indicator_details":details,"evidence":reason,
                     "improvement":"근거가 없는 지표에 대한 추가 탐구·수행 기록이 필요합니다."})
    growth = [{"grade":g,"summary":f"{g}학년에서 {sum(x['grade']==g for x in chunks)}개 근거 문장을 확인했습니다. 정량적 성장 판단은 별도 검토가 필요합니다."}
              for g in range(1,grade+1) if any(x['grade']==g for x in chunks)]
    strong = [f"{c['name']}: {c['evidence']}" for c in competencies if c['rating'] is not None and c['rating']>=3][:3]
    weak = [f"{c['name']}: 입력 자료만으로 충분한 근거를 확인하지 못했습니다." for c in competencies if c['rating'] is None]
    if not weak:
        weak = ["규칙 기반 분석이므로 문맥과 교사 평가를 통해 확인이 필요합니다."]
    return {"rubric_version":VERSION,"analysis_mode":"rule_based","competencies":competencies,
            "recommended_majors":recommendations,"major_fit":fits,
            "strengths":strong or ["특정 역량을 강점으로 단정할 만큼의 근거가 아직 부족합니다."],
            "weaknesses":weak,"growth":growth,
            "assessment_notice":"AI를 호출하지 않은 어휘·행동 규칙 기반 참고 평가입니다. 실제 역량·대학 합격 가능성을 측정하지 않으며, 미평가 지표는 점수에 포함하지 않습니다."}


def make_roadmap(major, grade, records, text):
    chunks = _record_chunks(records, text)
    related = [x for x in chunks if any(k in x['text'].casefold() for k in MAJORS.get(major, set()))]
    basis = related[0]['quote'][:75] if related else "현재 학생부에 명시된 활동 근거가 충분하지 않음"
    subject_map = {
        "인공지능학과": ["수학", "정보", "인공지능 기초"],
        "컴퓨터공학과": ["수학", "정보", "인공지능 기초"],
        "데이터사이언스학과": ["확률과 통계", "정보", "수학"],
        "수학과": ["대수", "미적분", "확률과 통계"],
    }
    subjects = subject_map.get(major, ["관련 기초 교과", "탐구 과목", "융합 선택 과목"])
    acts = [
        ("문제와 기준 정하기", "전공 관련 질문을 정하고 평가 기준·비교군을 명시합니다."),
        ("소규모 탐구 실행", "자료 수집, 탐구 설계, 실행 결과를 일지로 기록합니다."),
        ("검증과 개선", "오차·한계를 검토하고 방법을 수정하여 결과를 다시 비교합니다."),
    ]
    return {"rubric_version":VERSION,"analysis_mode":"rule_based","major":major,
            "recommended_subjects":[{"subject":s,"reason":f"{major}의 기초 학습과 연결됩니다. 학교 개설 여부를 확인하세요."} for s in subjects],
            "research_activities":[{"title":title,"description":desc,"steps":["목표 설정", "실행 및 기록", "결과 점검", "성찰과 개선"],"expected_result":"활동 일지와 검증 가능한 탐구 보고서"} for title,desc in acts],
            "grade_plan":[{"grade":g,"goal":("현재 수행 근거를 정리" if g==grade else "전공 탐색 심화"),
                           "actions":["관심과 문제를 구체적으로 설정", "활동을 실행하고 결과 기록", "피드백을 반영하여 후속 탐구 계획"]}
                           for g in range(grade,4)],
            "advice":f"현재 입력 근거: {basis}. 목표→실행→점검→성찰→조정 순서로 기록하세요. 이 로드맵은 템플릿 기반 제안이며 이미 수행한 활동이 아닙니다."}
