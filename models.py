from sqlalchemy import Column, Integer, String, Text, Boolean, DECIMAL, TIMESTAMP, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, ARRAY as PG_ARRAY
from sqlalchemy.orm import DeclarativeBase, relationship
from datetime import datetime
from typing import Optional, List, Dict, Any


class Base(DeclarativeBase):
    pass


class Run(Base):
    __tablename__ = "runs"
    
    id = Column(Integer, primary_key=True, index=True)
    objective = Column(Text, nullable=False)
    seeds = Column(PG_ARRAY(Text), nullable=False)
    rounds = Column(Integer, nullable=False)
    candidates_per_round = Column(Integer, nullable=False)
    top_k = Column(Integer, nullable=False)
    random_seed = Column(Integer, nullable=False)
    filters = Column(JSONB, nullable=False)
    status = Column(String(20), nullable=False, default='pending')
    current_round = Column(Integer, default=0)
    created_at = Column(TIMESTAMP(timezone=True), default=datetime.utcnow)
    started_at = Column(TIMESTAMP(timezone=True), nullable=True)
    completed_at = Column(TIMESTAMP(timezone=True), nullable=True)
    error_message = Column(Text, nullable=True)
    total_generated = Column(Integer, default=0)
    total_passed = Column(Integer, default=0)
    total_failed = Column(Integer, default=0)
    plan = relationship("Plan", back_populates="run", uselist=False, cascade="all, delete-orphan")
    molecules = relationship("Molecule", back_populates="run", cascade="all, delete-orphan")
    traces = relationship("Trace", back_populates="run", cascade="all, delete-orphan")


class Plan(Base):
    __tablename__ = "plans"
    
    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(Integer, ForeignKey("runs.id", ondelete="CASCADE"), nullable=False, unique=True)
    rounds = Column(Integer, nullable=False)
    candidates_per_round = Column(Integer, nullable=False)
    diversity_goal = Column(String(100), nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), default=datetime.utcnow)
    run = relationship("Run", back_populates="plan")


class Molecule(Base):
    __tablename__ = "molecules"
    
    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(Integer, ForeignKey("runs.id", ondelete="CASCADE"), nullable=False, index=True)
    round_number = Column(Integer, nullable=False)
    smiles = Column(Text, nullable=False)
    canonical_smiles = Column(Text, nullable=False)
    mw = Column(DECIMAL(10, 4), nullable=False)
    logp = Column(DECIMAL(10, 4), nullable=False)
    hbd = Column(Integer, nullable=False)
    hba = Column(Integer, nullable=False)
    tpsa = Column(DECIMAL(10, 4), nullable=False)
    rotb = Column(Integer, nullable=False)
    qed = Column(DECIMAL(10, 4), nullable=False)
    passed = Column(Boolean, nullable=False, default=False, index=True)
    violations = Column(Integer, nullable=False, default=0)
    violation_details = Column(JSONB, nullable=True)
    score = Column(DECIMAL(10, 4), nullable=True, index=True)
    rank_in_run = Column(Integer, nullable=True)
    generation_stats = Column(JSONB, nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), default=datetime.utcnow)
    run = relationship("Run", back_populates="molecules")
    __table_args__ = (
        UniqueConstraint('run_id', 'canonical_smiles', name='unique_run_canonical'),
    )


class Trace(Base):
    __tablename__ = "traces"
    
    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(Integer, ForeignKey("runs.id", ondelete="CASCADE"), nullable=False, index=True)
    agent_type = Column(String(50), nullable=False)
    action = Column(String(100), nullable=False)
    input_data = Column(JSONB, nullable=True)
    output_data = Column(JSONB, nullable=True)
    round_number = Column(Integer, nullable=True)
    status = Column(String(20), nullable=False, default='success')
    error_message = Column(Text, nullable=True)
    started_at = Column(TIMESTAMP(timezone=True), default=datetime.utcnow)
    completed_at = Column(TIMESTAMP(timezone=True), nullable=True)
    duration_ms = Column(Integer, nullable=True)
    run = relationship("Run", back_populates="traces")