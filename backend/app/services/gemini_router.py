"""Gemini Multimodal Voice & Text Intent Router with diagnosis-status detection."""

from __future__ import annotations

import asyncio
import base64
import logging
import re
from typing import Any, Iterable, Literal, Optional

from pydantic import BaseModel, Field

DiagnosisStatus = Literal["undiagnosed", "diagnosed", "unspecified"]

logger = logging.getLogger(__name__)

# Check negative/undiagnosed patterns BEFORE diagnosed patterns so phrases like
# "I have not been diagnosed" do not trigger positive diagnosis markers.
_UNDIAGNOSED_PATTERNS = [
    r"\bnot (?:yet )?(?:been )?(?:tested|diagnosed|checked)\b",
    r"\b(?:never|not)\s+(?:been\s+)?(?:tested|diagnosed)\b",
    r"\bhaven['’]?t (?:seen|visited|been to|been tested|been diagnosed)\b",
    r"\bhave not (?:seen|visited|been to|been tested|been diagnosed)\b",
    r"\bno test yet\b",
    r"\bnever (?:go|see|visit|do) (?:hospital|clinic|doctor|nurse|test)\b",
    r"\bdoctor never (?:test|check|see)\b",
    r"\bi never (?:do|run) test\b",
    r"\bdo i have\b",
    r"\bcould (?:this|it) be\b",
    r"\bhow do i know if\b",
    r"\bi suspect\b",
    r"k[oò]\s+t[ií][iì]\s+(?:ṣ|s)àyẹ̀wò",
    r"mi\s+[oò]\s+t[ií][iì]\s+(?:ṣ|s)àyẹ̀wò",
    r"mi\s+o\s+tii\s+sayewo",
    r"k[oò]\s+t[ií][iì]\s+lọ\s+s[ií]\s+ilé\s+ìwòsàn",
    r"mi\s+[oò]\s+t[ií][iì]\s+rí\s+dókítà",
    r"mi\s+o\s+tii\s+ri\s+dokita",
]

_DIAGNOSED_PATTERNS = [
    r"\b(?:been |was |am |already |just )?diagnosed\b",
    r"\b(?:doctor|nurse|clinician|pharmacist|hospital|clinic|lab|test) (?:said|told me|confirmed|showed|found|diagnosed|gave me|prescribed)\b",
    r"\btested positive\b",
    r"\btest(?:s)? (?:came back|was|is) positive\b",
    r"\b(?:have|got) a prescription\b",
    r"\bprescribed\b",
    r"\bdoctor (?:talk say|say|don test|don confirm|give me)\b",
    r"\bdem (?:don )?test me\b",
    r"\bhospital (?:give me|say|confirm)\b",
    r"\bresult show say\b",
    r"\bi don do test\b",
    r"dókítà\s+(?:sọ\s+pé|ti\s+ṣàyẹ̀wò|fún\s+mi)",
    r"dokita\s+(?:so\s+pe|ti\s+sayewo|fun\s+mi)",
    r"àyẹ̀wò\s+fihàn",
    r"ayewo\s+fihan",
    r"w[oọ]́n\s+ti\s+ṣàyẹ̀wò",
]

_COMPILED_UNDIAGNOSED = [re.compile(p, re.IGNORECASE) for p in _UNDIAGNOSED_PATTERNS]
_COMPILED_DIAGNOSED = [re.compile(p, re.IGNORECASE) for p in _DIAGNOSED_PATTERNS]


def detect_diagnosis_status(text: str) -> DiagnosisStatus:
    """Heuristically classify whether the user query mentions an existing diagnosis."""
    cleaned = (text or "").strip()
    if not cleaned:
        return "unspecified"
    for pat in _COMPILED_UNDIAGNOSED:
        if pat.search(cleaned):
            return "undiagnosed"
    for pat in _COMPILED_DIAGNOSED:
        if pat.search(cleaned):
            return "diagnosed"
    return "unspecified"


class CatalogEntry(BaseModel):
    faq_id: int
    intent_key: str
    question: str
    samples: list[str] = Field(default_factory=list)


