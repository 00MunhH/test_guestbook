# 환경별 생성 AWS 리소스 목록 (prd01 / prd02 / prd03)

Terraform 코드(`infra/`) 적용 시 생성되는 AWS 리소스와 주요 설정을 환경별로 정리했습니다.
리소스 이름은 모듈의 `${name}-...` 규칙을 따르며, `name`은 환경 이름(prd01/prd02/prd03)입니다.
리전은 모두 기본값 `ap-northeast-2`, AZ는 `a`/`c` 2개입니다.

> 값은 각 `envs/<env>/variables.tf` 기본값 기준입니다. tfvars로 변경하면 달라집니다.

---

## 공통 네트워크 대역
| 환경 | VPC CIDR | 퍼블릭 서브넷 | 프라이빗 서브넷 | NAT |
|------|----------|---------------|------------------|-----|
| prd01 | 10.1.0.0/16 | 10.1.0.0/24, 10.1.1.0/24 | 10.1.10.0/24, 10.1.11.0/24 | 없음 |
| prd02 | 10.2.0.0/16 | 10.2.0.0/24, 10.2.1.0/24 | 10.2.10.0/24, 10.2.11.0/24 | 있음(1개) |
| prd03 | 10.3.0.0/16 | 10.3.0.0/24, 10.3.1.0/24 | 10.3.10.0/24, 10.3.11.0/24 | 있음(1개) |

---

## prd01 — EC2 + EFS (app01)

| 리소스 종류 | 이름/식별 | 주요 설정 |
|-------------|-----------|-----------|
| VPC | prd01-vpc | 10.1.0.0/16, DNS 지원/호스트네임 on |
| Internet Gateway | prd01-igw | 퍼블릭 라우팅용 |
| Subnet (public ×2) | prd01-public-1, -2 | map_public_ip on |
| Subnet (private ×2) | prd01-private-1, -2 | (NAT 없음, 미사용 가능) |
| Route Table | prd01-public-rt / prd01-private-rt | 퍼블릭은 0.0.0.0/0→IGW |
| Security Group (app) | prd01-app-sg | 인바운드 8000(앱), 22(SSH, 지정 CIDR) |
| Security Group (efs) | prd01-efs-sg | 인바운드 2049(NFS) ← app-sg |
| EFS File System | prd01-efs | 암호화 on, creation token `prd01-efs` |
| EFS Mount Target ×2 | (public 서브넷) | efs-sg 적용 |
| EFS Access Point | prd01-efs-ap | 루트 `/data`, uid/gid 1000, 0755 |
| EC2 Instance | prd01-ec2 | t3.small, AL2023, gp3 30GB, IMDSv2, user_data로 Docker/EFS 마운트 |
| EIP | prd01-eip | EC2에 연결(고정 공인 IP) |

- 접속: `http://<EIP>:8000` (보안그룹 `app_ingress_cidrs` 기본 0.0.0.0/0)
- 서비스 배포: EC2에 SSH → `app01` 코드 clone → `docker compose up`

---

## prd02 — ECS Fargate(1) + EFS + ALB (app02)

| 리소스 종류 | 이름/식별 | 주요 설정 |
|-------------|-----------|-----------|
| VPC | prd02-vpc | 10.2.0.0/16 |
| IGW / NAT | prd02-igw / prd02-nat (+prd02-nat-eip) | 프라이빗 아웃바운드용 NAT 1개 |
| Subnet (public ×2) | prd02-public-1, -2 | ALB 배치 |
| Subnet (private ×2) | prd02-private-1, -2 | ECS 태스크 / EFS 배치 |
| Route Table | prd02-public-rt / prd02-private-rt | private는 0.0.0.0/0→NAT |
| SG (alb) | prd02-alb-sg | 인바운드 80/443 |
| SG (app) | prd02-app-sg | 인바운드 8000 ← alb-sg |
| SG (efs) | prd02-efs-sg | 인바운드 2049 ← app-sg |
| ECR Repository | guestbook-prd02 | scan on push |
| EFS File System | prd02-efs | 암호화 on |
| EFS Mount Target ×2 | (private 서브넷) | |
| EFS Access Point | prd02-efs-ap | 루트 `/data` |
| ALB | prd02-alb | internet-facing, public 서브넷 |
| Target Group | prd02-tg | HTTP 8000, target_type ip, 헬스체크 `/` |
| Listener | (HTTP 80) | → prd02-tg forward |
| ECS Cluster | prd02-cluster | Fargate |
| CloudWatch Log Group | /ecs/prd02 | 보존 14일 |
| ECS Task Definition | prd02 | cpu 512 / mem 1024, EFS 볼륨 `/data` 마운트 |
| ECS Service | prd02-svc | desired 1, min0/max100(단일 유지), ALB 연결 |
| IAM Role (exec) | prd02-ecs-exec-role | ECR pull/로그/SSM 시크릿 |
| IAM Role (task) | prd02-ecs-task-role | 앱 권한 |

