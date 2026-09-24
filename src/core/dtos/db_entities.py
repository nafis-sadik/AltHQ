"""Declarative database entities (Layer 3 DTOs) for the agent's persistence schema."""

from enum import StrEnum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Shared declarative base that every database entity registers its table on."""


class Gender(StrEnum):
    """Canonical gender values accepted by the persona system."""

    MALE = "male"
    FEMALE = "female"
    NON_BINARY = "non_binary"
    PREFER_NOT_TO_SAY = "prefer_not_to_say"


class Agent(Base):
    """Database entity describing the agent's identity, persona metadata, and prompt limits."""

    __tablename__ = "agents"

    id: Mapped[str] = mapped_column(
        String(32),
        primary_key=True,
        default=lambda: uuid.uuid4().hex,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    gender: Mapped[Gender] = mapped_column(String(30), nullable=False)
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


class EventLogNode(Base):
    """Time-series event node recording a notable agent experience ("line of truth")."""

    __tablename__ = "event_log_nodes"

    id: Mapped[str] = mapped_column(
        String(32),
        primary_key=True,
        default=lambda: uuid.uuid4().hex,
    )
    # Each timeline belongs to exactly one Agent row.
    agent_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("agents.id", ondelete="CASCADE"),
        nullable=False,
    )
    sequence_index: Mapped[int] = mapped_column(Integer, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.current_timestamp(),
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    def __repr__(self) -> str:
        """Return a compact debug representation of the node row."""
        return (
            f"EventLogNode(id={self.id!r}, agent_id={self.agent_id!r}, "
            f"sequence_index={self.sequence_index!r}, is_active={self.is_active!r})"
        )

    def to_dict(self) -> dict:
        """Return the node state as a plain dictionary for prompt compilation."""
        return {
            "id": self.id,
            "agent_id": self.agent_id,
            "sequence_index": self.sequence_index,
            "summary": self.summary,
            "timestamp": self.timestamp,
            "is_active": self.is_active,
        }


class Message(Base):
    """Dialogue message attached to an event node as a child record."""

    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(
        String(32),
        primary_key=True,
        default=lambda: uuid.uuid4().hex,
    )
    node_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("event_log_nodes.id", ondelete="CASCADE"),
        nullable=False,
    )
    # Stores the canonical local-user token or the owning Agent's primary key.
    sender: Mapped[str] = mapped_column(String(60), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # Conversation order is explicit and independent from the user-editable
    # conversation timestamp. This lets a user reorder messages while still
    # correcting the time at which a message was spoken.
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.current_timestamp(),
    )

    def __repr__(self) -> str:
        """Return a compact debug representation of the message row."""
        return (
            f"Message(id={self.id!r}, node_id={self.node_id!r}, "
            f"sender={self.sender!r}, position={self.position!r})"
        )

    def to_dict(self) -> dict:
        """Return the message state as a plain dictionary for prompt compilation."""
        return {
            "id": self.id,
            "node_id": self.node_id,
            "sender": self.sender,
            "content": self.content,
            "position": self.position,
            "timestamp": self.timestamp,
        }
