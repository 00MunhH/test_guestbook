package com.example.guestbook.auth;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

/**
 * 인증 서비스 — 카카오 OAuth 로그인, 사용자/프로필, 관리자.
 * FastAPI auth.py + account.py 에 대응. (스켈레톤: guestbook-service 패턴으로 채워 넣으면 됨)
 */
@SpringBootApplication
public class AuthServiceApplication {
    public static void main(String[] args) {
        SpringApplication.run(AuthServiceApplication.class, args);
    }
}
