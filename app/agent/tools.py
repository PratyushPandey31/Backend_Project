import json
import logging
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import or_
from app.core.database import SessionLocal, extract_city
from app.core.models import PropertyORM, UserORM, ConversationSessionORM, EscalationFlagORM
from app.analytics.portfolio_engine import PortfolioEngine, format_inr, canonical_macro_category
from app.analytics.scenario_engine import ScenarioEngine

logger = logging.getLogger(__name__)

# --- AGENT TOOL FUNCTIONS ---

def tool_get_portfolio_summary(user_id: str, db: Optional[Session] = None) -> Dict[str, Any]:
    """Retrieve full portfolio metrics and summary for a given user."""
    own_session = False
    if db is None:
        db = SessionLocal()
        own_session = True
    try:
        props = db.query(PropertyORM).filter(PropertyORM.user_id == user_id, PropertyORM.status == "Active").all()
        user = db.query(UserORM).filter(UserORM.user_id == user_id).first()
        summary = PortfolioEngine.calculate_summary(props, user_id)
        if user:
            summary["user_name"] = user.name
            summary["user_city"] = user.city
            summary["user_preferences"] = user.preferences
        return summary
    finally:
        if own_session:
            db.close()


def tool_search_properties(
    user_id: str,
    property_type: Optional[str] = None,
    city: Optional[str] = None,
    min_value: Optional[float] = None,
    max_value: Optional[float] = None,
    min_rent: Optional[float] = None,
    occupancy_status: Optional[str] = None,
    sort_by: Optional[str] = None,
    limit: int = 10,
    db: Optional[Session] = None
) -> Dict[str, Any]:
    """Search and filter properties owned by user based on asset type, city, value, or rent."""
    own_session = False
    if db is None:
        db = SessionLocal()
        own_session = True
    try:
        query = db.query(PropertyORM).filter(PropertyORM.user_id == user_id, PropertyORM.status == "Active")
        
        if property_type:
            pt = property_type.lower()
            if pt in ["commercial", "office", "commercial office"]:
                query = query.filter(or_(
                    PropertyORM.property_type.ilike("%commercial%"),
                    PropertyORM.property_type.ilike("%office%")
                ))
            else:
                query = query.filter(PropertyORM.property_type.ilike(f"%{property_type}%"))
                
        if city:
            query = query.filter(or_(
                PropertyORM.city.ilike(f"%{city}%"),
                PropertyORM.location.ilike(f"%{city}%")
            ))
            
        if min_value is not None:
            query = query.filter(PropertyORM.current_estimated_value_inr >= min_value)
            
        if max_value is not None:
            query = query.filter(PropertyORM.current_estimated_value_inr <= max_value)
            
        if min_rent is not None:
            query = query.filter(PropertyORM.annual_rent_inr >= min_rent)
            
        if occupancy_status:
            query = query.filter(PropertyORM.occupancy_status.ilike(f"%{occupancy_status}%"))
            
        if sort_by == "annual_rent_desc":
            query = query.order_by(PropertyORM.annual_rent_inr.desc())
        elif sort_by == "annual_rent_asc":
            query = query.order_by(PropertyORM.annual_rent_inr.asc())
        elif sort_by == "value_desc":
            query = query.order_by(PropertyORM.current_estimated_value_inr.desc())
        elif sort_by == "value_asc":
            query = query.order_by(PropertyORM.current_estimated_value_inr.asc())
        elif sort_by == "yield_desc":
            # In SQLite simple sort by rent/value
            pass
            
        props = query.limit(limit).all()
        
        results = []
        for p in props:
            p_yield = (p.annual_rent_inr / p.current_estimated_value_inr * 100) if p.current_estimated_value_inr > 0 else 0.0
            results.append({
                "property_id": p.property_id,
                "property_type": p.property_type,
                "sub_type": p.sub_type,
                "location": p.location,
                "city": p.city,
                "area_sqft": p.area_sqft,
                "current_estimated_value_inr": p.current_estimated_value_inr,
                "current_estimated_value_formatted": format_inr(p.current_estimated_value_inr),
                "annual_rent_inr": p.annual_rent_inr,
                "annual_rent_formatted": format_inr(p.annual_rent_inr),
                "rental_yield_pct": round(p_yield, 2),
                "occupancy_status": p.occupancy_status,
                "tenant_status": p.tenant_status
            })
            
        return {
            "user_id": user_id,
            "matched_count": len(results),
            "properties": results
        }
    finally:
        if own_session:
            db.close()


