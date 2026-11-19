"""Public read-only, voice ask, and feedback API endpoints for HealthYarn."""

from __future__ import annotations

import hashlib
import io
import json
import logging
import wave
from typing import Literal, Optional

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    Response,
    UploadFile,
    status,
)
from pydantic import BaseModel, Field as PydanticField
from sqlmodel import Session, select

from app.config import get_settings
from app.db import get_session
from app.models import (
    AppMeta,
    Clinic,
    FAQItem,
    QueryLog,
    RedFlagRule,
    SampleQuestion,
    SystemMessage,
    Topic,
    Translation,
)
from app.services.gemini_router import (
    CatalogEntry,
    DiagnosisStatus,
    GeminiRouteDecision,
    GeminiRouterError,
    GeminiVoiceRouter,
    detect_diagnosis_status,
)
from app.services.limiter import limiter
from app.services.logging import record_query_log
from app.services.matcher import FAQMatcher
from app.services.redflag import check_red_flags
from app.services.stt import STTError, STTProvider, get_stt_provider
from app.services.tts import EphemeralTTSService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["public"])

SUPPORTED_LANGS = {"en", "yo", "pcm"}
ALLOWED_AUDIO_MIMES = {
    "audio/webm",
    "video/webm",
    "audio/ogg",
    "audio/wav",
    "audio/x-wav",
    "audio/wave",
    "audio/mp4",
    "audio/x-m4a",
    "audio/aac",
    "audio/mpeg",
    "audio/mp3",
    "audio/flac",
    "application/ogg",
}


def validate_lang(lang: str) -> str:
    cleaned = lang.strip().lower()
    if cleaned not in SUPPORTED_LANGS:
        raise HTTPException(status_code=400, detail="Unsupported language. Use 'en', 'yo', or 'pcm'.")
    return cleaned


def get_meta_dict(session: Session) -> dict[str, str]:
    rows = session.exec(select(AppMeta)).all()
    return {r.key: r.value for r in rows}


def is_demo_mode(session: Session) -> bool:
    meta = get_meta_dict(session)
    if "demo_mode" in meta:
        return meta["demo_mode"].lower() == "true"
    return get_settings().DEMO_MODE


def _topic_name(topic: Topic, lang: str) -> str:
    return getattr(topic, f"name_{lang}", "") or topic.name_en or topic.slug


def _topic_desc(topic: Topic, lang: str) -> str:
    return getattr(topic, f"desc_{lang}", "") or topic.desc_en or ""


def get_matcher_service(request: Request, session: Session) -> FAQMatcher:
    matcher: Optional[FAQMatcher] = getattr(request.app.state, "matcher", None)
    if matcher is None:
        settings = get_settings()
        matcher = FAQMatcher(
            model_name=settings.EMBEDDING_MODEL,
            disable_heavy=settings.DISABLE_HEAVY_EMBEDDINGS,
        )
        matcher.build_index(session)
        request.app.state.matcher = matcher
    return matcher


def get_stt_service(request: Request) -> STTProvider:
    provider: Optional[STTProvider] = getattr(request.app.state, "stt_provider", None)
    if provider is None:
        provider = get_stt_provider(get_settings())
        request.app.state.stt_provider = provider
    return provider


def get_gemini_router_service(request: Request) -> Optional[GeminiVoiceRouter]:
    if hasattr(request.app.state, "gemini_router"):
        return request.app.state.gemini_router
    settings = get_settings()
    key = settings.GEMINI_API_KEY.strip()
    if not key or key.upper() == "TODO":
        return None
    router_svc = GeminiVoiceRouter(
        api_key=key,
        model=settings.GEMINI_MODEL,
        timeout_seconds=settings.STT_TIMEOUT_SECONDS,
    )
    request.app.state.gemini_router = router_svc
    return router_svc


def get_tts_service(request: Request) -> EphemeralTTSService:
    svc: Optional[EphemeralTTSService] = getattr(request.app.state, "tts_service", None)
    if svc is None:
        svc = EphemeralTTSService(get_settings())
        request.app.state.tts_service = svc
    return svc


def _normalize_diagnosis_hint(hint: Optional[str]) -> Optional[DiagnosisStatus]:
    cleaned = (hint or "").strip().lower()
    if cleaned in ("diagnosed", "undiagnosed"):
        return cleaned  # type: ignore[return-value]
    return None


