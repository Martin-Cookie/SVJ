import enum
from datetime import datetime

from sqlalchemy import (
    Boolean, Column, DateTime, Date, Enum, Float, ForeignKey, Integer, String, Text,
)
from sqlalchemy.orm import relationship

from app.database import Base


class VotingStatus(str, enum.Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    CLOSED = "closed"
    CANCELLED = "cancelled"


class VoteValue(str, enum.Enum):
    FOR = "for"
    AGAINST = "against"
    ABSTAIN = "abstain"
    INVALID = "invalid"


class BallotStatus(str, enum.Enum):
    GENERATED = "generated"
    SENT = "sent"
    RECEIVED = "received"
    PROCESSED = "processed"
    INVALID = "invalid"


class Voting(Base):
    __tablename__ = "votings"

    id = Column(Integer, primary_key=True)
    title = Column(String(300), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(Enum(VotingStatus), default=VotingStatus.DRAFT)
    template_path = Column(String(500), nullable=True)
    start_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True)
    total_votes_possible = Column(Integer, default=0)
    quorum_threshold = Column(Float, default=0.5)
    partial_owner_mode = Column(String(20), default="shared")  # shared / separate
    import_column_mapping = Column(Text, nullable=True)  # JSON string
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    items = relationship(
        "VotingItem", back_populates="voting", cascade="all, delete-orphan",
        order_by="VotingItem.order",
    )
    ballots = relationship("Ballot", back_populates="voting", cascade="all, delete-orphan")


class VotingItem(Base):
    __tablename__ = "voting_items"

    id = Column(Integer, primary_key=True)
    voting_id = Column(Integer, ForeignKey("votings.id"), nullable=False)
    order = Column(Integer, nullable=False)
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)

    voting = relationship("Voting", back_populates="items")
    votes = relationship("BallotVote", back_populates="voting_item", cascade="all, delete-orphan")


class Ballot(Base):
    __tablename__ = "ballots"

    id = Column(Integer, primary_key=True)
    voting_id = Column(Integer, ForeignKey("votings.id"), nullable=False)
    owner_id = Column(Integer, ForeignKey("owners.id"), nullable=False)
    status = Column(Enum(BallotStatus), default=BallotStatus.GENERATED)
    pdf_path = Column(String(500), nullable=True)
    scan_path = Column(String(500), nullable=True)
    voted_by_proxy = Column(Boolean, default=False)
    proxy_holder_name = Column(String(300), nullable=True)
    total_votes = Column(Integer, default=0)
    units_text = Column(String(200), nullable=True)
    sent_at = Column(DateTime, nullable=True)
    received_at = Column(DateTime, nullable=True)
    processed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    voting = relationship("Voting", back_populates="ballots")
    owner = relationship("Owner", back_populates="ballots")
    votes = relationship("BallotVote", back_populates="ballot", cascade="all, delete-orphan")


class BallotVote(Base):
    __tablename__ = "ballot_votes"

    id = Column(Integer, primary_key=True)
    ballot_id = Column(Integer, ForeignKey("ballots.id"), nullable=False)
    voting_item_id = Column(Integer, ForeignKey("voting_items.id"), nullable=False)
    vote = Column(Enum(VoteValue), nullable=True)
    votes_count = Column(Integer, default=0)
    manually_verified = Column(Boolean, default=False)

    ballot = relationship("Ballot", back_populates="votes")
    voting_item = relationship("VotingItem", back_populates="votes")
