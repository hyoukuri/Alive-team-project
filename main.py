"""SEEDU:ON standalone API. No external project Python modules required."""
from __future__ import annotations
import json
import os
import re
from collections import defaultdict
from typing import Any
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

app = FastAPI(title="SEEDU:ON", version="4.0.0")
origins = [x.strip() for x in os.getenv("CORS_ORIGINS", "https://alive-team-project.vercel.app,http://localhost:5500,http://127.0.0.1:5500").split(",") if x.strip()]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_origin_regex=r"https://[a-zA-Z0-9-]+\.vercel\.app", allow_methods=["GET", "POST", "OPTIONS"], allow_headers=["*"], allow_credentials=False)

COMPETENCIES = ("학업역량", "진로역량", "탐구역량", "공동체역량", "성장가능성")
INDICATORS = [("전공 관련 활동",30),("학업 역량",25),("관심의 지속성",20),("탐구 심화도",15),("융합 역량",10)]
MAJORS = {
 "컴퓨터공학과": {"words":["프로그래밍","파이썬","알고리즘","코딩","소프트웨어","컴퓨터","웹 개발","함수","데이터 시각화"],"subjects":["정보","수학"],"track":"software"},
 "인공지능학과": {"words":["인공지능","AI","머신러닝","데이터","예측","학습 데이터","모델","알고리즘"],"subjects":["정보","수학"],"track":"ai"},
 "수학과": {"words":["수학적","증명","함수","확률","통계","수열","최적화","수학 모델"],"subjects":["수학"],"track":"math"},
 "통계학과": {"words":["통계","데이터","표본","오차","변량","분포","확률","그래프"],"subjects":["수학"],"track":"math"},
 "화학과": {"words":["화학","물질","반응","분자","농도","촉매","용해","산화"],"subjects":["과학","화학"],"track":"science"},
 "생명과학과": {"words":["생명","세포","유전","효소","생태","미생물","생물"],"subjects":["과학","생명"],"track":"science"},
 "기계공학과": {"words":["기계","운동","힘","에너지","로봇","설계","구조","역학"],"subjects":["과학","물리"],"track":"engineering"},
 "전기전자공학과": {"words":["전기","전류","회로","센서","전자","반도체","에너지","제어"],"subjects":["과학","물리"],"track":"engineering"},
 "환경공학과": {"words":["환경","기후","탄소","환기","오염","재활용","에너지","대기"],"subjects":["과학","사회"],"track":"environment"},
 "교육학과": {"words":["교육","수업","교수","학습","학생","교육격차","학습법","학습효율"],"subjects":["사회","국어"],"track":"education"},
 "국어국문학과": {"words":["문학","시","소설","비평","표현","언어","서사","텍스트"],"subjects":["국어"],"track":"humanities"},
 "심리학과": {"words":["심리","행동","인지","동기","정서","설문","인식"],"subjects":["사회"],"track":"society"},
 "경영학과": {"words":["경영","기업","마케팅","소비자","경제","사업","시장","조직"],"subjects":["사회"],"track":"business"},
 "사회학과": {"words":["사회","불평등","지역","정책","공공","격차","인권","사회문제"],"subjects":["사회"],"track":"society"},
 "역사학과": {"words":["역사","사료","근현대","시대","문화유산","유적","사건"],"subjects":["한국사","역사"],"track":"humanities"},
}
TRACKS = {
 "software": {"courses":["수학 심화 선택과목(학교 개설 확인)","정보","데이터 과학"], "topics":[("생활 속 문제 해결 프로그램","학교생활의 반복 업무를 조사하고 파이썬으로 자동화 도구를 설계한다.","문제 정의 → 사용자 요구 조사 → 구현 → 오류 시험","동작하는 프로그램과 테스트 기록"),("알고리즘 성능 비교","같은 문제를 해결하는 두 알고리즘의 수행 시간을 입력 크기별로 비교한다.","알고리즘 선택 → 측정 → 그래프 → 한계 해석","비교 그래프 및 개선 제안"),("접근성 중심 웹 서비스","사용자 불편을 조사하고 접근성을 고려한 간단한 웹페이지를 제작한다.","사용자 조사 → 화면 설계 → 구현 → 피드백","프로토타입과 개선 보고서")]},
 "ai":{"courses":["수학 심화 선택과목(학교 개설 확인)","확률과 통계 관련 과목","인공지능 기초","데이터 과학"],"topics":[("데이터 편향과 AI 예측","공개 데이터의 집단별 구성 차이가 예측 결과에 미치는 영향을 탐구한다.","데이터 조사 → 분포 비교 → 모델 시험 → 윤리 검토","분석 보고서"),("예측 모델의 오차 비교","간단한 회귀 모델 두 가지를 구성하고 학습·검증 데이터의 오차를 비교한다.","문제 정의 → 데이터 분리 → 모델 학습 → 오차 분석","오차 비교표"),("일상 데이터 분류 프로젝트","생활 속 데이터를 수집하여 규칙 기반 방식과 분류 모델을 비교한다.","데이터 수집 → 기준 설정 → 분류 → 결과 검증","분류 결과와 한계 정리")]},
 "math":{"courses":["대수 관련 과목","미적분 관련 과목","확률과 통계 관련 과목"],"topics":[("현실 데이터의 함수 모델링","시간에 따른 변화를 서로 다른 함수로 근사하고 예측 오차를 분석한다.","자료 수집 → 함수 선정 → 오차 계산 → 해석","모델 비교 보고서"),("표본 크기와 통계적 변동","표본 크기를 바꾸면서 평균의 변동 폭이 어떻게 달라지는지 모의실험한다.","가설 → 반복 표집 → 시각화 → 해석","표본 실험 결과"),("최적화 문제 탐구","조건이 제한된 일상 문제를 수학적으로 표현해 최선의 선택을 찾는다.","조건 정의 → 수식화 → 계산 → 검증","최적화 풀이 및 반례 검토")]},
 "science":{"courses":["학교 개설 과학 심화 과목","수학 관련 선택과목"],"topics":[("변수 통제 실험","수업에서 다룬 현상을 정해 한 변수만 바꾸는 반복 실험을 설계한다.","가설 → 대조 조건 → 측정 → 오차 분석","실험 보고서"),("과학 논문의 재현성 분석","공개된 실험 사례를 조사하고 결과가 달라질 수 있는 조건을 분류한다.","문헌 조사 → 실험 조건 비교 → 한계 정리","재현성 분석 보고서"),("실생활 소재 분석","일상 소재의 성질을 측정하고 과학 원리와 연결해 해석한다.","질문 설정 → 측정 → 분석 → 적용","자료 기반 탐구 포스터")]},
 "engineering":{"courses":["물리학 관련 과목","미적분 관련 과목","정보"],"topics":[("센서를 활용한 생활 문제 해결","센서 측정값으로 생활환경 상태를 판단하는 시제품을 구상한다.","문제 탐색 → 설계 → 측정 → 개선","설계도와 성능 평가표"),("구조물 설계의 변수 비교","재료나 구조를 바꾸면서 하중에 따른 변화를 비교한다.","변수 설정 → 실험 → 측정 → 비교","구조 실험 보고서"),("에너지 효율 분석","생활 기기의 소비 에너지를 비교하고 효율 개선 방안을 평가한다.","자료 수집 → 계산 → 비교 → 제안","효율 분석 보고서")]},
 "environment":{"courses":["환경 관련 과학 선택과목","통계 관련 과목","지리 관련 과목"],"topics":[("교실 공기질 데이터 탐구","시간과 인원에 따른 CO₂ 농도 변화를 측정하고 환기 전략을 비교한다.","반복 측정 → 그래프 → 조건 비교","환기 개선 제안서"),("지역 기후 변화 분석","공공 기상 데이터를 이용해 장기 기온 추세와 변동성을 비교한다.","공공데이터 수집 → 시각화 → 추세 해석","기후 데이터 보고서"),("자원 순환 정책 비교","학교에서 발생하는 폐기물의 유형을 조사해 감축 방안을 비교한다.","현황 조사 → 대안 설정 → 효과 추정","학교 개선 제안서")]},
 "education":{"courses":["사회·심리 관련 선택과목","정보","교육 관련 진로 활동"],"topics":[("학습 방법 효과 비교","서로 다른 학습 전략을 일정 기간 적용하고 학습 과정의 변화를 기록한다.","전략 선정 → 관찰 → 비교 → 한계 검토","학습법 비교 보고서"),("교육 접근성 조사","학습 자료 접근성에 영향을 주는 요인을 문헌과 설문 설계로 검토한다.","문제 설정 → 문헌 조사 → 조사 설계","교육 개선 제안서"),("수업 자료 개선","한 개념을 다양한 수준의 학습자에게 설명하는 자료를 제작하고 피드백을 반영한다.","학습 목표 → 자료 제작 → 의견 수집","개선된 학습 자료")]},
 "humanities":{"courses":["국어·역사 관련 심화 과목","사회 관련 선택과목"],"topics":[("원문과 해석 비교","한 주제에 대한 두 텍스트의 표현과 관점 차이를 비교한다.","자료 선정 → 표현 분석 → 관점 비교","비평문"),("시대별 담론 변화","동일 주제의 시기별 자료를 비교해 관점 변화의 원인을 검토한다.","자료 수집 → 맥락 조사 → 비교","사료·텍스트 분석 보고서"),("디지털 인문학 기초","작은 텍스트 자료를 수집해 핵심 어휘의 빈도와 맥락을 분석한다.","자료 수집 → 분류 → 해석","텍스트 분석 포스터")]},
 "society":{"courses":["사회 관련 심화 과목","통계 관련 과목"],"topics":[("지역 사회 문제 조사","공공 통계와 관련 자료를 통해 지역의 문제를 한 가지 선정해 원인을 검토한다.","문헌 조사 → 지표 선택 → 비교","정책 제안서"),("설문 설계의 편향 분석","질문 표현을 달리한 설문 문항이 응답에 미치는 영향을 탐구한다.","설문 문항 설계 → 비교 → 해석","설문 방법 보고서"),("사회 정책 비교","같은 문제를 다루는 두 정책의 장점과 한계를 지표로 비교한다.","정책 조사 → 평가 기준 → 비교","비교 분석 보고서")]},
 "business":{"courses":["경제 관련 과목","통계 관련 과목","정보"],"topics":[("소비자 선택 조사","가상의 구매 선택 사례를 만들어 가격·품질 요인의 영향을 비교한다.","문제 설정 → 설문 설계 → 분석","소비자 행동 보고서"),("학교 행사 운영 기획","예산과 참여 수요를 추정해 행사 운영안을 설계한다.","수요 조사 → 예산 → 대안 비교","운영 기획서"),("기업의 ESG 지표 비교","기업 공개자료를 비교해 환경·사회 관련 지표의 의미와 한계를 분석한다.","자료 수집 → 평가 → 해석","기업 비교 보고서")]}
}

