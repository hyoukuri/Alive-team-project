import json
import os
import re
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from openai import OpenAI
from pydantic import BaseModel, Field

load_dotenv()
app = FastAPI(title="SEEDU:ON AI API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://alive-team-project.vercel.app"],
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

MODEL = os.getenv("OPENROUTER_MODEL", "openrouter/free")

class AnalyzeRequest(BaseModel):
    grade: int = Field(default=1, ge=1, le=3)
    records: Any = None
    text: str = ""
    subjects: list[str] = Field(default_factory=list)
    model_config = {"extra": "allow"}

class RoadmapRequest(BaseModel):
    grade: int = Field(default=1, ge=1, le=3)
    major: str = ""
    records: Any = None
    text: str = ""
    analysis: Any = None
    model_config = {"extra": "allow"}

MAJOR_FIT_RUBRIC = {
    "전공 관련 활동": {"전공 주제 관련성": 10, "활동의 구체성": 10, "활동 간 연계성": 10},
    "학업 역량": {"전공 기초 교과 역량": 10, "지식의 실제 적용": 10, "학습 태도와 개선": 5},
    "관심의 지속성": {"관심 주제의 반복·유지": 8, "관심의 발전 과정": 8, "자기주도적 확장": 4},
    "탐구 심화도": {"탐구 문제 설정": 4, "탐구 방법 설계": 4, "결과 분석 및 검증": 4, "개선 및 후속 탐구": 3},
    "융합 역량": {"타 분야 지식 활용": 4, "융합적 문제해결": 4, "융합 결과의 타당성": 2},
}
INDICATORS = [(category, indicator, weight) for category, group in MAJOR_FIT_RUBRIC.items() for indicator, weight in group.items()]
COMPETENCY_NAMES = ["학업역량", "진로역량", "탐구역량", "공동체역량", "성장가능성"]


def get_client():
    key = os.getenv("OPENROUTER_API_KEY")
    if not key:
        raise HTTPException(status_code=500, detail="OPENROUTER_API_KEY가 설정되지 않았습니다.")
    return OpenAI(base_url="https://openrouter.ai/api/v1", api_key=key, timeout=120.0)


def parse_json(content):
    if not isinstance(content, str) or not content.strip():
        raise ValueError("AI 응답이 비어 있습니다.")
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", content.strip(), flags=re.I)
    try:
        result = json.loads(cleaned)
    except json.JSONDecodeError:
        decoder = json.JSONDecoder()
        result = None
        for match in re.finditer(r"\{", cleaned):
            try:
                result, _ = decoder.raw_decode(cleaned[match.start():])
                break
            except json.JSONDecodeError:
                pass
        if result is None:
            raise ValueError("AI 응답에서 완전한 JSON 객체를 찾을 수 없습니다.")
    if not isinstance(result, dict):
        raise ValueError("AI 응답이 JSON 객체가 아닙니다.")
    return result


def ask_ai(system_prompt, user_prompt):
    try:
        response = get_client().chat.completions.create(
            model=MODEL,
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
            temperature=0,
        )
        return parse_json(response.choices[0].message.content)
    except HTTPException:
        raise
    except ValueError:
        raise
    except Exception as exc:
        print(f"AI 요청 오류: {type(exc).__name__}: {exc}")
        raise HTTPException(status_code=502, detail=f"AI 응답 처리 오류: {type(exc).__name__}") from exc


def integer_rating(value):
    if isinstance(value, bool):
        raise ValueError("불리언은 평가 등급이 아닙니다.")
    if isinstance(value, str) and value.strip() in {"0", "1", "2", "3", "4"}:
        value = int(value.strip())
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    if not isinstance(value, int) or not 0 <= value <= 4:
        raise ValueError(f"평가 등급은 0~4 정수여야 합니다: {value!r}")
    return value


def calculate_major_fit(ratings):
    """16개 등급을 검증하고 영역별 가중 점수와 총점을 계산한다."""
    if isinstance(ratings, list):
        if len(ratings) != len(INDICATORS):
            raise ValueError(f"평가 등급이 {len(ratings)}개입니다. 16개가 필요합니다.")
        values = [integer_rating(v) for v in ratings]
    elif isinstance(ratings, dict):
        values = []
        for category, indicator, _ in INDICATORS:
            group = ratings.get(category)
            if not isinstance(group, dict) or indicator not in group:
                raise ValueError(f"평가 항목 누락: {category} / {indicator}")
            values.append(integer_rating(group[indicator]))
    else:
        raise ValueError("ratings 형식 오류")

    category_scores = {name: 0.0 for name in MAJOR_FIT_RUBRIC}
    nested_ratings = {name: {} for name in MAJOR_FIT_RUBRIC}
    for (category, indicator, weight), rating in zip(INDICATORS, values):
        nested_ratings[category][indicator] = rating
        category_scores[category] += rating / 4 * weight
    category_scores = {k: round(v, 2) for k, v in category_scores.items()}
    return {"ratings": nested_ratings, "category_scores": category_scores,
            "total_score": round(sum(category_scores.values()), 2)}