def _check_wav_duration(audio_bytes: bytes, max_seconds: int) -> None:
    if len(audio_bytes) >= 12 and audio_bytes[:4] == b"RIFF" and audio_bytes[8:12] == b"WAVE":
        try:
            with wave.open(io.BytesIO(audio_bytes), "rb") as wf:
                frames = wf.getnframes()
                rate = wf.getframerate()
                if rate > 0 and (frames / float(rate)) > max_seconds:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Audio exceeds maximum duration of {max_seconds} seconds.",
                    )
        except wave.Error:
            pass


class FeedbackRequest(BaseModel):
    log_id: Optional[int] = None
    faq_id: Optional[int] = None
    lang: Optional[Literal["en", "yo", "pcm"]] = None
    rating: Literal[1, -1]


class AskTextRequest(BaseModel):
    text: str = PydanticField(min_length=1, max_length=1000)
    lang: Literal["en", "yo", "pcm"] = "en"
    diagnosis_hint: Optional[Literal["undiagnosed", "diagnosed", "unspecified"]] = None


class TTSRequest(BaseModel):
    text: str = PydanticField(min_length=1, max_length=700)
    lang: Literal["en", "yo", "pcm"] = "en"


def _get_sys_msg(session: Session, key: str, lang: str) -> Optional[SystemMessage]:
    return session.exec(
        select(SystemMessage).where(
            SystemMessage.key == key,
            SystemMessage.lang == lang,
            SystemMessage.status == "published",
        )
    ).first()


def _serialize_faq_answer(
    *,
    session: Session,
    faq: FAQItem,
    tr: Translation,
    lang: str,
    diagnosis_status: DiagnosisStatus = "unspecified",
    log_id: Optional[int] = None,
    confidence: Optional[float] = None,
    include_type: bool = False,
) -> dict:
    topic = session.get(Topic, faq.topic_id)
    disclaimer = _get_sys_msg(session, "disclaimer", lang)
    payload: dict = {
        "faq_id": faq.id,
        "intent_key": faq.intent_key,
        "topic_slug": topic.slug if topic else "",
        "topic_name": _topic_name(topic, lang) if topic else "",
        "lang": lang,
        "question": tr.question_text,
        "answer_text": tr.answer_text,
        "undiagnosed_text": tr.undiagnosed_text or tr.answer_text,
        "diagnosed_text": tr.diagnosed_text or tr.answer_text,
        "question_audio_url": tr.question_audio_url,
        "answer_audio_url": tr.answer_audio_url,
        "undiagnosed_audio_url": tr.undiagnosed_audio_url or tr.answer_audio_url,
        "diagnosed_audio_url": tr.diagnosed_audio_url or tr.answer_audio_url,
        "diagnosis_status": diagnosis_status,
        "answer_source": "verified_faq",
        "suggest_clinics": False,
        "source_reference": faq.source_reference,
        "disclaimer_text": disclaimer.text if disclaimer else "",
        "disclaimer_audio_url": disclaimer.audio_url if disclaimer else None,
        "demo_mode": is_demo_mode(session),
        "log_id": log_id,
    }
    if confidence is not None:
        payload["confidence"] = confidence
    if include_type:
        payload["type"] = "answer"
    return payload


def _serialize_ai_answer(
    *,
    session: Session,
    question: str,
    undiagnosed_text: str,
    diagnosed_text: str,
    lang: str,
    diagnosis_status: DiagnosisStatus,
    suggest_clinics: bool,
    log_id: Optional[int],
    confidence: float,
) -> dict:
    disclaimer = _get_sys_msg(session, "disclaimer", lang)
    primary_text = diagnosed_text if diagnosis_status == "diagnosed" else undiagnosed_text
    return {
        "type": "answer",
        "faq_id": 0,
        "intent_key": "ai_guardrailed_guidance",
        "topic_slug": "",
        "topic_name": "",
        "lang": lang,
        "question": question,
        "answer_text": primary_text,
        "undiagnosed_text": undiagnosed_text,
        "diagnosed_text": diagnosed_text,
        "question_audio_url": None,
        "answer_audio_url": None,
        "undiagnosed_audio_url": None,
        "diagnosed_audio_url": None,
        "diagnosis_status": diagnosis_status,
        "answer_source": "ai_guardrailed",
        "suggest_clinics": suggest_clinics,
        "source_reference": "General WHO & FMOH-aligned health principles (consult a qualified clinician)",
        "disclaimer_text": disclaimer.text if disclaimer else "",
        "disclaimer_audio_url": disclaimer.audio_url if disclaimer else None,
        "demo_mode": is_demo_mode(session),
        "log_id": log_id,
        "confidence": confidence,
    }


