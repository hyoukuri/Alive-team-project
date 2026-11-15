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
        # A pasted record can contain an explicit non-subject category inside
        # a subject-labelled block. Never attribute such content to that subject.
        embedded = re.match(
            r"^(행동특성 및 종합의견|자율[·ㆍ]자치활동|동아리활동|진로활동)\s*[:：]\s*",
            body,
        )
        if embedded and (label.startswith('과목:') or label == '기록'):
            label = embedded.group(1)
            body = body[embedded.end():].strip()
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


def _roadmap_domain(major):
    groups = [
      (("기계", "로봇", "자동차", "항공"), ["대수", "미적분", "물리학"], [
       ("종이 보의 단면 구조에 따른 처짐량 비교", "같은 길이·재료의 종이를 서로 다른 단면 형태로 접어 중앙에 동일한 하중을 걸어 처짐량을 측정합니다.", ["독립변인: 단면 형태, 종속변인: 처짐량", "하중·지지 간격·재료를 통제하여 3회 이상 반복 측정", "평균 처짐량 그래프를 작성하고 굽힘 강성 개념과 비교"], "단면별 처짐량 표·그래프·구조 해석"),
       ("경사면 각도에 따른 물체 이동 시간 분석", "경사각을 단계별로 바꾸고 같은 물체가 일정 거리를 이동하는 시간을 측정해 가속도와 마찰의 영향을 검토합니다.", ["독립변인: 경사각, 종속변인: 이동 시간", "동일 물체·거리·표면 조건으로 반복 측정", "예측과 관측의 차이를 정리하고 마찰·측정 오차 분석"], "경사각-이동시간 그래프·오차 분석표"),
       ("실내 환기장치의 팬 속도와 공기 흐름 비교", "안전한 소형 팬의 속도 조건을 바꾸고 일정 위치에서 종이 리본의 이동이나 풍속 센서 수치를 비교합니다.", ["관측 기준과 측정 지점을 고정", "팬의 속도·거리별 변화 측정", "소음·에너지 소비·기류 개선 효과의 상충 관계 정리"], "측정 기록·환기장치 개선 설계안")]),
      (("인공지능", "컴퓨터", "소프트웨어", "정보보안", "데이터", "통계"), ["대수", "확률과 통계", "정보"], [
       ("학교 생활 데이터의 특성 분석", "공개 또는 익명화된 학교 생활 데이터를 정리하여 변수별 분포와 이상값을 비교합니다.", ["데이터 출처·익명화 기준 확인", "빈도·평균·분포 시각화", "누락값·표본 편향 점검"], "변수별 시각화·데이터 품질 보고서"),
       ("간단한 예측모형과 기준모형 비교", "같은 데이터에서 평균값 예측과 간단한 회귀모형을 비교하고 오차를 계산합니다.", ["학습·검증 데이터 구분", "두 예측 방식 구현", "평균절대오차 비교"], "예측 결과표·오차 비교 그래프"),
       ("데이터 편향이 예측에 미치는 영향 검증", "표본 구성을 바꾸었을 때 예측 결과가 얼마나 달라지는지 실험합니다.", ["집단별 표본 비율 확인", "표본 균형 전후 모델 비교", "편향의 한계와 개선안 기록"], "편향 비교표·개선 제안서")]),
      (("화학", "생명", "의", "약", "간호", "보건", "식품"), ["화학", "생명과학", "확률과 통계"], [
       ("생활 속 생물·화학 현상의 변수 정하기", "안전한 공개 데이터에서 온도·시간과 반응 또는 생장 지표의 관계를 탐색합니다.", ["관측 가능한 변수 2개 선정", "공개 데이터 출처 검증", "변수 관계 그래프 구성"], "변수 설계표·자료 출처 목록"),
       ("서로 다른 조건의 실험자료 비교", "기존 실험·관측 데이터를 조건별로 나눠 평균과 분산을 비교합니다.", ["동일 조건 데이터 확보", "조건별 통계 계산", "교란 요인·표본 수 확인"], "조건별 비교표·해석 보고서"),
       ("결론의 재현성과 한계 검토", "서로 다른 공개자료에서 같은 경향이 나타나는지 검토합니다.", ["추가 자료 확보", "분석 기준 동일화", "다른 결과가 나올 경우 원인 기록"], "자료 간 비교 보고서")]),
      (("경제", "경영", "금융", "회계", "사회", "정치", "법", "행정", "복지"), ["사회와 문화", "경제", "확률과 통계"], [
       ("지역별 생활 지표의 차이 분석", "공공 통계를 이용해 지역별 한 가지 생활 지표의 격차를 비교합니다.", ["지표 정의와 기준 연도 통일", "지역별 자료 수집", "격차 시각화와 원인 가설 정리"], "통계 그래프·원인 가설 보고서"),
       ("정책 사례의 이해관계 비교", "같은 사회 문제에 대한 서로 다른 정책 접근을 비교합니다.", ["정책 목표·수단 정리", "이해관계자별 이득·비용 비교", "공개 근거로 주장 검증"], "정책 비교표·쟁점 분석"),
       ("개선안의 실행 가능성 검토", "제안한 대안을 비용·형평성·지속가능성 기준으로 평가합니다.", ["평가 기준 명시", "정책 대안 2개 비교", "한계와 후속 검토 항목 제시"], "정책 제안서·평가표")]),
      (("국어", "문학", "언어", "교육", "철학", "역사", "미디어", "광고"), ["독서와 작문", "사회와 문화", "세계사"], [
       ("동일 주제의 작품·기사 관점 비교", "같은 사회적 주제를 다룬 두 텍스트를 선정해 표현 방식과 논거를 비교합니다.", ["텍스트 두 편과 선정 기준 제시", "핵심 주장·서술 방식 표로 비교", "시대·저자 맥락의 영향 분석"], "작품·기사 비교표"),
       ("독자 반응과 해석의 차이 조사", "두 가지 해석에 대한 근거를 찾아 타당성을 비교합니다.", ["해석별 원문 근거 수집", "상반된 견해 분석", "근거가 부족한 주장 구별"], "근거 중심 비평문"),
       ("기존 해석의 반론 구성", "기존 해석에 대한 반례를 검토하고 수정된 해석을 제시합니다.", ["반론·반례 찾기", "기존 주장 수정", "동료 피드백 반영"], "수정 비평문·피드백 기록")]),
      (("디자인", "영상", "음악", "무용", "체육", "스포츠", "미술", "애니"), ["관련 예술·체육 선택과목", "진로 관련 실습", "융합 선택과목"], [
       ("표현 방식에 따른 전달 효과 비교", "같은 주제의 표현 방식을 두 가지로 구성해 비교합니다.", ["표현 목표와 대상 정하기", "시안 또는 실습 기록 제작", "피드백 항목 설계"], "시안 2종·비교표"),
       ("대상별 사용자 반응 조사", "자발적 참여자의 피드백을 익명으로 수집해 비교합니다.", ["사전 동의와 익명성 확보", "반응 항목별 정리", "차이가 난 원인 분석"], "반응 요약표"),
       ("수정안의 효과 검토", "피드백을 반영한 수정안의 전달 효과를 평가합니다.", ["수정 사항 기록", "동일 기준 재평가", "최종 결과·한계 정리"], "개선 전후 비교 보고서")]),
    ]
    for names,subjects,activities in groups:
        if any(word in major for word in names): return subjects, activities
    return ["관련 기초 교과", "탐구 과목", "융합 선택과목"], [
      ("희망 분야의 핵심 현상 정량화", "관찰 가능한 현상을 하나 정해 변수를 명확히 정의합니다.", ["관찰 대상 선정", "변수와 단위 정의", "공개 자료 확보"], "변수 정의서"),
      ("조건별 차이 검증", "조건 두 가지에서 관측 결과가 어떻게 달라지는지 비교합니다.", ["조건별 자료 확보", "관측 기준 통일", "차이 그래프 작성"], "비교 결과표"),
      ("반례와 개선안 도출", "관측 결과를 반박하는 사례를 검토합니다.", ["반례 탐색", "원인 정리", "대안 제안"], "검증·개선 보고서")]


