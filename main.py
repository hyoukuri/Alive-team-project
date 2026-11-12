"""SEEDU:ON Rubric 3.0 — one semantic AI call + deterministic scoring.

No change to /api/* account routes or frontend JSON contracts.
"""
import os
from typing import Any, Literal
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

load_dotenv()
app = FastAPI(title="SEEDU:ON Rubric 3.0 API")
app.add_middleware(CORSMiddleware,
    allow_origins=["https://alive-team-project.vercel.app"],
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,allow_methods=["*"],allow_headers=["*"])

from accounts import router as accounts_router  # noqa: E402
app.include_router(accounts_router)

from rubric_engine import make_roadmap  # noqa: E402
from semantic_engine import (VERSION,prepare,candidates_from_sources,
                             build_analysis,safe_fallback)  # noqa: E402
from ai_semantic import request_semantics  # noqa: E402

class AnalyzeRequest(BaseModel):
    grade:int = Field(default=1,ge=1,le=3)
    records:Any = None
    text:str = ""
    subjects:list[str] = Field(default_factory=list)
    analysis_mode: Literal["hybrid","fast"] = "hybrid"
    model_config={"extra":"allow"}

class RoadmapRequest(BaseModel):
    grade:int = Field(default=1,ge=1,le=3)
    major:str = ""
    records:Any = None
    text:str = ""
    analysis:Any = None
    model_config={"extra":"allow"}

@app.get("/")
def home():
    return {"message":"SEEDU:ON Rubric 3.0 running", "rubric_version":VERSION}

@app.get("/health")
def health():
    return {"status":"ok","rubric_version":VERSION}

@app.post("/analyze")
def analyze(request:AnalyzeRequest):
    try:
        sources=prepare(request.records,request.text,request.grade)
    except ValueError as exc:
        raise HTTPException(status_code=400,detail=str(exc)) from exc
    candidates=candidates_from_sources(sources)
    if request.analysis_mode == "fast":
        output=safe_fallback(request.records,request.text,request.grade, "fast_mode")
        output["ai_review"]={"used":False,"status":"skipped","reason":"fast_mode"}
        return output
    try:
        raw=request_semantics(sources,candidates)
        result=build_analysis(raw,request.records,request.text,request.grade,sources,candidates)
        result["ai_review"]={"used":True,"status":"reviewed","reason":"semantic_evidence"}
        return result
    except Exception as exc:
        # AI outage never causes 502 or a fabricated grade.
        print(f"SEEDU semantic fallback: {type(exc).__name__}: {str(exc)[:180]}")
        error_type = type(exc).__name__
        output=safe_fallback(request.records,request.text,request.grade,error_type)
        output["ai_review"]={"used":False,"status":"error","reason":"semantic_ai_failed","error_type":error_type}
        return output

@app.post("/roadmap")
def roadmap(request:RoadmapRequest):
    if not request.major.strip():
        raise HTTPException(status_code=400,detail="희망 학과를 입력해 주세요.")
    return make_roadmap(request.major.strip(),request.grade,request.records,request.text)