def _build_red_flag_response(session: Session, lang: str, input_mode: str) -> dict:
    alert_msg = _get_sys_msg(session, "red_flag_alert", lang) or _get_sys_msg(
        session, "red_flag_alert", "en"
    )
    clinics = session.exec(select(Clinic).order_by(Clinic.state, Clinic.name)).all()
    log_row = record_query_log(
        session,
        lang=lang,
        input_mode=input_mode,
        outcome="red_flag",
        confidence=1.0,
    )
    return {
        "type": "red_flag",
        "message_text": alert_msg.text
        if alert_msg
        else "Urgent medical danger sign detected. Please visit the nearest clinic immediately.",
        "message_audio_url": alert_msg.audio_url if alert_msg else None,
        "clinics": [
            {
                "id": c.id,
                "name": c.name,
                "lga": c.lga,
                "state": c.state,
                "phone": c.phone,
                "type": c.type,
                "lat": c.lat,
                "lng": c.lng,
            }
            for c in clinics
        ],
        "log_id": log_row.id,
    }


def _build_gemini_catalog(session: Session, lang: str) -> tuple[list[CatalogEntry], list[str]]:
    active_faqs = {
        f.id: f
        for f in session.exec(select(FAQItem).where(FAQItem.is_active == True)).all()  # noqa: E712
    }
    translations = session.exec(
        select(Translation).where(Translation.lang == lang, Translation.status == "published")
    ).all()
    en_questions: dict[int, str] = {}
    if lang != "en":
        for tr_en in session.exec(
            select(Translation).where(Translation.lang == "en", Translation.status == "published")
        ).all():
            en_questions[tr_en.faq_id] = tr_en.question_text

    samples_by_faq: dict[int, list[str]] = {}
    for smp in session.exec(
        select(SampleQuestion).where(SampleQuestion.lang.in_({lang, "en"}))  # type: ignore[attr-defined]
    ).all():
        samples_by_faq.setdefault(smp.faq_id, []).append(smp.phrasing)

    catalog: list[CatalogEntry] = []
    for tr in translations:
        faq = active_faqs.get(tr.faq_id)
        if faq and faq.id is not None:
            combined_samples = list(samples_by_faq.get(faq.id, []))
            en_q = en_questions.get(faq.id)
            if en_q and en_q not in combined_samples:
                combined_samples.insert(0, en_q)
            catalog.append(
                CatalogEntry(
                    faq_id=faq.id,
                    intent_key=faq.intent_key,
                    question=tr.question_text,
                    samples=combined_samples,
                )
            )
    rf_patterns = [
        rf.pattern
        for rf in session.exec(
            select(RedFlagRule).where(
                RedFlagRule.lang.in_({lang, "en"}),  # type: ignore[attr-defined]
                RedFlagRule.status == "published",
            )
        ).all()
    ]
    return catalog, rf_patterns