def normalize_competencies(raw):
    if not isinstance(raw, list) or len(raw) != 5:
        raise ValueError("5대 핵심 역량은 정확히 5개여야 합니다.")
    by_name = {}
    for item in raw:
        if not isinstance(item, dict) or item.get("name") not in COMPETENCY_NAMES:
            raise ValueError("핵심 역량 이름이 올바르지 않습니다.")
        name = item["name"]
        if name in by_name:
            raise ValueError(f"중복 핵심 역량: {name}")
        rating = integer_rating(item.get("rating", item.get("score")))
        by_name[name] = {"name": name, "score": rating * 25,
                         "evidence": str(item.get("evidence") or "기록에서 구체적인 평가 근거가 확인되지 않았습니다.")}
    if set(by_name) != set(COMPETENCY_NAMES):
        raise ValueError("필수 핵심 역량이 누락되었습니다.")
    return [by_name[name] for name in COMPETENCY_NAMES]


def validate_analysis(result):
    recommended = result.get("recommended_majors")
    fits = result.get("major_fit")
    if not isinstance(recommended, list) or len(recommended) != 3:
        raise ValueError("추천 학과가 정확히 3개가 아닙니다.")
    if not isinstance(fits, list) or len(fits) != 3:
        raise ValueError("전공 적합성 평가가 정확히 3개가 아닙니다.")
    names = [item.get("major") for item in recommended if isinstance(item, dict)]
    if len(names) != 3 or any(not isinstance(n, str) or not n.strip() for n in names) or len(set(names)) != 3:
        raise ValueError("추천 학과 이름이 올바르지 않습니다.")
    evaluated = {}
    for item in fits:
        if not isinstance(item, dict) or not isinstance(item.get("major"), str):
            raise ValueError("전공 적합성 학과명 형식 오류")
        major = item["major"]
        if major in evaluated:
            raise ValueError("중복된 전공 적합성 평가")
        computed = calculate_major_fit(item.get("ratings"))
        evaluated[major] = {"major": major, **computed,
                            "evidence": str(item.get("evidence") or ""),
                            "improvement": str(item.get("improvement") or "")}
    if set(names) != set(evaluated):
        raise ValueError("추천 학과와 평가 학과가 일치하지 않습니다.")
    result["competencies"] = normalize_competencies(result.get("competencies"))
    result["major_fit"] = [evaluated[name] for name in names]
    for field in ("strengths", "weaknesses"):
        if not isinstance(result.get(field), list):
            result[field] = []
    if not isinstance(result.get("growth"), (str, list, dict)):
        result["growth"] = "입력된 학년의 활동을 중심으로 성장 과정을 검토했습니다."
    return result


@app.get("/")
def home():
    return {"message": "SEEDU:ON AI 서버 실행 중"}


@app.get("/health")
def health():
    return {"status": "ok"}


# 동일 입력에 대한 분석 결과 임시 저장
ANALYSIS_CACHE = {}
ANALYSIS_VERSION = "v1"


def analysis_cache_key(request):
    data = request.model_dump()

    # 순서가 같은 입력은 동일한 키 사용
    normalized = json.dumps(
        data,
        ensure_ascii=False,
        sort_keys=True
    )

    return (
        ANALYSIS_VERSION,
        MODEL,
        normalized
    )

