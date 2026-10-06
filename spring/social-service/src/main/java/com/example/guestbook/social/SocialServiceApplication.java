package com.example.guestbook.social;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

/**
 * 소셜 서비스 — 친구(사이 맺기) + 알림.
 * FastAPI friends.py + notify.py 에 대응. (스켈레톤)
 */
@SpringBootApplication
public class SocialServiceApplication {
    public static void main(String[] args) {
        SpringApplication.run(SocialServiceApplication.class, args);
    }
}
