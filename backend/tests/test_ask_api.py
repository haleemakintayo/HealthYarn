"""Tests for POST /api/ask outcomes, upload bounds, STT timeout, and NDPA privacy."""

from sqlmodel import select

from app.config import get_settings
from app.models import QueryLog


def test_ask_all_four_outcomes_with_mock_stt(client):
    # 1. answer
    r_ans = client.post(
        "/api/ask",
        files={"audio": ("q.webm", b"MOCK:how to mix ors", "audio/webm")},
        data={"lang": "en", "duration_seconds": "2.5"},
    )
    assert r_ans.status_code == 200
    assert r_ans.json()["type"] == "answer"
    assert r_ans.json()["intent_key"] == "ors_how_to_prepare"

    # 2. red_flag
    r_rf = client.post(
        "/api/ask",
        files={"audio": ("q.webm", b"MOCK:my child is having convulsions", "audio/webm")},
        data={"lang": "en", "duration_seconds": "2.0"},
    )
    assert r_rf.status_code == 200
    assert r_rf.json()["type"] == "red_flag"
    assert len(r_rf.json()["clinics"]) >= 1

    # 3. unsure
    r_uns = client.post(
        "/api/ask",
        files={"audio": ("q.webm", b"MOCK:price of tomatoes in mile 12", "audio/webm")},
        data={"lang": "en", "duration_seconds": "2.0"},
    )
    assert r_uns.status_code == 200
    assert r_uns.json()["type"] == "unsure"
    assert len(r_uns.json()["candidates"]) == 3

    # 4. stt_failed (timeout & provider error)
    r_to = client.post(
        "/api/ask",
        files={"audio": ("q.webm", b"MOCK:TIMEOUT", "audio/webm")},
        data={"lang": "en", "duration_seconds": "2.0"},
    )
    assert r_to.status_code == 200
    assert r_to.json()["type"] == "error"
    assert r_to.json()["code"] == "stt_failed"


def test_ask_rejects_oversized_overlong_and_bad_mime(client):
    # Oversized > 1 MB
    big_bytes = b"0" * (1_048_576 + 100)
    r_big = client.post(
        "/api/ask",
        files={"audio": ("big.webm", big_bytes, "audio/webm")},
        data={"lang": "en"},
    )
    assert r_big.status_code == 413

    # Overlong > 15s
    r_long = client.post(
        "/api/ask",
        files={"audio": ("long.webm", b"MOCK:hello", "audio/webm")},
        data={"lang": "en", "duration_seconds": "18.5"},
    )
    assert r_long.status_code == 400

    # Unsupported MIME
    r_mime = client.post(
        "/api/ask",
        files={"audio": ("bad.txt", b"hello", "text/plain")},
        data={"lang": "en"},
    )
    assert r_mime.status_code == 400


def test_privacy_20_queries_leave_zero_audio_and_zero_transcripts(client, seeded_session):
    settings = get_settings()
    audio_dir = settings.static_audio_dir
    before_files = set(audio_dir.rglob("*")) if audio_dir.exists() else set()

    for i in range(20):
        resp = client.post(
            "/api/ask",
            files={"audio": (f"q{i}.webm", f"MOCK:how to mix ors {i}".encode(), "audio/webm")},
            data={"lang": "en", "duration_seconds": "1.5"},
        )
        assert resp.status_code == 200

    after_files = set(audio_dir.rglob("*")) if audio_dir.exists() else set()
    assert after_files == before_files, "No voice recording may ever be written to disk!"

    logs = seeded_session.exec(select(QueryLog)).all()
    assert len(logs) == 20
    for log_row in logs:
        assert log_row.unmatched_text is None


def test_spitch_stt_passes_filename_tuple(monkeypatch):
    import asyncio
    import sys
    import types
    from app.services.stt import SpitchSTT

    captured = {}

    class FakeResp:
        text = "  how i go mix ors water  "

    class FakeSpeech:
        def transcribe(self, *, language, content):
            captured["language"] = language
            captured["content"] = content
            return FakeResp()

    class FakeSpitch:
        def __init__(self, api_key):
            captured["api_key"] = api_key
            self.speech = FakeSpeech()

    monkeypatch.setitem(sys.modules, "spitch", types.SimpleNamespace(Spitch=FakeSpitch))
    provider = SpitchSTT(api_key="test-key", timeout_seconds=5.0)
    result = asyncio.run(provider.transcribe(b"webm-bytes", "pcm", filename="question.webm"))

    assert result == "how i go mix ors water"
    assert captured["language"] == "en"
    assert captured["content"] == ("question.webm", b"webm-bytes")


