"""Database engine and session helpers."""

from typing import Generator

from sqlalchemy import inspect, text
from sqlmodel import Session, SQLModel, create_engine

from app.config import get_settings


def build_engine(database_url: str | None = None):
    url = database_url or get_settings().DATABASE_URL
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    return create_engine(url, echo=False, connect_args=connect_args)


engine = build_engine()


def init_db(target_engine=None) -> None:
    eng = target_engine or engine
    SQLModel.metadata.create_all(eng)
    insp = inspect(eng)
    if "topics" in insp.get_table_names():
        cols = {c["name"] for c in insp.get_columns("topics")}
        with eng.begin() as conn:
            if "name_pcm" not in cols:
                conn.execute(text("ALTER TABLE topics ADD COLUMN name_pcm VARCHAR DEFAULT ''"))
            if "desc_pcm" not in cols:
                conn.execute(text("ALTER TABLE topics ADD COLUMN desc_pcm VARCHAR DEFAULT ''"))
    if "translations" in insp.get_table_names():
        tr_cols = {c["name"] for c in insp.get_columns("translations")}
        with eng.begin() as conn:
            for col_name in (
                "undiagnosed_text",
                "diagnosed_text",
                "undiagnosed_audio_url",
                "diagnosed_audio_url",
            ):
                if col_name not in tr_cols:
                    conn.execute(text(f"ALTER TABLE translations ADD COLUMN {col_name} TEXT"))


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session
