package com.example.guestbook.guestbook.domain;

import jakarta.persistence.*;
import java.time.Instant;
import lombok.Getter;
import lombok.Setter;

/** 방명록 글 (FastAPI GuestbookEntry 대응). */
@Entity
@Table(name = "guestbook_entries")
@Getter
@Setter
public class GuestbookEntry {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(columnDefinition = "text", nullable = false)
    private String message;

    // 인증 서비스의 사용자 ID (서비스 분리이므로 FK 대신 ID 참조)
    @Column(name = "author_id", nullable = false)
    private Long authorId;

    @Column(name = "author_name")
    private String authorName; // 표시 이름 스냅샷 (조회 편의)

    @Column(name = "created_at", nullable = false)
    private Instant createdAt = Instant.now();
}