def test_yarngpt_stt_maps_languages_and_polls_job():
    import asyncio
    import json
    import httpx
    from app.services.stt import YarnGPTSTT

    seen = {"posts": [], "polls": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/api/v1/asr":
            body_text = request.content.decode("latin1", errors="ignore")
            seen["posts"].append((request.headers.get("Idempotency-Key"), body_text))
            return httpx.Response(202, json={"job_id": "job-123", "status": "queued"})
        if request.method == "GET" and request.url.path == "/api/v1/asr/job-123":
            seen["polls"] += 1
            if seen["polls"] == 1:
                return httpx.Response(200, json={"job_id": "job-123", "status": "processing"})
            return httpx.Response(
                200,
                json={
                    "job_id": "job-123",
                    "status": "completed",
                    "transcript": "  how i go mix ors water  ",
                },
            )
        return httpx.Response(404, json={"detail": "not found"})

    provider = YarnGPTSTT(
        api_key="test-key",
        timeout_seconds=5.0,
        poll_interval_seconds=0.01,
        transport=httpx.MockTransport(handler),
    )
    out = asyncio.run(provider.transcribe(b"RIFF....", "pcm", filename="question.wav"))
    assert out == "how i go mix ors water"
    assert seen["polls"] == 2
    assert seen["posts"][0][0]  # Idempotency-Key sent
    assert "pidgin" in seen["posts"][0][1]


def test_yarngpt_stt_error_triggers_fallback_stt():
    import asyncio
    import httpx
    from app.services.stt import FallbackSTT, STTProvider, YarnGPTSTT

    def fail_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(402, json={"error": {"code": "QUOTA_EXCEEDED"}})

    class StubFallback(STTProvider):
        async def transcribe(self, audio_bytes: bytes, lang: str, filename: str = "audio.webm") -> str:
            return f"fallback:{lang}:{filename}"

    combo = FallbackSTT(
        primary=YarnGPTSTT(
            api_key="k",
            timeout_seconds=5.0,
            poll_interval_seconds=0.01,
            transport=httpx.MockTransport(fail_handler),
        ),
        fallback=StubFallback(),
    )
    out = asyncio.run(combo.transcribe(b"audio", "yo", filename="q.ogg"))
    assert out == "fallback:yo:q.ogg"


def test_detect_diagnosis_status_multilingual():
    from app.services.gemini_router import detect_diagnosis_status

    assert detect_diagnosis_status("I haven't seen a doctor yet, could this be malaria?") == "undiagnosed"
    assert detect_diagnosis_status("I have not been diagnosed, should I test first?") == "undiagnosed"
    assert detect_diagnosis_status("Doctor never test me for fever") == "undiagnosed"
    assert detect_diagnosis_status("Mi ò tíì ṣàyẹ̀wò ní ilé ìwòsàn") == "undiagnosed"

    assert detect_diagnosis_status("Doctor said I have malaria and gave me ACT") == "diagnosed"
    assert detect_diagnosis_status("Doctor don test me confirm high BP") == "diagnosed"
    assert detect_diagnosis_status("Dókítà sọ pé mo ní ibà") == "diagnosed"

    assert detect_diagnosis_status("How do I prepare ORS?") == "unspecified"


def test_gemini_router_audio_red_flag_and_fallback(client):
    import json
    import types
    from app.main import app
    from app.services.gemini_router import GeminiVoiceRouter

    calls = []

    class FakeInteractions:
        def __init__(self, handler):
            self._handler = handler

        def create(self, **kwargs):
            calls.append(kwargs)
            return types.SimpleNamespace(output_text=self._handler(kwargs))

    class FakeGenAIClient:
        def __init__(self, handler):
            self.interactions = FakeInteractions(handler)

    # 1. Multimodal audio routing returns diagnosed track + store=False
    app.state.gemini_router = GeminiVoiceRouter(
        api_key="test-gemini-key",
        model="gemini-3.5-flash-lite",
        client=FakeGenAIClient(
            lambda _kw: json.dumps(
                {
                    "heard_text": "Doctor said I have malaria, must I finish my tablets?",
                    "is_red_flag": False,
                    "matched_faq_id": 2,
                    "confidence": 0.94,
                    "candidate_faq_ids": [2, 1, 4],
                    "diagnosis_status": "diagnosed",
                }
            )
        ),
    )
    resp = client.post(
        "/api/ask",
        files={"audio": ("q.wav", b"RIFF\x24\x00\x00\x00WAVEfmt ", "audio/wav")},
        data={"lang": "en", "duration_seconds": "2.4"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["type"] == "answer"
    assert body["faq_id"] == 2
    assert body["diagnosis_status"] == "diagnosed"
    assert body["undiagnosed_text"]
    assert body["diagnosed_text"]
    assert body["undiagnosed_audio_url"].endswith(".ogg")
    assert body["diagnosed_audio_url"].endswith(".ogg")
    assert calls[0]["store"] is False
    assert calls[0]["model"] == "gemini-3.5-flash-lite"
    assert calls[0]["generation_config"] == {"thinking_level": "minimal"}
    assert calls[0]["input"][1]["type"] == "audio"

    # 2. Deterministic red-flag guardrail overrides LLM non-red-flag output
    app.state.gemini_router = GeminiVoiceRouter(
        api_key="test-gemini-key",
        client=FakeGenAIClient(
            lambda _kw: json.dumps(
                {
                    "heard_text": "My child is having convulsions right now",
                    "is_red_flag": False,
                    "matched_faq_id": 9,
                    "confidence": 0.88,
                    "candidate_faq_ids": [9],
                    "diagnosis_status": "undiagnosed",
                }
            )
        ),
    )
    rf_resp = client.post(
        "/api/ask",
        json={"text": "My child is having convulsions right now", "lang": "en"},
    )
    assert rf_resp.status_code == 200
    assert rf_resp.json()["type"] == "red_flag"

    # 3. Gemini error falls back automatically to STT + hybrid matcher
    def failing_handler(_kw):
        raise RuntimeError("simulated Gemini outage")

    app.state.gemini_router = GeminiVoiceRouter(
        api_key="test-gemini-key",
        client=FakeGenAIClient(failing_handler),
    )
    fb_resp = client.post(
        "/api/ask",
        files={"audio": ("q.webm", b"MOCK:how to mix ors", "audio/webm")},
        data={"lang": "en", "duration_seconds": "2.0"},
    )
    assert fb_resp.status_code == 200
    assert fb_resp.json()["type"] == "answer"
    assert fb_resp.json()["intent_key"] == "ors_how_to_prepare"


def test_answers_and_bundle_expose_dual_track_fields(client):
    r_ans = client.get("/api/answers/1?lang=en")
    assert r_ans.status_code == 200
    ans = r_ans.json()
    assert ans["diagnosis_status"] == "unspecified"
    assert "not been tested" in ans["undiagnosed_text"].lower()
    assert "diagnosed" in ans["diagnosed_text"].lower()
    assert ans["undiagnosed_audio_url"].endswith(".ogg")
    assert ans["diagnosed_audio_url"].endswith(".ogg")

    r_bundle = client.get("/api/bundle?lang=pcm")
    assert r_bundle.status_code == 200
    bundle = r_bundle.json()
    first_item = bundle["topics"][0]["items"][0]
    assert first_item["undiagnosed_text"]
    assert first_item["diagnosed_text"]
    assert first_item["undiagnosed_audio_url"] in bundle["audio_urls"]
    assert first_item["diagnosed_audio_url"] in bundle["audio_urls"]


def test_gemini_router_timeout_falls_back_cleanly(client):
    import time
    from app.main import app
    from app.services.gemini_router import GeminiVoiceRouter

    class SlowInteractions:
        def create(self, **kwargs):
            time.sleep(0.5)
            raise RuntimeError("should have timed out earlier")

    class SlowGenAIClient:
        def __init__(self):
            self.interactions = SlowInteractions()

    app.state.gemini_router = GeminiVoiceRouter(
        api_key="test-gemini-key",
        timeout_seconds=0.05,
        client=SlowGenAIClient(),
    )
    res = client.post(
        "/api/ask",
        json={"text": "Doctor said I have malaria, must I finish my tablets?", "lang": "en"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["type"] == "answer"
    assert body["diagnosis_status"] == "diagnosed"


def test_gemini_null_match_recovers_via_hybrid_matcher_and_empty_audio_falls_back(client):
    import json
    import types
    from app.main import app
    from app.services.gemini_router import GeminiVoiceRouter

    class FakeInteractions:
        def __init__(self, handler):
            self._handler = handler

        def create(self, **kwargs):
            return types.SimpleNamespace(output_text=self._handler(kwargs))

    class FakeGenAIClient:
        def __init__(self, handler):
            self.interactions = FakeInteractions(handler)

    # 1. Gemini transcribes English while UI is Pidgin ("pcm") and returns matched_faq_id=None -> hybrid matcher recovers it
    app.state.gemini_router = GeminiVoiceRouter(
        api_key="test-gemini-key",
        client=FakeGenAIClient(
            lambda _kw: json.dumps(
                {
                    "heard_text": "how do I mix ors for my child?",
                    "is_red_flag": False,
                    "matched_faq_id": None,
                    "confidence": 0.0,
                    "candidate_faq_ids": [],
                    "diagnosis_status": "unspecified",
                }
            )
        ),
    )
    recovered = client.post(
        "/api/ask",
        files={"audio": ("q.wav", b"RIFF\x24\x00\x00\x00WAVEfmt ", "audio/wav")},
        data={"lang": "pcm", "duration_seconds": "2.4"},
    )
    assert recovered.status_code == 200
    rjson = recovered.json()
    assert rjson["type"] == "answer"
    assert rjson["intent_key"] == "ors_how_to_prepare"

    # 2. Gemini returns empty transcript -> falls back to STT provider (MockSTT)
    app.state.gemini_router = GeminiVoiceRouter(
        api_key="test-gemini-key",
        client=FakeGenAIClient(
            lambda _kw: json.dumps(
                {
                    "heard_text": "   ",
                    "is_red_flag": False,
                    "matched_faq_id": None,
                    "confidence": 0.0,
                    "candidate_faq_ids": [],
                    "diagnosis_status": "unspecified",
                }
            )
        ),
    )
    fb = client.post(
        "/api/ask",
        files={"audio": ("q.webm", b"MOCK:how to mix ors", "audio/webm")},
        data={"lang": "en", "duration_seconds": "2.2"},
    )
    assert fb.status_code == 200
    assert fb.json()["type"] == "answer"
    assert fb.json()["intent_key"] == "ors_how_to_prepare"


def test_gemini_route_decision_strict_json_schema_requires_all_keys():
    from app.services.gemini_router import GeminiRouteDecision

    schema = GeminiRouteDecision.strict_json_schema()
    expected_keys = {
        "heard_text",
        "is_red_flag",
        "is_valid_health_question",
        "matched_faq_id",
        "confidence",
        "candidate_faq_ids",
        "diagnosis_status",
        "suggest_clinics",
        "dynamic_undiagnosed_text",
        "dynamic_diagnosed_text",
    }
    assert set(schema["required"]) == expected_keys


def test_tier3_ai_guardrailed_and_unsure_non_health_routing(client):
    import json
    import types
    from app.main import app
    from app.services.gemini_router import GeminiVoiceRouter

    class FakeInteractions:
        def __init__(self, handler):
            self._handler = handler

        def create(self, **kwargs):
            return types.SimpleNamespace(output_text=self._handler(kwargs))

    class FakeGenAIClient:
        def __init__(self, handler):
            self.interactions = FakeInteractions(handler)

    # 1. Valid health question outside the 20 FAQs (e.g. active labour) -> Tier 3 ai_guardrailed
    app.state.gemini_router = GeminiVoiceRouter(
        api_key="test-gemini-key",
        client=FakeGenAIClient(
            lambda _kw: json.dumps(
                {
                    "heard_text": "i think my wife is in labor, what should i do",
                    "is_red_flag": False,
                    "is_valid_health_question": True,
                    "matched_faq_id": None,
                    "confidence": 0.0,
                    "candidate_faq_ids": [14, 15],
                    "diagnosis_status": "unspecified",
                    "suggest_clinics": True,
                    "dynamic_undiagnosed_text": (
                        "Stay calm, keep her comfortable, and prepare to go to a clinic or hospital now. "
                        "Time her contractions and go immediately if water breaks or bleeding occurs."
                    ),
                    "dynamic_diagnosed_text": (
                        "Follow the birth plan given by her midwife or doctor and head to the delivery clinic now. "
                        "Seek urgent care if contractions are frequent or warning signs appear."
                    ),
                }
            )
        ),
    )
    res = client.post(
        "/api/ask",
        json={"text": "i think my wife is in labor, what should i do", "lang": "en"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["type"] == "answer"
    assert body["answer_source"] == "ai_guardrailed"
    assert body["suggest_clinics"] is True
    assert "clinic" in body["undiagnosed_text"].lower()
    assert "midwife" in body["diagnosed_text"].lower()
    assert body["answer_audio_url"] is None

    # 2. Non-health question -> unsure
    app.state.gemini_router = GeminiVoiceRouter(
        api_key="test-gemini-key",
        client=FakeGenAIClient(
            lambda _kw: json.dumps(
                {
                    "heard_text": "how much is a bag of rice in Abeokuta",
                    "is_red_flag": False,
                    "is_valid_health_question": False,
                    "matched_faq_id": None,
                    "confidence": 0.0,
                    "candidate_faq_ids": [],
                    "diagnosis_status": "unspecified",
                    "suggest_clinics": False,
                    "dynamic_undiagnosed_text": None,
                    "dynamic_diagnosed_text": None,
                }
            )
        ),
    )
    non_health = client.post(
        "/api/ask",
        json={"text": "how much is a bag of rice in Abeokuta", "lang": "en"},
    )
    assert non_health.status_code == 200
    assert non_health.json()["type"] == "unsure"


def test_ephemeral_tts_endpoint_streams_ogg_and_returns_503_when_unavailable(client):
    from app.main import app

    class FakeTTSService:
        def __init__(self, payload: bytes | None):
            self._payload = payload

        async def synthesize_ogg(self, text: str, lang: str) -> bytes | None:
            return self._payload

    app.state.tts_service = FakeTTSService(b"OggS\x00fake-opus-stream")
    ok_res = client.post(
        "/api/tts",
        json={"text": "Prepare to go to the nearest maternity clinic.", "lang": "en"},
    )
    assert ok_res.status_code == 200
    assert ok_res.headers["content-type"].startswith("audio/ogg")
    assert ok_res.headers.get("cache-control") == "no-store"
    assert ok_res.content == b"OggS\x00fake-opus-stream"

    app.state.tts_service = FakeTTSService(None)
    fail_res = client.post(
        "/api/tts",
        json={"text": "Prepare to go to the nearest maternity clinic.", "lang": "en"},
    )
    assert fail_res.status_code == 503


def test_ephemeral_tts_service_priority_cooldown_cache_and_tonemark():
    import asyncio
    from types import SimpleNamespace
    from app.config import Settings
    from app.services.tts import EphemeralTTSService

    # 1. Spitch primary -> 402 puts Spitch in cooldown & falls back to YarnGPT; 2nd call skips Spitch
    settings = Settings(
        SPITCH_API_KEY="test-spitch",
        YARNGPT_API_KEY="test-yarngpt",
        TTS_YO_PROVIDER_ORDER="spitch,yarngpt",
        TTS_ENABLE_SPITCH_TONE_MARK=True,
    )
    svc = EphemeralTTSService(settings)
    calls = {"spitch": 0, "yarngpt": 0, "tonemark": 0}

    class Quota402Error(Exception):
        status_code = 402

    async def fake_tone_mark(text: str) -> str:
        calls["tonemark"] += 1
        return "Ẹ jọ̀wọ́ lọ sí ilé ìwòsàn kíákíá."

    async def fake_spitch_402(text: str, lang: str) -> bytes:
        calls["spitch"] += 1
        raise Quota402Error("insufficient_credits")

    async def fake_yarngpt_ok(text: str, lang: str) -> bytes:
        calls["yarngpt"] += 1
        return b"OggS" + (b"y" * 80)

    svc._tone_mark_spitch = fake_tone_mark  # type: ignore[method-assign]
    svc._synthesize_spitch = fake_spitch_402  # type: ignore[method-assign]
    svc._synthesize_yarngpt = fake_yarngpt_ok  # type: ignore[method-assign]

    first = asyncio.run(svc.synthesize_ogg_with_meta("E jowo lo si ile iwosan kiakia.", "yo"))
    assert first is not None
    audio1, provider1 = first
    assert provider1 == "yarngpt"
    assert audio1.startswith(b"OggS")
    assert calls["tonemark"] == 1
    assert calls["spitch"] == 1
    assert calls["yarngpt"] == 1

    # Cache hit on exact same phrase -> zero new upstream calls
    replay = asyncio.run(svc.synthesize_ogg_with_meta("E jowo lo si ile iwosan kiakia.", "yo"))
    assert replay == first
    assert calls["spitch"] == 1
    assert calls["yarngpt"] == 1

    # Different Yorùbá text -> Spitch is in cooldown so it is skipped completely (stays 1 call)
    second = asyncio.run(svc.synthesize_ogg_with_meta("Ẹ ṣe àyẹ̀wò kíákíá.", "yo"))
    assert second is not None
    assert second[1] == "yarngpt"
    assert calls["spitch"] == 1
    assert calls["yarngpt"] == 2

    # 2. When Spitch is healthy & sparse Yorùbá text is given, tone_mark runs and Spitch serves primary
    svc2 = EphemeralTTSService(settings)
    received: list[str] = []

    async def fake_tm2(text: str) -> str:
        return "Ẹ jọ̀wọ́ mú omi púpọ̀ lónìí."

    async def fake_spitch_ok(text: str, lang: str) -> bytes:
        received.append(text)
        return b"OggS" + (b"s" * 80)

    svc2._tone_mark_spitch = fake_tm2  # type: ignore[method-assign]
    svc2._synthesize_spitch = fake_spitch_ok  # type: ignore[method-assign]
    res2 = asyncio.run(svc2.synthesize_ogg_with_meta("E jowo mu omi pupo lonii.", "yo"))
    assert res2 is not None
    assert res2[1] == "spitch"
    assert received == ["Ẹ jọ̀wọ́ mú omi púpọ̀ lónìí."]


def test_tts_endpoint_exposes_x_tts_provider_header(client):
    from app.main import app

    class MetaTTSService:
        async def synthesize_ogg_with_meta(self, text: str, lang: str):
            return b"OggS\x00spitch-yo", "spitch"

    app.state.tts_service = MetaTTSService()
    res = client.post("/api/tts", json={"text": "Ẹ kú ọjọ́.", "lang": "yo"})
    assert res.status_code == 200
    assert res.headers.get("x-tts-provider") == "spitch"
    assert res.headers.get("cache-control") == "no-store"


def test_tier3_yoruba_not_hijacked_by_borderline_local_matcher(client):
    import json
    import types
    from app.main import app
    from app.services.gemini_router import GeminiVoiceRouter
    from app.services.matcher import MatchCandidate, MatchResult

    class FakeInteractions:
        def __init__(self, handler):
            self._handler = handler

        def create(self, **kwargs):
            return types.SimpleNamespace(output_text=self._handler(kwargs))

    class FakeGenAIClient:
        def __init__(self, handler):
            self.interactions = FakeInteractions(handler)

    class BorderlineMatcher:
        def match(self, query: str, *, lang: str, threshold: float, margin: float):
            score = 0.52
            if score >= threshold:
                return MatchResult(
                    outcome="answer",
                    faq_id=2,
                    confidence=score,
                    candidates=[MatchCandidate(faq_id=2, question="Malaria FAQ", question_audio_url=None, score=score)],
                )
            return MatchResult(outcome="unsure", faq_id=None, confidence=score, candidates=[])

    app.state.matcher = BorderlineMatcher()
    app.state.gemini_router = GeminiVoiceRouter(
        api_key="test-gemini-key",
        client=FakeGenAIClient(
            lambda _kw: json.dumps(
                {
                    "heard_text": "Mo rò pé ìyàwó mi ti wà nínú ìrọbí, kí ni mo gbọ́dọ̀ ṣe?",
                    "is_red_flag": False,
                    "is_valid_health_question": True,
                    "matched_faq_id": None,
                    "confidence": 0.95,
                    "candidate_faq_ids": [13, 14],
                    "diagnosis_status": "unspecified",
                    "suggest_clinics": True,
                    "dynamic_undiagnosed_text": "Ẹ mú ìyàwó yín lọ sí ilé ìwòsàn tí ó sún mọ́ yín lẹ́sẹ̀kẹsẹ̀.",
                    "dynamic_diagnosed_text": "Ẹ tẹ̀ lé ìtọ́ni agbebí kí ẹ sì lọ sí ilé ìbí lẹ́sẹ̀kẹsẹ̀.",
                }
            )
        ),
    )

    res = client.post(
        "/api/ask",
        json={"text": "Mo rò pé ìyàwó mi ti wà nínú ìrọbí, kí ni mo gbọ́dọ̀ ṣe?", "lang": "yo"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["type"] == "answer"
    assert body["answer_source"] == "ai_guardrailed"
    assert body["suggest_clinics"] is True
    assert "ilé ìwòsàn" in body["undiagnosed_text"]






