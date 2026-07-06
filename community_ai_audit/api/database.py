"""SQLAlchemy engine, session, and models."""

import os
import uuid
from datetime import datetime, timezone
from sqlalchemy import create_engine, Column, String, Integer, Text, Float, DateTime, ForeignKey
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///data/jobs.db")

engine = create_engine(
    DATABASE_URL, connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {}
)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()


def new_id() -> str:
    return uuid.uuid4().hex[:12]


class Organization(Base):
    __tablename__ = "organizations"
    id = Column(String, primary_key=True, default=new_id)
    name = Column(String)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    users = relationship("User", backref="org")
    projects = relationship("Project", backref="org")


class User(Base):
    __tablename__ = "users"
    id = Column(String, primary_key=True, default=new_id)
    org_id = Column(String, ForeignKey("organizations.id"))
    email = Column(String, unique=True)
    password_hash = Column(String)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    api_keys = relationship("ApiKey", backref="user")


class ApiKey(Base):
    __tablename__ = "api_keys"
    id = Column(String, primary_key=True, default=new_id)
    key = Column(String, unique=True)
    user_id = Column(String, ForeignKey("users.id"))
    name = Column(String)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class Project(Base):
    __tablename__ = "projects"
    id = Column(String, primary_key=True, default=new_id)
    org_id = Column(String, ForeignKey("organizations.id"))
    name = Column(String)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    webhooks = relationship("Webhook", backref="project")
    schedules = relationship("Schedule", backref="project")


class Webhook(Base):
    __tablename__ = "webhooks"
    id = Column(String, primary_key=True, default=new_id)
    project_id = Column(String, ForeignKey("projects.id"))
    url = Column(String)
    events = Column(String)  # JSON list
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class Schedule(Base):
    __tablename__ = "schedules"
    id = Column(String, primary_key=True, default=new_id)
    project_id = Column(String, ForeignKey("projects.id"))
    cron_expr = Column(String)
    model_id = Column(String)
    next_run = Column(DateTime)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class UseageRecord(Base):
    __tablename__ = "usage_records"
    id = Column(String, primary_key=True, default=new_id)
    user_id = Column(String, ForeignKey("users.id"), nullable=True)
    org_id = Column(String, ForeignKey("organizations.id"), nullable=True)
    endpoint = Column(String)
    method = Column(String)
    status_code = Column(Integer)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class AuditJob(Base):
    __tablename__ = "audit_jobs"
    id = Column(String, primary_key=True, default=new_id)
    project_id = Column(String, ForeignKey("projects.id"), nullable=True)
    status = Column(String, default="pending")
    model_id = Column(String)
    provider = Column(String)
    scanners = Column(Text)
    results = Column(Text)
    error = Column(Text)
    risk_score = Column(Float)
    severity = Column(String)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime, nullable=True)


def init_db():
    Base.metadata.create_all(engine)


def get_session():
    return SessionLocal()
