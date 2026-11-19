# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

React + TypeScript + Vite + Tailwind CSS + vite-plugin-pwa (Workbox) frontend; Python 3.11 + FastAPI + SQLModel + SQLite (PostgreSQL-ready) backend.

## Users

1. **Primary Public Users**: Yorùbá-, Igbo-, and English-speaking adults in Nigeria (often with limited English literacy) accessing health guidance outdoors or in transit on low-end Android devices (Chrome, ~2 GB RAM, 3G or intermittent offline connectivity).
2. **Staff Users (`/admin`)**: Content editors (`editor`), clinical reviewers (`clinical_reviewer`), Yorùbá/Igbo language reviewers (`language_reviewer`), and system administrators (`admin`) who draft, verify, and publish reviewed guidance.

## Product Purpose

HealthYarn enables users to ask everyday health questions out loud in Yorùbá, Igbo, or English—or browse topics completely offline—and hear pre-approved, clinically and linguistically reviewed answers spoken in a natural Nigerian voice. If a question contains any danger sign, the app immediately displays an urgent warning and connects the user to local public health facilities.

## Positioning

HealthYarn follows a **3-tier guardrailed architecture**: Tier 1 immediately intercepts urgent red-flag emergencies with a locked emergency alert and local clinic call buttons; Tier 2 matches questions against clinically pre-approved, pre-synthesised core FAQs (`YarnGPT` / `Spitch`); and Tier 3 provides strictly guardrailed, non-diagnostic AI general health guidance with on-demand ephemeral audio for valid health questions outside the core FAQ library.

## Operating Context

- **Contest Context**: Built for the NCS IT Development Contest (ITDC 2026) under the theme *Innovative Digital Solutions for Intelligent and Accessible Healthcare Delivery*.
- **Voice Pipeline**: Spoken input recorded up to 15 seconds in memory, transcribed via pluggable `STTProvider` (`SpitchSTT`, `MockSTT`, optional `HFSTT`), normalized (including NFD diacritic stripping), checked against urgent red-flag rules before matching, and matched via multilingual embeddings (`LaBSE`) + fuzzy fallback (`RapidFuzz`).
- **Offline Tap Flow**: First online load caches the active language's JSON bundle and all Opus audio clips into browser storage so topics, questions, and answers remain playable with Wi-Fi turned off.

## Capabilities and Constraints

- **3-Tier Guardrailed Guidance**: Tier 1 enforces deterministic + contextual red-flag triage; Tier 2 serves clinician-verified core FAQs with offline pre-recorded voice clips; Tier 3 handles valid out-of-FAQ health questions using strict non-diagnostic, non-prescriptive guardrails (no drug names or dosages) paired with ephemeral `POST /api/tts` synthesis and clear provenance badges (`Verified HealthYarn Guide` vs `AI General Health Info — consult a clinic`).
- **No Guessing Below Threshold**: Below confidence threshold (`MATCH_THRESHOLD`) or narrow margin (`< 0.03`), present up to 3 candidate questions with audio previews instead of guessing.
- **Privacy (NDPA 2023)**: No public user accounts, no third-party analytics SDKs, voice recordings discarded immediately in memory, and zero PII/IPs stored in `query_logs`.
- **Content Safety**: Placeholder drafts (`[PLACEHOLDER – NOT REVIEWED]`) cannot be marked `published` unless seeded explicitly with `--demo`, which surfaces a persistent `"DEMO CONTENT"` banner.
- **Performance Budget**: Public JS bundle `< 200 KB` gzipped; first load `< 1 MB` excluding audio; ≥ 48×48 px touch targets; `18 px` base font size.

## Brand Commitments

- Name: **HealthYarn** (no pinned palette or legacy brand file; visual world derived via Impeccable `concept-seed` in `Operate` mode grounded in Nigerian Primary Health Centre daylight clarity).

## Evidence on Hand

- Seeded placeholder corpus across 5 topics (`malaria`, `hypertension`, `child_diarrhoea_ors`, `pregnancy_danger_signs`, `safe_medicine_use`), 20 FAQ structures, 10 urgent red-flag rules, 12 Nigerian public clinics, and 45 evaluation test cases in `content/*.json` (marked clearly as `[PLACEHOLDER – NOT REVIEWED]` until clinical/language team sign-off).

## Product Principles

1. **Safety Before Matching**: Danger signs interrupt matching immediately and enforce a 5-second non-dismissable clinic-call alert.
2. **Voice + Icon + Text Parity**: Every core action, topic, question, and alert pairs clear iconography, large readable typography, and spoken audio.
3. **Offline First Resilience**: A user without active data must still navigate topics and listen to every cached answer reliably.
4. **Honest Uncertainty**: When speech is unclear or below threshold, invite the user to pick from three spoken options rather than pretending certainty.

## Accessibility & Inclusion

- WCAG 2.1 AA baseline: ≥ 4.5:1 body text contrast, ≥ 3:1 large text contrast, visible keyboard focus rings, logical focus order, and full `aria-label` localisation in Yorùbá, Igbo, and English.
- TalkBack-compatible autoplay controls: respect `prefers-reduced-motion` and provide an explicit autoplay mute toggle so audio never talks over screen readers.
