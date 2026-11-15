"""Run once in your repository: python apply_main_patch.py

Backs up main.py and modifies only the semantic analysis call and failure handling.
Requires exact main.py structure previously provided by the user.
"""
from pathlib import Path
p = Path('main.py')
s = p.read_text(encoding='utf-8')
if 'from full_record_analysis import analyze_all_sources' in s:
    raise SystemExit('이미 적용되었습니다.')
old = 'from ai_semantic import request_semantics'
assert s.count(old) == 1, 'main.py import 구조가 달라서 중단했습니다.'
s = s.replace(old, old + '\nfrom full_record_analysis import analyze_all_sources')
old = '''        raw = request_semantics(sources, candidates)
        result = build_analysis(raw, req.records, req.text, req.grade, sources, candidates)'''
new = '''        result = analyze_all_sources(sources, req.records, req.text, req.grade, candidates)'''
assert s.count(old) == 1, 'main.py 분석 호출 구조가 달라서 중단했습니다.'
s = s.replace(old, new)
old = '''        return _preview(req, 'rate_limited' if status == 429 else type(exc).__name__)
    finally:'''
new = '''        # Do not misrepresent a partially processed record as a completed score.
        raise HTTPException(
            status_code=503,
            detail={
                'code': 'FULL_ANALYSIS_INCOMPLETE',
                'message': '전체 세특 분석이 완료되지 않았습니다. 잠시 후 다시 시도해 주세요.',
                'retryable': status in (429, 500, 502, 503, 504),
            },
        ) from exc
    finally:'''
assert s.count(old) == 1, 'main.py 예외 처리 구조가 달라서 중단했습니다.'
s = s.replace(old, new)
# An AI-unavailable cooldown must not silently return a partial rule preview.
old = '''    if limited:
        return _preview(req, 'free_model_cooldown')'''
new = '''    if limited:
        raise HTTPException(status_code=503, detail={
            'code': 'AI_COOLDOWN',
            'message': 'AI 사용량 제한으로 전체 세특 분석을 시작할 수 없습니다. 잠시 후 다시 시도해 주세요.',
        })'''
assert s.count(old) == 1, 'main.py cooldown 구조가 달라서 중단했습니다.'
s = s.replace(old, new)
old = "        return _preview(req, 'ai_busy_or_unavailable')"
new = "        raise HTTPException(status_code=503, detail='전체 세특 분석 대기 시간이 초과되었습니다. 다시 시도해 주세요.')"
assert s.count(old) == 1, 'main.py 대기 처리 구조가 달라서 중단했습니다.'
s = s.replace(old, new)
p.with_suffix('.py.before_full_analysis.bak').write_text(p.read_text(encoding='utf-8'), encoding='utf-8')
p.write_text(s, encoding='utf-8')
print('main.py 수정 완료. 원본 백업: main.py.before_full_analysis.bak')