class GeminiRouteDecision(BaseModel):
    heard_text: str = Field(
        description="Clean verbatim transcript of what the user asked in en, pcm, or yo."
    )
    is_red_flag: bool = Field(
        description="True ONLY if immediate life-threatening emergency danger signs are described."
    )
    is_valid_health_question: bool = Field(
        default=True,
        description="True if this is a genuine human health, symptom, maternal/labour, nutrition, first-aid, or medication question; False for non-health chatter or unrelated queries.",
    )
    matched_faq_id: Optional[int] = Field(
        default=None,
        description="Best matching integer faq_id from the approved catalog, or null if not clearly covered by those 20 FAQs.",
    )
    confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Confidence from 0.85 to 1.0 when matched_faq_id or dynamic health guidance clearly answers the user; below 0.50 when non-health or unclear.",
    )
    candidate_faq_ids: list[int] = Field(
        default_factory=list,
        description="Up to 3 most plausible integer faq_id values from the catalog.",
    )
    diagnosis_status: DiagnosisStatus = Field(
        default="unspecified",
        description="Whether the user has already been diagnosed ('diagnosed'), not yet tested ('undiagnosed'), or unspecified ('unspecified').",
    )
    suggest_clinics: bool = Field(
        default=False,
        description="True when matched_faq_id is null, is_valid_health_question is True, and the user should go to or consult a hospital/maternity clinic soon (for example active labour, contractions, water breaking, persistent symptoms).",
    )
    dynamic_undiagnosed_text: Optional[str] = Field(
        default=None,
        description="ONLY when matched_faq_id is null AND is_valid_health_question is True (and is_red_flag is False): 2-4 concise plain-language sentences in the preferred UI language ('en', 'pcm', or 'yo') for someone not yet checked by a clinician. Never diagnose or give drug doses. Null when matched_faq_id is set or non-health.",
    )
    dynamic_diagnosed_text: Optional[str] = Field(
        default=None,
        description="ONLY when matched_faq_id is null AND is_valid_health_question is True (and is_red_flag is False): 2-4 concise plain-language sentences in the preferred UI language ('en', 'pcm', or 'yo') for someone already checked/diagnosed by a doctor or midwife. Never prescribe doses. Null when matched_faq_id is set or non-health.",
    )

    @classmethod
    def strict_json_schema(cls) -> dict[str, Any]:
        schema = cls.model_json_schema()
        schema["required"] = list(cls.model_fields.keys())
        return schema


class GeminiRouterError(RuntimeError):
    """Raised when Gemini routing cannot be completed cleanly."""


_MIME_MAP = {
    "audio/x-wav": "audio/wav",
    "audio/wave": "audio/wav",
    "audio/mp4": "audio/m4a",
}


def normalize_gemini_audio_mime(mime_type: str) -> str:
    base = (mime_type or "audio/wav").split(";")[0].strip().lower()
    return _MIME_MAP.get(base, base or "audio/wav")


