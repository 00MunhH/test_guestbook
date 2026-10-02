# app02 — 카카오 로그인 방명록 (ECS + EFS 최소 구성)

현재 `app/`(SQLite 기반) 프로젝트를 **AWS ECS(Fargate)**에서 **단일 태스크 + EFS**로 운영하는 구성입니다.
애플리케이션 코드는 원본과 거의 동일하며, DB/업로드 경로를 EFS 마운트 지점(`/mnt/data`)으로 둡니다.

## ⚠️ 핵심 제약
- SQLite 파일 락 + in-memory SSE(단일 프로세스) 때문에 **태스크는 반드시 1개**(desired count = 1).
- 수평 확장이 필요하면 `app03`(RDS + S3 + Redis) 구성을 사용하세요.
- 배포 시 `maximumPercent=100`, `minimumHealthyPercent=0`으로 설정해 롤링 중 **중복 태스크가 뜨지 않도록** 합니다.

## 디렉터리
```
app02/
├── app/                      # 애플리케이션 코드 (원본과 동일)
├── Dockerfile                # /mnt/data 를 DB·업로드 경로로 사용
├── docker-compose.yml        # 로컬 실행용 (named volume = EFS 역할)
├── .env.example
└── deploy/ecs/
    └── task-definition.json  # Fargate + EFS 볼륨 마운트
```

## 로컬 실행
```bash
cp .env.example .env   # 값 채우기 (로컬은 DATABASE_URL=sqlite:///./guestbook.db 로 바꿔도 됨)
docker compose up -d --build
# http://localhost:8000
```

## ECS + EFS 배포 순서

### 1) 이미지 빌드/푸시 (ECR)
```bash
aws ecr create-repository --repository-name guestbook-app02
aws ecr get-login-password --region <REGION> | docker login --username AWS --password-stdin <ACCOUNT_ID>.dkr.ecr.<REGION>.amazonaws.com
docker build -t guestbook-app02 .
docker tag guestbook-app02:latest <ACCOUNT_ID>.dkr.ecr.<REGION>.amazonaws.com/guestbook-app02:latest
docker push <ACCOUNT_ID>.dkr.ecr.<REGION>.amazonaws.com/guestbook-app02:latest
```

### 2) EFS 생성
- EFS 파일시스템 생성
- **액세스 포인트** 생성: 루트 디렉터리 `/data`, POSIX uid/gid(예: 1000) 지정
- **마운트 타깃**을 ECS 태스크가 뜨는 서브넷에 생성
- 보안 그룹: ECS 태스크 SG → EFS SG 로 **2049(NFS)** 인바운드 허용

### 3) 비밀값 등록 (SSM 파라미터 스토어)
```bash
aws ssm put-parameter --name /guestbook/KAKAO_REST_API_KEY --type SecureString --value "..."
aws ssm put-parameter --name /guestbook/SESSION_SECRET_KEY --type SecureString --value "$(python -c 'import secrets;print(secrets.token_urlsafe(48))')"
aws ssm put-parameter --name /guestbook/ADMIN_PASSWORD --type SecureString --value "..."
# client_secret 미사용이면 빈 값으로 등록
aws ssm put-parameter --name /guestbook/KAKAO_CLIENT_SECRET --type SecureString --value " "
```

### 4) Task Definition 등록
`deploy/ecs/task-definition.json`의 `<...>` 플레이스홀더(ACCOUNT_ID, REGION, EFS ID, 액세스포인트, ALB 도메인)를 채운 뒤:
```bash
aws logs create-log-group --log-group-name /ecs/guestbook-app02
aws ecs register-task-definition --cli-input-json file://deploy/ecs/task-definition.json
```

### 5) 클러스터/서비스 생성
```bash
aws ecs create-cluster --cluster-name guestbook

aws ecs create-service \
  --cluster guestbook \
  --service-name guestbook-app02 \
  --task-definition guestbook-app02 \
  --desired-count 1 \
  --launch-type FARGATE \
  --deployment-configuration "maximumPercent=100,minimumHealthyPercent=0" \
  --network-configuration "awsvpcConfiguration={subnets=[<SUBNET>],securityGroups=[<ECS_SG>],assignPublicIp=ENABLED}" \
  --load-balancers "targetGroupArn=<TG_ARN>,containerName=web,containerPort=8000"
```
- ALB 타깃 그룹 헬스체크 경로: `/`
- ALB 보안 그룹: 인바운드 80/443, ECS SG는 ALB SG로부터 8000 허용

### 6) 카카오 설정
- 카카오 개발자 콘솔 Redirect URI를 `https://<ALB_도메인>/auth/kakao/callback`으로 등록
- `KAKAO_REDIRECT_URI` 환경변수도 동일하게

## 운영 확인
```bash
aws ecs describe-services --cluster guestbook --services guestbook-app02
aws logs tail /ecs/guestbook-app02 --follow
```

> 데이터(EFS)는 태스크 재시작/재배포에도 보존됩니다. 신규 컬럼은 앱 시작 시 자동 마이그레이션됩니다.