def _record_link_for_roadmap(chunks, major):
    """Conservatively connect source labels; generic actions are not evidence."""
    broad = {'분석','모델','제작','설계','운동','실험','학습','정보','그래프','연구','조사','활용','데이터','관심'}
    terms = {str(t).casefold() for t in MAJORS.get(major,set()) if len(str(t)) >= 2 and str(t) not in broad}
    related = [r for r in chunks if any(t in r['text'].casefold() for t in terms)]
    text_all = ' '.join(r['text'] for r in chunks)
    topic = None
    if ('기계' in major or '건축' in major) and '지진' in text_all:
        topic = '지진·구조물'
        related = [r for r in chunks if '지진' in r['text']]
    elif ('화학' in major or '환경' in major) and ('중화' in text_all or '산성비' in text_all):
        topic = '산성화·중화'
        related = [r for r in chunks if '중화' in r['text'] or '산성비' in r['text']]
    elif ('국어' in major or '문학' in major) and ('탱자나무' in text_all or '작가의 의도' in text_all):
        topic = '문학 작품 해석'
        related = [r for r in chunks if '탱자나무' in r['text'] or '작가의 의도' in r['text']]
    if not related:
        return '학생부에서 이 학과와 직접 연결되는 활동은 아직 확인되지 않았습니다. 다음 탐구는 신규 제안입니다.', False, None
    best = related[0]
    note = f"{best['grade']}학년 {best['source']} 기록을 출발점으로 삼는 후속 탐구 제안입니다. 이미 수행한 활동이 아닙니다."
    return note, True, topic


