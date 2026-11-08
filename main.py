
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

# Vercel 프론트엔드 접근 허용
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


# ==============================
# 요청 데이터
# ==============================

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


# ==============================
# OpenRouter 연결
# ==============================

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
                raise ValueError(
                    "AI 응답에서 JSON을 찾을 수 없습니다."
                )
            data = json.loads(match.group())

        if not isinstance(data, dict):
            raise ValueError(
                "AI 응답이 JSON 객체가 아닙니다."
            )

        return data

    except HTTPException:
        raise
    except Exception as exc:
        print(
            f"AI 요청 오류: {type(exc).__name__}: {exc}"
        )
        raise HTTPException(
            status_code=502,
            detail=(
                "AI 응답 처리 오류: "
                f"{type(exc).__name__}"
            ),
        )


# ==============================
# 전공 적합성 평가 기준
# ==============================

MAJOR_FIT_RUBRIC = {
    "전공 관련 활동": {
        "전공 주제 관련성": 10,
        "활동의 구체성": 10,
        "활동 간 연계성": 10,
    },
    "학업 역량": {
        "전공 기초 교과 역량": 10,
        "지식의 실제 적용": 10,
        "학습 태도와 개선": 5,
    },
    "관심의 지속성": {
        "관심 주제의 반복·유지": 8,
        "관심의 발전 과정": 8,
        "자기주도적 확장": 4,
    },
    "탐구 심화도": {
        "탐구 문제 설정": 4,
        "탐구 방법 설계": 4,
        "결과 분석 및 검증": 4,
        "개선 및 후속 탐구": 3,
    },
    "융합 역량": {
        "타 분야 지식 활용": 4,
        "융합적 문제해결": 4,
        "융합 결과의 타당성": 2,
    },
}


def calculate_major_fit(ratings: dict) -> dict:
    """
    각 세부 지표의 0~4등급을
    가중치가 반영된 100점 만점으로 환산한다.
    """
    if not isinstance(ratings, dict):
        raise ValueError("평가 데이터 형식 오류")

    category_scores = {}
    total = 0.0

    for category, indicators in MAJOR_FIT_RUBRIC.items():
        subtotal = 0.0

        for indicator, maximum in indicators.items():
            rating = ratings[category][indicator]

            if (
                type(rating) is not int
                or not 0 <= rating <= 4
            ):
                raise ValueError(
                    f"잘못된 평가 등급: "
                    f"{category} / {indicator}"
                )

            subtotal += rating / 4 * maximum

        category_scores[category] = round(
            subtotal, 2
        )
        total += subtotal

    return {
        "total_score": round(total, 2),
        "category_scores": category_scores,
    }


# ==============================
# 서버 상태 확인
# ==============================

@app.get("/")
def home():
    return {
        "message": "SEEDU:ON AI 서버 실행 중"
    }


@app.get("/health")
def health():
    return {"status": "ok"}


# ==============================
# AI 역량 및 전공 적합성 분석
# ==============================

