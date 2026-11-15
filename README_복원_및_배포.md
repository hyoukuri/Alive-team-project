# SEEDU:ON 원본 화면 + 로그인 복원판

이 패키지는 사용자가 직접 업로드한 `Alive-team-project-main.zip`을 기준으로 수정했습니다.
로그인/회원가입, 내 기록 저장, 원래의 홈/입력/분석/로드맵 화면과 Python 백엔드를 그대로 보존했습니다.

## 수정한 곳
- `frontend/seedu-fixes.css` 누락 해결: 기존 `index.html`이 참조했지만 파일이 없었습니다.
- 5대 역량 레이더 그래프는 왼쪽, 점수 카드 5개는 오른쪽에 표시되도록 CSS 추가.
- 학과 3개 평가 상세를 기본 펼침 상태로 복구. N/E는 0점으로 바꾸지 않음.
- 기존 `frontend/script.js`, `accounts.py`, `storage.py`, `semantic_engine.py`, `rubric_engine.py` 등 원본 유지.
- `frontend/vercel.json`, 최상위 `vercel.json`, `render.yaml` 추가/정리.

## GitHub 업로드
압축파일 바깥 폴더가 아니라 그 **안의 파일과 폴더**를 저장소 최상위에 업로드합니다.
`frontend/`와 `accounts.py`, `storage.py`, `ai_semantic.py`, `full_record_analysis.py`, `rubric_engine.py`, `rubric_v2.py`, `semantic_engine.py`까지 빠짐없이 업로드합니다.

## Vercel
- Framework Preset: Other
- Root Directory: `frontend` (권장, 폴더 안에 `vercel.json` 포함)
- Build Command: 비움 / Output Directory: 비움
- Branch: main
- Vercel `/api/*`는 Render `/api/*`로 프록시되어 로그인 쿠키가 같은 사이트에서 처리됩니다.
- 대안: Root Directory `./`를 설정하면 최상위 `vercel.json` 사용 (둘 중 하나만 선택).

## Render
- Root Directory: 공란
- Build Command: `pip install -r requirements.txt`
- Start Command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
- Env: `OPENAI_API_KEY`, `OPENAI_MODEL` 및 **기존** `DATABASE_URL` 유지
- `/health`로 API 상태 확인 가능

## 꼭 확인
- 기존 계정과 기록을 유지하려면 예전에 쓰던 Postgres `DATABASE_URL`을 절대로 바꾸지 마세요.
- 이 버전은 원본 코드에 근거한 복구본입니다. 실제 OpenAI API 요청과 배포 서버 연결은 배포 후 직접 확인해야 합니다.
- 새로 첨가한 루브릭은 아니며, 기존 분석 로직의 학과 추천 정확도는 별도 개선이 필요할 수 있습니다.
- 로드맵은 원본 `rubric_engine.py`에 3개 추천 탐구활동이 구현되어 있습니다. 현재는 규칙/템플릿 기반입니다.