def _topic_project(topic):
    """First follow-up project is grounded in a confirmed topic, never fabricated as done."""
    if topic == '지진·구조물':
        return ('건물 모형의 높이와 보강 방식에 따른 진동 안정성 비교',
            '진원지 탐구에서 지진의 위치를 다뤘다면, 후속 탐구로 건물 모형의 구조에 따른 진동 반응을 비교합니다. 안전한 소형 종이 모형을 사용합니다.',
            ['독립변인: 건물 모형 높이 또는 보강 방식, 종속변인: 흔들림 폭과 넘어짐 여부',
             '동일한 바닥·흔들림 횟수·재료 조건에서 모형별로 3회 이상 측정',
             '모형별 흔들림 결과를 표·그래프로 나타내고 안정성 차이를 해석'],
            '모형 설계도·반복 측정표·진동 안정성 비교 보고서')
    if topic == '산성화·중화':
        return ('산성화된 물의 중화 조건을 공개 실험자료로 비교',
            '학생부의 산성화·중화 탐구를 확장해 중화제 종류·투입량과 pH 변화의 관계를 공개 자료로 분석합니다.',
            ['독립변인: 중화제 종류 또는 투입량, 종속변인: pH 변화량',
             '공개 교육용 실험자료에서 초기 pH·투입량·측정 방법이 유사한 사례 수집',
             '중화 전후 pH와 과량 투입 사례를 그래프로 비교하고 자료의 한계 검토'],
            '중화 조건별 pH 비교표·그래프·자료 검증 보고서')
    if topic == '문학 작품 해석':
        return ('문학 작품의 상징 표현과 독자 해석 비교',
            '학생부에서 다룬 작품의 상징·서술 방식을 출발점으로 삼아 두 작품의 표현 효과와 해석 차이를 비교합니다.',
            ['두 작품에서 상징 표현을 3개 이상 선정하고 인용 근거를 정리',
             '화자·서술자·시대 배경과 상징의 의미를 같은 분석 기준으로 비교',
             '해석의 공통점·차이와 반례를 검토해 근거 중심 비평문 작성'],
            '작품 비교표·근거 인용 목록·비평문')
    return None