def _resolve_gemini_decision(
    *,
    session: Session,
    matcher: FAQMatcher,
    decision: GeminiRouteDecision,
    lang: str,
    input_mode: str,
    diagnosis_hint: Optional[str] = None,
) -> dict:
    settings = get_settings()
    heard = decision.heard_text.strip()

    # Deterministic keyword red-flag scan ALWAYS complements LLM classification
    if (heard and check_red_flags(session, heard, lang) is not None) or decision.is_red_flag:
        return _build_red_flag_response(session, lang, input_mode)

    resolved_diag: DiagnosisStatus = (
        _normalize_diagnosis_hint(diagnosis_hint)
        or (decision.diagnosis_status if decision.diagnosis_status != "unspecified" else None)
        or detect_diagnosis_status(heard)
    )

    if decision.matched_faq_id is not None and decision.confidence >= settings.MATCH_THRESHOLD:
        faq = session.get(FAQItem, decision.matched_faq_id)
        tr = (
            session.exec(
                select(Translation).where(
                    Translation.faq_id == decision.matched_faq_id,
                    Translation.lang == lang,
                    Translation.status == "published",
                )
            ).first()
            if faq and faq.is_active
            else None
        )
        if faq and tr:
            log_row = record_query_log(
                session,
                lang=lang,
                input_mode=input_mode,
                outcome="answer",
                matched_faq_id=faq.id,
                confidence=decision.confidence,
            )
            return _serialize_faq_answer(
                session=session,
                faq=faq,
                tr=tr,
                lang=lang,
                diagnosis_status=resolved_diag,
                log_id=log_row.id,
                confidence=decision.confidence,
                include_type=True,
            )

    # Local hybrid matcher fallback on Gemini's transcribed heard_text (recovers null/low-confidence & code-switched queries).
    # When Gemini already produced Tier 3 dynamic guidance, require a high >= 0.78 similarity before overriding with an FAQ.
    has_tier3_answer = bool(
        decision.is_valid_health_question and decision.dynamic_undiagnosed_text
    )
    local_threshold = (
        max(settings.MATCH_THRESHOLD, 0.78)
        if has_tier3_answer
        else settings.MATCH_THRESHOLD
    )
    local_res = (
        matcher.match(
            heard,
            lang=lang,
            threshold=local_threshold,
            margin=settings.MATCH_MARGIN,
        )
        if heard
        else None
    )
    if local_res is not None and local_res.outcome == "answer" and local_res.faq_id is not None:
        faq = session.get(FAQItem, local_res.faq_id)
        tr = (
            session.exec(
                select(Translation).where(
                    Translation.faq_id == local_res.faq_id,
                    Translation.lang == lang,
                    Translation.status == "published",
                )
            ).first()
            if faq and faq.is_active
            else None
        )
        if faq and tr:
            log_row = record_query_log(
                session,
                lang=lang,
                input_mode=input_mode,
                outcome="answer",
                matched_faq_id=faq.id,
                confidence=local_res.confidence,
            )
            return _serialize_faq_answer(
                session=session,
                faq=faq,
                tr=tr,
                lang=lang,
                diagnosis_status=resolved_diag,
                log_id=log_row.id,
                confidence=local_res.confidence,
                include_type=True,
            )

    # Tier 3 -> Guardrailed AI general health info for valid out-of-FAQ health questions
    if decision.is_valid_health_question and decision.dynamic_undiagnosed_text:
        dyn_u = decision.dynamic_undiagnosed_text.strip()
        dyn_d = (decision.dynamic_diagnosed_text or dyn_u).strip()
        if check_red_flags(session, dyn_u, lang) is not None:
            return _build_red_flag_response(session, lang, input_mode)
        log_row = record_query_log(
            session,
            lang=lang,
            input_mode=input_mode,
            outcome="ai_answer",
            matched_faq_id=None,
            confidence=decision.confidence,
        )
        return _serialize_ai_answer(
            session=session,
            question=heard,
            undiagnosed_text=dyn_u,
            diagnosed_text=dyn_d,
            lang=lang,
            diagnosis_status=resolved_diag,
            suggest_clinics=decision.suggest_clinics,
            log_id=log_row.id,
            confidence=decision.confidence,
        )

    # Unsure -> collect up to 3 published candidate FAQs (Gemini candidates + local matcher fallback)
    candidates_out: list[dict] = []
    seen_ids: set[int] = set()
    for cid in decision.candidate_faq_ids:
        faq = session.get(FAQItem, cid)
        tr = (
            session.exec(
                select(Translation).where(
                    Translation.faq_id == cid,
                    Translation.lang == lang,
                    Translation.status == "published",
                )
            ).first()
            if faq and faq.is_active
            else None
        )
        if faq and tr and faq.id is not None and faq.id not in seen_ids:
            seen_ids.add(faq.id)
            candidates_out.append(
                {
                    "faq_id": faq.id,
                    "question": tr.question_text,
                    "question_audio_url": tr.question_audio_url,
                }
            )
        if len(candidates_out) >= 3:
            break

    if len(candidates_out) < 3:
        fallback_res = local_res or matcher.match(
            heard or "health",
            lang=lang,
            threshold=settings.MATCH_THRESHOLD,
            margin=settings.MATCH_MARGIN,
        )
        for lc in fallback_res.candidates:
            if lc.faq_id not in seen_ids:
                seen_ids.add(lc.faq_id)
                candidates_out.append(
                    {
                        "faq_id": lc.faq_id,
                        "question": lc.question,
                        "question_audio_url": lc.question_audio_url,
                    }
                )
            if len(candidates_out) >= 3:
                break

    unsure_msg = _get_sys_msg(session, "unsure", lang)
    log_row = record_query_log(
        session,
        lang=lang,
        input_mode=input_mode,
        outcome="unsure",
        confidence=decision.confidence,
        transcript=heard,
        log_unmatched_text=settings.LOG_UNMATCHED_TEXT,
    )
    return {
        "type": "unsure",
        "heard_text": heard,
        "message_text": unsure_msg.text
        if unsure_msg
        else "I am not completely sure what you asked. Did you mean one of these three questions?",
        "message_audio_url": unsure_msg.audio_url if unsure_msg else None,
        "candidates": candidates_out[:3],
        "log_id": log_row.id,
    }


