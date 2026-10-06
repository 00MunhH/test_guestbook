package com.example.guestbook.guestbook.dto;

import java.time.Instant;
import java.util.List;
import java.util.Map;

/** 요청/응답 DTO 모음. */
public class Dtos {

    // ----- 요청 -----
    public record CreateEntryRequest(Long authorId, String authorName, String message) {}
    public record UpdateEntryRequest(Long authorId, String message) {}

    public record CreateCommentRequest(Long authorId, String authorName, String message, Long parentId) {}
    public record UpdateCommentRequest(Long authorId, String message) {}

    public record ReactRequest(Long userId, String reactionType) {}

    // ----- 응답 -----
    public record ReactionSummary(
            Map<String, Long> counts,
            String myReaction,
            Map<String, List<Long>> reactorIds
    ) {}

    public record CommentResponse(
            Long id, Long entryId, Long authorId, String authorName,
            String message, Long parentId, Instant createdAt,
            ReactionSummary reactions, List<CommentResponse> replies
    ) {}

    public record EntryResponse(
            Long id, Long authorId, String authorName, String message, Instant createdAt,
            long commentCount, ReactionSummary reactions, List<CommentResponse> comments
    ) {}

    public record PageResponse<T>(List<T> items, int page, int totalPages, long total) {}
}
