# 카카오 로그인 방명록 (FastAPI + SQLite)

카카오 OAuth 2.0 로그인 기반의 방명록 웹 서비스입니다.

- **조회**: 누구나 가능
- **작성**: 카카오 로그인한 사용자만 가능
- **설정**: 카카오 API Key 등은 `.env` 파일로 관리

## 기술 스택

- Python / FastAPI
- SQLite (SQLAlchemy 2.0 ORM)
- 카카오 REST API (OAuth 2.0)
- Jinja2 (HTML 렌더링), Starlette SessionMiddleware (세션 로그인)

## 프로젝트 구조

```
.
├── app/
│   ├── __init__.py
│   ├── main.py          # FastAPI 진입점 (미들웨어/라우터/홈)
│   ├── config.py        # .env 설정 로딩
│   ├── database.py      # SQLite 엔진/세션/Base
│   ├── models.py        # User, GuestbookEntry 모델
│   ├── auth.py          # 카카오 OAuth 로그인/콜백/로그아웃
│   ├── guestbook.py     # 방명록 조회/작성 라우터
│   └── templates/
│       └── index.html   # 방명록 페이지
├── requirements.txt
├── .env.example
└── README.md
```

## 1. 카카오 애플리케이션 설정

1. [카카오 개발자 사이트](https://developers.kakao.com)에 로그인 후 **내 애플리케이션 > 애플리케이션 추가하기**로 앱을 생성합니다.
2. **앱 키 > REST API 키**를 복사합니다. (`.env`의 `KAKAO_REST_API_KEY`에 사용)
3. **카카오 로그인 > 활성화 설정**을 ON으로 변경합니다.
4. **카카오 로그인 > Redirect URI**에 다음을 등록합니다.
   ```
   http://localhost:8000/auth/kakao/callback
   ```
5. **카카오 로그인 > 동의항목**에서 **닉네임**, **프로필 사진**을 사용 설정합니다.
6. (선택) **보안 > Client Secret**을 사용한다면 발급 후 `.env`의 `KAKAO_CLIENT_SECRET`에 넣습니다. 사용하지 않으면 비워둡니다.

## 2. 설치

Python 3.10 이상을 권장합니다.

```powershell
# 가상환경 생성 및 활성화 (Windows PowerShell)
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 패키지 설치
pip install -r requirements.txt
```

> macOS / Linux는 `source .venv/bin/activate`로 활성화합니다.

## 3. 환경변수 설정

`.env.example`을 복사해 `.env`를 만들고 값을 채웁니다.

```powershell
Copy-Item .env.example .env
```

```dotenv
KAKAO_REST_API_KEY=발급받은_REST_API_키
KAKAO_CLIENT_SECRET=사용_시_입력_아니면_비움
KAKAO_REDIRECT_URI=http://localhost:8000/auth/kakao/callback
SESSION_SECRET_KEY=임의의_긴_랜덤_문자열
DATABASE_URL=sqlite:///./guestbook.db
```

- `SESSION_SECRET_KEY`는 아래 명령으로 랜덤 값을 생성할 수 있습니다.
  ```powershell
  python -c "import secrets; print(secrets.token_urlsafe(48))"
  ```

## 4. 실행

```powershell
uvicorn app.main:app --reload
```

- 브라우저에서 `http://localhost:8000` 접속
- DB(`guestbook.db`)는 최초 실행 시 자동 생성됩니다.

## 5. 사용 방법

- 우측 상단 **카카오 로그인** 버튼으로 로그인합니다.
- 로그인 후 방명록 작성 폼이 나타나며, 글을 등록할 수 있습니다.
- 로그인하지 않아도 방명록 목록은 볼 수 있습니다.

## API 엔드포인트

| Method | Path                     | 설명                    | 인증     |
|--------|--------------------------|-------------------------|----------|
| GET    | `/`                      | 방명록 페이지(HTML)     | 불필요   |
| GET    | `/api/entries`           | 방명록 목록(JSON)       | 불필요   |
| GET    | `/api/entries/{id}`      | 방명록 단건(JSON)       | 불필요   |
| POST   | `/api/entries`           | 방명록 작성(JSON, form) | **필요** |
| POST   | `/entries`               | 방명록 작성(HTML 폼)    | **필요** |
| GET    | `/auth/kakao/login`      | 카카오 로그인 시작      | 불필요   |
| GET    | `/auth/kakao/callback`   | 카카오 OAuth 콜백       | 불필요   |
| GET    | `/auth/logout`           | 로그아웃                | 불필요   |

- 대화형 API 문서: `http://localhost:8000/docs`

## 참고

- 이 프로젝트는 세션 쿠키 기반 로그인을 사용합니다. 운영 환경에서는 HTTPS 사용과 함께 `SESSION_SECRET_KEY`를 안전하게 관리하세요.
- `.env`와 `*.db`는 `.gitignore`에 포함되어 있어 저장소에 커밋되지 않습니다.
