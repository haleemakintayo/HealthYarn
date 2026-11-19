"""Seed HealthYarn database from content/*.json with placeholder safety guard."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import bcrypt
from sqlmodel import Session, select

from app.config import get_settings
from app.db import engine, init_db
from app.models import (
    PLACEHOLDER_PREFIX,
    AppMeta,
    Clinic,
    FAQItem,
    RedFlagRule,
    SampleQuestion,
    SystemMessage,
    Topic,
    Translation,
    User,
    utc_now,
)


def is_placeholder_text(text: str) -> bool:
    return text.strip().startswith(PLACEHOLDER_PREFIX)


def hash_password_raw(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def seed_database(
    session: Session,
    content_dir: Path,
    demo: bool = False,
    seed_demo_staff: bool = True,
) -> dict[str, int]:
    topics_data = load_json(content_dir / "topics.json")
    faqs_data = load_json(content_dir / "faqs.json")
    red_flags_data = load_json(content_dir / "red_flags.json")
    clinics_data = load_json(content_dir / "clinics.json")
    sys_msgs_data = load_json(content_dir / "system_messages.json")

    counts = {"topics": 0, "faqs": 0, "translations": 0, "red_flags": 0, "clinics": 0, "system_messages": 0}

    # Clean up obsolete language rows not present in current content files (e.g., ig -> pcm switch)
    active_langs = {"en", "yo", "pcm"}
    for stale_tr in session.exec(select(Translation)).all():
        if stale_tr.lang not in active_langs:
            session.delete(stale_tr)
    for stale_smp in session.exec(select(SampleQuestion)).all():
        if stale_smp.lang not in active_langs:
            session.delete(stale_smp)
    for stale_rf in session.exec(select(RedFlagRule)).all():
        if stale_rf.lang not in active_langs:
            session.delete(stale_rf)
    for stale_msg in session.exec(select(SystemMessage)).all():
        if stale_msg.lang not in active_langs:
            session.delete(stale_msg)

    # 1. Topics
    topic_map: dict[str, Topic] = {}
    for item in topics_data:
        existing = session.exec(select(Topic).where(Topic.slug == item["slug"])).first()
        names = item.get("names", {})
        descs = item.get("descriptions", {})
        if existing:
            existing.icon = item["icon"]
            existing.sort_order = item["sort_order"]
            existing.name_en = names.get("en", item["slug"])
            existing.name_yo = names.get("yo", item["slug"])
            existing.name_pcm = names.get("pcm", item["slug"])
            existing.name_ig = names.get("ig", "")
            existing.desc_en = descs.get("en", "")
            existing.desc_yo = descs.get("yo", "")
            existing.desc_pcm = descs.get("pcm", "")
            existing.desc_ig = descs.get("ig", "")
            topic_obj = existing
        else:
            topic_obj = Topic(
                slug=item["slug"],
                icon=item["icon"],
                sort_order=item["sort_order"],
                name_en=names.get("en", item["slug"]),
                name_yo=names.get("yo", item["slug"]),
                name_pcm=names.get("pcm", item["slug"]),
                name_ig=names.get("ig", ""),
                desc_en=descs.get("en", ""),
                desc_yo=descs.get("yo", ""),
                desc_pcm=descs.get("pcm", ""),
                desc_ig=descs.get("ig", ""),
            )
            session.add(topic_obj)
            session.flush()
        topic_map[item["slug"]] = topic_obj
        counts["topics"] += 1

    # 2. FAQs, Translations, Samples
    any_placeholder_present = False
    for entry in faqs_data:
        topic_obj = topic_map[entry["topic"]]
        faq = session.exec(select(FAQItem).where(FAQItem.intent_key == entry["intent_key"])).first()
        if not faq:
            faq = FAQItem(
                topic_id=topic_obj.id,  # type: ignore[arg-type]
                intent_key=entry["intent_key"],
                source_reference=entry.get("source_reference", ""),
                is_active=True,
            )
            session.add(faq)
            session.flush()
        else:
            faq.topic_id = topic_obj.id  # type: ignore[assignment]
            faq.source_reference = entry.get("source_reference", "")
        counts["faqs"] += 1

        for lang, tdata in entry.get("translations", {}).items():
            q_text = tdata["question"]
            a_text = tdata["answer"]
            u_text = tdata.get("undiagnosed_text")
            d_text = tdata.get("diagnosed_text")
            u_audio = tdata.get("undiagnosed_audio_url")
            d_audio = tdata.get("diagnosed_audio_url")
            raw_status = tdata.get("status", "draft")
            has_placeholder = is_placeholder_text(q_text) or is_placeholder_text(a_text)
            if has_placeholder:
                any_placeholder_present = True

            if raw_status == "published" and has_placeholder and not demo:
                raise ValueError(
                    f"Refusing to publish placeholder translation for {entry['intent_key']} ({lang}) without --demo."
                )

            final_status = "published" if demo else raw_status
            if final_status == "published" and has_placeholder and not demo:
                raise ValueError(
                    f"Placeholder content cannot be marked published without --demo ({entry['intent_key']}/{lang})."
                )

            tr = session.exec(
                select(Translation).where(Translation.faq_id == faq.id, Translation.lang == lang)
            ).first()
            if tr:
                tr.question_text = q_text
                tr.answer_text = a_text
                tr.undiagnosed_text = u_text
                tr.diagnosed_text = d_text
                if u_audio is not None:
                    tr.undiagnosed_audio_url = u_audio
                if d_audio is not None:
                    tr.diagnosed_audio_url = d_audio
                tr.status = final_status
                tr.updated_at = utc_now()
            else:
                tr = Translation(
                    faq_id=faq.id,  # type: ignore[arg-type]
                    lang=lang,
                    question_text=q_text,
                    answer_text=a_text,
                    undiagnosed_text=u_text,
                    diagnosed_text=d_text,
                    undiagnosed_audio_url=u_audio,
                    diagnosed_audio_url=d_audio,
                    status=final_status,
                )
                session.add(tr)
            counts["translations"] += 1

        # Refresh samples for this FAQ
        existing_samples = session.exec(select(SampleQuestion).where(SampleQuestion.faq_id == faq.id)).all()
        existing_pairs = {(s.lang, s.phrasing) for s in existing_samples}
        for lang, phrases in entry.get("samples", {}).items():
            for p in phrases:
                if (lang, p) not in existing_pairs:
                    session.add(SampleQuestion(faq_id=faq.id, lang=lang, phrasing=p))  # type: ignore[arg-type]

    # 3. Red-flag rules (prune stale rules removed from content/red_flags.json)
    desired_rf_pairs = {(rf["lang"], rf["pattern"]) for rf in red_flags_data}
    for old_rf in session.exec(select(RedFlagRule)).all():
        if (old_rf.lang, old_rf.pattern) not in desired_rf_pairs:
            session.delete(old_rf)
    session.flush()

    for rf in red_flags_data:
        rf_status = "published" if demo else rf.get("status", "draft")
        existing_rf = session.exec(
            select(RedFlagRule).where(RedFlagRule.lang == rf["lang"], RedFlagRule.pattern == rf["pattern"])
        ).first()
        if existing_rf:
            existing_rf.status = rf_status
            existing_rf.severity = rf.get("severity", "urgent")
        else:
            session.add(
                RedFlagRule(
                    lang=rf["lang"],
                    pattern=rf["pattern"],
                    severity=rf.get("severity", "urgent"),
                    status=rf_status,
                )
            )
        counts["red_flags"] += 1

    # 4. System messages
    for msg in sys_msgs_data:
        msg_status = "published" if demo else msg.get("status", "draft")
        existing_msg = session.exec(
            select(SystemMessage).where(SystemMessage.key == msg["key"], SystemMessage.lang == msg["lang"])
        ).first()
        if existing_msg:
            existing_msg.text = msg["text"]
            existing_msg.status = msg_status
        else:
            session.add(
                SystemMessage(
                    key=msg["key"],
                    lang=msg["lang"],
                    text=msg["text"],
                    status=msg_status,
                )
            )
        counts["system_messages"] += 1

    # 5. Clinics (prune stale clinics removed from content/clinics.json)
    desired_clinic_pairs = {(cl["name"], cl["state"]) for cl in clinics_data}
    for old_cl in session.exec(select(Clinic)).all():
        if (old_cl.name, old_cl.state) not in desired_clinic_pairs:
            session.delete(old_cl)
    session.flush()

    for cl in clinics_data:
        existing_cl = session.exec(
            select(Clinic).where(Clinic.name == cl["name"], Clinic.state == cl["state"])
        ).first()
        if existing_cl:
            existing_cl.lga = cl["lga"]
            existing_cl.phone = cl["phone"]
            existing_cl.type = cl["type"]
            existing_cl.lat = cl.get("lat")
            existing_cl.lng = cl.get("lng")
        else:
            session.add(
                Clinic(
                    name=cl["name"],
                    lga=cl["lga"],
                    state=cl["state"],
                    phone=cl["phone"],
                    type=cl["type"],
                    lat=cl.get("lat"),
                    lng=cl.get("lng"),
                )
            )
        counts["clinics"] += 1

    # 6. App metadata markers (DEMO_MODE banner flag + last updated + credits)
    meta_entries = {
        "demo_mode": "true" if (demo and any_placeholder_present) else "false",
        "content_last_updated": utc_now().strftime("%Y-%m-%d"),
        "clinical_reviewers": "Clinical Review Team",
        "language_reviewers": "Yorùbá & Nigerian Pidgin Linguistic Team",
    }
    for k, v in meta_entries.items():
        row = session.get(AppMeta, k)
        if row:
            row.value = v
            row.updated_at = utc_now()
        else:
            session.add(AppMeta(key=k, value=v))

    # 7. Demo staff accounts (only when --demo is explicitly enabled)
    if demo and seed_demo_staff:
        demo_users = [
            ("Demo Admin", "admin@healthyarn.ng", "HealthYarnAdmin2026!", "admin"),
            ("Demo Clinical Reviewer", "clinical@healthyarn.ng", "HealthYarnClinic2026!", "clinical_reviewer"),
            ("Demo Language Reviewer", "language@healthyarn.ng", "HealthYarnLang2026!", "language_reviewer"),
            ("Demo Editor", "editor@healthyarn.ng", "HealthYarnEditor2026!", "editor"),
        ]
        for name, email, pw, role in demo_users:
            if not session.exec(select(User).where(User.email == email)).first():
                session.add(
                    User(
                        name=name,
                        email=email,
                        password_hash=hash_password_raw(pw),
                        role=role,
                        is_active=True,
                    )
                )

    session.commit()
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed HealthYarn database from content JSON files.")
    parser.add_argument("--demo", action="store_true", help="Publish placeholder items into local demo database.")
    args = parser.parse_args()

    settings = get_settings()
    init_db(engine)
    with Session(engine) as session:
        counts = seed_database(session, settings.content_dir, demo=args.demo)
    print(f"Seeded HealthYarn DB (demo={args.demo}): {counts}")


if __name__ == "__main__":
    main()