@app.post("/analyze")
def analyze(request: AnalyzeRequest):
    rubric_order = [{"index": i + 1, "category": cat, "indicator": indicator, "weight": weight}
                    for i, (cat, indicator, weight) in enumerate(INDICATORS)]
    system_prompt = """너는 한국 고등학생의 학교생활기록부를 분석하는 진로 상담 AI다.
학생이 입력한 기록만 근거로 평가하며 없는 활동·성과를 지어내지 않는다.
1학년에게 미래 학년 기록 부재로 감점하지 않는다. 같은 학년 내 연계도 평가할 수 있다.
2~3학년은 실제 기록된 발전 과정만 평가한다.
반드시 하나의 완전한 JSON 객체만 출력한다. 설명이나 마크다운을 덧붙이지 않는다.

5대 핵심 역량: 학업역량, 진로역량, 탐구역량, 공동체역량, 성장가능성.
각 역량의 rating은 반드시 0~4 정수다. score 필드는 작성하지 않는다.
0=근거 없음, 1=관심·단순 참여, 2=활동 확인되나 과정/결과 제한,
3=구체적 과정과 성취 확인, 4=자기주도적 심화·검증·발전 근거 충분.
서버가 rating * 25로 100점 환산한다. 근거가 없으면 높게 평가하지 않는다.

서로 다른 학과 3개를 추천하고 학과별 전공 적합성 16개 지표를 평가한다.
ratings는 아래 순서대로 0~4 정수 16개를 담은 배열로 작성한다.
전공 적합성은 서버가 각 등급/4*가중치로 계산한다.
평가 지표 순서와 가중치:\n""" + json.dumps(rubric_order, ensure_ascii=False) + """

출력 구조 (아래 숫자는 형식 예시이며 복사 금지):
{
  "competencies": [
    {"name":"학업역량","rating":3,"evidence":"학생 기록의 구체적인 근거"},
    {"name":"진로역량","rating":3,"evidence":"근거"},
    {"name":"탐구역량","rating":3,"evidence":"근거"},
    {"name":"공동체역량","rating":2,"evidence":"근거"},
    {"name":"성장가능성","rating":3,"evidence":"근거"}
  ],
  "recommended_majors": [
    {"major":"학과명1","reason":"추천 이유"},
    {"major":"학과명2","reason":"추천 이유"},
    {"major":"학과명3","reason":"추천 이유"}
  ],
  "major_fit": [
    {"major":"학과명1","ratings":[3,3,2,3,3,2,3,2,2,3,3,2,2,2,3,2],"evidence":"실제 활동 근거","improvement":"보완 방향"},
    {"major":"학과명2","ratings":[2,3,2,3,2,2,2,2,2,2,2,2,2,2,2,2],"evidence":"실제 활동 근거","improvement":"보완 방향"},
    {"major":"학과명3","ratings":[2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2],"evidence":"실제 활동 근거","improvement":"보완 방향"}
  ],
  "strengths":["강점1","강점2"],
  "weaknesses":["보완점1","보완점2"],
  "growth":"실제 기록에 근거한 학년별 성장 설명"
}
필수: competencies 5개, recommended_majors 3개, major_fit 3개,
각 major_fit의 ratings 정확히 16개, 학과명 일치, 모든 등급 0~4 정수.
위 예시 학과명과 숫자를 그대로 복사하지 말 것.
입력된 기록과 관련된 학과별 특성에 맞춰 독립적으로 평가한다.
공식 대학 합격 가능성 또는 입학 평가 결과라고 표현하지 않는다."""
    
    cache_key = analysis_cache_key(request)

    if cache_key in ANALYSIS_CACHE:
        print("저장된 AI 분석 결과 재사용")
        return ANALYSIS_CACHE[cache_key]

    user_prompt = json.dumps(
        request.model_dump(),
        ensure_ascii=False
    )

    last_error = ""
    for attempt in range(2):
        prompt = user_prompt if attempt == 0 else user_prompt + (
            "\n이전 응답은 검증에 실패했습니다: " + last_error +
            "\n이번에는 필수 키, 학과명 일치, 5개 핵심역량 및 학과별 16개 등급을 정확히 작성하세요."
        )
        try:
            
            result = validate_analysis(
                ask_ai(system_prompt, prompt)
            )

            ANALYSIS_CACHE[cache_key] = result

            return result

        except ValueError as exc:
            last_error = str(exc)
            print(f"AI 분석 검증 실패 ({attempt + 1}/2): {last_error}")
    raise HTTPException(status_code=502, detail="AI 평가 형식 검증에 실패했습니다. 다시 분석해 주세요. " + last_error)


@app.post("/roadmap")
def roadmap(request: RoadmapRequest):
    if not request.major.strip():
        raise HTTPException(status_code=400, detail="희망 학과를 입력해 주세요.")
    system_prompt = """너는 한국 고등학생의 진로 로드맵 상담 AI다.
학생의 현재 학년, 실제 세특 기록, 희망 학과를 바탕으로 실행 가능한 로드맵을 작성한다.
미래 활동은 제안으로 명시하고 이미 성취한 것처럼 쓰지 않는다.
현재 학년 이후 활동을 우선 제안한다. 학교별 과목 개설 여부는 확인이 필요하다.
JSON 객체 하나만 출력한다. 아래 키와 구조를 지킨다:
{
  "major":"희망 학과",
  "recommended_subjects":[{"subject":"추천 과목","reason":"추천 이유"}],
  "research_activities":[
    {"title":"탐구1","description":"내용","steps":["1단계","2단계","3단계"],"expected_result":"예상 산출물"},
    {"title":"탐구2","description":"내용","steps":["1단계","2단계","3단계"],"expected_result":"예상 산출물"},
    {"title":"탐구3","description":"내용","steps":["1단계","2단계","3단계"],"expected_result":"예상 산출물"}
  ],
  "grade_plan":[
    {"grade":1,"goal":"목표","actions":["실천1"]},
    {"grade":2,"goal":"목표","actions":["실천1"]},
    {"grade":3,"goal":"목표","actions":["실천1"]}
  ],
  "advice":"종합 조언"
}
탐구활동은 정확히 3개 작성한다. 기존 활동과 연계한다."""
    return ask_ai(system_prompt, json.dumps(request.model_dump(), ensure_ascii=False))