class AnalyzeRequest(BaseModel):
    grade: int = Field(1, ge=1, le=2)
    records: Any = None
    text: str = ""
    analysis_mode: str = "ai"

class RoadmapRequest(BaseModel):
    grade: int = Field(1, ge=1, le=2)
    major: str = Field(min_length=1, max_length=100)
    records: Any = None
    analysis: Any = None
    current_unit: str = ""


def clean(s:Any)->str:
    return re.sub(r"\s+", " ", str(s or "")).strip()

def parse_records(records:Any, text:str, grade:int)->list[dict]:
    out=[]
    if isinstance(records, dict):
        for k,v in records.items():
            if isinstance(v,dict):
                for sub,content in v.items():
                    if clean(content): out.append({"grade":int(str(k).replace("학년", "")) if str(k).replace("학년", "").isdigit() else grade,"subject":clean(sub)[:80],"text":clean(content)[:6000]})
            elif clean(v): out.append({"grade":grade,"subject":clean(k)[:80],"text":clean(v)[:6000]})
    if isinstance(records,list):
        for r in records:
            if not isinstance(r,dict):continue
            content=clean(r.get("text") or r.get("content") or r.get("record"))
            if content:
                try:g=int(r.get("grade", grade))
                except (TypeError,ValueError):g=grade
                if 1<=g<=grade:out.append({"grade":g,"subject":clean(r.get("subject") or r.get("name") or "기타")[:80],"text":content[:6000]})
    if not out and clean(text):out.append({"grade":grade,"subject":"통합 기록","text":clean(text)[:10000]})
    if len(out)>60:raise HTTPException(400,"입력 과목이 너무 많습니다(최대 60개).")
    if sum(len(r['text']) for r in out)>65000:raise HTTPException(400,"전체 입력 분량은 65,000자 이하여야 합니다.")
    return out


