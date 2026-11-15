"""Exhaustive, fail-closed multi-batch semantic analysis for SEEDU:ON.

Every nonempty character of every prepared source is submitted to the semantic
model exactly once (ignoring no records). No partial batch is presented as a
completed evaluation. Requires ai_semantic.py from this package.
"""
from __future__ import annotations

import logging
import os
from collections import defaultdict

from ai_semantic import request_semantics, _competency_scores
from semantic_engine import build_analysis

LOG = logging.getLogger('seedu.full_analysis')
BATCH_SIZE = 8
CHUNK_SIZE = 480  # original, unmodified text per AI excerpt; <= 550 quote validator


def _split_exact(text: str, size: int = CHUNK_SIZE) -> list[str]:
    """Partition without deleting or changing a character."""
    return [text[i:i + size] for i in range(0, len(text), size)]


def build_batches(sources: list[dict]) -> list[list[dict]]:
    pieces = []
    for original_index, source in enumerate(sources):
        content = str(source.get('text') or '')
        for part_index, part in enumerate(_split_exact(content)):
            if not part.strip():
                # Whitespace-only fragments still belong to the preceding/following
                # original text; no semantic evidence is lost, but count it below.
                pass
            pieces.append({
                'grade': source['grade'], 'source': source['source'],
                'text': part, '_original_index': original_index,
                '_part_index': part_index,
            })
    if not pieces:
        raise ValueError('분석할 세특 원문이 없습니다.')
    return [pieces[i:i+BATCH_SIZE] for i in range(0, len(pieces), BATCH_SIZE)]


def analyze_all_sources(sources: list[dict], records, text, grade, candidates,
                        *, semantic_fn=request_semantics):
    batches = build_batches(sources)
    if len(batches) > int(os.getenv('SEEDU_MAX_BATCHES', '40')):
        raise ValueError('전체 세특 분석에 필요한 구간 수가 서버 설정 한도를 초과했습니다.')

    merged_facts = []
    per_source_processed = [0] * len(sources)
    major_fact_ids = defaultdict(list)
    processed = 0
    expected_chars = sum(len(str(s.get('text') or '')) for s in sources)
    for batch_index, batch in enumerate(batches):
        # If any API request fails, propagate the error. Never score a subset.
        if any(part['text'].strip() for part in batch):
            partial = semantic_fn(batch, candidates)
        else:
            partial = {'facts': [], 'major_links': []}
        local_facts = partial.get('facts', [])
        offset = len(merged_facts)
        for fact in local_facts:
            local_index = fact['source_index']
            original_index = batch[local_index]['_original_index']
            copied = dict(fact)
            copied['source_index'] = original_index
            merged_facts.append(copied)
        for link in partial.get('major_links', []):
            name = link.get('major')
            if name not in candidates:
                continue
            for local_id in link.get('evidence_ids', []):
                if isinstance(local_id, int) and not isinstance(local_id, bool) and 0 <= local_id < len(local_facts):
                    major_fact_ids[name].append(offset + local_id)
        for part in batch:
            per_source_processed[part['_original_index']] += len(part['text'])
        processed += sum(len(part['text']) for part in batch)
        LOG.info('SEEDU full analysis progress: batch=%d/%d chars=%d/%d',
                 batch_index + 1, len(batches), processed, expected_chars)

    if processed != expected_chars or any(per_source_processed[i] != len(str(source.get('text') or '')) for i, source in enumerate(sources)):
        raise RuntimeError('전체 원문 구간 처리량 검증 실패')
    if not merged_facts:
        raise ValueError('전체 기록을 검토했지만 검증 가능한 수행 근거가 없습니다.')

    # Re-evaluate competencies over *all* verified facts. Final scoring ceilings
    # remain owned by semantic_engine.py, unchanged.
    competencies = _competency_scores(merged_facts)
    links = [{'major': name, 'evidence_ids': list(dict.fromkeys(major_fact_ids[name]))}
             for name in candidates[:3]]
    raw = {'facts': merged_facts, 'competencies': competencies, 'major_links': links}
    result = build_analysis(raw, records, text, grade, sources, candidates)
    facts_by_source = defaultdict(int)
    for fact in merged_facts:
        facts_by_source[fact['source_index']] += 1
    activity_coverage = [{
        'grade': source['grade'], 'source': source['source'],
        'input_chars': len(str(source.get('text') or '')),
        'processed_chars': per_source_processed[i],
        'verified_facts': facts_by_source[i],
        'status': 'evidence_found' if facts_by_source[i] else 'reviewed_no_verifiable_evidence',
    } for i, source in enumerate(sources)]
    result['input_coverage'] = {
        'activities_received': len(sources),
        'activities_processed': sum(x['processed_chars'] == x['input_chars'] for x in activity_coverage),
        'activities_with_verified_facts': sum(bool(x['verified_facts']) for x in activity_coverage),
        'activities': activity_coverage,
        'status': 'complete', 'input_chars': expected_chars,
        'processed_chars': processed, 'batches': len(batches),
        'grades_received': sorted({int(s['grade']) for s in sources if str(s.get('text') or '').strip()}),
        'grades_with_verified_facts': sorted({int(sources[f['source_index']]['grade']) for f in merged_facts}),
        'note': '전체 원문을 AI 검토 대상으로 전송함. 모든 활동의 의미를 완벽히 포착한다는 보장은 아님.',
    }
    return result
