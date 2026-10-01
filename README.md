# 카카오 로그인 방명록 (FastAPI + SQLite)

![version](https://img.shields.io/badge/version-v4.0-blue)

카카오 OAuth 2.0 로그인 기반의 방명록 웹 서비스입니다.

- **조회**: 누구나 가능
- **작성**: 카카오 로그인한 사용자만 가능
- **설정**: 카카오 API Key 등은 `.env` 파일로 관리

## 버전 관리

현재 버전: **v4.0**

### 기본 기능 (v1.0)

- 카카오 OAuth 2.0 로그인 / 로그아웃 (세션 기반)
- 방명록 **작성**(로그인 필요) / **조회**(누구나)
- 사용자 정보(닉네임, 프로필 이미지, 가입일) 저장 및 표시
- `.env` 기반 설정 관리, SQLite 저장

### 버전별 추가 기능

| 버전 | 추가된 기능 | 비고 |
|------|-------------|------|
| **v1.0** | 카카오 로그인, 방명록 작성/조회 | 최초 릴리스 |
| **v2.0** | 게시글 **반응**(👍 좋아요 / 👎 싫어요 / 🙏 감사해요), **댓글** 작성/삭제, **Docker 배포** 지원(Dockerfile, docker-compose) 및 EC2 배포 가이드 | 반응은 사용자당 글마다 1개(토글), 댓글 삭제는 본인만 |
| **v3.0** | 본인이 작성한 **게시글 삭제** 기능 (글 삭제 시 해당 글의 반응·댓글도 함께 삭제) | 작성자 본인만 삭제 가능 |
| **v4.0** | **내 정보 등록/변경**(표시 이름, 자기소개), **관리자 페이지**(회원 목록/삭제), **관리자 권한 부여·해제** | 최초 관리자는 `.env`의 `ADMIN_KAKAO_IDS`로 지정 |

> 참고: 댓글 삭제(본인만)는 v2.0부터 제공됩니다. v3.0에서는 게시글 자체의 삭제가 추가되었습니다.

> **v4.0 업그레이드 시 주의**: `users` 테이블에 컬럼이 추가되어, 기존 DB를 사용 중이라면 마이그레이션이 필요합니다. 아래 [8. 기존 DB 업그레이드](#8-기존-db-업그레이드-v4-마이그레이션) 참고.

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
ADMIN_KAKAO_IDS=카카오ID1,카카오ID2
```

- `SESSION_SECRET_KEY`는 아래 명령으로 랜덤 값을 생성할 수 있습니다.
  ```powershell
  python -c "import secrets; print(secrets.token_urlsafe(48))"
  ```
- `ADMIN_KAKAO_IDS`는 **최초 관리자**로 지정할 카카오 사용자 ID입니다. 쉼표로 여러 명 지정할 수 있으며, 비워두면 관리자가 없습니다. 여기 적힌 ID로 로그인하면 자동으로 관리자 권한이 부여됩니다. 이후에는 관리자 페이지에서 다른 회원을 관리자로 지정할 수 있습니다.
  - 본인의 카카오 ID는 한 번 로그인한 뒤 DB의 `users.kakao_id` 값에서 확인하거나, 카카오 로그인 사용자 정보(`id`)로 알 수 있습니다.

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
- 본인이 작성한 **게시글**은 삭제할 수 있습니다. (글을 삭제하면 그 글의 댓글과 반응도 함께 삭제됩니다)
- 상단 **내 정보**에서 표시 이름과 자기소개를 등록/변경할 수 있습니다. 표시 이름을 지정하면 방명록에 카카오 닉네임 대신 표시됩니다.
- 관리자는 상단 **관리자** 메뉴에서 회원 목록을 보고, 회원을 삭제하거나 다른 회원에게 관리자 권한을 부여/해제할 수 있습니다.
- 로그인하지 않아도 방명록 목록, 반응 수, 댓글은 모두 볼 수 있습니다. (작성/반응만 로그인 필요)

### 관리자 지정 방법

1. `.env`의 `ADMIN_KAKAO_IDS`에 최초 관리자의 카카오 ID를 적습니다.
2. 해당 계정으로 카카오 로그인하면 자동으로 관리자가 됩니다.
3. 상단 **관리자** 메뉴 → 회원 목록에서 다른 회원의 **관리자 지정** 버튼으로 권한을 부여할 수 있습니다.
   - 본인의 관리자 권한 해제와 본인 계정 삭제는 안전을 위해 차단되어 있습니다.

## API 엔드포인트

| Method | Path                     | 설명                    | 인증     |
|--------|--------------------------|-------------------------|----------|
| GET    | `/`                      | 방명록 페이지(HTML)     | 불필요   |
| GET    | `/api/entries`           | 방명록 목록(JSON)       | 불필요   |
| GET    | `/api/entries/{id}`      | 방명록 단건(JSON)       | 불필요   |
| POST   | `/api/entries`           | 방명록 작성(JSON, form) | **필요** |
| POST   | `/entries`               | 방명록 작성(HTML 폼)    | **필요** |
| POST   | `/entries/{id}/delete`   | 방명록 삭제(본인만)     | **필요** |
| POST   | `/entries/{id}/react`    | 반응 토글(좋아요/싫어요/감사해요) | **필요** |
| POST   | `/entries/{id}/comments` | 댓글 작성               | **필요** |
| POST   | `/comments/{id}/delete`  | 댓글 삭제(본인만)       | **필요** |
| GET    | `/me`                    | 내 정보 페이지          | **필요** |
| POST   | `/me`                    | 내 정보 등록/변경       | **필요** |
| GET    | `/admin`                 | 관리자 회원 관리 페이지 | **관리자** |
| POST   | `/admin/members/{id}/role`   | 관리자 권한 부여/해제 | **관리자** |
| POST   | `/admin/members/{id}/delete` | 회원 삭제           | **관리자** |
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

## 8. 기존 DB 업그레이드 (v4 마이그레이션)

v4.0에서 `users` 테이블에 `display_name`, `bio`, `is_admin` 컬럼이 추가되었습니다. **v3.0 이하에서 쓰던 DB가 이미 있다면** 아래 스크립트로 컬럼을 추가해야 합니다. (신규로 시작하는 경우에는 자동 생성되므로 불필요합니다.)

**로컬**

```powershell
python migrate_v4.py
```

**Docker(EC2) 환경** — 컨테이너 내부의 DB(`/data/guestbook.db`)에 적용합니다.

```bash
git pull origin main

# 컨테이너 안에서 마이그레이션 실행 (이미지에 migrate_v4.py가 없다면 아래 "대안" 참고)
docker compose run --rm -e DATABASE_URL=sqlite:////data/guestbook.db web python migrate_v4.py

# 재배포
docker compose up -d --build
```

- 스크립트는 이미 컬럼이 있으면 "변경 없음"을 출력하므로 여러 번 실행해도 안전합니다.
- 마이그레이션 없이 실행하면 로그인/조회 시 `no such column: users.is_admin` 류의 오류가 발생합니다.

> 대안: 테스트 단계라 데이터가 중요하지 않다면, 볼륨을 비우고(`docker compose down` 후 볼륨 삭제) 새로 시작하면 최신 스키마로 자동 생성됩니다. 단, 기존 방명록 데이터는 사라집니다.

## 참고

- 이 프로젝트는 세션 쿠키 기반 로그인을 사용합니다. 운영 환경에서는 HTTPS 사용과 함께 `SESSION_SECRET_KEY`를 안전하게 관리하세요.
- `.env`와 `*.db`는 `.gitignore`에 포함되어 있어 저장소에 커밋되지 않습니다. 마찬가지로 `.dockerignore`를 통해 이미지에도 포함되지 않습니다.