class GeminiVoiceRouter:
    """Single-step Multimodal Voice & Text Intent Router built on google-genai Interactions."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str = "gemini-3.5-flash-lite",
        timeout_seconds: float = 12.0,
        client: Optional[Any] = None,
    ) -> None:
        self.api_key = api_key.strip()
        self.model = model.strip() or "gemini-3.5-flash-lite"
        self.timeout_seconds = timeout_seconds
        self._client = client

    def _get_client(self) -> Any:
        if self._client is not None:
            return self._client
        if not self.api_key:
            raise GeminiRouterError("GEMINI_API_KEY is not configured.")
        from google import genai

        self._client = genai.Client(api_key=self.api_key)
        return self._client

    @staticmethod
    def _build_prompt(
        *,
        lang: str,
        catalog: Iterable[CatalogEntry],
        red_flag_examples: Iterable[str],
        query_text: Optional[str] = None,
    ) -> tuple[str, str]:
        catalog_lines = []
        for item in catalog:
            sample_hint = "; ".join(item.samples[:3])
            line = f"- faq_id={item.faq_id} ({item.intent_key}): {item.question}"
            if sample_hint:
                line += f" | examples: {sample_hint}"
            catalog_lines.append(line)

        rf_hint = ", ".join(list(red_flag_examples)[:12])
        system_instruction = (
            "You are HealthYarn's strict 3-tier multimodal health router for Nigerian communities "
            "(English 'en', Nigerian Pidgin 'pcm', and Yorùbá 'yo'). "
            "The speaker may talk in English, Pidgin, Yorùbá, or mix languages regardless of the UI language tab. "
            "Follow these 3 strict tiers:\n"
            "TIER 1 (is_red_flag=true): Set True ONLY if someone is CURRENTLY experiencing an acute life-threatening emergency "
            "(convulsions/seizures, unconscious/not waking, cannot breathe, heavy vaginal bleeding in pregnancy, unable to keep any fluids down, "
            "crushing chest pain, or swallowing poison). Set is_red_flag=false for educational questions AND for practical urgent guidance like early/active labour without heavy bleeding or collapse.\n"
            "TIER 2 (matched_faq_id): If the question clearly matches one of the 20 approved catalog FAQ IDs, set matched_faq_id to that integer id, "
            "is_valid_health_question=true, confidence between 0.85 and 1.0, suggest_clinics=false, dynamic_undiagnosed_text=null, dynamic_diagnosed_text=null.\n"
            "TIER 3 (Guardrailed general health info): If matched_faq_id is null AND is_valid_health_question=true (for example 'my wife is in labor, what should I do?', cough, mild rash, ulcer, typhoid, or maternal care): "
            f"write calm, concise (2-3 short natural spoken sentences, about 25-45 words max) WHO/FMOH-aligned general guidance in language '{lang}' "
            "('en'=simple Nigerian English, 'pcm'=natural Nigerian Pidgin, 'yo'=natural Yorùbá written for spoken Nigerian voice synthesis) "
            "for BOTH dynamic_undiagnosed_text (what to do before seeing a clinician) AND dynamic_diagnosed_text (following clinician/midwife care). "
            "For 'yo', ALWAYS use complete Yorùbá tonal diacritics (à, á, è, é, ẹ, ẹ̀, ẹ́, ì, í, ò, ó, ọ, ọ̀, ọ́, ṣ, ù, ú), keep proper word spacing (never fuse words like 'ìyípadàkankan'), and write words naturally for speech without raw English acronyms (no 'WHO', 'FMOH', 'ACT', or 'ORS'). "
            "NEVER state a diagnosis ('you have X') and NEVER recommend drug names or specific dosages. "
            "Set suggest_clinics=true if they should visit a hospital, maternity centre, or clinic promptly (always True for labour/water breaking).\n"
            "OUT OF SCOPE (is_valid_health_question=false): For non-health questions (e.g., food/rice prices, sports, weather, jokes, greetings), "
            "set matched_faq_id=null, is_valid_health_question=false, suggest_clinics=false, confidence below 0.40, dynamic_undiagnosed_text=null, dynamic_diagnosed_text=null.\n"
            "Always classify diagnosis_status ('diagnosed', 'undiagnosed', or 'unspecified'), populate heard_text, and return ONLY valid JSON matching the schema."
        )
        prompt_parts = [
            f"Preferred UI language: {lang}.",
            "Approved FAQ Catalog (select matched_faq_id strictly from these integer faq_id values):",
            "\n".join(catalog_lines),
        ]
        if rf_hint:
            prompt_parts.append(f"Emergency red-flag trigger concepts ({lang}): {rf_hint}")
        if query_text is not None:
            prompt_parts.append(f"User text query: {query_text}")
        else:
            prompt_parts.append(
                "Listen to the attached audio recording of the user's question in English, Pidgin, or Yorùbá and classify it."
            )
        return system_instruction, "\n\n".join(prompt_parts)

    def _generation_config(self) -> dict[str, str]:
        lowered = self.model.lower()
        if "flash-lite" in lowered or "3.6-flash" in lowered or "3-flash" in lowered:
            return {"thinking_level": "minimal"}
        return {"thinking_level": "low"}

    def _call_sync(
        self,
        *,
        system_instruction: str,
        input_payload: Any,
    ) -> GeminiRouteDecision:
        client = self._get_client()
        try:
            interaction = client.interactions.create(
                model=self.model,
                input=input_payload,
                system_instruction=system_instruction,
                store=False,
                generation_config=self._generation_config(),
                response_format={
                    "type": "text",
                    "mime_type": "application/json",
                    "schema": GeminiRouteDecision.strict_json_schema(),
                },
                timeout=self.timeout_seconds,
            )
            raw_json = getattr(interaction, "output_text", None)
            if not raw_json:
                raise GeminiRouterError("Gemini returned empty output_text.")
            return GeminiRouteDecision.model_validate_json(raw_json)
        except GeminiRouterError:
            raise
        except Exception as exc:
            raise GeminiRouterError(f"Gemini interaction failed: {exc}") from exc

    @staticmethod
    def _sanitize_decision(
        decision: GeminiRouteDecision,
        valid_ids: set[int],
    ) -> GeminiRouteDecision:
        matched = decision.matched_faq_id if decision.matched_faq_id in valid_ids else None
        candidates: list[int] = []
        for cid in decision.candidate_faq_ids:
            if cid in valid_ids and cid not in candidates:
                candidates.append(cid)
            if len(candidates) >= 3:
                break
        if matched is not None and matched not in candidates:
            candidates.insert(0, matched)
            candidates = candidates[:3]
        diag = decision.diagnosis_status
        if diag == "unspecified" and decision.heard_text:
            diag = detect_diagnosis_status(decision.heard_text)

        dyn_u = (decision.dynamic_undiagnosed_text or "").strip() or None
        dyn_d = (decision.dynamic_diagnosed_text or "").strip() or None
        is_valid_health = bool(decision.is_valid_health_question or matched is not None)
        suggest_clinics = bool(decision.suggest_clinics) if (is_valid_health and matched is None) else False

        if matched is not None:
            dyn_u = None
            dyn_d = None
        elif not is_valid_health:
            dyn_u = None
            dyn_d = None
        elif dyn_u and not dyn_d:
            dyn_d = dyn_u
        elif dyn_d and not dyn_u:
            dyn_u = dyn_d

        if matched is not None:
            confidence = decision.confidence if decision.confidence > 0.0 else 0.9
        elif is_valid_health and dyn_u is not None:
            confidence = decision.confidence if decision.confidence > 0.0 else 0.85
        else:
            confidence = min(decision.confidence, 0.49) if not is_valid_health else 0.0

        return GeminiRouteDecision(
            heard_text=decision.heard_text.strip(),
            is_red_flag=decision.is_red_flag,
            is_valid_health_question=is_valid_health,
            matched_faq_id=matched,
            confidence=confidence,
            candidate_faq_ids=candidates,
            diagnosis_status=diag,
            suggest_clinics=suggest_clinics,
            dynamic_undiagnosed_text=dyn_u,
            dynamic_diagnosed_text=dyn_d,
        )

    async def _run_with_timeout(
        self,
        *,
        system_instruction: str,
        input_payload: Any,
    ) -> GeminiRouteDecision:
        try:
            return await asyncio.wait_for(
                asyncio.to_thread(
                    self._call_sync,
                    system_instruction=system_instruction,
                    input_payload=input_payload,
                ),
                timeout=self.timeout_seconds + 2.0,
            )
        except (asyncio.TimeoutError, TimeoutError) as exc:
            raise GeminiRouterError(
                f"Gemini request timed out after {self.timeout_seconds:.1f}s"
            ) from exc

    async def route_audio(
        self,
        *,
        audio_bytes: bytes,
        mime_type: str,
        lang: str,
        catalog: list[CatalogEntry],
        red_flag_examples: list[str],
    ) -> GeminiRouteDecision:
        valid_ids = {c.faq_id for c in catalog}
        system_instruction, prompt_text = self._build_prompt(
            lang=lang,
            catalog=catalog,
            red_flag_examples=red_flag_examples,
        )
        encoded = base64.b64encode(audio_bytes).decode("ascii")
        input_payload = [
            {"type": "text", "text": prompt_text},
            {
                "type": "audio",
                "data": encoded,
                "mime_type": normalize_gemini_audio_mime(mime_type),
            },
        ]
        raw_decision = await self._run_with_timeout(
            system_instruction=system_instruction,
            input_payload=input_payload,
        )
        sanitized = self._sanitize_decision(raw_decision, valid_ids)
        if not sanitized.heard_text:
            raise GeminiRouterError("Gemini returned an empty transcript for audio input.")
        return sanitized

    async def route_text(
        self,
        *,
        query_text: str,
        lang: str,
        catalog: list[CatalogEntry],
        red_flag_examples: list[str],
    ) -> GeminiRouteDecision:
        valid_ids = {c.faq_id for c in catalog}
        system_instruction, prompt_text = self._build_prompt(
            lang=lang,
            catalog=catalog,
            red_flag_examples=red_flag_examples,
            query_text=query_text,
        )
        raw_decision = await self._run_with_timeout(
            system_instruction=system_instruction,
            input_payload=prompt_text,
        )
        if not raw_decision.heard_text:
            raw_decision.heard_text = query_text.strip()
        return self._sanitize_decision(raw_decision, valid_ids)
