# guestbook-cloud — Spring Cloud 마이크로서비스 버전

기존 FastAPI **모놀리식**(`app/`)을 도메인 단위로 분해해 **Spring Cloud 마이크로서비스**로 재구성한 프로젝트입니다.
Gradle 멀티모듈로 구성되며, 서비스 디스커버리(Eureka) · 중앙 설정(Config) · 게이트웨이(Gateway) 위에
비즈니스 서비스들이 등록됩니다.

## 아키텍처

```
                        ┌──────────────────┐
   client ───────────▶ │   api-gateway     │  (8080, 단일 진입점)
                        └────────┬─────────┘
                                 │ lb:// (Eureka로 라우팅)
      ┌──────────────┬──────────┼───────────────┬───────────────┐
      ▼              ▼          ▼               ▼               ▼
 guestbook-svc   auth-svc   social-svc      chat-svc        (확장)
   (8081)         (8082)     (8083)          (8084)
      │              │          │               │
      └──────────────┴──────────┴───────────────┘
                 모두 Eureka 등록 + Config 조회
                                 ▲
          ┌──────────────────────┴───────────────────────┐
          ▼                                               ▼
   discovery-server (Eureka, 8761)            config-server (8888)
```

## 모놀리식 → 서비스 매핑
| FastAPI(app/) 모듈 | Spring 서비스 | 책임 |
|---------------------|---------------|------|
| auth.py, account.py | **auth-service** | 카카오 OAuth 로그인, 사용자/프로필, 관리자 |
| guestbook.py (+ models: entry/comment/reaction) | **guestbook-service** | 게시글/댓글/대댓글/반응 |
| friends.py, notify.py | **social-service** | 친구(사이 맺기), 알림 |
| chat.py, events.py | **chat-service** | 채팅방/메시지/파일/실시간(SSE·추후 WebSocket) |
| main.py(템플릿/라우팅) | **api-gateway** | 라우팅/진입점(프론트는 별도 or 템플릿 서비스) |

## 모듈 구성
```
spring/
├── settings.gradle / build.gradle      # 멀티모듈 루트 + Spring Cloud BOM
├── discovery-server/   (Eureka Server,  :8761)
├── config-server/      (Config Server,  :8888)
├── api-gateway/        (Spring Cloud Gateway, :8080)
├── guestbook-service/  (:8081)  ← 이번에 완성 구현
├── auth-service/       (:8082)  ← 스켈레톤/동일 패턴
├── social-service/     (:8083)  ← 스켈레톤/동일 패턴
└── chat-service/       (:8084)  ← 스켈레톤/동일 패턴
```

## 기술 스택
- Java 17, Spring Boot 3.3.5, Spring Cloud 2023.0.3, Gradle 멀티모듈
- Eureka(Netflix), Spring Cloud Gateway, Spring Cloud Config
- Spring Data JPA (로컬 H2 / 운영 PostgreSQL), Lombok

## 사전 준비
- **JDK 17** 설치 후 `JAVA_HOME` 환경변수 등록 (Windows 예시):
  ```powershell
  setx JAVA_HOME "C:\Program Files\Java\jdk-17.0.20.1"
  setx PATH "%PATH%;%JAVA_HOME%\bin"
  # 등록 후 터미널(창)을 새로 열어야 적용됩니다. 확인:
  java -version
  ```
- Gradle은 별도 설치가 필요 없습니다. 저장소에 포함된 **Gradle Wrapper**(`gradlew` / `gradlew.bat`)를 사용합니다.

## 실행 순서 (로컬)

각 `bootRun`은 서버가 계속 떠 있는 **포그라운드 명령**이라, 한 터미널에서 순차 실행하면 첫 명령에서 멈춥니다.
**서비스마다 별도 터미널(창)을 열어** 아래 순서대로 실행하세요.

- 디스커버리 → 설정 → 게이트웨이 → 비즈니스 서비스 순서

**Windows (PowerShell)** — `.\gradlew.bat` 사용:
```powershell
cd C:\ai_project\20260930_TEST\spring
# 터미널 1
.\gradlew.bat :discovery-server:bootRun
# 터미널 2
.\gradlew.bat :config-server:bootRun
# 터미널 3
.\gradlew.bat :api-gateway:bootRun
# 터미널 4
.\gradlew.bat :guestbook-service:bootRun
```

**Linux / macOS** — `./gradlew` 사용:
```bash
cd spring
./gradlew :discovery-server:bootRun   # 터미널 1
./gradlew :config-server:bootRun      # 터미널 2
./gradlew :api-gateway:bootRun        # 터미널 3
./gradlew :guestbook-service:bootRun  # 터미널 4
```

- Eureka 대시보드: http://localhost:8761 (서비스들이 등록되는지 확인)
- 게이트웨이 경유 호출 예: `GET http://localhost:8080/api/guestbook/entries`
- 첫 실행은 의존성 다운로드로 수 분 걸릴 수 있습니다.

