"""In-memory multilingual FAQ matcher (embeddings + hybrid lexical/synonym fallback)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

import numpy as np
from rapidfuzz import fuzz
from sklearn.feature_extraction.text import TfidfVectorizer
from sqlmodel import Session, select

from app.models import PLACEHOLDER_PREFIX, FAQItem, SampleQuestion, Translation
from app.services.redflag import normalize_text

STOPWORDS = {
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "to", "of", "in", "on", "at", "for",
    "with", "by", "from", "about", "as", "into", "like", "through", "after", "over", "between", "out",
    "against", "during", "without", "before", "under", "around", "among", "i", "me", "my", "we", "our",
    "you", "your", "he", "him", "his", "she", "her", "it", "its", "they", "them", "their", "what",
    "which", "who", "whom", "this", "that", "these", "those", "am", "have", "has", "had", "do", "does",
    "did", "will", "would", "shall", "should", "can", "could", "may", "might", "must", "how", "when",
    "where", "why", "please", "tell", "know", "want", "need", "ask", "question", "help", "someone",
    "abeg", "wetin", "make", "dey", "go", "fit", "na", "wey", "for", "dem", "una", "person", "get",
    "se", "bawo", "ni", "ti", "ko", "ki", "le", "ma", "n", "fun", "mi", "re", "wa", "si", "pe", "abi",
}

SYNONYMS = {
    "bp": "blood pressure hypertension",
    "hypertension": "blood pressure hypertension",
    "drug": "medicine",
    "drugs": "medicine",
    "tablet": "medicine",
    "tablets": "medicine",
    "pill": "medicine",
    "pills": "medicine",
    "medication": "medicine",
    "medications": "medicine",
    "baby": "child",
    "kid": "child",
    "kids": "child",
    "toddler": "child",
    "children": "child",
    "purge": "diarrhoea stool ors",
    "purging": "diarrhoea stool ors",
    "stooling": "diarrhoea stool ors",
    "poop": "diarrhoea stool",
    "watery": "diarrhoea ors",
    "rehydration": "ors",
    "sachet": "ors",
    "keep": "store",
    "keeping": "store",
    "storage": "store",
    "stored": "store",
    "fine": "better normal",
    "okay": "better normal",
    "well": "better",
}


def clean_indexed_text(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith(PLACEHOLDER_PREFIX):
        stripped = stripped[len(PLACEHOLDER_PREFIX) :].strip()
    return stripped


def expand_and_stem(folded: str) -> tuple[str, list[str]]:
    words = re.findall(r"[a-z0-9]+", folded.lower())
    expanded_words: list[str] = []
    for w in words:
        expanded_words.append(w)
        if w in SYNONYMS:
            expanded_words.extend(SYNONYMS[w].split())

    tokens: list[str] = []
    for w in expanded_words:
        if w in STOPWORDS or len(w) < 2:
            continue
        stem = re.sub(r"(ing|ed|es|s|e)$", "", w) if len(w) > 4 else w
        tokens.append(stem if len(stem) >= 3 else w)
    return " ".join(expanded_words), tokens


@dataclass
class IndexedEntry:
    faq_id: int
    lang: str
    raw_text: str
    folded_text: str
    expanded_text: str
    tokens: list[str]
    display_question: str
    question_audio_url: Optional[str]
    weight: float = 1.0


@dataclass
class MatchCandidate:
    faq_id: int
    question: str
    question_audio_url: Optional[str]
    score: float


@dataclass
class MatchResult:
    outcome: str  # "answer" | "unsure"
    faq_id: Optional[int]
    confidence: float
    candidates: list[MatchCandidate]


class FAQMatcher:
    def __init__(self, model_name: str = "sentence-transformers/LaBSE", disable_heavy: bool = False) -> None:
        self.model_name = model_name
        self.disable_heavy = disable_heavy
        self._st_model = None
        self._st_tried = False
        self._tfidf: Optional[TfidfVectorizer] = None
        self._word_tfidf: Optional[TfidfVectorizer] = None
        self._entries: list[IndexedEntry] = []
        self._matrix: Optional[np.ndarray] = None
        self._word_matrix: Optional[np.ndarray] = None
        self._faq_meta: dict[tuple[int, str], tuple[str, Optional[str]]] = {}

    def _load_sentence_transformer(self):
        if self._st_tried or self.disable_heavy:
            return self._st_model
        self._st_tried = True
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore

            self._st_model = SentenceTransformer(self.model_name)
        except Exception:
            self._st_model = None
        return self._st_model

    @staticmethod
    def _normalize_rows(mat: np.ndarray) -> np.ndarray:
        norms = np.linalg.norm(mat, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return mat / norms

    def _fit_vectors(self, entries: list[IndexedEntry]) -> tuple[np.ndarray, Optional[np.ndarray]]:
        if not entries:
            return np.zeros((0, 1), dtype=np.float32), None

        model = self._load_sentence_transformer()
        if model is not None:
            texts = [e.folded_text for e in entries]
            vecs = model.encode(texts, normalize_embeddings=True, convert_to_numpy=True)
            return np.asarray(vecs, dtype=np.float32), None

        char_texts = [e.expanded_text for e in entries]
        word_texts = [" ".join(e.tokens) or e.expanded_text for e in entries]

        self._tfidf = TfidfVectorizer(
            analyzer="char_wb",
            ngram_range=(3, 5),
            sublinear_tf=True,
            lowercase=True,
        )
        char_mat = self._normalize_rows(
            self._tfidf.fit_transform(char_texts).toarray().astype(np.float32)
        )

        self._word_tfidf = TfidfVectorizer(
            analyzer="word",
            ngram_range=(1, 2),
            sublinear_tf=True,
            lowercase=True,
        )
        word_mat = self._normalize_rows(
            self._word_tfidf.fit_transform(word_texts).toarray().astype(np.float32)
        )
        return char_mat, word_mat

    def _encode_dense_query(self, query_folded: str) -> np.ndarray:
        assert self._st_model is not None
        vec = self._st_model.encode([query_folded], normalize_embeddings=True, convert_to_numpy=True)
        return np.asarray(vec[0], dtype=np.float32)

    @staticmethod
    def _transform_unit(vec_model: TfidfVectorizer, text: str) -> np.ndarray:
        vec = vec_model.transform([text]).toarray().astype(np.float32)[0]
        norm = float(np.linalg.norm(vec))
        if norm > 0:
            vec = vec / norm
        return vec

    def build_index(self, session: Session) -> int:
        active_faqs = {
            f.id: f
            for f in session.exec(select(FAQItem).where(FAQItem.is_active == True)).all()  # noqa: E712
        }
        published_trs = session.exec(
            select(Translation).where(Translation.status == "published")
        ).all()

        published_pairs: set[tuple[int, str]] = set()
        faq_meta: dict[tuple[int, str], tuple[str, Optional[str]]] = {}
        entries: list[IndexedEntry] = []

        for tr in published_trs:
            if tr.faq_id not in active_faqs:
                continue
            published_pairs.add((tr.faq_id, tr.lang))
            faq_meta[(tr.faq_id, tr.lang)] = (tr.question_text, tr.question_audio_url)
            q_clean = clean_indexed_text(tr.question_text)
            raw_norm, folded_norm = normalize_text(q_clean)
            if folded_norm:
                exp_q, toks_q = expand_and_stem(folded_norm)
                entries.append(
                    IndexedEntry(
                        faq_id=tr.faq_id,
                        lang=tr.lang,
                        raw_text=raw_norm,
                        folded_text=folded_norm,
                        expanded_text=exp_q,
                        tokens=toks_q,
                        display_question=tr.question_text,
                        question_audio_url=tr.question_audio_url,
                        weight=1.0,
                    )
                )

            a_clean = clean_indexed_text(tr.answer_text)
            u_clean = clean_indexed_text(tr.undiagnosed_text or "")
            d_clean = clean_indexed_text(tr.diagnosed_text or "")
            intent_words = active_faqs[tr.faq_id].intent_key.replace("_", " ")
            combo_raw = f"{q_clean} {intent_words} {a_clean} {u_clean} {d_clean}"
            raw_combo, fold_combo = normalize_text(combo_raw)
            if fold_combo:
                exp_c, toks_c = expand_and_stem(fold_combo)
                entries.append(
                    IndexedEntry(
                        faq_id=tr.faq_id,
                        lang=tr.lang,
                        raw_text=raw_combo,
                        folded_text=fold_combo,
                        expanded_text=exp_c,
                        tokens=toks_c,
                        display_question=tr.question_text,
                        question_audio_url=tr.question_audio_url,
                        weight=0.92,
                    )
                )

        samples = session.exec(select(SampleQuestion)).all()
        for smp in samples:
            if (smp.faq_id, smp.lang) not in published_pairs:
                continue
            disp_q, q_audio = faq_meta[(smp.faq_id, smp.lang)]
            raw_norm, folded_norm = normalize_text(smp.phrasing)
            if folded_norm:
                exp_s, toks_s = expand_and_stem(folded_norm)
                entries.append(
                    IndexedEntry(
                        faq_id=smp.faq_id,
                        lang=smp.lang,
                        raw_text=raw_norm,
                        folded_text=folded_norm,
                        expanded_text=exp_s,
                        tokens=toks_s,
                        display_question=disp_q,
                        question_audio_url=q_audio,
                        weight=1.0,
                    )
                )

        self._entries = entries
        self._faq_meta = faq_meta
        self._matrix, self._word_matrix = self._fit_vectors(entries)
        return len(entries)

    def match(
        self,
        query: str,
        lang: str,
        threshold: float = 0.62,
        margin: float = 0.03,
    ) -> MatchResult:
        raw_q, folded_q = normalize_text(query)
        if not folded_q or not self._entries or self._matrix is None:
            return MatchResult(outcome="unsure", faq_id=None, confidence=0.0, candidates=[])

        best_by_faq: dict[int, float] = {}

        if self._st_model is not None:
            q_vec = self._encode_dense_query(folded_q)
            cos_scores = np.dot(self._matrix, q_vec)
            for idx, entry in enumerate(self._entries):
                if entry.lang != lang and entry.lang != "en":
                    continue
                cos_sim = float(max(0.0, min(1.0, cos_scores[idx])))
                fuzzy_raw = fuzz.token_set_ratio(raw_q, entry.raw_text)
                fuzzy_folded = fuzz.token_set_ratio(folded_q, entry.folded_text)
                fuzzy_sim = max(fuzzy_raw, fuzzy_folded) / 100.0
                combined = (0.8 * cos_sim + 0.2 * fuzzy_sim) * entry.weight
                if lang != "en" and entry.lang == "en":
                    combined *= 0.95
                if combined > best_by_faq.get(entry.faq_id, -1.0):
                    best_by_faq[entry.faq_id] = combined
        else:
            assert self._tfidf is not None and self._word_tfidf is not None and self._word_matrix is not None
            exp_q, q_toks = expand_and_stem(folded_q)
            q_tok_set = set(q_toks)
            c_vec = self._transform_unit(self._tfidf, exp_q)
            w_vec = self._transform_unit(self._word_tfidf, " ".join(q_toks) or exp_q)
            char_scores = np.dot(self._matrix, c_vec)
            word_scores = np.dot(self._word_matrix, w_vec)

            for idx, entry in enumerate(self._entries):
                if entry.lang != lang and entry.lang != "en":
                    continue
                cs = float(max(0.0, min(1.0, char_scores[idx])))
                ws = float(max(0.0, min(1.0, word_scores[idx])))
                fz = max(
                    fuzz.token_set_ratio(exp_q, entry.expanded_text),
                    fuzz.WRatio(exp_q, entry.expanded_text),
                ) / 100.0
                overlap = (
                    len(q_tok_set & set(entry.tokens))
                    / float(max(1, min(len(q_tok_set), len(set(entry.tokens)))))
                    if (q_tok_set and entry.tokens)
                    else 0.0
                )

                if not q_tok_set:
                    combined = 0.25 * cs
                else:
                    combined = (0.25 * cs + 0.35 * ws + 0.20 * fz + 0.20 * overlap) * entry.weight
                    if overlap >= 0.60 and (ws >= 0.30 or fz >= 0.68):
                        combined = min(0.97, combined + 0.16)

                if lang != "en" and entry.lang == "en":
                    combined *= 0.95
                if combined > best_by_faq.get(entry.faq_id, -1.0):
                    best_by_faq[entry.faq_id] = combined

        if not best_by_faq:
            return MatchResult(outcome="unsure", faq_id=None, confidence=0.0, candidates=[])

        ranked = sorted(best_by_faq.items(), key=lambda kv: kv[1], reverse=True)
        candidates: list[MatchCandidate] = []
        for faq_id, score in ranked[:3]:
            meta = self._faq_meta.get((faq_id, lang)) or self._faq_meta.get((faq_id, "en"))
            q_text, q_audio = meta if meta else ("", None)
            candidates.append(
                MatchCandidate(
                    faq_id=faq_id,
                    question=q_text,
                    question_audio_url=q_audio,
                    score=round(score, 4),
                )
            )

        best_faq_id, best_score = ranked[0]
        runner_up_score = ranked[1][1] if len(ranked) > 1 else 0.0

        if best_score >= threshold and (len(ranked) == 1 or (best_score - runner_up_score) >= margin):
            return MatchResult(
                outcome="answer",
                faq_id=best_faq_id,
                confidence=round(best_score, 4),
                candidates=candidates,
            )

        return MatchResult(
            outcome="unsure",
            faq_id=None,
            confidence=round(best_score, 4),
            candidates=candidates,
        )
