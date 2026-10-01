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
- 각 글에 **좋아요 👍 / 싫어요 👎 / 감사해요 🙏** 반응을 남길 수 있습니다. 같은 반응을 다시 누르면 취소되고, 다른 반응을 누르면 변경됩니다(사용자당 글마다 1개).
- 각 글에 **댓글**을 작성할 수 있으며, 본인이 작성한 댓글은 삭제할 수 있습니다.
- 로그인하지 않아도 방명록 목록, 반응 수, 댓글은 모두 볼 수 있습니다. (작성/반응만 로그인 필요)

## API 엔드포인트

| Method | Path                     | 설명                    | 인증     |
|--------|--------------------------|-------------------------|----------|
| GET    | `/`                      | 방명록 페이지(HTML)     | 불필요   |
| GET    | `/api/entries`           | 방명록 목록(JSON)       | 불필요   |
| GET    | `/api/entries/{id}`      | 방명록 단건(JSON)       | 불필요   |
| POST   | `/api/entries`           | 방명록 작성(JSON, form) | **필요** |
| POST   | `/entries`               | 방명록 작성(HTML 폼)    | **필요** |
| POST   | `/entries/{id}/react`    | 반응 토글(좋아요/싫어요/감사해요) | **필요** |
| POST   | `/entries/{id}/comments` | 댓글 작성               | **필요** |
| POST   | `/comments/{id}/delete`  | 댓글 삭제(본인만)       | **필요** |
| GET    | `/auth/kakao/login`      | 카카오 로그인 시작      | 불필요   |
| GET    | `/auth/kakao/callback`   | 카카오 OAuth 콜백       | 불필요   |
| GET    | `/auth/logout`           | 로그아웃                | 불필요   |

- 대화형 API 문서: `http://localhost:8000/docs`

## 6. AWS EC2 + Docker 배포

GitHub에 올린 코드를 EC2에서 받아 Docker 이미지로 빌드하고 컨테이너로 실행하는 방법입니다.

### 6-1. 사전 준비 (EC2)

1. EC2 인스턴스(Amazon Linux 2023 또는 Ubuntu)에 SSH 접속합니다.
2. Docker를 설치합니다.

   **Amazon Linux 2023**
   ```bash
   sudo dnf update -y
   sudo dnf install -y docker git
   sudo systemctl enable --now docker
   sudo usermod -aG docker $USER   # 재로그인 후 sudo 없이 docker 사용
   ```

   **Ubuntu**
   ```bash
   sudo apt update && sudo apt install -y docker.io git
   sudo systemctl enable --now docker
   sudo usermod -aG docker $USER   # 재로그인 후 sudo 없이 docker 사용
   ```

3. **보안 그룹(인바운드 규칙)** 에서 접속 포트를 엽니다.
   - 유형: 사용자 지정 TCP, 포트: `8000`, 소스: `0.0.0.0/0` (또는 허용할 IP 대역)
   - SSH(22)는 본인 IP로만 열어두는 것을 권장합니다.

### 6-2. 코드 내려받기

```bash
git clone https://github.com/00MunhH/test_guestbook.git
cd test_guestbook
```

### 6-3. .env 작성

저장소에는 `.env`가 포함되지 않으므로 EC2에서 직접 생성합니다.

```bash
cp .env.example .env
nano .env   # 값 입력 후 저장
```

- `KAKAO_REST_API_KEY`: 카카오 REST API 키
- `KAKAO_REDIRECT_URI`: **EC2 공인 주소로 변경**
  ```
  http://<EC2_퍼블릭_IP>:8000/auth/kakao/callback
  ```
- `SESSION_SECRET_KEY`: 긴 랜덤 문자열
  ```bash
  python3 -c "import secrets; print(secrets.token_urlsafe(48))"
  ```

> 중요: 카카오 개발자 콘솔의 **Redirect URI**와 **Web 플랫폼 도메인**에도 위 EC2 주소(`http://<EC2_퍼블릭_IP>:8000/...`)를 추가해야 로그인이 동작합니다.

### 6-4. 이미지 빌드 & 컨테이너 실행

**방법 A — Docker 명령 직접 사용**

```bash
# 이미지 빌드
docker build -t guestbook:latest .

# 컨테이너 실행 (DB는 호스트 볼륨에 보존)
docker run -d \
  --name guestbook \
  -p 8000:8000 \
  --env-file .env \
  -e DATABASE_URL=sqlite:////data/guestbook.db \
  -v guestbook_data:/data \
  --restart unless-stopped \
  guestbook:latest
```

**방법 B — docker compose 사용 (권장)**

```bash
docker compose up -d --build
```

### 6-5. 외부에서 접속

브라우저에서 아래 주소로 접속합니다.

```
http://<EC2_퍼블릭_IP>:8000
```

- 접속이 안 되면 다음을 확인하세요.
  - EC2 보안 그룹에서 8000 포트 인바운드가 열려 있는지
  - 컨테이너가 떠 있는지: `docker ps`
  - 앱이 `0.0.0.0:8000`에 바인딩됐는지 (Dockerfile의 CMD가 처리)

### 6-6. 운영 명령

```bash
docker ps                 # 실행 중 컨테이너 확인
docker logs -f guestbook  # 로그 실시간 확인
docker stop guestbook     # 중지
docker start guestbook    # 시작
docker rm -f guestbook    # 삭제 (볼륨 guestbook_data는 유지됨)

# 코드 업데이트 반영
git pull
docker compose up -d --build   # 또는 docker build 후 run 재실행
```

> 데이터 보존: SQLite DB는 `guestbook_data` 볼륨(컨테이너 내부 `/data`)에 저장되어 컨테이너를 재생성해도 유지됩니다.

> HTTPS/도메인: 운영에서는 Nginx 리버스 프록시 + Let's Encrypt로 443 포트에 HTTPS를 구성하고, 카카오 Redirect URI도 `https://도메인/...` 형태로 등록하는 것을 권장합니다.

## 참고

- 이 프로젝트는 세션 쿠키 기반 로그인을 사용합니다. 운영 환경에서는 HTTPS 사용과 함께 `SESSION_SECRET_KEY`를 안전하게 관리하세요.
- `.env`와 `*.db`는 `.gitignore`에 포함되어 있어 저장소에 커밋되지 않습니다. 마찬가지로 `.dockerignore`를 통해 이미지에도 포함되지 않습니다.