@app.post("/analyze")
def analyze(request: AnalyzeRequest):

    rubric_json = json.dumps(
        MAJOR_FIT_RUBRIC,
        ensure_ascii=False,
    )

    system_prompt = """
너는 한국 고등학생의 학교생활기록부를
분석하는 진로 상담 AI다.

[기본 원칙]
1. 학생이 입력한 기록만 근거로 분석한다.
2. 기록에 없는 활동이나 성취를 만들지 않는다.
3. 적합한 학과 3개를 추천한다.
4. 추천 학과마다 15개 지표를 독립 평가한다.
5. 각 지표는 0~4의 정수 등급을 부여한다.
6. 근거가 부족하면 높은 등급을 부여하지 않는다.
7. 1학년에게 미래 학년 기록 부재로 감점하지 않는다.
8. 1학년은 같은 학년 내 활동 연계를 평가한다.
9. 2~3학년은 학년별 변화와 발전도 평가한다.
10. 실제 대학의 공식 입학 평가로 표현하지 않는다.
11. JSON 객체 하나만 반환한다.

[평가 등급]
0 = 관련 근거를 확인할 수 없음
1 = 관심 표현 또는 단순 참여
2 = 활동이 있으나 과정과 결과가 제한적
3 = 구체적인 과정과 성취 근거 확인
4 = 자기주도적 심화, 검증 또는 발전 근거 충분

[평가 기준]
""" + rubric_json + """

[출력 JSON 구조]
{
  "competencies": [
    {
      "name": "학업역량",
      "score": 80,
      "evidence": "실제 기록에 근거한 설명"
    },
    {
      "name": "진로역량",
      "score": 80,
      "evidence": "근거"
    },
    {
      "name": "탐구역량",
      "score": 80,
      "evidence": "근거"
    },
    {
      "name": "공동체역량",
      "score": 80,
      "evidence": "근거"
    },
    {
      "name": "성장가능성",
      "score": 80,
      "evidence": "근거"
    }
  ],
  "recommended_majors": [
    {
      "major": "학과명1",
      "reason": "추천 이유"
    },
    {
      "major": "학과명2",
      "reason": "추천 이유"
    },
    {
      "major": "학과명3",
      "reason": "추천 이유"
    }
  ],
  "major_fit": [
    {
      "major": "학과명1",
      "ratings": {
        "전공 관련 활동": {
          "전공 주제 관련성": 3,
          "활동의 구체성": 3,
          "활동 간 연계성": 2
        },
        "학업 역량": {
          "전공 기초 교과 역량": 3,
          "지식의 실제 적용": 3,
          "학습 태도와 개선": 2
        },
        "관심의 지속성": {
          "관심 주제의 반복·유지": 3,
          "관심의 발전 과정": 2,
          "자기주도적 확장": 2
        },
        "탐구 심화도": {
          "탐구 문제 설정": 3,
          "탐구 방법 설계": 3,
          "결과 분석 및 검증": 2,
          "개선 및 후속 탐구": 2
        },
        "융합 역량": {
          "타 분야 지식 활용": 3,
          "융합적 문제해결": 3,
          "융합 결과의 타당성": 2
        }
      },
      "evidence": "실제 학생부 근거",
      "improvement": "보완할 활동"
    }
  ],
  "strengths": [
    "강점1",
    "강점2",
    "강점3"
  ],
  "weaknesses": [
    "보완점1",
    "보완점2"
  ],
  "growth": "학년별 성장 분석"
}

[필수 규칙]
- competencies는 정확히 5개 작성한다.
- recommended_majors는 정확히 3개 작성한다.
- major_fit도 정확히 3개 작성한다.
- major_fit의 학과명은 추천 학과명과 일치한다.
- 각 학과의 ratings에는 15개 지표를 모두 포함한다.
- 0~4 정수 등급만 사용한다.
- 위 예시 점수를 복사하지 않는다.
- 학과별 특성을 고려하여 독립적으로 평가한다.
- 실제 입력 기록에서 확인되는 근거만 설명한다.
- 최종 점수 계산은 서버가 수행한다.
- Markdown이나 JSON 외 텍스트는 출력하지 않는다.
"""

    user_prompt = json.dumps(
        request.model_dump(),
        ensure_ascii=False,
    )

    result = ask_ai(
        system_prompt,
        user_prompt,
    )

    # 기존 분석 데이터는 유지
    # 학과별 점수는 Python에서 직접 계산
    recommended = result.get(
        "recommended_majors", []
    )
    raw_major_fit = result.get("major_fit", [])

    if (
        not isinstance(recommended, list)
        or len(recommended) != 3
        or not isinstance(raw_major_fit, list)
        or len(raw_major_fit) != 3
    ):
        raise HTTPException(
            status_code=502,
            detail=(
                "AI가 학과별 평가 3개를 "
                "완전하게 반환하지 않았습니다."
            ),
        )

    major_fit_results = []
    seen_majors = set()

    for item in raw_major_fit:
        try:
            major = item["major"]

            if not isinstance(major, str):
                raise ValueError("학과명 형식 오류")

            if major in seen_majors:
                raise ValueError("중복된 학과 평가")

            seen_majors.add(major)

            calculated = calculate_major_fit(
                item["ratings"]
            )

            major_fit_results.append({
                "major": major,
                "ratings": item["ratings"],
                "total_score": calculated[
                    "total_score"
                ],
                "category_scores": calculated[
                    "category_scores"
                ],
                "evidence": item.get(
                    "evidence", ""
                ),
                "improvement": item.get(
                    "improvement", ""
                ),
            })

        except (
            KeyError,
            TypeError,
            ValueError,
        ) as exc:
            raise HTTPException(
                status_code=502,
                detail=(
                    "전공 적합성 평가 데이터 오류: "
                    f"{exc}"
                ),
            )

    try:
        recommended_names = {
            item["major"] for item in recommended
        }
    except (KeyError, TypeError):
        raise HTTPException(
            status_code=502,
            detail="추천 학과 데이터 형식 오류",
        )

    if recommended_names != seen_majors:
        raise HTTPException(
            status_code=502,
            detail=(
                "추천 학과와 평가 학과가 "
                "일치하지 않습니다."
            ),
        )

    result["major_fit"] = major_fit_results

    return result


# ==============================
# AI 맞춤 진로 로드맵
# ==============================

@app.post("/roadmap")
def roadmap(request: RoadmapRequest):

    if not request.major.strip():
        raise HTTPException(
            status_code=400,
            detail="희망 학과를 입력해 주세요.",
        )

    system_prompt = """
너는 한국 고등학생의 진로 및 과목 선택을
돕는 AI 상담사다.

학생의 현재 학년, 세특, 희망 학과를 고려해
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
      "title": "탐구활동 제목1",
      "description": "탐구 내용",
      "steps": [
        "1단계",
        "2단계",
        "3단계"
      ],
      "expected_result": "예상 산출물"
    },
    {
      "title": "탐구활동 제목2",
      "description": "탐구 내용",
      "steps": [
        "1단계",
        "2단계",
        "3단계"
      ],
      "expected_result": "예상 산출물"
    },
    {
      "title": "탐구활동 제목3",
      "description": "탐구 내용",
      "steps": [
        "1단계",
        "2단계",
        "3단계"
      ],
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

[추가 규칙]
- 현재 학년 이후의 활동을 우선 추천한다.
- 탐구활동은 정확히 3개 작성한다.
- 학생의 기존 활동과 연결되는 주제를 제안한다.
- 학교별 과목 개설 여부는 확인이 필요하다.
- 기록에 없는 성취를 만들어내지 않는다.
"""

    user_prompt = json.dumps(
        request.model_dump(),
        ensure_ascii=False,
    )

    return ask_ai(
        system_prompt,
        user_prompt,
    )
