"""Shared pytest fixtures for HealthYarn backend test suite."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlalchemy.pool import StaticPool

from app.config import get_settings
from app.db import get_session
from app.main import app
from app.services.limiter import limiter
from app.services.matcher import FAQMatcher
from app.services.stt import MockSTT
from scripts.seed import seed_database


@pytest.fixture()
def test_engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    yield engine
    SQLModel.metadata.drop_all(engine)


@pytest.fixture()
def seeded_session(test_engine):
    settings = get_settings()
    with Session(test_engine) as session:
        seed_database(session, settings.content_dir, demo=True)
        yield session


@pytest.fixture()
def client(test_engine, seeded_session):
    limiter.reset()
    def override_get_session():
        with Session(test_engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session

    with TestClient(app) as c:
        app.state.stt_provider = MockSTT()
        app.state.gemini_router = None
        matcher = FAQMatcher(disable_heavy=True)
        matcher.build_index(seeded_session)
        app.state.matcher = matcher
        yield c

    if hasattr(app.state, "gemini_router"):
        delattr(app.state, "gemini_router")
    app.dependency_overrides.clear()
