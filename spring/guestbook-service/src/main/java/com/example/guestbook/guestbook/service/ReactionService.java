package com.example.guestbook.guestbook.service;

import com.example.guestbook.guestbook.domain.Reaction;
import com.example.guestbook.guestbook.domain.ReactionType;
import com.example.guestbook.guestbook.dto.Dtos.ReactionSummary;
import com.example.guestbook.guestbook.repository.ReactionRepository;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/** 글/댓글 공용 반응 토글 및 요약. FastAPI react_entry/react_comment + _reactor_names 대응. */
@Service
public class ReactionService {

    private final ReactionRepository reactions;

    public ReactionService(ReactionRepository reactions) {
        this.reactions = reactions;
    }

    /** 토글: 같은 타입 재요청=취소, 다른 타입=변경, 없으면 생성. 반응이 '추가/변경'되면 true 반환(알림 트리거용). */
    @Transactional
    public boolean toggleForEntry(Long userId, Long entryId, ReactionType type) {
        Optional<Reaction> existing = reactions.findByUserIdAndEntryId(userId, entryId);
        return toggle(existing, type, () -> {
            Reaction r = new Reaction();
            r.setUserId(userId);
            r.setEntryId(entryId);
            r.setReactionType(type);
            return r;
        });
    }

    @Transactional
    public boolean toggleForComment(Long userId, Long commentId, ReactionType type) {
        Optional<Reaction> existing = reactions.findByUserIdAndCommentId(userId, commentId);
        return toggle(existing, type, () -> {
            Reaction r = new Reaction();
            r.setUserId(userId);
            r.setCommentId(commentId);
            r.setReactionType(type);
            return r;
        });
    }

    private boolean toggle(Optional<Reaction> existing, ReactionType type,
                           java.util.function.Supplier<Reaction> factory) {
        if (existing.isEmpty()) {
            reactions.save(factory.get());
            return true;
        }
        Reaction r = existing.get();
        if (r.getReactionType() == type) {
            reactions.delete(r); // 같은 반응 재클릭 → 취소
            return false;
        }
        r.setReactionType(type); // 변경
        reactions.save(r);
        return true;
    }

    public ReactionSummary summaryForEntry(Long entryId, Long viewerId) {
        return summarize(reactions.findByEntryId(entryId), viewerId);
    }

    public ReactionSummary summaryForComment(Long commentId, Long viewerId) {
        return summarize(reactions.findByCommentId(commentId), viewerId);
    }

    private ReactionSummary summarize(List<Reaction> list, Long viewerId) {
        Map<String, Long> counts = new LinkedHashMap<>();
        Map<String, List<Long>> reactorIds = new LinkedHashMap<>();
        for (ReactionType t : ReactionType.values()) {
            counts.put(t.name(), 0L);
            reactorIds.put(t.name(), new ArrayList<>());
        }
        String mine = null;
        for (Reaction r : list) {
            String key = r.getReactionType().name();
            counts.merge(key, 1L, Long::sum);
            reactorIds.get(key).add(r.getUserId());
            if (viewerId != null && viewerId.equals(r.getUserId())) {
                mine = key;
            }
        }
        return new ReactionSummary(counts, mine, reactorIds);
    }
}