def snippets(records:list[dict])->list[dict]:
    """Traceable original text snippets. Every claim must cite a literal original span."""
    result=[]
    for i,r in enumerate(records):
        sentences=[s.strip() for s in re.split(r"(?<=[.!?。])\s+|\n+",r['text']) if len(s.strip())>=12]
        if not sentences:sentences=[r['text']]
        for s in sentences:
            # split long sentences without silently dropping remaining content
            pieces=[s[j:j+340] for j in range(0,len(s),340)]
            for part in pieces:
                result.append({"id":f"e{len(result)+1}","record_index":i,"grade":r['grade'],"subject":r['subject'],"quote":part})
    return result


def rule_labels(evidence:list[dict]):
    # Pre-filter by substantive topic cues; never use generic study etiquette as major evidence.
    scored=[]
    for name,spec in MAJORS.items():
        matched=[]
        for e in evidence:
            q=e['quote'].lower()
            terms=[w for w in spec['words'] if w.lower() in q]
            if not terms:continue
            # subject itself cannot create a match; only text can
            s= min(4,len(set(terms))) + (1 if any(t in e['subject'] for t in spec['subjects']) else 0)
            matched.append((s,e))
        if matched:
            matched.sort(key=lambda x:-x[0]); ids=[x[1]['id'] for x in matched[:3]]
            scored.append({"major":name,"evidence_ids":ids,"rank_signal":sum(x[0] for x in matched[:5]),"track":spec['track']})
    scored.sort(key=lambda x:-x['rank_signal'])
    return scored