def tool_compare_exposure(user_id: str, db: Optional[Session] = None) -> Dict[str, Any]:
    """Compare residential, commercial/office, and retail asset allocations and exposures."""
    summary = tool_get_portfolio_summary(user_id, db=db)
    macro_breakdown = summary.get("breakdown_by_macro_type", {})
    
    comparisons = []
    for asset_class, data in macro_breakdown.items():
        comparisons.append({
            "asset_class": asset_class,
            "count": data["count"],
            "total_value": data["value_formatted"],
            "value_share_pct": f"{data['value_share_pct']}%",
            "annual_rent": data["rent_formatted"],
            "rental_yield": f"{data['yield_pct']}%",
            "total_area_sqft": data["area"]
        })
        
    return {
        "user_id": user_id,
        "total_portfolio_value": summary["total_portfolio_value_formatted"],
        "comparison": comparisons
    }


def find_property_by_identifier(db: Session, user_id: str, identifier: str) -> Optional[PropertyORM]:
    """Fuzzy lookup property by ID (P001) or locality keywords ('Bandra', 'Indiranagar')."""
    ident = identifier.strip().lower()
    
    # 1. Exact ID
    prop = db.query(PropertyORM).filter(PropertyORM.user_id == user_id, PropertyORM.property_id.ilike(ident)).first()
    if prop:
        return prop
        
    # 2. Match locality / location
    props = db.query(PropertyORM).filter(PropertyORM.user_id == user_id, PropertyORM.status == "Active").all()
    for p in props:
        if ident in p.location.lower() or ident in (p.sub_type or "").lower() or ident in p.property_type.lower():
            return p
            
    # 3. Partial word match
    tokens = ident.split()
    for p in props:
        for t in tokens:
            if len(t) > 3 and t in p.location.lower():
                return p
                
    return None


def tool_simulate_hypothetical(user_id: str, exclude_identifier: str, db: Optional[Session] = None) -> Dict[str, Any]:
    """Run hypothetical sandbox analysis excluding a specific property without altering the database."""
    own_session = False
    if db is None:
        db = SessionLocal()
        own_session = True
    try:
        props = db.query(PropertyORM).filter(PropertyORM.user_id == user_id, PropertyORM.status == "Active").all()
        target = find_property_by_identifier(db, user_id, exclude_identifier)
        if not target:
            return {
                "error": f"Could not find any property matching '{exclude_identifier}' in user's portfolio.",
                "available_properties": [f"{p.property_id}: {p.location} ({p.property_type})" for p in props]
            }
            
        simulation = ScenarioEngine.simulate_exclusion(props, user_id, [target.property_id])
        return simulation
    finally:
        if own_session:
            db.close()


