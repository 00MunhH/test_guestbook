package com.example.guestbook.guestbook.domain;

import jakarta.persistence.*;
import java.time.Instant;
import lombok.Getter;
import lombok.Setter;

/** 댓글/대댓글 (parentId 가 있으면 대댓글). FastAPI Comment 대응. */
@Entity
@Table(name = "comments")
@Getter
@Setter
public class Comment {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(columnDefinition = "text", nullable = false)
    private String message;

    @Column(name = "entry_id", nullable = false)
    private Long entryId;

    @Column(name = "author_id", nullable = false)
    private Long authorId;

    @Column(name = "author_name")
    private String authorName;

    // 최상위 댓글이면 null, 대댓글이면 상위 댓글 id
    @Column(name = "parent_id")
    private Long parentId;

    @Column(name = "created_at", nullable = false)
    private Instant createdAt = Instant.now();
}