def _run_safety_and_matching(
    *,
    session: Session,
    matcher: FAQMatcher,
    text: str,
    lang: str,
    input_mode: str,
    diagnosis_hint: Optional[str] = None,
) -> dict:
    settings = get_settings()

    # 1. Red-flag check ALWAYS runs before matching
    rf_hit = check_red_flags(session, text, lang)
    if rf_hit is not None:
        return _build_red_flag_response(session, lang, input_mode)

    resolved_diag = _normalize_diagnosis_hint(diagnosis_hint) or detect_diagnosis_status(text)

    # 2. Hybrid semantic + fuzzy FAQ matching
    match_res = matcher.match(
        text,
        lang=lang,
        threshold=settings.MATCH_THRESHOLD,
        margin=settings.MATCH_MARGIN,
    )

    if match_res.outcome == "answer" and match_res.faq_id is not None:
        faq = session.get(FAQItem, match_res.faq_id)
        tr = session.exec(
            select(Translation).where(
                Translation.faq_id == match_res.faq_id,
                Translation.lang == lang,
                Translation.status == "published",
            )
        ).first()
        if faq and tr:
            log_row = record_query_log(
                session,
                lang=lang,
                input_mode=input_mode,
                outcome="answer",
                matched_faq_id=faq.id,
                confidence=match_res.confidence,
            )
            return _serialize_faq_answer(
                session=session,
                faq=faq,
                tr=tr,
                lang=lang,
                diagnosis_status=resolved_diag,
                log_id=log_row.id,
                confidence=match_res.confidence,
                include_type=True,
            )

    # 3. Below threshold or tight tie -> return unsure with top 3 candidates
    unsure_msg = _get_sys_msg(session, "unsure", lang)
    log_row = record_query_log(
        session,
        lang=lang,
        input_mode=input_mode,
        outcome="unsure",
        confidence=match_res.confidence,
        transcript=text,
        log_unmatched_text=settings.LOG_UNMATCHED_TEXT,
    )
    return {
        "type": "unsure",
        "heard_text": text.strip(),
        "message_text": unsure_msg.text
        if unsure_msg
        else "I am not completely sure what you asked. Did you mean one of these three questions?",
        "message_audio_url": unsure_msg.audio_url if unsure_msg else None,
        "candidates": [
            {
                "faq_id": c.faq_id,
                "question": c.question,
                "question_audio_url": c.question_audio_url,
            }
            for c in match_res.candidates[:3]
        ],
        "log_id": log_row.id,
    }


@router.post("/ask")
@limiter.limit("20/minute")
async def ask_question(
    request: Request,
    audio: Optional[UploadFile] = File(default=None),
    lang: Optional[str] = Form(default=None),
    duration_seconds: Optional[float] = Form(default=None),
    diagnosis_hint: Optional[str] = Form(default=None),
    session: Session = Depends(get_session),
) -> dict:
    settings = get_settings()
    matcher = get_matcher_service(request, session)
    gemini_router = get_gemini_router_service(request)

    content_type = (request.headers.get("content-type") or "").lower()
    if "application/json" in content_type:
        try:
            body_raw = await request.json()
        except Exception as exc:
            raise HTTPException(status_code=400, detail="Invalid JSON request body") from exc
        parsed = AskTextRequest.model_validate(body_raw)
        clean_lang = validate_lang(parsed.lang)
        if gemini_router is not None:
            try:
                catalog, rf_examples = _build_gemini_catalog(session, clean_lang)
                if catalog:
                    decision = await gemini_router.route_text(
                        query_text=parsed.text,
                        lang=clean_lang,
                        catalog=catalog,
                        red_flag_examples=rf_examples,
                    )
                    return _resolve_gemini_decision(
                        session=session,
                        matcher=matcher,
                        decision=decision,
                        lang=clean_lang,
                        input_mode="voice",
                        diagnosis_hint=parsed.diagnosis_hint,
                    )
            except (GeminiRouterError, TimeoutError) as exc:
                logger.warning("Gemini text router failed, falling back to local matcher: %s", exc)

        return _run_safety_and_matching(
            session=session,
            matcher=matcher,
            text=parsed.text,
            lang=clean_lang,
            input_mode="voice",
            diagnosis_hint=parsed.diagnosis_hint,
        )

    # Multipart voice upload path
    if audio is None:
        raise HTTPException(status_code=400, detail="Audio file or JSON text payload is required.")

    clean_lang = validate_lang(lang or "en")
    mime_base = (audio.content_type or "").split(";")[0].strip().lower()
    if mime_base not in ALLOWED_AUDIO_MIMES:
        raise HTTPException(status_code=400, detail=f"Unsupported audio MIME type: {mime_base}")

    if duration_seconds is not None and duration_seconds > settings.MAX_AUDIO_SECONDS:
        raise HTTPException(
            status_code=400,
            detail=f"Audio exceeds maximum length of {settings.MAX_AUDIO_SECONDS} seconds.",
        )

    audio_bytes = await audio.read()
    try:
        if not audio_bytes:
            raise HTTPException(status_code=400, detail="Audio recording is empty.")
        if len(audio_bytes) > settings.MAX_AUDIO_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"Audio file exceeds {settings.MAX_AUDIO_BYTES} byte limit.",
            )
        _check_wav_duration(audio_bytes, settings.MAX_AUDIO_SECONDS)

        if gemini_router is not None:
            try:
                catalog, rf_examples = _build_gemini_catalog(session, clean_lang)
                if catalog:
                    decision = await gemini_router.route_audio(
                        audio_bytes=audio_bytes,
                        mime_type=mime_base,
                        lang=clean_lang,
                        catalog=catalog,
                        red_flag_examples=rf_examples,
                    )
                    return _resolve_gemini_decision(
                        session=session,
                        matcher=matcher,
                        decision=decision,
                        lang=clean_lang,
                        input_mode="voice",
                        diagnosis_hint=diagnosis_hint,
                    )
            except (GeminiRouterError, TimeoutError) as exc:
                logger.warning("Gemini audio router failed, falling back to STT+Matcher: %s", exc)

        stt_provider = get_stt_service(request)
        try:
            transcript = await stt_provider.transcribe(
                audio_bytes,
                clean_lang,
                filename=audio.filename or "audio.webm",
            )
        except STTError:
            stt_msg = _get_sys_msg(session, "stt_failed", clean_lang)
            log_row = record_query_log(
                session,
                lang=clean_lang,
                input_mode="voice",
                outcome="error",
            )
            return {
                "type": "error",
                "code": "stt_failed",
                "message_text": stt_msg.text
                if stt_msg
                else "Could not transcribe voice input right now. Please tap a topic.",
                "message_audio_url": stt_msg.audio_url if stt_msg else None,
                "log_id": log_row.id,
            }
    finally:
        # Never persist audio bytes to disk or leave references in memory
        del audio_bytes

    return _run_safety_and_matching(
        session=session,
        matcher=matcher,
        text=transcript,
        lang=clean_lang,
        input_mode="voice",
        diagnosis_hint=diagnosis_hint,
    )


