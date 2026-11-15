# SEEDU:ON — 필수 파일만 정리한 배포본

기준: 기존 로그인·회원가입·DB 저장·원래 분석 화면과 레이더 그래프를 보존한 복원 코드.
이번 정리는 중복 파일과 사용하지 않는 임시 파일을 제거한 것입니다.
AI 분석 품질 및 실서버 동작을 새롭게 보증하는 것은 아닙니다.

## 파일 구성
- `main.py`: FastAPI 서버, 분석 및 로드맵 API
- `accounts.py`, `storage.py`: 로그인·회원가입 및 기록 저장
- `ai_semantic.py`, `semantic_engine.py`, `full_record_analysis.py`: 세특 분석
- `rubric_engine.py`, `rubric_v2.py`: 역량·학과 평가
- `frontend/index.html`, `script.js`, `style.css`, `seedu-fixes.css`: 원래 웹 화면
- `frontend/vercel.json`: Vercel API 경로 설정
- `requirements.txt`, `render.yaml`: Render 실행 설정
- `.env.example`: 환경 변수 예시 (실제 비밀 키 아님)

## 배포 설정
Render: Root Directory 비움 / Branch main
Build: `pip install -r requirements.txt`
Start: `uvicorn main:app --host 0.0.0.0 --port $PORT`
Environment: 기존 `OPENAI_API_KEY`, `OPENAI_MODEL`, `DATABASE_URL` 유지.
기존 계정·저장 기록이 필요하다면 DATABASE_URL을 절대 지우지 마세요.

Vercel: Root Directory `frontend` / Framework Other / Branch main
별도의 Build Command, Output Directory는 설정하지 마세요.
Vercel의 Root Directory를 `./`로 두면 이 구조와 맞지 않습니다.

## GitHub 업로드
압축을 풀고 **바깥 폴더가 아닌 안쪽 파일·폴더 전체**를 GitHub 저장소 최상위에 업로드하세요.
기존 파일과 같은 경로는 덮어써지지만 **이름이 다른 옛 파일은 자동 삭제되지 않습니다.**
GitHub에서 아래와 같은 구버전 중복 파일은 별도로 정리해야 합니다.
- 최상위 `index.html`, `script.js`, `style.css`, `seedu-fixes.css`, `vercel.json`
- `apply_main_patch.py`, `ai_reviewer.py` (현재 실행 경로에서 참조되지 않음)
- 이전 임시 적용 안내 문서들
`frontend/` 아래의 네 화면 파일과 `frontend/vercel.json`은 유지하세요.
삭제 전에 저장소 백업을 권장합니다.

## 검증 범위
Python 파일 문법, JavaScript 문법, 필수 파일 구성 및 ZIP 무결성 검증.
실제 Render·Vercel 배포와 OpenAI API, 로그인 DB 연결은 별도 확인 필요.