- 환경변수: `DATABASE_URL=sqlite:////data/guestbook.db`, `UPLOAD_DIR=/data/uploads`
- 시크릿(SSM, 수동 등록): `/guestbook/prd02/{KAKAO_REST_API_KEY, KAKAO_CLIENT_SECRET, SESSION_SECRET_KEY, ADMIN_PASSWORD}`
- 접속: `http://<prd02-alb DNS>`

---

## prd03 — ECS Fargate(N) + RDS + Redis + S3 + ALB (app03)

| 리소스 종류 | 이름/식별 | 주요 설정 |
|-------------|-----------|-----------|
| VPC | prd03-vpc | 10.3.0.0/16 |
| IGW / NAT | prd03-igw / prd03-nat (+prd03-nat-eip) | NAT 1개 |
| Subnet (public ×2) | prd03-public-1, -2 | ALB |
| Subnet (private ×2) | prd03-private-1, -2 | ECS / RDS / Redis |
| Route Table | prd03-public-rt / prd03-private-rt | private→NAT |
| SG (alb) | prd03-alb-sg | 80/443 |
| SG (app) | prd03-app-sg | 8000 ← alb-sg |
| SG (rds) | prd03-rds-sg | 5432 ← app-sg |
| SG (redis) | prd03-redis-sg | 6379 ← app-sg |
| ECR Repository | guestbook-prd03 | scan on push |
| S3 Bucket | (var.s3_bucket_name) | 비공개(퍼블릭 차단), 버저닝 on |
| RDS Subnet Group | prd03-db-subnet | private 서브넷 |
| RDS (PostgreSQL) | prd03-pg | db.t3.micro, 20GB, PG16, 암호화 on, single-AZ, 비공개 |
| ElastiCache Subnet Group | prd03-redis-subnet | private 서브넷 |
| ElastiCache (Redis) | prd03-redis | cache.t3.micro, Redis 7.1, 노드 1 |
| ALB | prd03-alb | internet-facing |
| Target Group | prd03-tg | HTTP 8000, target_type ip, 헬스체크 `/` |
| Listener | (HTTP 80) | → prd03-tg |
| ECS Cluster | prd03-cluster | Fargate |
| CloudWatch Log Group | /ecs/prd03 | 보존 14일 |
| ECS Task Definition | prd03 | cpu 512 / mem 1024 |
| ECS Service | prd03-svc | desired 2, min100/max200(수평 확장), ALB 연결 |
| IAM Role (exec) | prd03-ecs-exec-role | ECR/로그/SSM |
| IAM Role (task) | prd03-ecs-task-role | + S3 접근 정책 연결 |
| IAM Policy | prd03-s3-access | 버킷 get/put/delete/list |
| SSM Parameter | /guestbook/prd03/DATABASE_URL | **Terraform이 자동 등록**(RDS 접속 URL) |

- 환경변수: `REDIS_URL`(Redis), `S3_BUCKET`, `AWS_REGION`, `KAKAO_REDIRECT_URI`, `ADMIN_USERNAME`
- 시크릿(SSM): `DATABASE_URL`(자동) + `/guestbook/prd03/{KAKAO_REST_API_KEY, KAKAO_CLIENT_SECRET, SESSION_SECRET_KEY, ADMIN_PASSWORD}`(수동)
- 스키마: 컨테이너 시작 시 `alembic upgrade head` 자동 적용
- 접속: `http://<prd03-alb DNS>`

---

## 환경 비교 요약
| 항목 | prd01 | prd02 | prd03 |
|------|-------|-------|-------|
| 컨테이너 실행 | EC2 Docker(수동) | ECS Fargate | ECS Fargate |
| 태스크/인스턴스 수 | 1 | 1 | 2 (확장 가능) |
| DB | SQLite(EFS) | SQLite(EFS) | RDS PostgreSQL |
| 파일 저장 | EFS | EFS | S3 |
| 실시간(SSE) | in-memory | in-memory | Redis Pub/Sub |
| 로드밸런서 | 없음(직접 8000) | ALB | ALB |
| NAT 게이트웨이 | 없음 | 1 | 1 |
| 수평 확장 | 불가 | 불가(단일 태스크) | 가능 |

> 비용 주의: NAT 게이트웨이(prd02/03), RDS·ElastiCache(prd03), ALB(prd02/03)는 시간당 과금됩니다.
> 테스트 후에는 `terraform destroy`로 정리하세요.