def _enrich_project(major, row, idx, record_link, grade):
    """Concrete and distinct fallback project design when AI is unavailable."""
    item = dict(row)
    steps = list(item.get('steps') or [])
    while len(steps) < 3:
        steps.append('자료를 검토하고 결과를 표·그래프로 정리한 뒤 한계를 기술합니다.')
    item['steps'] = [
        '1주차 · 탐구 질문과 비교 조건 확정 — ' + steps[0],
        '2주차 · 자료 수집 및 반복 수행 — ' + steps[1],
        '3주차 · 결과 분석 및 시각화 — ' + steps[2],
        '4주차 · 검증·보고서 작성 — 조건별 결과의 차이, 오류 원인, 다음 탐구 방향을 정리합니다.',
    ]
    item['record_connection'] = record_link
    item['research_question'] = [
        f"{item['title']}에서 어떤 조건이 관측 결과를 가장 크게 바꾸는가?",
        f"{item['title']}의 관측값은 반복 측정해도 같은 경향을 보이는가?",
        f"{item['title']}의 결론은 다른 조건이나 자료에도 적용되는가?",
    ][idx % 3]
    item['duration'] = '4주 권장 · 주 1~2회 진행'
    item['data_to_collect'] = [
        '독립변인·종속변인·통제변인 정의표, 조건별 관측값, 반복 측정 기록',
        '자료 출처·측정 단위·표본 수, 조건별 평균과 변동 폭',
        '초기 결과와 추가 검증 결과, 예외 사례 및 오차 요인',
    ][idx % 3]
    item['evaluation'] = [
        '조건을 통제했는지, 반복 측정이 충분한지, 그래프가 주장과 일치하는지 점검',
        '같은 절차를 반복했을 때 결과가 재현되는지, 자료 출처가 신뢰 가능한지 점검',
        '반례가 있는지, 비교 기준을 동일하게 유지했는지, 한계를 명시했는지 점검',
    ][idx % 3]
    item['extension'] = [
        '실험 조건을 한 가지 더 늘려 결과가 달라지는 경계 조건을 찾아봅니다.',
        '측정 방식을 바꾸거나 공개 데이터를 추가해 결과를 교차 검증합니다.',
        '관찰된 한계를 보완한 설계안을 만들고 기존 결과와 비교합니다.',
    ][idx % 3]
    return item


def _subject_reason(subject, major):
    reasons = {
        '대수':'변수 사이 관계를 식과 그래프로 모델링해 탐구 결과를 설명하는 기초를 쌓습니다.',
        '미적분':'변화율·누적량을 이용해 운동, 반응, 성장 등 시간에 따른 현상을 정량 분석합니다.',
        '물리학':'힘·운동·에너지 개념을 활용해 측정 결과와 이론적 예측을 비교합니다.',
        '화학':'물질의 성질과 반응 원리를 활용해 조건에 따른 실험 결과를 해석합니다.',
        '생명과학':'생명 현상의 원리와 변인 관계를 이해하고 자료 해석에 적용합니다.',
        '확률과 통계':'표본, 평균, 산포와 오차를 이용해 탐구 결과의 신뢰도를 판단합니다.',
        '정보':'데이터 정리·시각화 및 간단한 프로그램 구현을 통해 탐구 과정을 재현합니다.',
        '사회와 문화':'사회 현상을 조사할 때 개념·변인·표본·관점의 차이를 구분합니다.',
        '경제':'경제적 의사결정과 지표 변화를 분석하는 이론적 토대를 마련합니다.',
        '독서와 작문':'원문 근거를 정리하고 논리적인 탐구 보고서와 비평문을 작성합니다.',
        '세계사':'작품·사건·제도의 시대적 맥락을 비교하여 해석을 심화합니다.',
    }
    return reasons.get(subject, f"{major}와 연계한 탐구의 개념·방법을 익히고 교과 학습을 수행 기록으로 발전시킵니다.")