def ai_extract(records:list[dict], evidence:list[dict]):
    """AI supports interpretation, not fabricated quotes. Batches cover every evidence item."""
    key=os.getenv('OPENAI_API_KEY','').strip()
    if not key:return None,"API 키 미설정 · 규칙 기반 참고 분석"
    try:
        from openai import OpenAI
        client=OpenAI(api_key=key,timeout=50,max_retries=1)
        selections=[]
        batch=[]; chars=0
        for e in evidence:
            row={"id":e['id'],"subject":e['subject'],"text":e['quote']}
            n=len(e['quote'])
            if batch and chars+n>6500:
                selections.append(batch);batch=[];chars=0
            batch.append(row);chars+=n
        if batch:selections.append(batch)
        merged={"competency_evidence":defaultdict(list),"major_evidence":defaultdict(list)}
        for group in selections:
            response=client.chat.completions.create(
                model=os.getenv('OPENAI_MODEL','gpt-4.1-mini'),
                response_format={"type":"json_object"},
                temperature=0,
                messages=[
                    {"role":"system","content":"당신은 학생부 근거 추출기입니다. 반드시 입력된 id만 사용하세요. 학업역량,진로역량,탐구역량,공동체역량,성장가능성 5개 역량의 근거 id를 골라 주세요. 전공 관련성은 실질적인 활동만 선택하고, 수업 태도나 일반적인 협력만으로 특정 전공을 추천하지 마세요. JSON 형식: {\"competency_evidence\":{\"학업역량\":[\"e1\"],...},\"major_evidence\":{\"컴퓨터공학과\":[\"e2\"],...}}. 언급되지 않은 항목은 빈 배열. 전공 후보는 제공된 목록 안에서만 선택하세요. 모든 항목 근거가 없어도 괜찮습니다."},
                    {"role":"user","content":json.dumps({"majors":list(MAJORS),"evidence":group},ensure_ascii=False)}
                ]
            )
            data=json.loads(response.choices[0].message.content or '{}')
            allowed={e['id'] for e in group}
            for k in ['competency_evidence','major_evidence']:
                obj=data.get(k,{})
                if not isinstance(obj,dict):continue
                valid_keys=COMPETENCIES if k=='competency_evidence' else MAJORS.keys()
                for name,ids in obj.items():
                    if name in valid_keys and isinstance(ids,list):
                        merged[k][name].extend(x for x in ids if isinstance(x,str) and x in allowed)
        return {k:dict(v) for k,v in merged.items()},"OpenAI 의미 근거 검토"
    except Exception as exc:
        # Do not leak API key or student's record into errors
        code=getattr(exc,'status_code',None)
        return None,f"AI 연결 오류({code or type(exc).__name__}) · 규칙 기반 참고 분석"