@router.get("/meta")
def read_meta(session: Session = Depends(get_session)) -> dict:
    settings = get_settings()
    meta = get_meta_dict(session)
    demo = is_demo_mode(session)
    content_reviewed = bool(settings.CONTENT_REVIEWED and not demo)
    sys_msgs = session.exec(
        select(SystemMessage).where(
            SystemMessage.status == "published",
            SystemMessage.key.in_(["welcome", "consent", "hero_intro"]),  # type: ignore[attr-defined]
        )
    ).all()
    welcome_audio: dict[str, str | None] = {}
    consent_audio: dict[str, str | None] = {}
    hero_intro_audio: dict[str, str | None] = {}
    for m in sys_msgs:
        if m.key == "welcome":
            welcome_audio[m.lang] = m.audio_url
        elif m.key == "consent":
            consent_audio[m.lang] = m.audio_url
        elif m.key == "hero_intro":
            hero_intro_audio[m.lang] = m.audio_url

    hero_audio: dict[str, str | None] = {
        lang_code: hero_intro_audio.get(lang_code) or welcome_audio.get(lang_code)
        for lang_code in sorted(SUPPORTED_LANGS)
    }

    sample_faq = session.exec(
        select(FAQItem).where(FAQItem.intent_key == "ors_how_to_prepare", FAQItem.is_active == True)  # noqa: E712
    ).first()
    if not sample_faq:
        sample_faq = session.exec(select(FAQItem).where(FAQItem.is_active == True)).first()  # noqa: E712

    sample_audio: dict[str, str | None] = {lang_code: None for lang_code in sorted(SUPPORTED_LANGS)}
    if sample_faq:
        sample_trs = session.exec(
            select(Translation).where(
                Translation.faq_id == sample_faq.id,
                Translation.status == "published",
            )
        ).all()
        for tr in sample_trs:
            if tr.lang in sample_audio:
                sample_audio[tr.lang] = tr.answer_audio_url

    return {
        "demo_mode": demo,
        "content_reviewed": content_reviewed,
        "content_last_updated": meta.get("content_last_updated", ""),
        "clinical_reviewers": meta.get("clinical_reviewers", "Clinical Review Board"),
        "language_reviewers": meta.get("language_reviewers", "Yorùbá & Nigerian Pidgin Review Team"),
        "welcome_audio": welcome_audio,
        "consent_audio": consent_audio,
        "hero_audio": hero_audio,
        "sample_audio": sample_audio,
    }