def _grade_roadmap(grade, projects, major):
    titles = [x['title'] for x in projects]
    plan = []
    for g in range(grade, 4):
        if g == 1:
            goal = '관심 분야 구체화와 교과 개념을 활용한 첫 탐구 설계'
            actions = [f"{major}와 관련된 핵심 개념 2~3개를 교과서에서 정리하고 질문을 만듭니다.",
                       f"‘{titles[0]}’을 출발 주제로 삼아 변인·비교 기준을 정합니다.",
                       '탐구 일지에 자료 출처, 조사 방법, 처음 예상과 실제 관찰을 기록합니다.']
            result = '탐구 계획서 1부 + 기초 자료표 + 활동 성찰 기록'
        elif g == 2:
            goal = '변인 통제·반복 검증으로 탐구의 신뢰도 높이기'
            actions = [f"‘{titles[min(1,len(titles)-1)]}’을 수행하고 조건별 결과를 최소 3회 비교합니다.",
                       '교과 개념을 근거로 결과를 해석하고 오차·예외 사례를 따로 정리합니다.',
                       '선행 탐구와 비교해 무엇을 개선했는지 표와 그래프로 제시합니다.']
            result = '심화 탐구 보고서 + 결과 그래프 + 오차 분석표'
        else:
            goal = '독립적인 심화 주제와 검증 가능한 결론 완성'
            actions = [f"‘{titles[min(2,len(titles)-1)]}’을 중심으로 새로운 가설을 세웁니다.",
                       '기존 자료와 추가 자료를 비교해 결론의 재현성·한계를 검토합니다.',
                       '후속 질문과 전공 연계성을 발표 자료로 정리하고 피드백을 반영합니다.']
            result = '최종 연구 보고서 + 발표 자료 + 후속 탐구 제안서'
        plan.append({'grade':g,'goal':goal,'actions':actions,'deliverable':result})
    return plan


def _ai_propose_roadmap(major, grade, chunks, fallback_projects):
    """Return detailed student-record-grounded proposals, or None if unavailable."""
    import json
    import os
    key = os.getenv('OPENAI_API_KEY','').strip()
    model = os.getenv('OPENAI_MODEL','').strip()
    if not key or not model:
        return None
    try:
        from openai import OpenAI
        seen, excerpts = set(), []
        for row in chunks:
            signature = (row.get('grade'),row.get('source'),row.get('text'))
            if signature in seen: continue
            seen.add(signature)
            excerpts.append(f"[{row['grade']}학년 {row['source']}] {row['text'][:650]}")
            if sum(map(len,excerpts)) > 6500: break
        record_excerpt = '\n'.join(excerpts) or '학생부 원문 없음'
        examples = json.dumps(fallback_projects, ensure_ascii=False)
        prompt = (f"희망 학과: {major}; 현재 학년: {grade}.\n"
            f"실제 학생부 기록(수행 완료 여부는 이 기록에서만 확인):\n{record_excerpt}\n"
            f"참고 가능한 프로젝트: {examples}\n"
            "한국 고등학생이 앞으로 실행할 수 있는 서로 다른 심화 탐구 정확히 3개를 설계하세요. "
            "각 주제는 학생부에서 확인된 활동과 연결하고, 관련 기록이 없으면 '직접적인 연계 근거 없음'이라고 쓰세요. "
            "주제마다 ① 기록과 연결되는 이유(record_connection) ② 검증 가능한 연구 질문(research_question) "
            "③ 목적·배경(description) ④ 4~5개의 구체적인 순차 수행 단계(steps; 각 단계에 무엇을 어떻게 하는지) "
            "⑤ 측정·수집 자료(data_to_collect) ⑥ 검증 기준(evaluation) ⑦ 산출물(expected_result) "
            "⑧ 후속 심화 방향(extension)을 제공하세요. 모든 내용은 학과별로 구체적이어야 하며, "
            "기존에 수행했다고 허위로 쓰지 마세요. 위험하거나 의료적인 실험을 제안하지 마세요. "
            "출력은 한국어 JSON 객체만: {\"activities\":[{\"title\":\"\",\"record_connection\":\"\",\"research_question\":\"\",\"description\":\"\",\"steps\":[\"\",\"\",\"\",\"\"],\"data_to_collect\":\"\",\"evaluation\":\"\",\"expected_result\":\"\",\"extension\":\"\"}],\"basis_note\":\"\"}."
        )
        client = OpenAI(api_key=key, timeout=50)
        result = client.chat.completions.create(
            model=model,
            messages=[{'role':'system','content':'한국 고등학생 진로 탐구 설계 전문가. 기록에 없는 학생 성과를 만들지 말고 미래의 제안으로 서술하세요.'},
                      {'role':'user','content':prompt}],
            response_format={'type':'json_object'}, max_completion_tokens=3500,
        )
        data = json.loads(result.choices[0].message.content)
        acts = data.get('activities',[])
        if not isinstance(acts,list) or len(acts)!=3: return None
        validated=[]
        for row in acts:
            if not isinstance(row,dict): return None
            title=str(row.get('title') or '').strip()
            desc=str(row.get('description') or '').strip()
            steps=row.get('steps',[])
            expected=str(row.get('expected_result') or '').strip()
            if not title or not desc or not expected or not isinstance(steps,list) or len(steps)<3: return None
            validated.append({
                'title':title[:140], 'description':desc[:900],
                'steps':[str(x)[:260] for x in steps[:6]],
                'expected_result':expected[:400],
                'record_connection':str(row.get('record_connection') or '')[:450],
                'research_question':str(row.get('research_question') or '')[:450],
                'data_to_collect':str(row.get('data_to_collect') or '')[:500],
                'evaluation':str(row.get('evaluation') or '')[:450],
                'extension':str(row.get('extension') or '')[:450],
                'duration':'약 4~6주 · 학생 일정에 맞게 조정',
            })
        return validated,str(data.get('basis_note') or '').strip()[:400]
    except Exception:
        return None


