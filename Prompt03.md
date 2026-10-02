# Prompt03 — AWS ECS + RDS/S3/Redis 확장형 배포 프롬프트

> ECS(Fargate)에서 **여러 태스크로 수평 확장**할 수 있도록, 로컬 상태 의존성을 모두 관리형 서비스로
> 전환하기 위한 프롬프트입니다. 이 작업은 **애플리케이션 코드 구조 변경이 필요**합니다.
>
> 전환 요약:
> - DB: SQLite → **Amazon RDS(PostgreSQL)**
> - 파일 업로드: 로컬 디스크 → **Amazon S3**
> - 실시간(SSE): in-memory pub/sub → **ElastiCache(Redis) Pub/Sub**
> - 스키마 관리: 앱 시작 시 ALTER 자동 마이그레이션 → **Alembic**

---

현재 FastAPI + SQLite 방명록/소셜 프로젝트를 AWS ECS(Fargate)에서 **수평 확장 가능**하도록 리팩터링하고 배포 구성을 만들어줘. 설명과 진행은 한국어로, 단계별로 나눠 각 단계마다 스모크 테스트 → 커밋/푸시해줘. 기존 기능(방명록/댓글/반응/알림/친구/채팅/멘션/읽음)은 동작이 바뀌지 않게 유지하는 게 목표야.

## 단계별 작업

### 1단계 — DB를 PostgreSQL(RDS)로 전환
- `requirements.txt`에 Postgres 드라이버 추가(`psycopg[binary]` 등). SQLAlchemy는 `DATABASE_URL`만 교체(`postgresql+psycopg://...`).
- SQLite 전용 코드 제거/일반화: `connect_args={"check_same_thread": False}`는 sqlite일 때만 적용(이미 분기되어 있으면 유지), SQLite 전용 자동 마이그레이션(ALTER 방식)·`_relax_reactions_entry_nullable` 등은 **Alembic으로 대체**.
- Alembic 도입: `alembic init`, 현재 모델 기준 초기 마이그레이션 생성, 앱 시작 시 `create_all` 대신 Alembic 기반으로 스키마 관리. 로컬에서 Postgres(docker-compose에 postgres 서비스 추가)로 전체 기능 스모크 테스트.
- 로컬 개발은 여전히 SQLite로도 돌아가게 하려면 분기 처리(선택).

### 2단계 — 파일 업로드를 S3로 전환
- `boto3` 추가. `chat.py`의 파일 저장/다운로드를 로컬 디스크 → **S3 업로드/presigned URL(또는 스트리밍 다운로드)**로 변경.
- 설정 추가: `S3_BUCKET`, `AWS_REGION`(자격증명은 ECS Task Role로 주입, 코드에 키 하드코딩 금지).
- 멤버만 접근 가능한 권한 체크는 유지(앱에서 멤버 확인 후 presigned URL 발급 또는 프록시 다운로드).
- 10MB 제한, 원본 파일명 보존 로직 유지. 로컬 테스트는 moto 또는 MinIO로.

### 3단계 — 실시간(SSE)을 Redis Pub/Sub으로 전환
- `redis`(async) 추가. `app/events.py`의 in-memory `EventBroker`를 **Redis Pub/Sub 기반**으로 교체해, 여러 태스크(워커) 간 이벤트가 공유되게 해줘.
- 설정 추가: `REDIS_URL`. 댓글/채팅 SSE 모두 Redis 채널을 통해 브로드캐스트되도록. 로컬 테스트는 docker-compose의 redis 서비스로.

### 4단계 — ECS 배포 리소스 & 가이드
- `deploy/ecs/`에 Fargate `task-definition.json`(포트 8000, awslogs, 환경변수/시크릿은 Secrets Manager/SSM로 주입), 서비스는 **desired count 2+**로 수평 확장, ALB 타깃 그룹(헬스체크 `/`).
- Task Role 권한: S3 버킷 접근, (필요 시) Secrets 읽기.
- 네트워크: RDS(5432)·ElastiCache(6379)는 ECS 태스크 보안그룹에서만 접근 허용(프라이빗 서브넷 권장).
- 배포 순서 가이드(CLI 예시): ECR 빌드/푸시 → RDS/ElastiCache/S3 생성 → Secrets 등록 → Task Definition 등록 → 서비스 생성/업데이트 → Alembic 마이그레이션 실행 방법(일회성 태스크 또는 엔트리포인트) → 카카오 Redirect URI를 ALB/도메인으로 등록.
- SSE/ALB 주의: 유휴 타임아웃 늘리기, `proxy_buffering`/`X-Accel-Buffering` 고려.

## 산출물
- 변경된 코드(DB/S3/Redis), Alembic 마이그레이션, docker-compose(로컬: postgres+redis+minio), ECS 리소스 파일, 배포 README.
- 각 단계는 독립 커밋 + 태그. 기능 회귀가 없는지 단계마다 스모크 테스트 결과를 보여줘.

## 중요 원칙
- 비밀값(DB 비밀번호, 세션 키, 카카오 키)은 코드/이미지에 넣지 말고 Secrets Manager/SSM 또는 ECS 환경변수로 주입.
- 기존 사용자 데이터 마이그레이션(SQLite→RDS)이 필요하면 별도 이관 스크립트도 제안해줘.

---

## 참고: 왜 코드 구조 변경이 필요한가
- **SQLite → RDS**: SQLAlchemy URL 교체만으로 대부분 되지만, SQLite 전용 자동 마이그레이션을 Alembic으로 바꿔야 한다.
- **로컬 파일 → S3**: 업로드/다운로드 코드가 로컬 디스크에 묶여 있어 S3 API로 재작성 필요.
- **in-memory SSE → Redis**: 현재 pub/sub은 단일 프로세스 전제라, 태스크 2개 이상이면 이벤트가 공유되지 않는다. Redis로 교체해야 수평 확장에서 실시간이 동작한다.
- 이 세 가지를 끝내야 ECS에서 **태스크를 2개 이상으로 안전하게 확장**할 수 있다.