@router.get("/topics")
def list_topics(
    lang: str = Query(default="en"),
    session: Session = Depends(get_session),
) -> dict:
    lang = validate_lang(lang)
    topics = session.exec(select(Topic).order_by(Topic.sort_order)).all()
    faqs = session.exec(select(FAQItem).where(FAQItem.is_active == True)).all()  # noqa: E712
    faq_by_id = {f.id: f for f in faqs}

    translations = session.exec(
        select(Translation).where(Translation.lang == lang, Translation.status == "published")
    ).all()

    questions_by_topic: dict[int, list[dict]] = {}
    for tr in translations:
        faq = faq_by_id.get(tr.faq_id)
        if not faq:
            continue
        questions_by_topic.setdefault(faq.topic_id, []).append(
            {
                "faq_id": faq.id,
                "intent_key": faq.intent_key,
                "question": tr.question_text,
                "question_audio_url": tr.question_audio_url,
            }
        )

    result_topics = []
    for t in topics:
        qs = sorted(questions_by_topic.get(t.id, []), key=lambda q: q["faq_id"])
        result_topics.append(
            {
                "id": t.id,
                "slug": t.slug,
                "icon": t.icon,
                "sort_order": t.sort_order,
                "name": _topic_name(t, lang),
                "description": _topic_desc(t, lang),
                "questions": qs,
            }
        )

    return {
        "lang": lang,
        "demo_mode": is_demo_mode(session),
        "topics": result_topics,
    }


@router.get("/answers/{faq_id}")
def get_answer(
    faq_id: int,
    lang: str = Query(default="en"),
    record_tap: bool = Query(default=True),
    diagnosis_status: str = Query(default="unspecified"),
    session: Session = Depends(get_session),
) -> dict:
    lang = validate_lang(lang)
    faq = session.get(FAQItem, faq_id)
    if not faq or not faq.is_active:
        raise HTTPException(status_code=404, detail="FAQ item not found")

    tr = session.exec(
        select(Translation).where(
            Translation.faq_id == faq_id,
            Translation.lang == lang,
            Translation.status == "published",
        )
    ).first()
    if not tr:
        raise HTTPException(status_code=404, detail="Published answer not found for this language")

    log_id: Optional[int] = None
    if record_tap:
        log_row = record_query_log(
            session,
            lang=lang,
            input_mode="tap",
            matched_faq_id=faq.id,
            confidence=1.0,
            outcome="answer",
        )
        log_id = log_row.id

    resolved_diag: DiagnosisStatus = _normalize_diagnosis_hint(diagnosis_status) or "unspecified"
    return _serialize_faq_answer(
        session=session,
        faq=faq,
        tr=tr,
        lang=lang,
        diagnosis_status=resolved_diag,
        log_id=log_id,
    )


