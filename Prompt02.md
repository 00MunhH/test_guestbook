# Prompt02 — AWS ECS + EFS 최소 구성 배포 프롬프트

> 기존 SQLite 기반 코드를 **거의 그대로** 유지한 채, AWS ECS(Fargate)에서 단일 태스크로 운영하고
> DB(SQLite)와 업로드 파일을 **EFS**에 영속화하는 구성을 만들기 위한 프롬프트입니다.
>
> 전제/주의:
> - 이 구성은 **수평 확장 불가**입니다. SQLite 파일 락과 in-memory SSE 브로커 특성상
>   태스크(컨테이너)는 **반드시 1개**(desired count = 1)로만 운영해야 합니다.
> - 애플리케이션 **코드 변경은 거의 없습니다**. DB/업로드 경로를 EFS 마운트 지점으로 두고,
>   배포 리소스(Task Definition 등)와 가이드를 추가하는 작업이 중심입니다.

---

현재 FastAPI + SQLite 방명록/소셜 프로젝트를 AWS ECS(Fargate)에 **EFS를 사용한 최소 구성**으로 배포할 수 있게 만들어줘. 설명과 진행은 한국어로 하고, 애플리케이션 코드 변경은 최소화해줘. 작업 후 각 파일의 역할과 배포 순서를 README에 정리하고 커밋/푸시해줘.

## 제약 / 아키텍처 전제
- 데이터는 SQLite 파일 1개 + 업로드 파일 디렉터리를 그대로 사용한다.
- SQLite 파일 락과 in-memory SSE(단일 프로세스 pub/sub) 때문에 **태스크는 1개만** 띄운다(desired count = 1, 롤링 중복 방지를 위해 deployment maximumPercent=100, minimumHealthyPercent=0).
- SQLite 파일과 업로드 파일은 **EFS**에 저장해 태스크 재시작/재배포 시에도 보존한다.

## 해야 할 일
1. **환경변수 정리**: `DATABASE_URL=sqlite:////mnt/data/guestbook.db`, `UPLOAD_DIR=/mnt/data/uploads`처럼 EFS 마운트 경로를 쓰도록 `.env.example`과 문서를 맞춰줘. 코드의 기본값/볼륨 경로도 이 전제와 일관되게.
2. **Dockerfile 점검**: EFS를 마운트할 디렉터리(`/mnt/data`)를 전제로 하고, 이미지에는 DB/업로드를 포함하지 않도록 `.dockerignore` 확인.
3. **ECS 리소스 파일 생성** (`deploy/ecs/` 디렉터리):
   - `task-definition.json` — Fargate 태스크 정의. 컨테이너 포트 8000, 로그는 awslogs(CloudWatch), **EFS 볼륨 마운트**(efsVolumeConfiguration + mountPoints `/mnt/data`), 환경변수는 `.env` 값 참조(민감값은 Secrets Manager/SSM 파라미터로 주입하는 예시 포함).
   - `service.json` 또는 생성 가이드 — 서비스 desired count=1, ALB 타깃 그룹(헬스체크 경로 `/`), 보안 그룹(8000/443) 설명.
4. **배포 가이드(README 섹션 또는 `deploy/ecs/README.md`)**: 아래 순서를 CLI 예시와 함께.
   - ECR 리포지토리 생성 → 이미지 빌드/푸시
   - EFS 파일시스템 생성 + 액세스 포인트(POSIX uid/gid, 루트 디렉터리 `/data`) + 마운트 타깃(서브넷/보안그룹)
   - 보안 그룹: ECS 태스크 ↔ EFS(2049 NFS) 허용
   - ECS 클러스터/서비스 생성, Task Definition 등록, 서비스 실행
   - 카카오 Redirect URI를 ALB 도메인(`https://.../auth/kakao/callback`)으로 등록하는 주의사항
   - 로그/상태 확인(aws ecs, CloudWatch Logs)
5. **주의사항 문서화**: 왜 태스크가 1개여야 하는지(SQLite/SSE), 확장이 필요하면 Prompt03(RDS+S3+Redis)로 가야 한다는 안내.

## 검증
- Task Definition JSON이 유효한지(필수 필드), 로컬에서 `UPLOAD_DIR`/`DATABASE_URL`을 EFS 경로로 바꿔도 앱이 정상 기동하는지 스모크 테스트로 확인해줘.

최종적으로 README 버전 관리 표에 이 배포 구성 항목을 추가하고, 커밋/태그를 남겨줘.

---

## 참고: 코드 구조 변경 여부
- **거의 없음.** 이미 `DATABASE_URL`/`UPLOAD_DIR`이 환경변수로 분리되어 있어, 값만 EFS 경로로 바꾸면 된다.
- 자동 스키마 마이그레이션(SQLite ALTER 방식)도 그대로 사용 가능.
- 단, **단일 태스크 운영이 필수 조건**이라는 점이 이 구성의 핵심 한계다.
