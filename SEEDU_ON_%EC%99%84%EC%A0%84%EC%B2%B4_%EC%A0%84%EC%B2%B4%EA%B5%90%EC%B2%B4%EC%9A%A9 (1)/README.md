# SEEDU:ON — 독립형 통합 프로젝트

이 프로젝트는 기존 저장소의 다른 Python 모듈에 의존하지 않습니다. **기존 저장소를 백업한 뒤** 이 ZIP 안의 파일과 폴더를 GitHub 저장소 최상위에 넣으면 됩니다. GitHub 저장소 자체는 삭제할 필요가 없습니다.

## 구성

- `main.py` — FastAPI 백엔드. `/health`, `/analyze`, `/roadmap` 제공
- `frontend/index.html`, `style.css`, `script.js`, `config.js` — 웹 화면
- `requirements.txt`, `render.yaml`, `vercel.json` — 배포 파일
- `.env.example` — 환경 변수 양식. 실제 API 키를 GitHub에 올리지 마세요.
- `tests/` — 최소 API 검증

## 배포

1. GitHub에서 작업 전 기존 프로젝트를 백업 또는 브랜치로 보존합니다.
2. 저장소 최상위 파일 및 `frontend/` 폴더를 ZIP 구성으로 교체합니다. 이전 `accounts.py`, `semantic_engine.py` 등은 새 프로젝트에서 사용하지 않습니다.
3. Render: `pip install -r requirements.txt`; 시작 명령: `uvicorn main:app --host 0.0.0.0 --port $PORT`.
4. Render 환경 변수 `OPENAI_API_KEY`에 **유효한 개인 API 키**, `OPENAI_MODEL`에 사용 권한이 있는 모델명(기본 `gpt-4.1-mini`)을 지정합니다. API 키가 없거나 호출이 실패하면 **규칙 기반 참고 분석**으로 명확히 표시합니다. OpenAI API 비용이 발생할 수 있습니다.
5. Vercel: 저장소 루트 디렉터리를 프로젝트 루트(`.`)로 지정. `vercel.json`의 경로 재작성으로 `frontend/`의 정적 파일을 배포합니다. 프레임워크 프리셋은 Other, 빌드 명령 없음.
6. `frontend/config.js`의 `window.SEEDU_API_BASE`를 실제 Render 주소로 설정합니다.
7. 접속 후 입력 → 분석 → 레이더 그래프 → 전공 탐색 후보 → 진로 로드맵 → 탐구활동 TOP 3 순서로 사용합니다.

## 로컬 구동

```bash
python -m pip install -r requirements.txt
uvicorn main:app --reload
```

프론트엔드는 별도 터미널에서 `python -m http.server 5500 --directory frontend` 명령으로 실행하고 `http://localhost:5500`을 여세요. 백엔드 로컬 테스트를 위해 `frontend/config.js` URL을 `http://127.0.0.1:8000`으로 바꾸세요. `localhost` 접속은 허용된 CORS 목록에 포함됩니다.

## 중요한 기능과 한계

- 1·2학년 입력 지원. 존재하지 않는 과목이나 미이수 과목을 자동 생성하지 않습니다.
- 입력된 **모든 과목**을 근거 단위로 분리해 사용합니다. AI 모드에서 모든 배치의 검토가 실패하면 규칙 기반 참고 분석으로 표시합니다.
- 레이더 그래프는 **항상 표시**합니다. 역량 근거가 확인되지 않은 경우 N/E로 표시하며 0점으로 간주하지 않습니다.
- 학과 추천은 **탐색 후보**이며 합격 확률이나 확정 적합도 퍼센트가 아닙니다.
- 선택과목 및 심화 탐구활동 추천은 **교과 계열별 일반 로드맵 템플릿**을 사용합니다. 실제 학교 개설 과목 및 교과 단원 적합성은 확인해야 합니다.
- 서버 DB 저장과 계정 기능은 **포함하지 않습니다**. 내 기록은 해당 브라우저 localStorage에 최대 5개 저장합니다. 공유 컴퓨터에서는 분석 후 기록을 삭제하세요. 실제 분석을 위해 입력 세특은 Render/OpenAI에 전송될 수 있습니다.
- 모형 AI 평가 결과는 참고 정보이며 정량 타당성이 검증된 평가가 아닙니다.

## 오류 점검

- Render `/health`에서 `status: ok` 확인
- Vercel 브라우저 개발자 도구에서 `script.js`, `style.css` 200 확인
- CORS 문제가 나면 Render `CORS_ORIGINS`에 정확한 Vercel 도메인 추가
- API 키 오류는 `/health`의 `ai_configured`와 Render 환경 변수를 확인. 비밀 키는 화면이나 로그로 공유하지 마세요.
- `/roadmap`이 정상 응답하면 `activities`가 3개 있는지 확인