def tool_create_property(
    user_id: str,
    property_type: str,
    location: str,
    area_sqft: float,
    current_estimated_value_inr: float,
    sub_type: Optional[str] = None,
    annual_rent_inr: float = 0.0,
    occupancy_status: str = "Vacant",
    tenant_status: str = "No",
    db: Optional[Session] = None
) -> Dict[str, Any]:
    """Add a new property to the user's real estate portfolio."""
    own_session = False
    if db is None:
        db = SessionLocal()
        own_session = True
    try:
        # Generate new property ID
        max_prop = db.query(PropertyORM).order_by(PropertyORM.property_id.desc()).first()
        if max_prop and max_prop.property_id.startswith("P"):
            try:
                num = int(max_prop.property_id[1:]) + 1
                new_id = f"P{num:03d}"
            except ValueError:
                new_id = f"P{db.query(PropertyORM).count() + 1:03d}"
        else:
            new_id = f"P{db.query(PropertyORM).count() + 1:03d}"
            
        city = extract_city(location)
        if annual_rent_inr > 0 and tenant_status == "No":
            tenant_status = "Yes"
            occupancy_status = "Tenanted"

        new_prop = PropertyORM(
            property_id=new_id,
            user_id=user_id,
            property_type=property_type,
            sub_type=sub_type or property_type,
            location=location,
            city=city,
            area_sqft=area_sqft,
            current_estimated_value_inr=current_estimated_value_inr,
            annual_rent_inr=annual_rent_inr,
            occupancy_status=occupancy_status,
            tenant_status=tenant_status,
            ownership_percent=100.0,
            status="Active"
        )
        db.add(new_prop)
        db.commit()
        db.refresh(new_prop)
        
        return {
            "success": True,
            "message": f"Successfully added {property_type} in {location} with ID {new_id} to portfolio.",
            "property": {
                "property_id": new_id,
                "location": location,
                "city": city,
                "property_type": property_type,
                "area_sqft": area_sqft,
                "value": format_inr(current_estimated_value_inr),
                "annual_rent": format_inr(annual_rent_inr),
                "occupancy_status": occupancy_status
            }
        }
    except Exception as e:
        db.rollback()
        return {"success": False, "error": str(e)}
    finally:
        if own_session:
            db.close()


def tool_update_property(
    user_id: str,
    property_identifier: str,
    current_estimated_value_inr: Optional[float] = None,
    annual_rent_inr: Optional[float] = None,
    occupancy_status: Optional[str] = None,
    notes: Optional[str] = None,
    db: Optional[Session] = None
) -> Dict[str, Any]:
    """Update property details like current estimated valuation, rental income, or occupancy status."""
    own_session = False
    if db is None:
        db = SessionLocal()
        own_session = True
    try:
        prop = find_property_by_identifier(db, user_id, property_identifier)
        if not prop:
            return {"success": False, "error": f"Property '{property_identifier}' not found for user {user_id}."}
            
        changes = []
        if current_estimated_value_inr is not None:
            old_val = prop.current_estimated_value_inr
            prop.current_estimated_value_inr = current_estimated_value_inr
            changes.append(f"Valuation: {format_inr(old_val)} -> {format_inr(current_estimated_value_inr)}")
            
        if annual_rent_inr is not None:
            old_rent = prop.annual_rent_inr
            prop.annual_rent_inr = annual_rent_inr
            changes.append(f"Annual Rent: {format_inr(old_rent)} -> {format_inr(annual_rent_inr)}")
            if annual_rent_inr > 0:
                prop.occupancy_status = "Tenanted"
                prop.tenant_status = "Yes"
                
        if occupancy_status is not None:
            old_occ = prop.occupancy_status
            prop.occupancy_status = occupancy_status
            prop.tenant_status = "Yes" if occupancy_status.lower() == "tenanted" else "No"
            changes.append(f"Occupancy: {old_occ} -> {occupancy_status}")
            
        db.commit()
        db.refresh(prop)
        
        return {
            "success": True,
            "property_id": prop.property_id,
            "location": prop.location,
            "message": f"Updated {prop.property_id} ({prop.location}): " + "; ".join(changes),
            "changes": changes,
            "current_status": {
                "value": format_inr(prop.current_estimated_value_inr),
                "annual_rent": format_inr(prop.annual_rent_inr),
                "occupancy": prop.occupancy_status
            }
        }
    except Exception as e:
        db.rollback()
        return {"success": False, "error": str(e)}
    finally:
        if own_session:
            db.close()


def tool_flag_conversation(
    user_id: str,
    conversation_id: str,
    reason: str,
    severity: str = "Medium",
    db: Optional[Session] = None
) -> Dict[str, Any]:
    """Flag conversation for business team attention / human wealth manager intervention."""
    own_session = False
    if db is None:
        db = SessionLocal()
        own_session = True
    try:
        import uuid
        flag = EscalationFlagORM(
            id=f"flag_{uuid.uuid4().hex[:8]}",
            conversation_id=conversation_id,
            user_id=user_id,
            reason=reason,
            severity=severity,
            status="Open"
        )
        db.add(flag)
        
        # Also mark session
        sess = db.query(ConversationSessionORM).filter(ConversationSessionORM.id == conversation_id).first()
        if sess:
            sess.is_flagged = True
            sess.flag_reason = reason
            
        db.commit()
        return {
            "success": True,
            "flag_id": flag.id,
            "message": f"Conversation escalated to human wealth advisor: {reason}"
        }
    except Exception as e:
        db.rollback()
        return {"success": False, "error": str(e)}
    finally:
        if own_session:
            db.close()


