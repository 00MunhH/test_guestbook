# infra — Terraform으로 구성하는 AWS 인프라 (prd01 / prd02 / prd03)

방명록 서비스를 세 가지 아키텍처(환경)로 배포하기 위한 Terraform 코드입니다. **모듈화 + 변수화**되어 있어
공통 네트워크 모듈을 세 환경이 재사용하고, 환경별 차이는 `envs/<env>`와 `tfvars`로 분리했습니다.

## 환경 ↔ 서비스 매핑
| 환경 | 대응 코드 | 아키텍처 | 확장 |
|------|-----------|----------|------|
| **prd01** | `app01` | VPC + EC2 1대 + EFS (수동 Docker 배포) | 단일 |
| **prd02** | `app02` | VPC + ALB + ECS Fargate(1 태스크) + EFS | 단일 태스크 |
| **prd03** | `app03` | VPC + ALB + ECS Fargate(N) + RDS + ElastiCache(Redis) + S3 | 수평 확장 |

## 디렉터리 구조
```
infra/
├── modules/                 # 재사용 모듈
│   ├── network/             # VPC/서브넷/IGW/NAT/라우팅
│   ├── security/            # 보안그룹(플래그로 alb/app/efs/rds/redis 생성)
│   ├── ecr/  s3/  efs/      # 리소스 모듈
│   ├── alb/  ec2/  ecs/
│   └── rds/  redis/
└── envs/                    # 환경별 조합(루트 모듈)
    ├── prd01/   (EC2+EFS)
    ├── prd02/   (ECS+EFS+ALB)
    └── prd03/   (ECS+RDS+Redis+S3+ALB)
```

## 사전 준비
- Terraform ≥ 1.5, AWS CLI, Docker
- AWS 자격증명 설정 (`aws configure` 또는 환경변수)
- (권장) 원격 상태용 S3 버킷 + DynamoDB 락 테이블 → 각 `envs/*/versions.tf`의 `backend "s3"` 주석 해제

---

## 공통: 인프라 배포 흐름
```bash
cd infra/envs/<env>
cp terraform.tfvars.example terraform.tfvars   # 값 채우기
terraform init
terraform plan
terraform apply
terraform output        # ALB DNS, ECR URL, EC2 IP 등 확인
```

---

## prd01 (EC2 + EFS) 배포

### 1) 인프라
```bash
cd infra/envs/prd01
cp terraform.tfvars.example terraform.tfvars   # ssh_ingress_cidrs 등 수정
terraform init && terraform apply
terraform output ec2_public_ip
```
- EC2 부팅 시 user_data가 Docker/EFS 유틸 설치 + `/mnt/efs` 마운트까지 수행합니다.

### 2) 서비스 배포 (EC2에 SSH 후)
```bash
ssh ec2-user@<ec2_public_ip>
git clone https://github.com/00MunhH/test_guestbook.git
cd test_guestbook/app01
cp .env.example .env && nano .env   # 카카오 키, SESSION_SECRET_KEY, 관리자 비번, KAKAO_REDIRECT_URI
EFS_DATA_DIR=/mnt/efs/guestbook docker compose up -d --build
```
- 보안그룹에서 8000 포트는 `app_ingress_cidrs`로 열림. 접속: `http://<ec2_public_ip>:8000`

---

## prd02 (ECS Fargate + EFS) 배포

### 1) 인프라(ECR 포함) 먼저 생성
```bash
cd infra/envs/prd02
cp terraform.tfvars.example terraform.tfvars
terraform init && terraform apply
terraform output        # ecr_repository_url, alb_dns_name 확인
```

### 2) 시크릿 등록 (SSM 파라미터)
```bash
P=/guestbook/prd02
aws ssm put-parameter --name $P/KAKAO_REST_API_KEY  --type SecureString --value "..."
aws ssm put-parameter --name $P/KAKAO_CLIENT_SECRET --type SecureString --value " "
aws ssm put-parameter --name $P/SESSION_SECRET_KEY  --type SecureString --value "$(python -c 'import secrets;print(secrets.token_urlsafe(48))')"
aws ssm put-parameter --name $P/ADMIN_PASSWORD      --type SecureString --value "..."
```