@router.get("/bundle")
def get_offline_bundle(
    lang: str = Query(default="en"),
    session: Session = Depends(get_session),
) -> dict:
    lang = validate_lang(lang)
    topics = session.exec(select(Topic).order_by(Topic.sort_order)).all()
    faqs = session.exec(select(FAQItem).where(FAQItem.is_active == True)).all()  # noqa: E712
    faq_by_id = {f.id: f for f in faqs}

    translations = session.exec(
        select(Translation).where(Translation.lang == lang, Translation.status == "published")
    ).all()

    items_by_topic: dict[int, list[dict]] = {}
    audio_urls: set[str] = set()

    for tr in translations:
        faq = faq_by_id.get(tr.faq_id)
        if not faq:
            continue
        u_audio = tr.undiagnosed_audio_url or tr.answer_audio_url
        d_audio = tr.diagnosed_audio_url or tr.answer_audio_url
        for url in (tr.question_audio_url, tr.answer_audio_url, u_audio, d_audio):
            if url:
                audio_urls.add(url)
        items_by_topic.setdefault(faq.topic_id, []).append(
            {
                "faq_id": faq.id,
                "intent_key": faq.intent_key,
                "source_reference": faq.source_reference,
                "question": tr.question_text,
                "answer_text": tr.answer_text,
                "undiagnosed_text": tr.undiagnosed_text or tr.answer_text,
                "diagnosed_text": tr.diagnosed_text or tr.answer_text,
                "question_audio_url": tr.question_audio_url,
                "answer_audio_url": tr.answer_audio_url,
                "undiagnosed_audio_url": u_audio,
                "diagnosed_audio_url": d_audio,
            }
        )

    bundle_topics = []
    for t in topics:
        qs = sorted(items_by_topic.get(t.id, []), key=lambda q: q["faq_id"])
        bundle_topics.append(
            {
                "id": t.id,
                "slug": t.slug,
                "icon": t.icon,
                "sort_order": t.sort_order,
                "name": _topic_name(t, lang),
                "description": _topic_desc(t, lang),
                "items": qs,
            }
        )

    sys_msgs = session.exec(
        select(SystemMessage).where(SystemMessage.lang == lang, SystemMessage.status == "published")
    ).all()
    system_messages: dict[str, dict] = {}
    for m in sys_msgs:
        if m.audio_url:
            audio_urls.add(m.audio_url)
        system_messages[m.key] = {
            "text": m.text,
            "audio_url": m.audio_url,
        }

    clinics = session.exec(select(Clinic).order_by(Clinic.state, Clinic.name)).all()
    clinic_list = [
        {
            "id": c.id,
            "name": c.name,
            "lga": c.lga,
            "state": c.state,
            "phone": c.phone,
            "type": c.type,
            "lat": c.lat,
            "lng": c.lng,
        }
        for c in clinics
    ]

    settings = get_settings()
    meta = get_meta_dict(session)
    demo = is_demo_mode(session)
    content_reviewed = bool(settings.CONTENT_REVIEWED and not demo)
    payload_for_hash = {
        "lang": lang,
        "demo_mode": demo,
        "content_reviewed": content_reviewed,
        "topics": bundle_topics,
        "system_messages": system_messages,
        "clinics": clinic_list,
    }
    version_hash = hashlib.sha256(
        json.dumps(payload_for_hash, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()[:16]

    return {
        "lang": lang,
        "version_hash": version_hash,
        "demo_mode": demo,
        "content_reviewed": content_reviewed,
        "meta": {
            "content_last_updated": meta.get("content_last_updated", ""),
            "clinical_reviewers": meta.get("clinical_reviewers", "Clinical Review Board"),
            "language_reviewers": meta.get("language_reviewers", "Yorùbá & Nigerian Pidgin Review Team"),
        },
        "topics": bundle_topics,
        "system_messages": system_messages,
        "clinics": clinic_list,
        "audio_urls": sorted(audio_urls),
    }


@router.get("/clinics")
def list_clinics(
    state: Optional[str] = Query(default=None),
    session: Session = Depends(get_session),
) -> dict:
    clinics = session.exec(select(Clinic).order_by(Clinic.state, Clinic.name)).all()
    if state:
        s_lower = state.strip().lower()
        clinics = [c for c in clinics if c.state.lower() == s_lower]
    return {
        "clinics": [
            {
                "id": c.id,
                "name": c.name,
                "lga": c.lga,
                "state": c.state,
                "phone": c.phone,
                "type": c.type,
                "lat": c.lat,
                "lng": c.lng,
            }
            for c in clinics
        ]
    }


@router.post("/feedback", status_code=status.HTTP_204_NO_CONTENT)
def submit_feedback(
    body: FeedbackRequest,
    session: Session = Depends(get_session),
) -> Response:
    if body.log_id is not None:
        log = session.get(QueryLog, body.log_id)
        if not log:
            raise HTTPException(status_code=404, detail="Query log not found")
        log.rating = body.rating
        session.add(log)
        session.commit()
    elif body.faq_id is not None:
        log = QueryLog(
            lang=body.lang or "en",
            input_mode="tap",
            matched_faq_id=body.faq_id,
            confidence=1.0,
            outcome="answer",
            rating=body.rating,
        )
        session.add(log)
        session.commit()
    else:
        raise HTTPException(status_code=400, detail="Provide log_id or faq_id")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/tts")
@limiter.limit("20/minute")
async def synthesize_ephemeral_tts(
    request: Request,
    body: TTSRequest,
) -> Response:
    tts_svc = get_tts_service(request)
    if hasattr(tts_svc, "synthesize_ogg_with_meta"):
        res = await tts_svc.synthesize_ogg_with_meta(body.text, body.lang)
        if res is None:
            audio_bytes = None
            provider = "none"
        else:
            audio_bytes, provider = res
    else:
        audio_bytes = await tts_svc.synthesize_ogg(body.text, body.lang)
        provider = "unknown"

    if not audio_bytes:
        raise HTTPException(
            status_code=503,
            detail="Live voice synthesis temporarily unavailable.",
        )
    return Response(
        content=audio_bytes,
        media_type="audio/ogg",
        headers={
            "Cache-Control": "no-store",
            "X-TTS-Provider": provider,
        },
    )