> 참고: 모든 서비스를 한 번에 종료하려면 각 터미널에서 `Ctrl + C`.
> 전체를 한 터미널에서 백그라운드로 띄우려면 `Start-Process`(PowerShell)나 `&`(bash), 또는 Docker Compose 구성을 권장합니다.

## 구현 범위 안내
이 저장소는 **인프라 서비스 3종(discovery/config/gateway) + guestbook-service를 완성 수준**으로 제공합니다.
auth/social/chat 서비스는 guestbook-service와 **동일한 패턴**(Entity → Repository → Service → Controller,
Eureka client, Config client)으로 복제하면 됩니다. 각 서비스의 뼈대와 복제 가이드는 하단 참고.

## FastAPI 버전과의 관계
- 데이터 모델/도메인 규칙은 `app/models.py`, 각 라우터와 1:1로 대응합니다.
- 세션 쿠키 기반 인증은 Spring에서 보통 **Spring Session + Redis** 또는 **JWT**로 전환합니다(아래 참고).

---

## guestbook-service 패키지 구조 (대표)
```
guestbook-service/src/main/java/com/example/guestbook/guestbook/
├── GuestbookServiceApplication.java
├── domain/      GuestbookEntry, Comment, Reaction, ReactionType
├── repository/  EntryRepository, CommentRepository, ReactionRepository
├── dto/         Dtos (record 모음)
├── service/     GuestbookService, ReactionService
└── web/         GuestbookController
```

## API 예시 (게이트웨이 경유, 포트 8080)
> 인증은 auth-service가 담당. 데모에서는 호출자를 `X-User-Id` / `X-User-Name` 헤더로 전달합니다.
> (실제로는 게이트웨이의 인증 필터가 세션/JWT를 검증해 이 헤더를 주입하는 구조를 권장)

```bash
# 글 목록 (페이지네이션)
curl "http://localhost:8080/api/guestbook/entries?page=1&size=5" -H "X-User-Id: 1"

# 글 작성
curl -X POST http://localhost:8080/api/guestbook/entries \
  -H "X-User-Id: 1" -H "X-User-Name: 홍길동" -H "Content-Type: application/json" \
  -d '{"message":"안녕하세요"}'

# 댓글 / 대댓글(parentId)
curl -X POST http://localhost:8080/api/guestbook/entries/1/comments \
  -H "X-User-Id: 2" -H "X-User-Name: 밥" -H "Content-Type: application/json" \
  -d '{"message":"반가워요","parentId":null}'

# 반응 토글 (LIKE / DISLIKE / THANKS)
curl -X POST http://localhost:8080/api/guestbook/entries/1/react \
  -H "X-User-Id: 2" -H "Content-Type: application/json" \
  -d '{"reactionType":"LIKE"}'
```

## 나머지 서비스 구현 가이드 (auth / social / chat)
현재 auth/social/chat은 **빌드되는 스켈레톤**(Application + yml + build.gradle)만 있습니다.
guestbook-service와 **똑같은 레이어 패턴**으로 채우면 됩니다:

1. `domain/` — FastAPI `models.py`의 해당 엔티티를 JPA Entity로
   - auth: `User`(kakao_id, nickname, display_name, is_admin ...)
   - social: `Friendship`(requesterId, addresseeId, status, relationLabel), `Notification`
   - chat: `ChatRoom`, `ChatMembership`(status, lastReadMessageId), `ChatMessage`
2. `repository/` — Spring Data JPA 인터페이스
3. `service/` — FastAPI 각 라우터의 로직을 이식 (권한 체크, 토글, 집계 등)
4. `web/` — REST 컨트롤러 (게이트웨이 경로: `/api/<svc>/...`, StripPrefix=2)
5. `application.yml` — 포트/DB/eureka (이미 작성됨)

### 서비스 간 통신
- 조회성 결합(예: 채팅에서 친구 확인)은 **OpenFeign** 또는 **WebClient + lb://** 사용
  ```java
  // 예: social-service 호출
  @FeignClient(name = "social-service")
  interface SocialClient { @GetMapping("/friends/{id}/ids") List<Long> friendIds(@PathVariable Long id); }
  ```
- 이벤트성(알림/실시간)은 메시지 브로커(**Redis Pub/Sub** 또는 **Kafka/RabbitMQ**) 권장

### 인증/세션 전환
- FastAPI의 세션 쿠키 → Spring에서는 **JWT**(게이트웨이에서 검증 후 `X-User-*` 헤더 주입) 또는
  **Spring Session + Redis**(쿠키 공유)로 전환하는 것이 일반적입니다.

## 운영 배포
- 각 서비스는 독립 컨테이너로 빌드(`./gradlew :<svc>:bootBuildImage` 또는 Dockerfile).
- ECS/EKS에 서비스별 배포. DB는 서비스별 분리(또는 스키마 분리) + RDS, 실시간은 Redis/Kafka.
- 이 저장소 루트의 `infra/` Terraform(prd01~03)과 결합하면 ECS 기반 배포로 확장 가능.