def build_analysis(records:list[dict],want_ai:bool)->dict:
    evidence=snippets(records)
    byid={e['id']:e for e in evidence}
    ai,note=ai_extract(records,evidence) if want_ai else (None,'규칙 기반 참고 분석')
    is_ai=ai is not None
    rules=rule_labels(evidence)
    candidates=[]
    if is_ai:
        for major,ids in ai.get('major_evidence',{}).items():
            valid=list(dict.fromkeys(x for x in ids if x in byid))
            if valid:
                candidates.append({'major':major,'evidence_ids':valid[:4],'rank_signal':len(valid),'track':MAJORS[major]['track']})
        candidates.sort(key=lambda d:-d['rank_signal'])
    else:candidates=rules
    # Even AI-backed candidates are *exploration candidates*, not calibrated fit percentages.
    cands=candidates[:3]
    marker_terms={
        '학업역량':['학습','이해','계산','비교','분석','자료','문제','설명','함수','수학','과학'],
        '진로역량':['진로','관심','전공','인공지능','프로그래밍','환경','교육','공학','심리','경영','데이터'],
        '탐구역량':['탐구','실험','조사','가설','측정','분석','비교','검증','오차'],
        '공동체역량':['모둠','협력','토론','의견','조율','함께','배려','피드백'],
        '성장가능성':['개선','수정','확장','이후','한계','보완','발전','재설계']}
    competencies=[]
    for name in COMPETENCIES:
        if is_ai:ids=list(dict.fromkeys(ai.get('competency_evidence',{}).get(name,[])))[:3]
        else:
            ranks=[]
            for e in evidence:
                hits=sum(bool(re.search(re.escape(w),e['quote'],re.I)) for w in marker_terms[name])
                if hits:ranks.append((hits,e['id']))
            ranks.sort(reverse=True)
            ids=[x[1] for x in ranks[:3]]
        # scores are bounded, explicitly tentative indicators, not probability or true ability
        score=min(85, 25+15*len(ids)) if ids else None
        competencies.append({'name':name,'score':score,'status':'evidence_based_reference' if ids else 'NE','evidence_ids':ids,'summary':brief(byid[ids[0]]['quote']) if ids else '입력된 기록에서 관련 근거가 확인되지 않았습니다.'})
    majors=[]
    for c in cands:
        ids=c['evidence_ids']; q=[byid[x] for x in ids]
        detail=[];coverage=0;partial=0
        for ix,(title,weight) in enumerate(INDICATORS):
            if ix==0: support=ids[:2]
            elif ix==1:support=[x for x in ids if any(t in byid[x]['quote'] for t in ['분석','계산','해석','비교','학습','설명'])][:2]
            elif ix==2:support=ids[:2] if len(set(x['subject'] for x in q))>=2 else []
            elif ix==3:support=[x for x in ids if any(t in byid[x]['quote'] for t in ['실험','검증','오차','심화','한계','추가'])][:2]
            else:support=[x for x in ids if any(t in byid[x]['quote'] for t in ['연결','융합','다른','함께','사회','과학'])][:2]
            if support:
                # 2 / 4 = tentative rubric rating; insufficient info means N/E, never zero
                rating=2 if len(support)==1 else 3
                scored=round(weight*rating/4,1)
                coverage+=weight;partial+=scored
                detail.append({'name':title,'weight':weight,'score':scored,'status':'evaluated','evidence_ids':support})
            else:detail.append({'name':title,'weight':weight,'score':None,'status':'NE','evidence_ids':[]})
        majors.append({'major':c['major'],'summary':f"{q[0]['subject']} 기록에서 관련 활동이 확인된 탐색 후보입니다.",
             'evidence_ids':ids,'score_status':'hold','total_score':None,'partial_score':round(partial,1),
             'coverage_weight':coverage,'details':detail})
    strengths=[{'title':x['name'],'text':x['summary'],'evidence_ids':x['evidence_ids'][:1]} for x in sorted(competencies,key=lambda x:-(x['score'] or 0)) if x['score'] is not None][:2]
    improvements=[{'title':x['name'],'text':f"{x['name']}의 활동 과정과 결과를 더 구체적으로 기록해 보세요.", 'evidence_ids':[]} for x in competencies if x['score'] is None][:2]
    if not improvements:
        improvements=[{'title':'탐구 과정 구체화','text':'활동의 가설, 검증 과정, 한계를 기록하면 근거가 더 분명해집니다.','evidence_ids':[]}]
    growth=[]
    for g in range(1,max(r['grade'] for r in records)+1):
        grp=[r for r in records if r['grade']==g]
        if grp:growth.append({'grade':g,'subjects':[r['subject'] for r in grp], 'summary':f"{g}학년 {len(grp)}개 과목 기록이 입력되었습니다."})
    return {'version':'4.0.0','mode':'ai_reviewed' if is_ai else 'rule_preview', 'notice':note,
       'record_count':len(records),'evidence_count':len(evidence),'competencies':competencies,
       'strengths':strengths,'improvements':improvements,'majors':majors,'growth':growth,
       'evidence':evidence,'disclaimer':'역량 점수는 기록 내 관찰 가능한 근거를 단순화한 참고 지표입니다. 학과 적합도·합격 확률이 아닙니다. N/E는 0점이 아닙니다.'}

