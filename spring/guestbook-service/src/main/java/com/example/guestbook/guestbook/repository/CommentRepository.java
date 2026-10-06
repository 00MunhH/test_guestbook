package com.example.guestbook.guestbook.repository;

import com.example.guestbook.guestbook.domain.Comment;
import java.util.List;
import org.springframework.data.jpa.repository.JpaRepository;

public interface CommentRepository extends JpaRepository<Comment, Long> {
    List<Comment> findByEntryIdOrderByCreatedAtAsc(Long entryId);
    List<Comment> findByParentIdOrderByCreatedAtAsc(Long parentId);
    long countByEntryId(Long entryId);
}
