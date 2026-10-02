# app01 — 카카오 로그인 방명록 (EC2 + Docker + EFS)

`app/`(SQLite 기반) 프로젝트를 **EC2 1대에서 Docker로 실행**하되, 데이터(SQLite DB·업로드 파일)를
**EFS(공유 파일시스템)**에 저장하는 구성입니다. EC2를 교체/재생성해도 데이터가 EFS에 남아 보존됩니다.

## 다른 구성과의 차이
| 구성 | 컨테이너 관리 | 데이터 | 확장 |
|------|--------------|--------|------|
| EC2 + Docker + EBS (최초 기본) | 수동(SSH) | 인스턴스 디스크 | 단일 |
| **app01: EC2 + Docker + EFS** | 수동(SSH) | **EFS(인스턴스와 분리)** | 단일 |
| app02: ECS Fargate + EFS | AWS 자동 | EFS | 단일 태스크 |
| app03: ECS + RDS/S3/Redis | AWS 자동 | 관리형 | 수평 확장 |

> **중요**: EFS를 써도 **수평 확장은 안 됩니다.** SQLite 파일 락 + in-memory SSE 때문에
> EC2는 1대로만 운영하세요. EFS의 이점은 "확장"이 아니라 **"인스턴스와 데이터의 분리(교체 시 보존)"** 입니다.
> 진짜 확장이 필요하면 app03를 쓰세요.

## 로컬 실행 (EFS 없이 로컬 디렉터리로)
```bash
cp .env.example .env   # 값 채우기
# EFS_DATA_DIR 기본값은 ./data (로컬 폴더). 그대로 실행:
docker compose up -d --build
# http://localhost:8000
```

## EC2 + EFS 배포

### 1) EFS 생성
- EFS 파일시스템 생성 (VPC는 EC2와 동일하게)
- **마운트 타깃**을 EC2가 있는 서브넷/AZ에 생성
- 보안 그룹: EC2의 SG → EFS의 SG 로 **2049(NFS)** 인바운드 허용

### 2) EC2에 Docker / EFS 유틸 설치
Amazon Linux 2023 기준:
```bash
sudo dnf update -y
sudo dnf install -y docker git amazon-efs-utils
sudo systemctl enable --now docker
sudo usermod -aG docker $USER   # 재로그인 후 sudo 없이 docker 사용
# docker compose 플러그인
sudo mkdir -p /usr/libexec/docker/cli-plugins
sudo curl -SL https://github.com/docker/compose/releases/latest/download/docker-compose-linux-x86_64 \
  -o /usr/libexec/docker/cli-plugins/docker-compose
sudo chmod +x /usr/libexec/docker/cli-plugins/docker-compose
```
Ubuntu면 `apt install -y docker.io git amazon-efs-utils`(또는 nfs-common).

### 3) EFS 마운트 + 영속화(fstab)
```bash
sudo mkdir -p /mnt/efs
# amazon-efs-utils 사용 (전송 암호화)
sudo mount -t efs -o tls <EFS_FILE_SYSTEM_ID>:/ /mnt/efs

# 데이터용 하위 디렉터리 생성
sudo mkdir -p /mnt/efs/guestbook/uploads

# 재부팅 시 자동 마운트 (/etc/fstab)
echo '<EFS_FILE_SYSTEM_ID>:/ /mnt/efs efs _netdev,tls 0 0' | sudo tee -a /etc/fstab
# 확인
mount | grep efs
```
> NFS로 직접 마운트하려면:
> `sudo mount -t nfs4 -o nfsvers=4.1 <EFS_FS_ID>.efs.<REGION>.amazonaws.com:/ /mnt/efs`

### 4) 코드 받기 & 실행
```bash
git clone https://github.com/00MunhH/test_guestbook.git
cd test_guestbook/app01
cp .env.example .env
nano .env   # 카카오 키, SESSION_SECRET_KEY, 관리자 비번, KAKAO_REDIRECT_URI(EC2 공인주소) 등

# EFS 경로를 bind mount 하도록 EFS_DATA_DIR 지정
EFS_DATA_DIR=/mnt/efs/guestbook docker compose up -d --build
```
- 보안 그룹에서 **8000 포트 인바운드** 개방
- 브라우저: `http://<EC2_퍼블릭_IP>:8000`
- 카카오 콘솔 Redirect URI에 `http://<EC2_퍼블릭_IP>:8000/auth/kakao/callback` 등록

### 5) 운영 명령
```bash
docker compose ps
docker compose logs -f
# 코드 업데이트
git pull
EFS_DATA_DIR=/mnt/efs/guestbook docker compose up -d --build
```

## 데이터 보존 포인트
- DB(`/mnt/efs/guestbook/guestbook.db`)와 업로드(`/mnt/efs/guestbook/uploads`)가 **EFS**에 있으므로,
  EC2 인스턴스를 교체/재생성해도 새 인스턴스에서 EFS만 다시 마운트하면 데이터가 그대로 유지됩니다.
- 신규 컬럼은 앱 시작 시 자동 마이그레이션됩니다(원본 `app/`과 동일).

## 참고
- `EFS_DATA_DIR`를 지정하지 않으면 로컬 `./data` 폴더에 저장됩니다(로컬 개발용).
- HTTPS/도메인이 필요하면 Nginx + Let's Encrypt를 앞단에 두고, 카카오 Redirect URI도 `https://...`로 등록하세요.
