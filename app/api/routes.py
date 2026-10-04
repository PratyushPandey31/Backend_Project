import logging
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.core.database import get_db, seed_database_if_empty
from app.core.models import (
    ChatRequest, UserORM, PropertyORM, ConversationSessionORM, MessageORM, ToolTraceORM, EscalationFlagORM, FlagResolutionRequest
)
from app.agent.orchestrator import AgentOrchestrator
from app.analytics.portfolio_engine import PortfolioEngine, format_inr

logger = logging.getLogger(__name__)
router = APIRouter()
orchestrator = AgentOrchestrator()

@router.post("/chat")
def handle_chat(req: ChatRequest):
    """Handle conversational message from user via WhatsApp simulation interface."""
    if not req.user_id:
        raise HTTPException(status_code=400, detail="user_id is required")
    if not req.message:
        raise HTTPException(status_code=400, detail="message cannot be empty")
        
    res = orchestrator.process_message(
        user_id=req.user_id,
        user_message=req.message,
        conversation_id=req.conversation_id,
        model_override=req.model_override,
        api_key_override=req.api_key_override
    )
    return res

@router.get("/users")
def get_users(db: Session = Depends(get_db)):
    """List all available users with portfolio summary."""
    users = db.query(UserORM).all()
    out = []
    for u in users:
        props = db.query(PropertyORM).filter(PropertyORM.user_id == u.user_id, PropertyORM.status == "Active").all()
        tot_val = sum(p.current_estimated_value_inr for p in props)
        tot_rent = sum(p.annual_rent_inr for p in props)
        out.append({
            "user_id": u.user_id,
            "name": u.name,
            "city": u.city,
            "preferences": u.preferences,
            "preferred_locations": u.preferred_locations,
            "portfolio_value_preference_inr": u.portfolio_value_preference_inr,
            "total_properties": len(props),
            "total_value_inr": tot_val,
            "total_value_formatted": format_inr(tot_val),
            "total_rent_formatted": format_inr(tot_rent)
        })
    return out

@router.get("/users/{user_id}/portfolio")
def get_user_portfolio(user_id: str, db: Session = Depends(get_db)):
    """Retrieve full portfolio metrics and properties for a user."""
    props = db.query(PropertyORM).filter(PropertyORM.user_id == user_id, PropertyORM.status == "Active").all()
    user = db.query(UserORM).filter(UserORM.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    summary = PortfolioEngine.calculate_summary(props, user_id)
    summary["user_name"] = user.name
    summary["user_city"] = user.city
    return summary

@router.get("/conversations")
def get_conversations(db: Session = Depends(get_db)):
    """List all conversation sessions for Business Interface."""
    sessions = db.query(ConversationSessionORM).order_by(ConversationSessionORM.updated_at.desc()).all()
    results = []
    for s in sessions:
        msg_count = db.query(MessageORM).filter(MessageORM.conversation_id == s.id).count()
        last_msg = db.query(MessageORM).filter(MessageORM.conversation_id == s.id).order_by(MessageORM.created_at.desc()).first()
        user = db.query(UserORM).filter(UserORM.user_id == s.user_id).first()
        
        results.append({
            "id": s.id,
            "user_id": s.user_id,
            "user_name": user.name if user else s.user_id,
            "title": s.title,
            "is_flagged": s.is_flagged,
            "flag_reason": s.flag_reason,
            "message_count": msg_count,
            "last_message": last_msg.content if last_msg else None,
            "last_message_sender": last_msg.sender if last_msg else None,
            "updated_at": s.updated_at.isoformat() if s.updated_at else None
        })
    return results

@router.get("/conversations/{conversation_id}")
def get_conversation_details(conversation_id: str, db: Session = Depends(get_db)):
    """Inspect an individual conversation with full messages and tool traces."""
    session_obj = db.query(ConversationSessionORM).filter(ConversationSessionORM.id == conversation_id).first()
    if not session_obj:
        raise HTTPException(status_code=404, detail="Conversation not found")
        
    messages = db.query(MessageORM).filter(MessageORM.conversation_id == conversation_id).order_by(MessageORM.created_at.asc()).all()
    traces = db.query(ToolTraceORM).filter(ToolTraceORM.conversation_id == conversation_id).order_by(ToolTraceORM.created_at.asc()).all()
    user = db.query(UserORM).filter(UserORM.user_id == session_obj.user_id).first()
    
    return {
        "session": {
            "id": session_obj.id,
            "user_id": session_obj.user_id,
            "user_name": user.name if user else session_obj.user_id,
            "title": session_obj.title,
            "is_flagged": session_obj.is_flagged,
            "flag_reason": session_obj.flag_reason,
            "created_at": session_obj.created_at.isoformat()
        },
        "messages": [
            {
                "id": m.id,
                "sender": m.sender,
                "content": m.content,
                "latency_ms": m.latency_ms,
                "created_at": m.created_at.isoformat()
            } for m in messages
        ],
        "tool_traces": [
            {
                "id": t.id,
                "tool_name": t.tool_name,
                "input": t.tool_input_json,
                "output": t.tool_output_json,
                "execution_time_ms": t.execution_time_ms,
                "success": t.success,
                "created_at": t.created_at.isoformat()
            } for t in traces
        ]
    }

@router.post("/conversations/{conversation_id}/resolve-flag")
def resolve_flag(conversation_id: str, req: FlagResolutionRequest, db: Session = Depends(get_db)):
    """Resolve an escalation flag from the Business Team Interface."""
    session_obj = db.query(ConversationSessionORM).filter(ConversationSessionORM.id == conversation_id).first()
    if not session_obj:
        raise HTTPException(status_code=404, detail="Conversation not found")
        
    session_obj.is_flagged = False
    session_obj.flag_reason = f"Resolved: {req.notes or 'Reviewed by business team'}"
    db.commit()
    return {"success": True, "message": "Flag resolved successfully."}

@router.get("/business/stats")
def get_business_stats(db: Session = Depends(get_db)):
    """High-level metrics for the business observation interface."""
    total_users = db.query(UserORM).count()
    total_props = db.query(PropertyORM).filter(PropertyORM.status == "Active").count()
    all_props = db.query(PropertyORM).filter(PropertyORM.status == "Active").all()
    total_aum = sum(p.current_estimated_value_inr for p in all_props)
    total_convs = db.query(ConversationSessionORM).count()
    flagged_convs = db.query(ConversationSessionORM).filter(ConversationSessionORM.is_flagged == True).count()
    total_traces = db.query(ToolTraceORM).count()
    
    return {
        "total_users": total_users,
        "total_properties": total_props,
        "total_aum_formatted": format_inr(total_aum),
        "total_conversations": total_convs,
        "flagged_conversations": flagged_convs,
        "total_tool_executions": total_traces
    }

@router.post("/reset-database")
def reset_database():
    """Reset database to initial seed data from CSV files."""
    seed_database_if_empty(force_reset=True)
    return {"success": True, "message": "Database reset to initial seed data successfully."}
