# app03 — 카카오 로그인 방명록 (ECS + RDS/S3/Redis 확장형)

`app/`(SQLite 단일 프로세스) 프로젝트를 **AWS ECS(Fargate)에서 여러 태스크로 수평 확장**할 수 있도록
리팩터링한 구성입니다. 로컬 상태 의존성을 모두 관리형 서비스로 전환했습니다.

| 항목 | app(원본)/app02 | app03 |
|------|------------------|-------|
| DB | SQLite 파일 | **PostgreSQL (RDS)** |
| 파일 업로드 | 로컬 디스크/EFS | **S3** |
| 실시간(SSE) | in-memory pub/sub | **Redis Pub/Sub (ElastiCache)** |
| 스키마 관리 | 앱 시작 시 ALTER 자동 | **Alembic** |
| 확장 | 태스크 1개 | **태스크 N개 수평 확장** |

## 코드 변경 요약 (원본 대비)
- `config.py` — DATABASE_URL(Postgres 기본), S3_*, REDIS_URL 설정 추가
- `database.py` — SQLite 전용 자동 마이그레이션 제거, 스키마는 Alembic이 담당 (로컬 sqlite일 때만 create_all)
- `events.py` — in-memory 브로커 → **Redis Pub/Sub** 브로커 (인터페이스 동일, 호출부 무수정)
- `storage.py` (신규) — S3 업로드 / presigned 다운로드
- `chat.py` — 파일 저장/다운로드를 로컬 디스크 → **S3**로 전환
- `alembic/` — 마이그레이션. 초기 리비전은 현재 모델 전체 생성

## 로컬 개발 (compose: 앱 + Postgres + Redis + MinIO)
```bash
cp .env.example .env   # 카카오 키 등 채우기
docker compose up -d --build
# 최초 1회 MinIO 버킷 생성 (콘솔 http://localhost:9001, minioadmin/minioadmin)
#   또는 aws cli:  aws --endpoint-url http://localhost:9000 s3 mb s3://guestbook
# http://localhost:8000
```
> 컨테이너 시작 시 `entrypoint.sh`가 `alembic upgrade head`를 실행해 스키마를 만듭니다.

## ECS 배포 순서

### 1) 관리형 리소스 생성
- **RDS PostgreSQL** 생성 (프라이빗 서브넷 권장)
- **ElastiCache Redis** 생성
- **S3 버킷** 생성
- 보안 그룹: ECS 태스크 SG → RDS(5432) / Redis(6379) 인바운드 허용

### 2) 비밀값/설정 등록 (SSM 파라미터)
```bash
aws ssm put-parameter --name /guestbook/DATABASE_URL --type SecureString \
  --value "postgresql+psycopg://<user>:<pass>@<rds-endpoint>:5432/guestbook"
aws ssm put-parameter --name /guestbook/SESSION_SECRET_KEY --type SecureString \
  --value "$(python -c 'import secrets;print(secrets.token_urlsafe(48))')"
aws ssm put-parameter --name /guestbook/KAKAO_REST_API_KEY --type SecureString --value "..."
aws ssm put-parameter --name /guestbook/KAKAO_CLIENT_SECRET --type SecureString --value " "
aws ssm put-parameter --name /guestbook/ADMIN_PASSWORD --type SecureString --value "..."
```

### 3) Task Role 권한
- S3 버킷 `get/put-object` 권한, (secrets 사용 시) SSM 읽기 권한을 Task Role에 부여
- 코드에 AWS 키를 넣지 않음 (Task Role로 자동 주입)

### 4) 이미지 빌드/푸시 & 서비스
```bash
aws ecr create-repository --repository-name guestbook-app03
# build & push (app02 README와 동일 패턴)
aws logs create-log-group --log-group-name /ecs/guestbook-app03
# task-definition.json의 <...> 치환 후:
aws ecs register-task-definition --cli-input-json file://deploy/ecs/task-definition.json

aws ecs create-service \
  --cluster guestbook \
  --service-name guestbook-app03 \
  --task-definition guestbook-app03 \
  --desired-count 2 \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[<SUBNET_A>,<SUBNET_B>],securityGroups=[<ECS_SG>],assignPublicIp=DISABLED}" \
  --load-balancers "targetGroupArn=<TG_ARN>,containerName=web,containerPort=8000"
```

### 5) 마이그레이션
- 각 태스크 시작 시 `entrypoint.sh`가 `alembic upgrade head`를 실행 (멱등).
- 대량 배포 시엔 **일회성 마이그레이션 태스크**를 먼저 돌리는 것을 권장:
  `aws ecs run-task ... --overrides '{"containerOverrides":[{"name":"web","command":["alembic","upgrade","head"]}]}'`

### 6) 카카오/ALB
- ALB(443) → 타깃그룹(8000), 헬스체크 `/`
- SSE를 위해 ALB **유휴 타임아웃을 60s 이상**으로 늘리기
- 카카오 Redirect URI = `https://<도메인>/auth/kakao/callback`

## 수평 확장이 되는 이유
- DB는 공유 RDS, 파일은 공유 S3, 실시간은 Redis Pub/Sub으로 **모든 태스크가 같은 상태를 공유**하므로
  desired count를 2 이상으로 올려도 데이터·실시간 이벤트가 일관됩니다.

## 기존 데이터 이관 (SQLite → RDS)
- 소규모면 간단한 파이썬 스크립트로 SQLite를 읽어 ORM으로 RDS에 재삽입하는 방식을 권장합니다.
  (요청 시 이관 스크립트를 제공할 수 있습니다.)
