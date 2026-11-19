"""On-demand ephemeral Nigerian TTS synthesizer (Spitch & YarnGPT with cooldown + RAM cache)."""

from __future__ import annotations

import asyncio
from collections import OrderedDict
import logging
import time
from typing import Optional
import unicodedata

import httpx

from app.config import Settings

logger = logging.getLogger(__name__)

_VALID_PROVIDERS = ("spitch", "yarngpt")


def _parse_provider_order(raw: str, *, fallback: list[str] | None = None) -> list[str]:
    seen: list[str] = []
    for part in (raw or "").split(","):
        name = part.strip().lower()
        if name in _VALID_PROVIDERS and name not in seen:
            seen.append(name)
    if seen:
        return seen
    return list(fallback) if fallback is not None else []


def _is_quota_error(exc: Exception) -> bool:
    if getattr(exc, "status_code", None) == 402:
        return True
    resp = getattr(exc, "response", None)
    if getattr(resp, "status_code", None) == 402:
        return True
    msg = str(exc).lower()
    return "insufficient_credits" in msg or "quota_exceeded" in msg or " 402 " in msg or "status/402" in msg or msg.startswith("error code: 402")


def _has_sparse_yoruba_diacritics(text: str) -> bool:
    nfd = unicodedata.normalize("NFD", text or "")
    letters = sum(1 for ch in nfd if ch.isalpha())
    if letters < 15:
        return False
    marks = sum(1 for ch in nfd if unicodedata.combining(ch) > 0)
    return (marks / letters) < 0.14


