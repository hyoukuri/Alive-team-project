
import os
import json
import re
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from openai import OpenAI

load_dotenv()

app = FastAPI(title="SEEDU:ON AI API")

# Vercel 웹사이트에서 Render API에 접근할 수 있도록 허용
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://alive-team-project.vercel.app",
    ],
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

API_KEY = os.getenv("OPENROUTER_API_KEY")
MODEL = os.getenv("OPENROUTER_MODEL", "openrouter/free")


class AnalyzeRequest(BaseModel):
    grade: int = 1
    records: Any = None
    text: str = ""
    subjects: list[str] = Field(default_factory=list)

    model_config = {"extra": "allow"}


class RoadmapRequest(BaseModel):
    grade: int = 1
    major: str = ""
    records: Any = None
    text: str = ""
    analysis: Any = None

    model_config = {"extra": "allow"}


def get_client():
    if not API_KEY:
        raise HTTPException(
            status_code=500,
            detail="OPENROUTER_API_KEY가 설정되지 않았습니다.",
        )

    return OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=API_KEY,
        timeout=90.0,
    )


def ask_ai(system_prompt: str, user_prompt: str) -> dict:
    try:
        response = get_client().chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,
        )

        content = response.choices[0].message.content

        if not content:
            raise ValueError("AI 응답이 비어 있습니다.")

        # Markdown 코드블록이 포함되어도 JSON 추출
        content = re.sub(
            r"^```(?:json)?\s*|\s*```$",
            "",
            content.strip(),
            flags=re.IGNORECASE,
        )

        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", content, re.DOTALL)
            if not match:
                raise ValueError("AI 응답에서 JSON을 찾을 수 없습니다.")
            data = json.loads(match.group())

        if not isinstance(data, dict):
            raise ValueError("AI 응답이 JSON 객체가 아닙니다.")

        return data

    except HTTPException:
        raise
    except Exception as exc:
        print(f"AI 요청 오류: {type(exc).__name__}: {exc}")
        raise HTTPException(
            status_code=502,
            detail=f"AI 응답 처리 오류: {type(exc).__name__}",
        )


@app.get("/")
def home():
    return {"message": "SEEDU:ON AI 서버 실행 중"}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/analyze")
def analyze(request: AnalyzeRequest):
    system_prompt = """
너는 한국 고등학생의 학교생활기록부를 분석하는 진로 상담 AI다.
제공된 세특 기록만 근거로 분석하고 없는 활동은 만들어내지 않는다.
응답은 반드시 유효한 JSON 객체 하나만 반환한다.
Markdown이나 추가 설명은 출력하지 않는다.

다음 구조를 사용한다.

{
  "competencies": [
    {"name": "학업역량", "score": 80, "evidence": "근거"},
    {"name": "진로역량", "score": 80, "evidence": "근거"},
    {"name": "탐구역량", "score": 80, "evidence": "근거"},
    {"name": "공동체역량", "score": 80, "evidence": "근거"},
    {"name": "성장가능성", "score": 80, "evidence": "근거"}
  ],
  "recommended_majors": [
    {"major": "학과명", "reason": "추천 이유"},
    {"major": "학과명", "reason": "추천 이유"},
    {"major": "학과명", "reason": "추천 이유"}
  ],
  "strengths": ["강점1", "강점2", "강점3"],
  "weaknesses": ["보완점1", "보완점2"],
  "growth": "학년별 성장 분석"
}

역량 점수는 0~100 범위의 참고용 추정치이며
실제 대학 입학 평가 점수가 아니다.
"""

    user_prompt = json.dumps(
        request.model_dump(),
        ensure_ascii=False,
    )

    return ask_ai(system_prompt, user_prompt)


@app.post("/roadmap")
def roadmap(request: RoadmapRequest):
    if not request.major.strip():
        raise HTTPException(
            status_code=400,
            detail="희망 학과를 입력해 주세요.",
        )

    system_prompt = """
너는 한국 고등학생의 진로 및 과목 선택을 돕는 AI 상담사다.
학생의 현재 학년, 세특, 희망 학과를 고려하여
실행 가능한 맞춤 진로 로드맵을 작성한다.

반드시 JSON 객체 하나만 반환한다.
Markdown이나 추가 설명은 출력하지 않는다.

{
  "major": "희망 학과",
  "recommended_subjects": [
    {
      "subject": "추천 과목",
      "reason": "추천 이유"
    }
  ],
  "research_activities": [
    {
      "title": "탐구활동 제목",
      "description": "탐구 내용",
      "steps": ["1단계", "2단계", "3단계"],
      "expected_result": "예상 산출물"
    },
    {
      "title": "탐구활동 제목",
      "description": "탐구 내용",
      "steps": ["1단계", "2단계", "3단계"],
      "expected_result": "예상 산출물"
    },
    {
      "title": "탐구활동 제목",
      "description": "탐구 내용",
      "steps": ["1단계", "2단계", "3단계"],
      "expected_result": "예상 산출물"
    }
  ],
  "grade_plan": [
    {
      "grade": 1,
      "goal": "목표",
      "actions": ["실천1", "실천2"]
    },
    {
      "grade": 2,
      "goal": "목표",
      "actions": ["실천1", "실천2"]
    },
    {
      "grade": 3,
      "goal": "목표",
      "actions": ["실천1", "실천2"]
    }
  ],
  "advice": "종합 조언"
}

현재 학년 이후에 실천 가능한 활동을 우선 제안한다.
탐구활동은 정확히 3개 작성한다.
학교별 과목 개설 여부는 확인이 필요하다는 점을 고려한다.
"""

    user_prompt = json.dumps(
        request.model_dump(),
        ensure_ascii=False,
    )

    return ask_ai(system_prompt, user_prompt)
