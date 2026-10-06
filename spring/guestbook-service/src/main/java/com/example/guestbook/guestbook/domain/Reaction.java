package com.example.guestbook.guestbook.domain;

import jakarta.persistence.*;
import java.time.Instant;
import lombok.Getter;
import lombok.Setter;

/**
 * 글 또는 댓글에 대한 반응 (좋아요/싫어요/감사해요).
 * entryId 가 있으면 글 반응, commentId 가 있으면 댓글 반응. 사용자당 대상마다 1개.
 * FastAPI Reaction 대응.
 */
@Entity
@Table(name = "reactions",
        uniqueConstraints = {
            @UniqueConstraint(name = "uq_reaction_user_entry", columnNames = {"user_id", "entry_id"}),
            @UniqueConstraint(name = "uq_reaction_user_comment", columnNames = {"user_id", "comment_id"})
        })
@Getter
@Setter
public class Reaction {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Enumerated(EnumType.STRING)
    @Column(name = "reaction_type", length = 16, nullable = false)
    private ReactionType reactionType;

    @Column(name = "user_id", nullable = false)
    private Long userId;

    @Column(name = "entry_id")
    private Long entryId;

    @Column(name = "comment_id")
    private Long commentId;

    @Column(name = "created_at", nullable = false)
    private Instant createdAt = Instant.now();
}
