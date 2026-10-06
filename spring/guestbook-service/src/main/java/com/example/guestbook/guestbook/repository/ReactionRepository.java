package com.example.guestbook.guestbook.repository;

import com.example.guestbook.guestbook.domain.Reaction;
import java.util.List;
import java.util.Optional;
import org.springframework.data.jpa.repository.JpaRepository;

public interface ReactionRepository extends JpaRepository<Reaction, Long> {
    List<Reaction> findByEntryId(Long entryId);
    List<Reaction> findByCommentId(Long commentId);
    Optional<Reaction> findByUserIdAndEntryId(Long userId, Long entryId);
    Optional<Reaction> findByUserIdAndCommentId(Long userId, Long commentId);
}