# --- TOOL SCHEMAS FOR OPENROUTER / OPENAI FUNCTION CALLING ---

AGENT_TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "get_portfolio_summary",
            "description": "Calculates overall portfolio summary including total value, annual rent, rental yields, asset class breakdown, and city concentration.",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {"type": "string", "description": "The user ID (e.g. U001)"}
                },
                "required": ["user_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_properties",
            "description": "Filters and queries user properties based on property type (retail, commercial, office, residential), city, valuation thresholds, or rent.",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {"type": "string", "description": "The user ID (e.g. U001)"},
                    "property_type": {"type": "string", "description": "Retail, Commercial Office, Office, or Residential"},
                    "city": {"type": "string", "description": "City name like Mumbai, Bengaluru, Gurugram, Noida"},
                    "min_value": {"type": "number", "description": "Minimum property value in INR"},
                    "max_value": {"type": "number", "description": "Maximum property value in INR"},
                    "min_rent": {"type": "number", "description": "Minimum annual rent in INR"},
                    "sort_by": {"type": "string", "enum": ["annual_rent_desc", "annual_rent_asc", "value_desc", "value_asc"], "description": "Sort order"}
                },
                "required": ["user_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "compare_exposure",
            "description": "Compares exposure across asset classes: Residential, Commercial/Office, and Retail.",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {"type": "string", "description": "The user ID"}
                },
                "required": ["user_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "simulate_hypothetical_exclusion",
            "description": "Performs what-if hypothetical analysis excluding a specific property to see impact on portfolio value, rental income, and yields without mutating actual data.",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {"type": "string", "description": "The user ID"},
                    "exclude_identifier": {"type": "string", "description": "Property ID or locality name (e.g. 'Bandra' or 'P001')"}
                },
                "required": ["user_id", "exclude_identifier"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_property",
            "description": "Adds a new real estate property to the user's portfolio and persists it in the database.",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {"type": "string", "description": "User ID"},
                    "property_type": {"type": "string", "description": "Retail, Commercial Office, Office, or Residential"},
                    "location": {"type": "string", "description": "Locality, City (e.g. 'Indiranagar, Bengaluru')"},
                    "area_sqft": {"type": "number", "description": "Property area in square feet"},
                    "current_estimated_value_inr": {"type": "number", "description": "Property estimated value in INR"},
                    "sub_type": {"type": "string", "description": "Optional sub type (e.g. High-street retail, Apartment)"},
                    "annual_rent_inr": {"type": "number", "description": "Annual rent in INR if tenanted (default 0)"},
                    "occupancy_status": {"type": "string", "enum": ["Tenanted", "Vacant", "Self-occupied"], "description": "Occupancy status"}
                },
                "required": ["user_id", "property_type", "location", "area_sqft", "current_estimated_value_inr"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "update_property",
            "description": "Updates an existing property in the database (e.g. valuation, rent, or occupancy status).",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {"type": "string", "description": "User ID"},
                    "property_identifier": {"type": "string", "description": "Property ID (P001) or locality (Bandra)"},
                    "current_estimated_value_inr": {"type": "number", "description": "New estimated value in INR"},
                    "annual_rent_inr": {"type": "number", "description": "New annual rent in INR"},
                    "occupancy_status": {"type": "string", "description": "Tenanted, Vacant, or Self-occupied"}
                },
                "required": ["user_id", "property_identifier"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "flag_for_human_attention",
            "description": "Flags this conversation for business team attention or escalation to a human wealth advisor.",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {"type": "string", "description": "User ID"},
                    "reason": {"type": "string", "description": "Reason for human attention or escalation"},
                    "severity": {"type": "string", "enum": ["Low", "Medium", "High", "Critical"]}
                },
                "required": ["user_id", "reason"]
            }
        }
    }
]
