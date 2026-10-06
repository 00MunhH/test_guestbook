package com.example.guestbook.guestbook;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

/**
 * 방명록 서비스 — 게시글/댓글/대댓글/반응 담당.
 * FastAPI 의 guestbook.py + models(Entry/Comment/Reaction) 에 대응.
 */
@SpringBootApplication
public class GuestbookServiceApplication {
    public static void main(String[] args) {
        SpringApplication.run(GuestbookServiceApplication.class, args);
    }
}