def make_roadmap(major, grade, records, text):
    """Provide detailed actionable roadmap, labeling AI vs subject-domain fallback."""
    major=str(major or '').strip()
    if not major: raise ValueError('희망 학과를 선택해 주세요.')
    grade=max(1,min(2,int(grade or 1)))
    chunks=_record_chunks(records,text)
    record_link, has_related, topic = _record_link_for_roadmap(chunks, major)
    subjects,activities=_roadmap_domain(major)
    if topic:
        activities = [_topic_project(topic)] + list(activities[1:])
    project_rows=[_enrich_project(major,{
        'title':title,'description':description,'steps':steps,'expected_result':output
    },idx,record_link,grade) for idx,(title,description,steps,output) in enumerate(activities)]
    ai_result=_ai_propose_roadmap(major,grade,chunks,project_rows)
    if ai_result:
        project_rows,basis_note=ai_result
        proposal_mode='ai_record_grounded_proposals'
    else:
        basis_note=''
        proposal_mode='subject_domain_proposals'
    return {
        'rubric_version':VERSION, 'analysis_mode':proposal_mode,'major':major,
        'evidence_status':'related_record_found' if has_related else 'evidence_not_confirmed',
        'recommended_subjects':[{'subject':subject,'reason':_subject_reason(subject,major)} for subject in subjects],
        'research_activities':project_rows,
        'grade_plan':_grade_roadmap(grade,project_rows,major),
        'advice':(
            f"{major}에 맞는 탐구 주제를 학생부 기록과 연결하여 제안했습니다. " if has_related
            else f"학생부에서 {major}의 직접적인 관련 활동이 확인되지 않았으므로 전공 기초 탐구부터 제안합니다. "
        ) + (('AI 연계 근거: '+basis_note+' ') if basis_note else '') +
            '추천 선택과목은 학교별 개설 여부와 실제 교육과정을 확인하세요. 모든 탐구활동은 앞으로 수행할 계획이며, 이미 수행한 활동이 아닙니다.'
    }
