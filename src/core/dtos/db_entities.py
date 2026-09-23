"""Declarative database entities (Layer 3 DTOs) for the agent's persistence schema."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Shared declarative base that every database entity registers its table on."""


class Gender:
    """Canonical gender values accepted by the persona system."""

    MALE = "male"
    FEMALE = "female"
    UNSPECIFIED = "unspecified"

    ALL = (MALE, FEMALE, UNSPECIFIED)


class Agent(Base):
    """Database entity describing the agent's identity, persona metadata, and prompt limits."""

    __tablename__ = "agents"

    id: Mapped[str] = mapped_column(
        String(32),
        primary_key=True,
        default=lambda: uuid.uuid4().hex,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    gender: Mapped[str] = mapped_column(String(30), nullable=False)
    profile_picture: Mapped[str] = mapped_column(String(500), nullable=False)
    bio: Mapped[str] = mapped_column(Text, nullable=False)
    background_story: Mapped[str] = mapped_column(Text, nullable=False)
    active_node_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=20)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.current_timestamp(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )

    def __repr__(self) -> str:
        """Return a compact debug representation of the agent row."""
        return (
            f"Agent(id={self.id!r}, name={self.name!r}, "
            f"active_node_limit={self.active_node_limit!r})"
        )

    def to_dict(self) -> dict:
        """Return the agent's persona state as a plain dictionary for prompt compilation."""
        return {
            "id": self.id,
            "name": self.name,
            "gender": self.gender,
            "profile_picture": self.profile_picture,
            "bio": self.bio,
            "background_story": self.background_story,
            "active_node_limit": self.active_node_limit,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
class CharacterSheet(Base):
    """Database entity recording an uploaded character reference sheet image."""

    __tablename__ = "character_sheets"

    id: Mapped[str] = mapped_column(
        String(32),
        primary_key=True,
        default=lambda: uuid.uuid4().hex,
    )
    agent_id: Mapped[str] = mapped_column(String(32), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.current_timestamp(),
    )

    def __repr__(self) -> str:
        """Return a compact debug representation of the sheet row."""
        return (
            f"CharacterSheet(id={self.id!r}, agent_id={self.agent_id!r}, "
            f"original_filename={self.original_filename!r})"
        )
