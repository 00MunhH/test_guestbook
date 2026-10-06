package com.example.guestbook.guestbook.service;

import com.example.guestbook.guestbook.domain.Comment;
import com.example.guestbook.guestbook.domain.GuestbookEntry;
import com.example.guestbook.guestbook.dto.Dtos.*;
import com.example.guestbook.guestbook.repository.CommentRepository;
import com.example.guestbook.guestbook.repository.EntryRepository;
import java.util.List;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.server.ResponseStatusException;

/** 방명록 핵심 로직. FastAPI guestbook.py 라우터 로직에 대응. */
@Service
public class GuestbookService {

    private final EntryRepository entries;
    private final CommentRepository comments;
    private final ReactionService reactionService;

    public GuestbookService(EntryRepository entries, CommentRepository comments,
                            ReactionService reactionService) {
        this.entries = entries;
        this.comments = comments;
        this.reactionService = reactionService;
    }

    // ---------- 게시글 ----------
    @Transactional(readOnly = true)
    public PageResponse<EntryResponse> listEntries(int page, int size, Long viewerId) {
        Page<GuestbookEntry> p = entries.findAllByOrderByCreatedAtDesc(
                PageRequest.of(Math.max(0, page - 1), size));
        List<EntryResponse> items = p.getContent().stream()
                .map(e -> toEntryResponse(e, viewerId))
                .toList();
        return new PageResponse<>(items, page, p.getTotalPages(), p.getTotalElements());
    }

    @Transactional
    public EntryResponse createEntry(CreateEntryRequest req) {
        if (req.message() == null || req.message().isBlank()) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "내용을 입력해주세요.");
        }
        GuestbookEntry e = new GuestbookEntry();
        e.setMessage(req.message().strip());
        e.setAuthorId(req.authorId());
        e.setAuthorName(req.authorName());
        entries.save(e);
        return toEntryResponse(e, req.authorId());
    }

    @Transactional
    public EntryResponse updateEntry(Long id, UpdateEntryRequest req) {
        GuestbookEntry e = entries.findById(id)
                .orElseThrow(() -> notFound("방명록을 찾을 수 없습니다."));
        requireOwner(e.getAuthorId(), req.authorId());
        if (req.message() != null && !req.message().isBlank()) {
            e.setMessage(req.message().strip());
        }
        return toEntryResponse(e, req.authorId());
    }

    @Transactional
    public void deleteEntry(Long id, Long authorId) {
        GuestbookEntry e = entries.findById(id)
                .orElseThrow(() -> notFound("방명록을 찾을 수 없습니다."));
        requireOwner(e.getAuthorId(), authorId);
        // 댓글/반응 cascade는 별도 정리(간단화를 위해 댓글만 삭제)
        comments.deleteAll(comments.findByEntryIdOrderByCreatedAtAsc(id));
        entries.delete(e);
    }

    // ---------- 댓글/대댓글 ----------
    @Transactional
    public CommentResponse createComment(Long entryId, CreateCommentRequest req) {
        entries.findById(entryId).orElseThrow(() -> notFound("방명록을 찾을 수 없습니다."));
        if (req.message() == null || req.message().isBlank()) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "내용을 입력해주세요.");
        }
        Long parentId = req.parentId();
        if (parentId != null) {
            Comment parent = comments.findById(parentId)
                    .orElseThrow(() -> new ResponseStatusException(HttpStatus.BAD_REQUEST, "원 댓글을 찾을 수 없습니다."));
            // 대댓글의 대댓글은 최상위로 묶음 (1단계 깊이 유지)
            if (parent.getParentId() != null) parentId = parent.getParentId();
        }
        Comment c = new Comment();
        c.setEntryId(entryId);
        c.setAuthorId(req.authorId());
        c.setAuthorName(req.authorName());
        c.setMessage(req.message().strip());
        c.setParentId(parentId);
        comments.save(c);
        return toCommentResponse(c, req.authorId());
    }

    @Transactional
    public CommentResponse updateComment(Long commentId, UpdateCommentRequest req) {
        Comment c = comments.findById(commentId)
                .orElseThrow(() -> notFound("댓글을 찾을 수 없습니다."));
        requireOwner(c.getAuthorId(), req.authorId());
        if (req.message() != null && !req.message().isBlank()) {
            c.setMessage(req.message().strip());
        }
        return toCommentResponse(c, req.authorId());
    }

    @Transactional
    public void deleteComment(Long commentId, Long authorId) {
        Comment c = comments.findById(commentId)
                .orElseThrow(() -> notFound("댓글을 찾을 수 없습니다."));
        requireOwner(c.getAuthorId(), authorId);
        comments.delete(c);
    }

    // ---------- 조립 ----------
    private EntryResponse toEntryResponse(GuestbookEntry e, Long viewerId) {
        List<Comment> all = comments.findByEntryIdOrderByCreatedAtAsc(e.getId());
        List<CommentResponse> tops = all.stream()
                .filter(c -> c.getParentId() == null)
                .map(c -> toCommentResponseWithReplies(c, all, viewerId))
                .toList();
        return new EntryResponse(
                e.getId(), e.getAuthorId(), e.getAuthorName(), e.getMessage(), e.getCreatedAt(),
                all.size(), reactionService.summaryForEntry(e.getId(), viewerId), tops);
    }

    private CommentResponse toCommentResponseWithReplies(Comment c, List<Comment> all, Long viewerId) {
        List<CommentResponse> replies = all.stream()
                .filter(r -> c.getId().equals(r.getParentId()))
                .map(r -> toCommentResponse(r, viewerId))
                .toList();
        return new CommentResponse(
                c.getId(), c.getEntryId(), c.getAuthorId(), c.getAuthorName(),
                c.getMessage(), c.getParentId(), c.getCreatedAt(),
                reactionService.summaryForComment(c.getId(), viewerId), replies);
    }

    private CommentResponse toCommentResponse(Comment c, Long viewerId) {
        return new CommentResponse(
                c.getId(), c.getEntryId(), c.getAuthorId(), c.getAuthorName(),
                c.getMessage(), c.getParentId(), c.getCreatedAt(),
                reactionService.summaryForComment(c.getId(), viewerId), List.of());
    }

    private void requireOwner(Long ownerId, Long requesterId) {
        if (requesterId == null || !requesterId.equals(ownerId)) {
            throw new ResponseStatusException(HttpStatus.FORBIDDEN, "본인만 수정/삭제할 수 있습니다.");
        }
    }

    private ResponseStatusException notFound(String msg) {
        return new ResponseStatusException(HttpStatus.NOT_FOUND, msg);
    }
}
