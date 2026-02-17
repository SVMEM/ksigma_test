import enum
from datetime import datetime
from sqlalchemy import (
    String, Integer, BigInteger, ForeignKey, DateTime, Boolean, Text
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import Base
from sqlalchemy import UniqueConstraint

class Admin(Base):
    __tablename__ = "admins"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tg_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    added_by_tg_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class QType(str, enum.Enum):
    single = "single"
    multi = "multi"

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tg_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    username: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    full_name: Mapped[str] = mapped_column(String(128))
    grade_group: Mapped[str] = mapped_column(String(16))  # "8-", "9", "10", "11"

class Subject(Base):
    __tablename__ = "subjects"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True)  # biology/economics
    name: Mapped[str] = mapped_column(String(64))

class Topic(Base):
    __tablename__ = "topics"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    subject_id: Mapped[int] = mapped_column(ForeignKey("subjects.id"))
    name: Mapped[str] = mapped_column(String(128))
    subject = relationship("Subject")

class Subtopic(Base):
    __tablename__ = "subtopics"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    topic_id: Mapped[int] = mapped_column(ForeignKey("topics.id"))
    name: Mapped[str] = mapped_column(String(128))
    topic = relationship("Topic")

class Question(Base):
    __tablename__ = "questions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    subject_id: Mapped[int] = mapped_column(ForeignKey("subjects.id"))
    topic_id: Mapped[int] = mapped_column(ForeignKey("topics.id"))
    subtopic_id: Mapped[int | None] = mapped_column(ForeignKey("subtopics.id"), nullable=True)

    text: Mapped[str] = mapped_column(Text)
    image_file_id: Mapped[str | None] = mapped_column(String(256), nullable=True)
    qtype: Mapped[str] = mapped_column(String(16))  # single/multi
    explanation: Mapped[str] = mapped_column(Text)

class Option(Base):
    __tablename__ = "options"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id"), index=True)
    text: Mapped[str] = mapped_column(String(512))
    is_correct: Mapped[bool] = mapped_column(Boolean, default=False)

class Attempt(Base):
    __tablename__ = "attempts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id"), index=True)
    is_correct: Mapped[bool] = mapped_column(Boolean)
    chosen_option_ids: Mapped[str] = mapped_column(String(256))  # "1,2"
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class WebLoginCode(Base):
    __tablename__ = "web_login_codes"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tg_id: Mapped[int] = mapped_column(BigInteger, index=True)
    code_hash: Mapped[str] = mapped_column(String(128), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
