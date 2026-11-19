"""SQLModel database schema for HealthYarn."""

from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, SQLModel

PLACEHOLDER_PREFIX = "[PLACEHOLDER – NOT REVIEWED]"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Topic(SQLModel, table=True):
    __tablename__ = "topics"

    id: Optional[int] = Field(default=None, primary_key=True)
    slug: str = Field(index=True, unique=True)
    icon: str
    sort_order: int = Field(default=0, index=True)
    name_en: str = ""
    name_yo: str = ""
    name_pcm: str = ""
    name_ig: str = ""
    desc_en: str = ""
    desc_yo: str = ""
    desc_pcm: str = ""
    desc_ig: str = ""


class FAQItem(SQLModel, table=True):
    __tablename__ = "faq_items"

    id: Optional[int] = Field(default=None, primary_key=True)
    topic_id: int = Field(foreign_key="topics.id", index=True)
    intent_key: str = Field(index=True, unique=True)
    source_reference: str = ""
    is_active: bool = Field(default=True, index=True)


class Translation(SQLModel, table=True):
    __tablename__ = "translations"

    id: Optional[int] = Field(default=None, primary_key=True)
    faq_id: int = Field(foreign_key="faq_items.id", index=True)
    lang: str = Field(index=True)  # yo | ig | en
    question_text: str
    answer_text: str
    undiagnosed_text: Optional[str] = None
    diagnosed_text: Optional[str] = None
    question_audio_url: Optional[str] = None
    answer_audio_url: Optional[str] = None
    undiagnosed_audio_url: Optional[str] = None
    diagnosed_audio_url: Optional[str] = None
    audio_takes_json: Optional[str] = None  # JSON array of generated answer audio URLs
    voice_name: Optional[str] = None
    status: str = Field(default="draft", index=True)  # draft | clinical_ok | language_ok | published
    clinical_reviewer_id: Optional[int] = Field(default=None, foreign_key="users.id")
    language_reviewer_id: Optional[int] = Field(default=None, foreign_key="users.id")
    review_comment: Optional[str] = None
    regen_requested: bool = Field(default=False)
    approved_at: Optional[datetime] = None
    updated_at: datetime = Field(default_factory=utc_now)


class SampleQuestion(SQLModel, table=True):
    __tablename__ = "sample_questions"

    id: Optional[int] = Field(default=None, primary_key=True)
    faq_id: int = Field(foreign_key="faq_items.id", index=True)
    lang: str = Field(index=True)
    phrasing: str


class RedFlagRule(SQLModel, table=True):
    __tablename__ = "red_flag_rules"

    id: Optional[int] = Field(default=None, primary_key=True)
    lang: str = Field(index=True)
    pattern: str
    severity: str = Field(default="urgent")
    status: str = Field(default="draft", index=True)  # draft | clinical_ok | published
    clinical_reviewer_id: Optional[int] = Field(default=None, foreign_key="users.id")


class SystemMessage(SQLModel, table=True):
    __tablename__ = "system_messages"

    id: Optional[int] = Field(default=None, primary_key=True)
    key: str = Field(index=True)  # red_flag_alert | disclaimer | unsure | stt_failed | welcome | consent
    lang: str = Field(index=True)
    text: str
    audio_url: Optional[str] = None
    status: str = Field(default="draft", index=True)


class Clinic(SQLModel, table=True):
    __tablename__ = "clinics"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    lga: str
    state: str = Field(index=True)
    phone: str
    type: str
    lat: Optional[float] = None
    lng: Optional[float] = None


class User(SQLModel, table=True):
    __tablename__ = "users"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    email: str = Field(index=True, unique=True)
    password_hash: str
    role: str = Field(index=True)  # editor | clinical_reviewer | language_reviewer | admin
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=utc_now)


class QueryLog(SQLModel, table=True):
    __tablename__ = "query_logs"

    id: Optional[int] = Field(default=None, primary_key=True)
    lang: str = Field(index=True)
    input_mode: str = Field(index=True)  # voice | tap
    matched_faq_id: Optional[int] = Field(default=None, foreign_key="faq_items.id", index=True)
    confidence: Optional[float] = None
    outcome: str = Field(index=True)  # answer | unsure | red_flag | error
    rating: Optional[int] = None  # 1 | -1
    unmatched_text: Optional[str] = None  # Stored ONLY if outcome==unsure AND LOG_UNMATCHED_TEXT=true
    created_at: datetime = Field(default_factory=utc_now, index=True)


class AuditLog(SQLModel, table=True):
    __tablename__ = "audit_log"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    action: str = Field(index=True)
    entity: str
    entity_id: int
    details: Optional[str] = None
    timestamp: datetime = Field(default_factory=utc_now, index=True)


class AppMeta(SQLModel, table=True):
    __tablename__ = "app_meta"

    key: str = Field(primary_key=True)
    value: str
    updated_at: datetime = Field(default_factory=utc_now)
