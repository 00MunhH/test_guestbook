package com.example.guestbook.guestbook.web;

import com.example.guestbook.guestbook.domain.ReactionType;
import com.example.guestbook.guestbook.dto.Dtos.*;
import com.example.guestbook.guestbook.service.GuestbookService;
import com.example.guestbook.guestbook.service.ReactionService;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.*;

/**
 * 방명록 REST API.
 * 게이트웨이 경유 경로 예: GET /api/guestbook/entries  (StripPrefix=2 후 /entries 로 도달)
 *
 * 인증은 분리된 auth-service가 담당. 여기서는 호출자 식별을 위해 헤더 X-User-Id / X-User-Name 를
 * 게이트웨이(또는 auth 필터)가 주입한다고 가정한다. (데모 단순화)
 */
@RestController
@RequestMapping
public class GuestbookController {

    private final GuestbookService service;
    private final ReactionService reactionService;

    public GuestbookController(GuestbookService service, ReactionService reactionService) {
        this.service = service;
        this.reactionService = reactionService;
    }

    // ----- 게시글 -----
    @GetMapping("/entries")
    public PageResponse<EntryResponse> list(
            @RequestParam(defaultValue = "1") int page,
            @RequestParam(defaultValue = "5") int size,
            @RequestHeader(value = "X-User-Id", required = false) Long viewerId) {
        return service.listEntries(page, size, viewerId);
    }

    @PostMapping("/entries")
    @ResponseStatus(HttpStatus.CREATED)
    public EntryResponse create(
            @RequestHeader("X-User-Id") Long userId,
            @RequestHeader(value = "X-User-Name", required = false) String userName,
            @RequestBody MessageBody body) {
        return service.createEntry(new CreateEntryRequest(userId, userName, body.message()));
    }

    @PutMapping("/entries/{id}")
    public EntryResponse update(
            @PathVariable Long id,
            @RequestHeader("X-User-Id") Long userId,
            @RequestBody MessageBody body) {
        return service.updateEntry(id, new UpdateEntryRequest(userId, body.message()));
    }

    @DeleteMapping("/entries/{id}")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    public void delete(@PathVariable Long id, @RequestHeader("X-User-Id") Long userId) {
        service.deleteEntry(id, userId);
    }

    // ----- 댓글/대댓글 -----
    @PostMapping("/entries/{entryId}/comments")
    @ResponseStatus(HttpStatus.CREATED)
    public CommentResponse addComment(
            @PathVariable Long entryId,
            @RequestHeader("X-User-Id") Long userId,
            @RequestHeader(value = "X-User-Name", required = false) String userName,
            @RequestBody CommentBody body) {
        return service.createComment(entryId,
                new CreateCommentRequest(userId, userName, body.message(), body.parentId()));
    }

    @PutMapping("/comments/{id}")
    public CommentResponse editComment(
            @PathVariable Long id,
            @RequestHeader("X-User-Id") Long userId,
            @RequestBody MessageBody body) {
        return service.updateComment(id, new UpdateCommentRequest(userId, body.message()));
    }

    @DeleteMapping("/comments/{id}")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    public void deleteComment(@PathVariable Long id, @RequestHeader("X-User-Id") Long userId) {
        service.deleteComment(id, userId);
    }

    // ----- 반응 -----
    @PostMapping("/entries/{id}/react")
    public ReactionSummary reactEntry(
            @PathVariable Long id,
            @RequestHeader("X-User-Id") Long userId,
            @RequestBody ReactBody body) {
        reactionService.toggleForEntry(userId, id, ReactionType.fromString(body.reactionType()));
        return reactionService.summaryForEntry(id, userId);
    }

    @PostMapping("/comments/{id}/react")
    public ReactionSummary reactComment(
            @PathVariable Long id,
            @RequestHeader("X-User-Id") Long userId,
            @RequestBody ReactBody body) {
        reactionService.toggleForComment(userId, id, ReactionType.fromString(body.reactionType()));
        return reactionService.summaryForComment(id, userId);
    }

    // ----- 간단 요청 바디 -----
    public record MessageBody(String message) {}
    public record CommentBody(String message, Long parentId) {}
    public record ReactBody(String reactionType) {}
}
