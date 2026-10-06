package com.example.guestbook.chat;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

/**
 * 채팅 서비스 — 채팅방/멤버/메시지/파일/실시간.
 * FastAPI chat.py + events.py 에 대응. 실시간은 WebSocket(+멀티인스턴스 시 Redis Pub/Sub). (스켈레톤)
 */
@SpringBootApplication
public class ChatServiceApplication {
    public static void main(String[] args) {
        SpringApplication.run(ChatServiceApplication.class, args);
    }
}
