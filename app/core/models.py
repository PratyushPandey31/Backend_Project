from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy import Column, String, Integer, Float, Text, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import declarative_base, relationship
from pydantic import BaseModel, Field

Base = declarative_base()

# SQLAlchemy ORM Models

class UserORM(Base):
    __tablename__ = "users"
    
    user_id = Column(String(50), primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    city = Column(String(100), nullable=True)
    preferences = Column(String(200), nullable=True)
    preferred_locations = Column(String(200), nullable=True)
    portfolio_value_preference_inr = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    properties = relationship("PropertyORM", back_populates="user", cascade="all, delete-orphan")
    conversations = relationship("ConversationSessionORM", back_populates="user")


class PropertyORM(Base):
    __tablename__ = "properties"
    
    property_id = Column(String(50), primary_key=True, index=True)
    user_id = Column(String(50), ForeignKey("users.user_id"), nullable=False, index=True)
    property_type = Column(String(50), nullable=False)  # Retail, Commercial Office, Office, Residential
    sub_type = Column(String(100), nullable=True)      # High-street retail, Apartment, Villa, etc.
    location = Column(String(255), nullable=False)      # e.g., "Bandra West, Mumbai"
    city = Column(String(100), nullable=True)          # Extracted city e.g. "Mumbai"
    area_sqft = Column(Float, nullable=False)
    current_estimated_value_inr = Column(Float, nullable=False)
    purchase_price_inr = Column(Float, nullable=True)   # Blank in seed data
    purchase_date = Column(String(50), nullable=True)   # Optional historical date
    annual_rent_inr = Column(Float, default=0.0)
    occupancy_status = Column(String(50), default="Vacant") # Tenanted, Vacant, Self-occupied
    tenant_status = Column(String(50), default="No")        # Yes, No
    ownership_percent = Column(Float, default=100.0)
    status = Column(String(50), default="Active")           # Active, Sold, Archived
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("UserORM", back_populates="properties")


class ConversationSessionORM(Base):
    __tablename__ = "conversation_sessions"
    
    id = Column(String(100), primary_key=True, index=True)
    user_id = Column(String(50), ForeignKey("users.user_id"), nullable=False)
    title = Column(String(255), default="Portfolio Discussion")
    is_flagged = Column(Boolean, default=False)
    flag_reason = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("UserORM", back_populates="conversations")
    messages = relationship("MessageORM", back_populates="session", cascade="all, delete-orphan", order_by="MessageORM.created_at")
    traces = relationship("ToolTraceORM", back_populates="session", cascade="all, delete-orphan")


class MessageORM(Base):
    __tablename__ = "messages"
    
    id = Column(String(100), primary_key=True, index=True)
    conversation_id = Column(String(100), ForeignKey("conversation_sessions.id"), nullable=False, index=True)
    sender = Column(String(20), nullable=False) # "user", "assistant", "system"
    content = Column(Text, nullable=False)
    tool_calls_json = Column(Text, nullable=True) # JSON array of tool calls
    latency_ms = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    session = relationship("ConversationSessionORM", back_populates="messages")


class ToolTraceORM(Base):
    __tablename__ = "tool_traces"
    
    id = Column(String(100), primary_key=True, index=True)
    conversation_id = Column(String(100), ForeignKey("conversation_sessions.id"), nullable=False, index=True)
    user_id = Column(String(50), nullable=False)
    tool_name = Column(String(100), nullable=False)
    tool_input_json = Column(Text, nullable=True)
    tool_output_json = Column(Text, nullable=True)
    execution_time_ms = Column(Float, default=0.0)
    success = Column(Boolean, default=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    session = relationship("ConversationSessionORM", back_populates="traces")


class EscalationFlagORM(Base):
    __tablename__ = "escalation_flags"
    
    id = Column(String(100), primary_key=True, index=True)
    conversation_id = Column(String(100), nullable=False, index=True)
    user_id = Column(String(50), nullable=False)
    reason = Column(String(255), nullable=False)
    severity = Column(String(20), default="Medium") # Low, Medium, High, Critical
    status = Column(String(20), default="Open")     # Open, Resolved
    resolved_by = Column(String(100), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)


# Pydantic Request / Response Schemas

class ChatRequest(BaseModel):
    user_id: str
    message: str
    conversation_id: Optional[str] = None
    model_override: Optional[str] = None
    api_key_override: Optional[str] = None


class PropertySchema(BaseModel):
    property_id: str
    user_id: str
    property_type: str
    sub_type: Optional[str] = None
    location: str
    city: Optional[str] = None
    area_sqft: float
    current_estimated_value_inr: float
    purchase_price_inr: Optional[float] = None
    annual_rent_inr: float = 0.0
    occupancy_status: str = "Vacant"
    tenant_status: str = "No"
    ownership_percent: float = 100.0
    status: str = "Active"
    
    # Computed fields for wealth analysis
    rental_yield_pct: Optional[float] = None
    rate_per_sqft: Optional[float] = None
    rent_per_sqft_month: Optional[float] = None


class PortfolioSummary(BaseModel):
    user_id: str
    total_properties: int
    total_portfolio_value_inr: float
    total_portfolio_value_formatted: str
    total_annual_rent_inr: float
    total_annual_rent_formatted: str
    overall_rental_yield_pct: float
    total_area_sqft: float
    occupancy_rate_pct: float
    breakdown_by_type: Dict[str, Any]
    breakdown_by_city: Dict[str, Any]
    properties: List[PropertySchema]


class FlagResolutionRequest(BaseModel):
    status: str = "Resolved"
    resolved_by: str = "Business Team Analyst"
    notes: Optional[str] = None
