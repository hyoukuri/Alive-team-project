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

# 로그인 / 분석 기록 API (/api/...) — 기존 /analyze, /roadmap은 그대로 둔다
from accounts import router as accounts_router  # noqa: E402  (load_dotenv 이후에 불러와야 DATABASE_URL을 읽는다)
app.include_router(accounts_router)

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

from rubric_v2 import (
    VERSION as RUBRIC_VERSION,
    MAJOR_FIT_RUBRIC,
    INDICATORS,
    COMPETENCY_NAMES,
    scoring_guidance,
    validate_analysis_v2,
)

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


@app.get("/")
def home():
    return {"message": "SEEDU:ON AI 서버 실행 중"}


@app.get("/health")
def health():
    return {"status": "ok"}


# 동일 입력에 대한 분석 결과 임시 저장
ANALYSIS_CACHE = {}
ANALYSIS_VERSION = RUBRIC_VERSION


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
    if not request.text.strip() and not (isinstance(request.records, dict) and any(str(v or "").strip() for v in request.records.values())):
        raise HTTPException(status_code=400, detail="학생부 기록을 먼저 입력해 주세요.")

    cache_key = analysis_cache_key(request)
    if cache_key in ANALYSIS_CACHE:
        return ANALYSIS_CACHE[cache_key]

    rubric_order = [
        {"index": i + 1, "category": cat, "indicator": label, "weight": weight}
        for i, (cat, label, weight) in enumerate(INDICATORS)
    ]
    system_prompt = (
        "너는 한국 고등학생의 학교생활기록부를 분석하는 진로 상담 AI다. "
        "학생부 원문에 있는 활동만 근거로 판단하고 없는 활동·성과를 지어내지 않는다. "
        "학생부의 교과 세특, 자율·자치활동, 동아리활동, 진로활동, 행동특성 및 종합의견을 구분해 읽는다. "
        "상위 학년 미입력은 감점하지 않는다. 미래 활동은 현재 성취로 간주하지 않는다. "
        "서로 다른 학과를 정확히 3개 추천한다. 학과 추천은 합격 가능성 예측이 아니다. "
        "AI는 등급만 판단하고 가중합과 점수는 Python에서 계산한다. "
        "한 개의 완전한 JSON 객체만 출력한다.\n"
        + scoring_guidance()
        + "\n16개 지표 순서: " + json.dumps(rubric_order, ensure_ascii=False)
        + "\n필수 JSON 구조: "
        + json.dumps({
            "competencies": [{"name": name, "rating": 2, "evidence": "해당 활동 설명", "evidence_quote": "원문에 실제 있는 표현"} for name in COMPETENCY_NAMES],
            "recommended_majors": [{"major": f"서로 다른 학과{i}", "reason": "학생 기록에 근거한 추천 이유", "learning_value": "해당 학과에서 배울 수 있는 내용", "exploration": "후속 탐색 활동"} for i in range(1,4)],
            "major_fit": [{"major": f"서로 다른 학과{i}", "ratings": [2]*16, "evidence_quotes": ["원문에 실제 있는 표현"]*16, "evidence": "실제 근거 요약", "improvement": "추가로 필요한 활동"} for i in range(1,4)],
            "strengths": ["근거 있는 강점"], "weaknesses": ["확인이 필요한 부분"],
            "growth": "학년별 발전 근거에 따른 설명"
        }, ensure_ascii=False)
        + "\n위 JSON의 예시 값·학과명·점수를 복사하지 말 것. "
        "rating=null은 자료가 부족해서 판단 불가능할 때만 사용한다. "
        "0점은 평가 가능한 자료에서 해당 행동이 확인되지 않는 경우다. "
        "원문 인용 evidence_quote / evidence_quotes는 사용자의 실제 기록에 존재하는 짧은 연속 구절을 그대로 사용한다. "
        "0점 또는 null 인용은 빈 문자열로 둔다. 인용 없는 1~4점은 금지한다. "
        "한 문장만으로 높은 점수를 주지 말고 행동 증거 수준에 따라 보수적으로 평가한다."
    )
    user_prompt = json.dumps(request.model_dump(), ensure_ascii=False)
    last_error = ""
    for attempt in range(3):
        prompt = user_prompt if attempt == 0 else (
            user_prompt + "\n이전 응답 검증 실패: " + last_error
            + "\n원문 인용 일치, 정확한 16개 등급/인용, 학과명, 필수 키를 다시 확인해 출력해 주세요."
        )
        try:
            result = validate_analysis_v2(
                ask_ai(system_prompt, prompt), request.records, request.text
            )
            # 캐시는 같은 프로세스 내 동일 요청 응답을 재사용하므로 실험 시 캐시 비활성화 가능.
            if os.getenv("DISABLE_ANALYSIS_CACHE", "0") != "1":
                ANALYSIS_CACHE[cache_key] = result
            return result
        except ValueError as exc:
            last_error = str(exc)
            print(f"루브릭 2.0 검증 실패 ({attempt + 1}/3): {last_error}")
    raise HTTPException(
        status_code=502,
        detail="AI 평가 응답을 검증하지 못했습니다. 다시 분석해 주세요. " + last_error,
    )


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
탐구활동은 정확히 3개 작성한다. 기존 활동과 연계한다.\n로드맵은 목표 설정→실행→점검→성찰→수정의 자기조절학습 과정을 단계별 행동으로 제안한다.\n기록에 없는 성취나 활동은 과거의 실제 경험처럼 표현하지 않는다."""
    return ask_ai(system_prompt, json.dumps(request.model_dump(), ensure_ascii=False))
