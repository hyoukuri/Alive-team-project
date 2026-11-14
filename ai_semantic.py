"""SEEDU:ON 3.1: compact evidence annotation with strict source verification.

Only this file needs replacement. OpenRouter model is configured with
OPENROUTER_MODEL; no implicit model change or repeated completion calls.
AI selects pre-numbered real student-record excerpts and semantic tags.
Python derives conservative ratings, using only validated excerpts.
"""
from __future__ import annotations

import json
import logging
import os
import re
from typing import Any

from rubric_v2 import COMPETENCY_NAMES

LOG = logging.getLogger('seedu.semantic')
BASE_URL = 'https://openrouter.ai/api/v1'
TAGS = set('learning career question method result validation revision collaboration leadership reflection planning interdisciplinary comparison application continuity concept'.split())
ALIASES = {
    '학습':'learning', '진로':'career', '문제':'question', '문제설정':'question',
    '방법':'method', '수행':'method', '결과':'result', '성과':'result',
    '검증':'validation', '개선':'revision', '수정':'revision',
    '협업':'collaboration', '협력':'collaboration', '주도':'leadership',
    '성찰':'reflection', '피드백':'reflection', '계획':'planning',
    '융합':'interdisciplinary', '비교':'comparison', '적용':'application',
    '지속':'continuity', '개념':'concept'
}
SYSTEM = (
    '학생부 의미 분석기다. 제공한 s의 각 요소는 실제 학생부 원문 구절이고 n은 0부터 시작하는 고유번호다. '
    '문장을 다시 쓰거나 점수를 매기지 말고, 실제 수행 행동을 보여주는 구절의 n과 의미 태그만 고르라. '
    '단순 관심과 활동 참여에 결과·검증·개선 태그를 붙이지 마라. '
    '정확히 이 형식의 JSON 객체 하나만 출력하라: '
    '{"e":[[0,["learning","method"]],[2,["result","revision"]]],"m":[[0,2],[0],[]]}. '
    'e는 최대 6개; 각 요소 [원문번호,태그배열]. m은 순서대로 전공 후보 3개의 관련 원문번호 배열. '
    '원문번호는 입력 s의 n과 반드시 일치해야 한다. '
    '태그는 learning,career,question,method,result,validation,revision,collaboration,leadership,reflection,planning,interdisciplinary,comparison,application,continuity,concept 중 선택. '
    '근거가 부족하면 배열을 비워라. 설명·마크다운 없이 JSON만 출력하라.'
)


def _source_spans(sources: list[dict]) -> list[dict]:
    if not sources:
        raise ValueError('학생부 기록 없음')
    result = []
    # Include the first meaningful sentences per record; maintain original source indexes.
    for source_idx, item in enumerate(sources[:6]):
        raw = str(item.get('text') or '').strip()
        if not raw:
            continue
        sentences = [p.strip() for p in re.split(r'(?<=[.!?。])\s+|\n+', raw) if p.strip()]
        if not sentences:
            sentences = [raw]
        seen = set()
        for part in sentences:
            if len(seen) >= 2:
                break
            quote = part[:220].strip()
            if len(quote) < 12 or quote in seen:
                continue
            seen.add(quote)
            result.append({'n':len(result), 'i':source_idx, 't':quote})
        if not seen and len(raw) >= 12:
            result.append({'n':len(result), 'i':source_idx, 't':raw[:220]})
    if not result:
        raise ValueError('분석 가능한 학생부 구절이 없습니다')
    return result


def _payload(sources, candidates):
    spans = _source_spans(sources)
    return json.dumps({'s':spans, 'm':list(candidates[:3])},ensure_ascii=False,separators=(',',':')),spans


