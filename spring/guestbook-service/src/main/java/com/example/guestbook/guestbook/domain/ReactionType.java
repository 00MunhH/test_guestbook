package com.example.guestbook.guestbook.domain;

/** 반응 종류 (FastAPI REACTION_TYPES 대응). */
public enum ReactionType {
    LIKE,     // 좋아요
    DISLIKE,  // 싫어요
    THANKS;   // 감사해요

    public static ReactionType fromString(String v) {
        return ReactionType.valueOf(v.trim().toUpperCase());
    }
}
