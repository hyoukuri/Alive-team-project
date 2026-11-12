"""SEEDU:ON Hybrid 2.2 - Python scoring, optional bounded AI evidence review."""
import os
from typing import Any, Literal
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

load_dotenv()
app = FastAPI(title="SEEDU:ON Hybrid API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://alive-team-project.vercel.app"],
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)

from accounts import router as accounts_router  # noqa: E402
app.include_router(accounts_router)
from rubric_engine import VERSION, analyze_records, make_roadmap  # noqa: E402
from ai_reviewer import run_review  # noqa: E402

class AnalyzeRequest(BaseModel):
    grade: int = Field(default=1, ge=1, le=3)
    records: Any = None
    text: str = ""
    subjects: list[str] = Field(default_factory=list)
    analysis_mode: Literal["hybrid", "fast"] = "hybrid"
    model_config = {"extra":"allow"}

class RoadmapRequest(BaseModel):
    grade: int = Field(default=1, ge=1, le=3)
    major: str = ""
    records: Any = None
    text: str = ""
    analysis: Any = None
    model_config = {"extra":"allow"}

@app.get("/")
def home():
    return {"message":"SEEDU:ON Hybrid 2.2 server running", "rubric_version":VERSION}

@app.get("/health")
def health():
    return {"status":"ok", "analysis":"hybrid"}

@app.post("/analyze")
def analyze(request: AnalyzeRequest):
    try:
        result = analyze_records(request.records, request.text, request.grade)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    # Text is untrusted; AI suggestions never replace rubric scores.
    full_text = "\n".join(str(x or "") for x in request.records.values()) if isinstance(request.records,dict) else request.text
    status = run_review(result, full_text, request.analysis_mode)
    result["ai_review"] = status
    result["analysis_mode"] = "hybrid_ai_assisted" if status["used"] else "rule_based"
    return result

@app.post("/roadmap")
def roadmap(request: RoadmapRequest):
    if not request.major.strip():
        raise HTTPException(status_code=400, detail="희망 학과를 입력해 주세요.")
    return make_roadmap(request.major.strip(), request.grade, request.records, request.text)