def _json_object(content: Any) -> dict:
    if not isinstance(content, str) or not content.strip():
        raise ValueError('AI 응답이 비어 있습니다')
    clean = re.sub(r'^```(?:json)?\s*','',content.strip(),flags=re.I)
    clean = re.sub(r'\s*```$','',clean)
    beg,end = clean.find('{'),clean.rfind('}')
    if beg < 0 or end <= beg:
        raise ValueError('완성된 JSON 응답이 없습니다')
    try:
        value = json.loads(clean[beg:end+1])
    except json.JSONDecodeError as e:
        raise ValueError('AI JSON 구문 오류 위치='+str(e.pos)) from e
    if not isinstance(value,dict):
        raise ValueError('AI JSON 객체가 아닙니다')
    return value


def _id(val):
    # Accept integer and string integer only. Never accept bool, floats or arbitrary text.
    if type(val) is int:
        return val
    if isinstance(val,str) and re.fullmatch(r'\s*\d+\s*',val):
        return int(val.strip())
    return None


def _tags(val):
    if isinstance(val,str):
        val = re.split(r'[,/\s]+',val)
    if not isinstance(val,list):
        return []
    result=[]
    for tag in val:
        if not isinstance(tag,str):
            continue
        token=ALIASES.get(tag.strip(),tag.strip().lower())
        if token in TAGS and token not in result:
            result.append(token)
    return result


def _annotation_rows(parsed):
    # Tolerate equivalent object and list forms, including prior schema `f`.
    raw = parsed.get('e', parsed.get('evidence', parsed.get('facts', parsed.get('f',[]))))
    if isinstance(raw,dict):
        raw=list(raw.values())
    return raw if isinstance(raw,list) else []


def _get_row(row):
    if isinstance(row,dict):
        return _id(row.get('n',row.get('id',row.get('source_id',row.get('span_id'))))),_tags(row.get('tags',row.get('t',[])))
    if isinstance(row,list) and len(row)>=2:
        # Old `f` format: [source_index, quote, tags] cannot supply span IDs reliably;
        # accept only its explicit id + tags variant.
        return _id(row[0]),_tags(row[1] if isinstance(row[1],(str,list)) else [])
    return None,[]


def _major_ids(raw, valid):
    if not isinstance(raw,list):
        return []
    result=[]
    for val in raw:
        n=_id(val)
        if n is not None and n in valid and n not in result:
            result.append(n)
    return result


def _competency_scores(facts):
    # Conservative evidence-driven ceilings: annotation of a behavior is not
    # proof of advanced independent achievement. No automatic 4 without
    # multiple actual excerpts proving result, verification, and revision.
    rules = (
        {'learning','concept','application','method'},
        {'career','continuity','planning'},
        {'question','method','result','validation','comparison','revision'},
        {'collaboration','leadership'},
        {'reflection','revision','planning','continuity'},
    )
    competencies=[]
    for i,name in enumerate(COMPETENCY_NAMES):
        evidence_ids=[k for k,f in enumerate(facts) if set(f['tags']) & rules[i]]
        group=[facts[k] for k in evidence_ids]
        tags=set().union(*(set(f['tags']) for f in group)) if group else set()
        rating=None
        if group:
            rating=1
            if (len(group)>=1 and
                (('method' in tags or 'application' in tags) if i in (0,2) else
                 ('career' in tags if i==1 else
                  ('collaboration' in tags if i==3 else 'revision' in tags)))):
                rating=2
            if (len(group)>=2 and 'result' in tags and
                (('method' in tags or 'application' in tags) if i in (0,2) else
                 ('continuity' in tags if i==1 else
                  ('leadership' in tags if i==3 else 'revision' in tags)))):
                rating=3
            if (i in (0,2,4) and len(group)>=3 and
                {'result','validation','revision'} <= tags):
                rating=4
        competencies.append({'name':name,'rating':rating,'evidence_ids':evidence_ids})
    return competencies