### 3) 이미지 빌드/푸시
```bash
ECR=$(terraform output -raw ecr_repository_url)
REGION=ap-northeast-2
aws ecr get-login-password --region $REGION | docker login --username AWS --password-stdin ${ECR%/*}
docker build -t guestbook ../../../app02
docker tag guestbook:latest $ECR:latest
docker push $ECR:latest
```

### 4) 서비스 반영
- `kakao_redirect_uri`를 `terraform output alb_dns_name` 기준으로 tfvars에 갱신 후 `terraform apply`
- 카카오 콘솔 Redirect URI도 `http://<alb_dns_name>/auth/kakao/callback` 등록
- 롤링 재배포(이미지 갱신 후):
  ```bash
  aws ecs update-service --cluster prd02-cluster --service prd02-svc --force-new-deployment
  ```
- 접속: `http://<alb_dns_name>`

---

## prd03 (ECS + RDS + Redis + S3) 배포

### 1) 시크릿 중 DB 비밀번호는 tfvars/환경변수로
```bash
cd infra/envs/prd03
cp terraform.tfvars.example terraform.tfvars   # s3_bucket_name(전역 유일) 지정
export TF_VAR_db_password='<STRONG_DB_PASSWORD>'
terraform init && terraform apply
terraform output
```
> `DATABASE_URL`은 RDS 생성 결과로 **Terraform이 SSM(`/guestbook/prd03/DATABASE_URL`)에 자동 등록**합니다.

### 2) 나머지 시크릿 등록
```bash
P=/guestbook/prd03
aws ssm put-parameter --name $P/KAKAO_REST_API_KEY  --type SecureString --value "..."
aws ssm put-parameter --name $P/KAKAO_CLIENT_SECRET --type SecureString --value " "
aws ssm put-parameter --name $P/SESSION_SECRET_KEY  --type SecureString --value "$(python -c 'import secrets;print(secrets.token_urlsafe(48))')"
aws ssm put-parameter --name $P/ADMIN_PASSWORD      --type SecureString --value "..."
```

### 3) 이미지 빌드/푸시 (app03)
```bash
ECR=$(terraform output -raw ecr_repository_url)
REGION=ap-northeast-2
aws ecr get-login-password --region $REGION | docker login --username AWS --password-stdin ${ECR%/*}
docker build -t guestbook ../../../app03
docker tag guestbook:latest $ECR:latest
docker push $ECR:latest
```

### 4) S3 버킷 CORS/권한
- 버킷은 Terraform이 생성(비공개). 다운로드는 앱이 presigned URL을 발급하므로 추가 공개 설정 불필요.

### 5) 서비스 반영
- `terraform apply` 후 `alb_dns_name` 기준으로 카카오 Redirect URI 등록
- 스키마는 컨테이너 시작 시 `alembic upgrade head`(app03 `entrypoint.sh`)가 자동 적용
- 롤링/스케일:
  ```bash
  aws ecs update-service --cluster prd03-cluster --service prd03-svc --force-new-deployment
  aws ecs update-service --cluster prd03-cluster --service prd03-svc --desired-count 4   # 스케일아웃
  ```

---

## 변수화 포인트 (요약)
- 네트워크: `vpc_cidr`, `azs`, `public/private_subnet_cidrs`
- 공통: `region`, `name`(=env 접두사), `image_tag`
- prd01: `instance_type`, `key_name`, `ssh_ingress_cidrs`, `app_ingress_cidrs`
- prd03: `desired_count`, `db_username/db_password`, `s3_bucket_name`

## 정리(삭제)
```bash
cd infra/envs/<env>
terraform destroy
```
> prd03의 S3 버킷에 객체가 있으면 먼저 비워야 destroy가 됩니다. RDS는 `skip_final_snapshot=true`로 설정돼 있습니다(운영 전환 시 변경 권장).

## 주의
- 이 머신엔 Terraform이 없어 `validate`는 수행하지 못했고, 모듈 참조/변수 정합성은 정적 점검으로 확인했습니다. 실제 적용 전 각 환경에서 `terraform init && terraform validate && terraform plan`으로 최종 확인하세요.
- 비밀값(DB 비번, 카카오 키, 세션 키)은 코드/tfvars에 커밋하지 말고 환경변수(`TF_VAR_*`)나 SSM으로 주입하세요.