class EphemeralTTSService:
    """Synthesizes short audio clips strictly in memory without persisting to disk."""

    def __init__(self, settings: Settings) -> None:
        self.spitch_api_key = (settings.SPITCH_API_KEY or "").strip()
        self.yarngpt_api_key = (settings.YARNGPT_API_KEY or "").strip()
        self.yarngpt_base_url = (settings.YARNGPT_BASE_URL or "https://api.yarngpt.ai").rstrip("/")

        self.provider_order = _parse_provider_order(
            getattr(settings, "TTS_PROVIDER_ORDER", "spitch,yarngpt"),
            fallback=["spitch", "yarngpt"],
        )
        self.yo_provider_order = _parse_provider_order(
            getattr(settings, "TTS_YO_PROVIDER_ORDER", ""),
            fallback=[],
        )
        spitch_yo = (getattr(settings, "SPITCH_VOICE_YO", "sade") or "sade").strip() or "sade"
        yarngpt_yo = (getattr(settings, "YARNGPT_VOICE_YO", "wura") or "wura").strip() or "wura"
        self.spitch_voices: dict[str, str] = {
            "en": "remi",
            "pcm": "ufoma",
            "yo": spitch_yo,
        }
        self.yarngpt_voices: dict[str, str] = {
            "en": "idera",
            "pcm": "idera",
            "yo": yarngpt_yo,
        }
        self.enable_spitch_tone_mark = bool(
            getattr(settings, "TTS_ENABLE_SPITCH_TONE_MARK", True)
        )
        self.cooldown_seconds = 300.0
        self.cache_ttl_seconds = 900.0
        self.cache_max_entries = 32
        self._cooldown_until: dict[str, float] = {}
        # Strict RAM-only LRU cache: (lang, cleaned_text) -> (expires_at, audio_bytes, provider_name)
        self._cache: OrderedDict[tuple[str, str], tuple[float, bytes, str]] = OrderedDict()

    def _providers_for_lang(self, lang: str) -> list[str]:
        if lang == "yo" and self.yo_provider_order:
            return list(self.yo_provider_order)
        return list(self.provider_order)

    def _has_key(self, provider: str) -> bool:
        if provider == "spitch":
            return bool(self.spitch_api_key and self.spitch_api_key.upper() != "TODO")
        if provider == "yarngpt":
            return bool(self.yarngpt_api_key and self.yarngpt_api_key.upper() != "TODO")
        return False

    def _is_in_cooldown(self, provider: str) -> bool:
        until = self._cooldown_until.get(provider, 0.0)
        return time.monotonic() < until

    def _mark_cooldown(self, provider: str, exc: Exception) -> None:
        self._cooldown_until[provider] = time.monotonic() + self.cooldown_seconds
        logger.warning(
            "%s TTS returned 402 quota/credit error; pausing provider for %.0fs: %s",
            provider.upper(),
            self.cooldown_seconds,
            exc,
        )

    def _get_cached(self, key: tuple[str, str]) -> Optional[tuple[bytes, str]]:
        entry = self._cache.get(key)
        if entry is None:
            return None
        expires_at, audio_bytes, provider_name = entry
        if time.monotonic() >= expires_at:
            del self._cache[key]
            return None
        self._cache.move_to_end(key)
        return audio_bytes, provider_name

    def _put_cached(self, key: tuple[str, str], audio_bytes: bytes, provider_name: str) -> None:
        self._cache[key] = (
            time.monotonic() + self.cache_ttl_seconds,
            audio_bytes,
            provider_name,
        )
        self._cache.move_to_end(key)
        while len(self._cache) > self.cache_max_entries:
            self._cache.popitem(last=False)

    async def _maybe_tone_mark_yoruba(self, text: str) -> str:
        if (
            not self.enable_spitch_tone_mark
            or not self._has_key("spitch")
            or self._is_in_cooldown("spitch")
            or not _has_sparse_yoruba_diacritics(text)
        ):
            return text

        try:
            marked = await self._tone_mark_spitch(text)
            if marked and marked.strip():
                return marked.strip()
        except Exception as exc:
            if _is_quota_error(exc):
                self._mark_cooldown("spitch", exc)
            else:
                logger.warning("Spitch Yorùbá tone_mark skipped: %s", exc)
        return text

    async def _tone_mark_spitch(self, text: str) -> str:
        from spitch import Spitch  # type: ignore

        def _call() -> str:
            client = Spitch(api_key=self.spitch_api_key)
            resp = client.text.tone_mark(language="yo", text=text)
            return getattr(resp, "text", "") or ""

        return await asyncio.wait_for(asyncio.to_thread(_call), timeout=4.0)

    async def synthesize_ogg_with_meta(
        self, text: str, lang: str
    ) -> Optional[tuple[bytes, str]]:
        cleaned = " ".join((text or "").split()).strip()
        if not cleaned:
            return None

        cache_key = (lang, cleaned)
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        synth_text = await self._maybe_tone_mark_yoruba(cleaned) if lang == "yo" else cleaned

        for provider in self._providers_for_lang(lang):
            if not self._has_key(provider) or self._is_in_cooldown(provider):
                continue
            try:
                if provider == "spitch":
                    audio = await self._synthesize_spitch(synth_text, lang)
                else:
                    audio = await self._synthesize_yarngpt(synth_text, lang)
                if audio and len(audio) > 64:
                    self._put_cached(cache_key, audio, provider)
                    return audio, provider
            except Exception as exc:
                if _is_quota_error(exc):
                    self._mark_cooldown(provider, exc)
                else:
                    logger.warning("On-demand %s TTS failed: %s", provider, exc)

        return None

    async def synthesize_ogg(self, text: str, lang: str) -> Optional[bytes]:
        result = await self.synthesize_ogg_with_meta(text, lang)
        return result[0] if result is not None else None

    async def _synthesize_spitch(self, text: str, lang: str) -> bytes:
        from spitch import Spitch  # type: ignore

        voice = self.spitch_voices.get(lang, "remi")
        api_lang = "en" if lang == "pcm" else lang

        def _call() -> bytes:
            client = Spitch(api_key=self.spitch_api_key)
            resp = client.speech.generate(
                text=text,
                voice=voice,  # type: ignore[arg-type]
                language=api_lang,
                format="ogg_opus",
            )
            return resp.read()

        return await asyncio.wait_for(asyncio.to_thread(_call), timeout=12.0)

    async def _synthesize_yarngpt(self, text: str, lang: str) -> bytes:
        voice = self.yarngpt_voices.get(lang, "idera")
        headers = {
            "Authorization": f"Bearer {self.yarngpt_api_key}",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=12.0, follow_redirects=True) as client:
            prep = await client.post(
                f"{self.yarngpt_base_url}/api/v1/tts/prepare",
                headers=headers,
                json={"text": text, "voice": voice, "output_format": "opus"},
            )
            prep.raise_for_status()
            data = prep.json()
            stream_path = str(data.get("stream_url") or "")
            if not stream_path:
                ticket = data.get("ticket", "")
                stream_path = f"/api/v1/tts/stream/{ticket}"
            stream_url = (
                stream_path
                if stream_path.startswith("http")
                else f"{self.yarngpt_base_url}{stream_path}"
            )
            # Signed stream tickets carry auth in URL; do not attach Bearer header
            audio_resp = await client.get(stream_url)
            audio_resp.raise_for_status()
            if audio_resp.headers.get("X-Yarn-Partial") == "1":
                raise RuntimeError("Partial audio returned from YarnGPT stream")
            return audio_resp.content