def brief(txt:str, limit:int=95)->str:
    s=clean(txt)
    return s[:limit].rstrip()+('…' if len(s)>limit else '')

@app.get('/')
def home():return {'name':'SEEDU:ON','version':'4.0.0','docs':'/docs'}

@app.get('/health')
def health():return {'status':'ok','version':'4.0.0','ai_configured':bool(os.getenv('OPENAI_API_KEY','').strip())}

@app.post('/analyze')
def analyze(req:AnalyzeRequest):
    records=parse_records(req.records,req.text,req.grade)
    if not records:raise HTTPException(400,'최소 1개 과목의 세특을 입력해 주세요.')
    result=build_analysis(records,req.analysis_mode=='ai')
    return JSONResponse(result)

@app.post('/roadmap')
def roadmap(req:RoadmapRequest):
    records=parse_records(req.records,'',req.grade)
    major=clean(req.major)
    if not major:raise HTTPException(400,'희망 학과를 선택해 주세요.')
    if major in MAJORS:track=MAJORS[major]['track']
    else:
        # A custom major should still produce a useful roadmap rather than a blank screen.
        track='society'
        for k,v in MAJORS.items():
            if major in k or k in major:track=v['track'];break
    spec=TRACKS[track]
    current_unit=clean(req.current_unit)[:100]
    related=[]
    for r in records:
        if r['subject'] not in related:related.append(r['subject'])
    activities=[]
    for i,(title,desc,steps,output) in enumerate(spec['topics'],1):
        activities.append({'rank':i,'title':title,'description':desc,'steps':[x.strip() for x in steps.split('→')],
                           'expected_result':output,'connection':f"현재 입력한 {related[0]} 과목 활동과 연결해 보세요." if related else '관심 주제와 연결해 보세요.'})
    if current_unit:
        activities[0]['connection']=f"현재 수업 단원 '{current_unit}'에서 배운 개념과 연결하여 시작하세요."
    return {'major':major,'grade':req.grade,'mode':'curriculum_reference','subjects':spec['courses'],
       'activities':activities,'grade_plan':[
           {'grade':req.grade,'title':'현재 학년','actions':['관심 있는 교과 개념 1개 선택','기록된 활동의 확장 질문 작성']},
           {'grade':min(req.grade+1,3),'title':'다음 단계','actions':['학교 개설 선택과목 확인','탐구활동 1개 실행 및 결과 검증']}
       ],'notice':'선택과목 개설 여부와 이수 조건은 학교 교육과정에서 확인하세요. 제안 활동은 실제 수행 전까지 생기부 활동으로 간주하지 않습니다.'}
