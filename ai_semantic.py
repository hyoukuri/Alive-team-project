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
    '너는 학생부의 실제 행동을 구분하는 근거 분류기다. 점수는 매기지 않는다. '
    's 배열의 n은 원문 구절 번호다. 원문을 고쳐 쓰지 말고 번호만 선택하라. '
    '5개 역량을 모두 살펴라: 학업(learning/concept/application), 진로(career/planning), '
    '탐구(question/method/result/validation), 공동체(collaboration/leadership), '
    '성장(reflection/revision/continuity). '
    '특히 마지막의 공동체·성장 관련 구절도 빠뜨리지 말고, 기록에 실제 행동이 있는 경우 해당 n을 e에 포함하라. '
    '단순 참여를 리더십으로, 개선 계획을 실천한 개선으로 과장하지 마라. '
    '원문에 확인 가능한 수행 행동이 없는 역량은 비워도 된다. '
    '정확히 JSON 객체 하나만 반환: '
    '{"e":[[0,["learning","method"]],[2,["collaboration"]],[3,["reflection","revision"]]],"m":[[0],[0],[]]}. '
    'e는 [n,영문태그배열]이며 최대 10개, n은 s에 실제 존재해야 한다. '
    'm은 전공 후보 3개의 관련 근거 번호 배열이다. '
    '태그는 learning,career,question,method,result,validation,revision,collaboration,leadership,'
    'reflection,planning,interdisciplinary,comparison,application,continuity,concept 중에서만 선택. '
    'e는 학업·진로·탐구만 반복하지 말고 공동체·성장 관련 수행도 검토하라. 설명 없이 JSON만 출력.'
)


def _source_spans(sources: list[dict]) -> list[dict]:
    """Select beginning AND later evidence from each record, with source diversity.

    This only selects text for AI review; no keyword triggers a competency score.
    Each excerpt is an exact contiguous substring of its original source.
    """
    if not sources:
        raise ValueError('학생부 기록 없음')
    records=[]
    for source_idx,item in enumerate(sources[:10]):
        raw=str(item.get('text') or '').strip()
        if not raw:
            continue
        sentences=[part.strip() for part in re.split(r'(?<=[.!?。])\s+|\n+',raw) if part.strip()]
        sentences=[part for part in sentences if len(part)>=12]
        if not sentences and len(raw)>=12:
            sentences=[raw]
        if sentences:
            records.append((source_idx,sentences))
    if not records:
        raise ValueError('분석 가능한 학생부 구절이 없습니다')

    # One opening and one concluding excerpt from each record, within 14 total.
    # Later sentences frequently describe collaboration, feedback and improvement.
    chosen=[]
    for idx,parts in records:
        chosen.append((idx,parts[0]))
    for idx,parts in records:
        if len(chosen)>=14:
            break
        if len(parts)>1:
            chosen.append((idx,parts[-1]))
    # Add a middle excerpt where space permits so multi-step actions aren't lost.
    def category_priority(record):
        idx, parts = record
        category = str(sources[idx].get('source') or '').lower()
        if any(x in category for x in ('행동', '종합')):
            return 0
        if any(x in category for x in ('자율', '자치', '동아리')):
            return 1
        return 2
    for idx,parts in sorted(records,key=category_priority):
        if len(chosen)>=14:
            break
        if len(parts)>2:
            chosen.append((idx,parts[len(parts)//2]))

    result=[]
    seen=set()
    for idx,part in chosen:
        excerpt=part[:210].strip()
        key=(idx,excerpt)
        if len(excerpt)<12 or key in seen:
            continue
        seen.add(key)
        result.append({'n':len(result),'i':idx,'t':excerpt})
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
    for row in rows[:16]:
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
    facts=facts[:10]
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
