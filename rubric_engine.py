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
# Additional exploration fields; signals are subject-domain hints, not aptitude scores.
MAJORS.update({
    '소프트웨어학과': {'프로그램 개발', '앱 개발', '웹 개발', '소프트웨어 개발', '소프트웨어 설계', '소프트웨어공학'},
    '정보보안학과': {'암호화', '네트워크 보안', '해킹 방어', '취약점', '정보보안', '사이버보안'},
    '통계학과': {'통계적 추론', '통계학', '표본분포', '확률분포', '회귀분석', '가설검정'},
    '물리학과': {'양자역학', '입자물리', '상대성이론', '전자기학', '파동', '광학'},
    '천문우주학과': {'행성', '은하', '항성', '우주', '천문 관측', '천체'},
    '지구과학과': {'암석', '지질', '판 구조론', '대기 순환', '지진', '해양 순환'},
    '화학공학과': {'분리 공정', '화학공정', '촉매 반응', '고분자', '공정 설계', '반응기'},
    '신소재공학과': {'나노소재', '금속 재료', '복합재료', '소재 물성', '결정구조', '신소재'},
    '반도체공학과': {'반도체 공정', '집적회로', '웨이퍼', '트랜지스터', '리소그래피', '반도체 소자'},
    '전기공학과': {'발전기', '전력망', '전기 에너지', '모터 제어', '전력전자', '전력계통'},
    '로봇공학과': {'로봇 제어', '로봇공학', '로봇팔', '자율주행 로봇', '로봇 센서', '로봇 구동'},
    '자동차공학과': {'차량 설계', '배터리 관리', '자동차', '전기차', '차량 동역학', '자율주행'},
    '항공우주공학과': {'항공역학', '위성 자세 제어', '비행체', '로켓 추진', '우주발사체', '항공우주'},
    '건축학과': {'건축설계', '건축 공간', '도시 건축', '건축 디자인', '건축 모형', '건축물'},
    '건축공학과': {'콘크리트 구조', '건축 환경', '구조 안전', '내진 설계', '건축 시공', '건축구조'},
    '토목공학과': {'토목', '수자원 관리', '교량', '도로 설계', '구조물 안전', '지반'},
    '도시공학과': {'교통 계획', '도시재생', '도시계획', '스마트시티', '도시 공간', '도시 인프라'},
    '산업공학과': {'생산관리', '운영연구', '산업공학', '품질관리', '작업 동선', '공정 최적화'},
    '에너지공학과': {'에너지 저장', '신재생에너지', '수소에너지', '풍력발전', '에너지 변환', '태양광'},
    '생명공학과': {'생명공학', '유전자 재조합', '단백질 공학', '세포 배양', '유전자 편집', '바이오 공정'},
    '의생명공학과': {'바이오센서', '생체신호', '의료기기', '의료영상', '의공학', '생체재료'},
    '식품공학과': {'발효 공정', '식품 가공', '식품 품질', '식품 안전', '식품공학', '식품 미생물'},
    '간호학과': {'환자 안전', '건강 사정', '간호사', '간호', '간호 중재', '환자 간호'},
    '의예과': {'질병 치료', '의학', '병리', '임상', '의료 윤리', '진단'},
    '약학과': {'의약품', '약물 상호작용', '약동학', '약학', '약물', '약물 전달'},
    '치의예과': {'치아 교정', '치주', '구강 건강', '구강 질환', '치과', '치아'},
    '수의예과': {'반려동물 건강', '동물 질병', '동물 진료', '동물 의학', '수의학', '가축 질병'},
    '물리치료학과': {'근골격계 재활', '보행 분석', '물리치료', '운동치료', '관절 가동범위', '재활 운동'},
    '작업치료학과': {'작업치료', '재활치료', '작업 수행', '일상생활동작', '감각통합', '인지재활'},
    '보건행정학과': {'건강보험', '의료기관 운영', '의료 행정', '의료 정보 관리', '보건행정', '보건의료 정책'},
    '공중보건학과': {'역학조사', '공중보건', '감염병 예방', '지역사회 건강', '질병 감시', '건강 불평등'},
    '농생명과학과': {'농업 생산', '작물 재배', '식물 육종', '토양 관리', '농업 생명', '식물 생리'},
    '스마트팜학과': {'정밀농업', '생육 환경', '식물 생육 센서', '농업 자동화', '스마트팜', '양액 관리'},
    '산림자원학과': {'산림 복원', '임업', '산림 탄소', '숲 생태', '산림', '산불 예방'},
    '해양학과': {'해수', '해류', '해양생태', '바다 생태', '해양환경', '해양 관측'},
    '해양공학과': {'수중로봇', '해양 에너지', '해양구조물', '해양 플랜트', '해양 설비', '해양공학'},
    '국제통상학과': {'국제무역', '무역협정', '국제 물류', '국제통상', '관세', '수출입'},
    '회계학과': {'원가회계', '회계 기준', '감사보고서', '재무회계', '회계', '재무제표'},
    '금융학과': {'금리', '채권', '자산운용', '금융상품', '금융시장', '투자 포트폴리오'},
    '행정학과': {'행정학', '지방자치', '행정 서비스', '행정 개혁', '공공행정', '공공조직'},
    '정치외교학과': {'국제관계', '선거 제도', '외교', '국제 분쟁', '안보 정책', '정치 제도'},
    '법학과': {'헌법', '법적 쟁점', '판례', '법률', '민법', '법제도'},
    '사회복지학과': {'지역사회 복지', '복지 정책', '복지 서비스', '사례 관리', '사회복지', '취약계층 지원'},
    '미디어커뮤니케이션학과': {'대중매체', '뉴스 보도', '미디어', '언론', '광고 매체', '미디어 리터러시'},
    '광고홍보학과': {'광고 기획', '공익광고', '소비자 반응', '광고 캠페인', '브랜드 홍보', '홍보 전략'},
    '지리학과': {'GIS', '지리적 분포', '지리정보', '공간분석', '지형', '인문지리'},
    '역사학과': {'역사 해석', '역사학', '사료 분석', '역사적 맥락', '역사 연구', '시대사'},
    '철학과': {'논리학', '철학적 논증', '윤리학', '철학 사상', '존재론', '인식론'},
    '영어영문학과': {'영어 소설', '영문학', '영어 번역', '영어학', '영어권 문화', '영어 문학'},
    '중어중문학과': {'중국어', '중국 문화', '한중 번역', '중국어학', '중국문학', '중국 고전'},
    '언어학과': {'언어학', '통사론', '음운론', '의미론', '형태론', '언어 분석'},
    '초등교육과': {'초등교육', '초등 학습', '초등 교과', '초등 교사', '초등학생 지도', '초등 수업'},
    '특수교육과': {'특수교사', '발달장애 교육', '특수교육', '장애학생 지원', '개별화교육', '통합교육'},
    '유아교육과': {'놀이중심 교육', '유치원 교육', '유아 교사', '유아교육', '유아 발달', '아동 놀이'},
    '체육교육과': {'운동 지도', '학교 체육', '체육 교수법', '체육 교사', '체육교육', '체육 수업'},
    '스포츠과학과': {'스포츠과학', '운동역학', '스포츠 퍼포먼스', '체력 측정', '스포츠 데이터', '운동생리학'},
    '디자인학과': {'제품디자인', '편집 디자인', '디자인 프로세스', '시각디자인', '사용자 경험 디자인', '디자인 시안'},
    '산업디자인학과': {'사용자 조사', '제품 사용성', '프로토타입 디자인', '제품 디자인', '제품 형태', '산업디자인'},
    '시각디자인학과': {'브랜드 아이덴티티', '시각디자인', '시각정보', '타이포그래피', '그래픽디자인', '포스터 디자인'},
    '영상학과': {'영상 제작', '영상 콘텐츠', '다큐멘터리 제작', '영상 편집', '영상 연출', '촬영 기법'},
    '애니메이션학과': {'애니메이션', '프레임 애니메이션', '애니메이팅', '모션그래픽', '스토리보드', '캐릭터 디자인'},
    '음악학과': {'화성학', '음악 작품', '음악사', '음악 이론', '연주 분석', '작곡'},
    '국악과': {'가야금', '장단', '전통음악', '판소리', '국악기', '국악'},
    '무용학과': {'무용', '무용 공연', '현대무용', '안무', '신체 표현', '발레'},
    '관광학과': {'관광 자원', '여행 상품', '관광 정책', '관광 산업', '관광객', '관광'},
    '호텔경영학과': {'호텔 운영', '호텔 서비스', '호텔 산업', '객실 관리', '호텔 마케팅', '호텔경영'},
    '조리학과': {'식재료 가공', '레시피 개발', '조리과학', '식품 조리', '조리', '급식 조리'},
})

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
    """학과+입력된 학습 주제에 맞는 단계형 탐구 3개.

    기록에 없는 활동을 수행했다고 주장하지 않는다. 정보 부족은
    평가 점수가 아닌 향후 탐색 계획으로 돌려준다.
    """
    major = str(major or "").strip()
    if not major:
        raise ValueError("희망 학과를 선택해 주세요.")
    grade = max(1, min(2, int(grade or 1)))
    chunks = _record_chunks(records, text)
    keys = MAJORS.get(major, set())
    related = [x for x in chunks if any(k in x['text'].casefold() for k in keys)]
    # 가장 최근 자료보다 탐구 과정(실험·비교·측정 등)이 기술된 실제 기록을 우선합니다.
    actions = ("탐구", "측정", "분석", "비교", "실험", "조사", "설계", "토론", "제작", "검증")
    basis_entry = next((x for x in related if any(k in x['text'] for k in actions)), None)
    if basis_entry is None:
        basis_entry = next((x for x in chunks if any(k in x['text'] for k in actions)), None)
    basis_source = basis_entry['source'] if basis_entry else None
    # 분야별 내용은 학과명으로 분류하되 모든 활동은 '앞으로 할 제안'으로 명시합니다.
    fields = [
        (("인공지능", "컴퓨터", "소프트웨어", "데이터", "정보보안", "통계"),
         ["대수", "확률과 통계", "정보"], "자료의 패턴과 예측", "데이터 표본 구성 및 시각화", "간단한 예측·분류 방법 비교", "오차와 편향 검토"),
        (("환경", "지구", "천문", "해양", "산림", "농생명", "스마트팜"),
         ["지구과학", "생명과학", "확률과 통계"], "환경과 관측 자료의 변화", "관측·공개자료 수집", "기간·조건별 추세 비교", "예외 사례와 변수 검증"),
        (("수학", "통계", "물리"),
         ["대수", "미적분", "확률과 통계"], "수학적 모델과 실제 자료의 관계", "문제 조건과 데이터 정리", "대안 모델·풀이 방법 비교", "가정과 오차 검토"),
        (("기계", "로봇", "반도체", "전기", "전자", "자동차", "항공", "건축", "토목", "에너지", "공학"),
         ["대수", "미적분", "물리학"], "구조·물리량의 변화", "측정 기준과 작동 원리 조사", "모형·계산 결과 비교", "조건 변화에 따른 설계 개선"),
        (("화학", "생명", "의학", "의예", "약학", "치의", "수의", "간호", "보건", "식품"),
         ["화학", "생명과학", "확률과 통계"], "생명·물질과 실험 변수", "안전한 문헌 및 공개자료 조사", "변수에 따른 결과 비교", "오차와 윤리적 한계 검토"),
        (("경제", "경영", "무역", "통상", "회계", "금융", "정치", "행정", "법학", "사회", "복지"),
         ["경제", "사회와 문화", "확률과 통계"], "사회 현상의 원인과 영향", "공개 통계·사례 비교", "이해관계자 관점의 차이 분석", "해결책의 비용·형평성 검토"),
        (("국어", "문학", "언어", "역사", "철학", "교육", "미디어", "홍보"),
         ["독서와 작문", "사회와 문화", "세계사"], "텍스트와 사회적 맥락", "자료·관점별 텍스트 비교", "근거에 따른 해석 구성", "반론과 해석 한계 검토"),
        (("디자인", "영상", "애니", "음악", "미술", "체육", "스포츠", "무용"),
         ["예술 관련 선택과목", "진로 관련 실습", "융합 선택과목"], "표현 방법과 수용자 경험", "작품 및 사례 비교", "콘셉트 시안·동작 구성", "피드백을 반영한 개선"),
        (("지구", "천문", "해양", "산림", "농생명", "스마트팜", "환경"),
         ["지구과학", "생명과학", "확률과 통계"], "환경과 관측 자료의 변화", "관측·공개자료 수집", "기간·조건별 추세 비교", "예외 사례와 변수 검증"),
    ]
    subjects = ["관련 기초 교과", "탐구 과목", "융합 선택과목"]
    topic, step1, step2, step3 = ("전공 관련 문제", "자료 수집", "비교 분석", "결과 검증")
    for keys2, s, t, p1, p2, p3 in fields:
        if any(k in major for k in keys2):
            subjects, topic, step1, step2, step3 = s, t, p1, p2, p3
            break
    context = f"{basis_source}의 실제 기록" if basis_source else "기존 기록에서 수행 근거가 명확하지 않은 상태"
    acts = [
        {"title":f"{major} 연계 질문 설계", "description":f"{context}을 출발점으로 {topic}에 관한 구체적인 질문을 만듭니다. {step1}에 앞서 평가 기준을 정해 보세요.",
         "steps":["기존 기록의 주제와 아직 확인되지 않은 점 구분", "탐구 질문·비교 기준 작성", "출처와 자료 수집 계획 수립"],"expected_result":"탐구 질문지·자료 목록"},
        {"title":f"{topic} 탐구 실행", "description":f"{major} 관련 방법을 적용하여 {step2}을 수행하고 결과를 표·그래프·논증으로 기록하도록 제안합니다.",
         "steps":["공개자료 또는 안전한 측정 자료 확보", step2, "과정·한계·중간 결과 기록"],"expected_result":"탐구 보고서 초안·결과 표"},
        {"title":f"{major} 탐구 검증과 심화", "description":f"앞 단계 결과에 대해 {step3}을 진행하고, 다른 조건에서도 같은 결론이 성립하는지 점검합니다.",
         "steps":["오류·반례·자료의 편향 확인", step3, "피드백을 반영한 후속 질문 도출"],"expected_result":"보완 보고서·후속 탐구 계획"},
    ]
    return {
        "rubric_version":VERSION,"analysis_mode":"rule_based_planning","major":major,
        "evidence_status":"related" if related else "not_confirmed",
        "recommended_subjects":[{"subject":s,"reason":f"{major} 탐색과 관련된 과목 예시입니다. 학교 개설 여부를 확인하세요."} for s in subjects],
        "research_activities":acts,
        "grade_plan":[{"grade":g,"goal":("현재 기록에서 확인된 탐구 주제 정리" if g==grade else "질문·근거를 확장한 심화 탐구"),
                       "actions":["탐구 질문 수립", "활동·결과 기록", "검증·후속 활동 설계"]} for g in range(grade,4)],
        "advice":f"연계 출발점: {context}. 학생부 근거 미확인은 능력 부족을 뜻하지 않습니다. 위 탐구는 수행 사실이 아닌 앞으로의 제안입니다."
    }