def _normalize(parsed, candidates, spans, sources):
    span_by_id={s['n']:s for s in spans}
    facts=[]
    selected=set()
    rows=_annotation_rows(parsed)
    invalid=0
    for row in rows[:12]:
        n,tags=_get_row(row)
        if n not in span_by_id or not tags:
            invalid+=1
            continue
        if n in selected:
            # Merge tags if the same evidence span is mentioned twice.
            existing=next(f for f in facts if f['_n']==n)
            existing['tags']=list(dict.fromkeys(existing['tags']+tags))
            continue
        s=span_by_id[n]
        source_idx=s['i']
        quote=s['t']
        if not (0<=source_idx<len(sources) and quote in str(sources[source_idx].get('text') or '')):
            invalid+=1
            continue
        selected.add(n)
        facts.append({'_n':n,'source_index':source_idx,'quote':quote,'tags':tags})
    facts=facts[:6]
    ordered={f['_n']:i for i,f in enumerate(facts)}
    major_raw=parsed.get('m',parsed.get('majors',[]))
    majors=[]
    for i,name in enumerate(candidates[:3]):
        candidates_raw=major_raw[i] if isinstance(major_raw,list) and i<len(major_raw) else []
        if isinstance(candidates_raw,dict):
            candidates_raw=candidates_raw.get('ids',candidates_raw.get('evidence_ids',[]))
        majors.append({'major':name,'evidence_ids':[ordered[n] for n in _major_ids(candidates_raw,ordered)]})
    for f in facts:
        f.pop('_n',None)
    competencies=_competency_scores(facts)
    LOG.info('SEEDU semantic normalized: spans=%d rows=%d invalid_rows=%d facts=%d rated=%d',
             len(spans),len(rows),invalid,len(facts),sum(x['rating'] is not None for x in competencies))
    return {'facts':facts,'competencies':competencies,'major_links':majors}


def _usage(reply):
    u=getattr(reply,'usage',None)
    d=getattr(u,'completion_tokens_details',None)
    return str(getattr(reply,'model','unknown'))[:100],getattr(u,'completion_tokens',None),getattr(d,'reasoning_tokens',None)


def request_semantics(sources,candidates,*,call_fn=None):
    payload,spans=_payload(sources,candidates)
    if call_fn is not None:
        result=_normalize(_json_object(call_fn(SYSTEM,payload)),candidates,spans,sources)
    else:
        key=os.getenv('OPENROUTER_API_KEY','').strip()
        model=os.getenv('OPENROUTER_MODEL','').strip()
        if not key:
            raise ValueError('Render OPENROUTER_API_KEY 미설정')
        if not model:
            raise ValueError('Render OPENROUTER_MODEL 미설정')
        from openai import OpenAI
        params={'model':model,
                'messages':[{'role':'system','content':SYSTEM},{'role':'user','content':payload}],
                'max_tokens':1600,'temperature':0,
                'response_format':{'type':'json_object'}}
        # Keep the selected model-specific reasoning setting in one known place.
        if model=='inclusionai/ling-3.2-flash:free':
            params['extra_body']={'reasoning':{'enabled':False}}
        with OpenAI(base_url=BASE_URL,api_key=key,timeout=40.0,max_retries=0) as client:
            reply=client.chat.completions.create(**params)
        selected,completion,reasoning=_usage(reply)
        choices=getattr(reply,'choices',[]) or []
        if not choices:
            raise ValueError('AI 응답이 없습니다')
        if getattr(choices[0],'finish_reason',None)=='length':
            LOG.warning('SEEDU semantic length: model=%s completion=%s reasoning=%s',selected,completion,reasoning)
            raise ValueError('AI 출력 토큰 한도 초과')
        result=_normalize(_json_object(getattr(getattr(choices[0],'message',None),'content',None)),candidates,spans,sources)
        LOG.info('SEEDU semantic response: model=%s completion=%s reasoning=%s',selected,completion,reasoning)
    if not result['facts'] or not any(c['rating'] is not None for c in result['competencies']):
        raise ValueError('AI가 유효한 근거 번호·태그를 반환하지 않았습니다')
    return result
