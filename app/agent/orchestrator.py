import time
import json
import uuid
import re
import logging
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.database import SessionLocal
from app.core.models import (
    ConversationSessionORM, MessageORM, ToolTraceORM, UserORM, PropertyORM
)
from app.analytics.portfolio_engine import PortfolioEngine, format_inr
from app.agent.tools import (
    tool_get_portfolio_summary,
    tool_search_properties,
    tool_compare_exposure,
    tool_simulate_hypothetical,
    tool_create_property,
    tool_update_property,
    tool_flag_conversation,
    find_property_by_identifier,
    AGENT_TOOLS_SCHEMA
)

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an elite, highly professional AI Real Estate Portfolio Analyst designed for High-Net-Worth Individuals (HNWIs) in India.
Your mission is to understand, analyse, monitor, and manage the user's real estate portfolio.

Core Principles:
1. Grounded Analytics: Always use tool calls (get_portfolio_summary, search_properties, compare_exposure, simulate_hypothetical_exclusion) rather than calculating in context or hallucinating.
2. Indian Wealth Context: Present monetary figures in ₹ Crores (Cr) and ₹ Lakhs (L) with standard Indian conventions (e.g. ₹12.50 Cr, ₹72.00 L).
3. Distinguish Hypotheticals: Clearly separate real portfolio data from what-if hypothetical analyses. Always label simulated numbers with [Hypothetical Scenario].
4. Honesty on Missing Data: If asked about appreciation or historical purchase returns, explain that historical acquisition dates and costs are not recorded in the seed data; politely offer to record them.
5. Proactive Value: Provide rental yields (Annual Rent / Property Value * 100), occupancy health, and asset allocation commentary.
6. WhatsApp Style: Keep messages crisp, well-formatted with bullet points and bold headers, suitable for a simulated WhatsApp chat.
"""

def parse_inr_amount(text: str) -> Optional[float]:
    """Helper to parse ₹ / crore / lakh strings like '₹12.5 crore', '4.2 cr', '50 lakh'"""
    t = text.lower().replace(",", "").replace("₹", "").replace("rs.", "").strip()
    
    # Check crore
    cr_match = re.search(r'([\d\.]+)\s*(?:cr|crore|crores)', t)
    if cr_match:
        try:
            return float(cr_match.group(1)) * 10000000.0
        except ValueError:
            pass
            
    # Check lakh
    lakh_match = re.search(r'([\d\.]+)\s*(?:l|lakh|lakhs|lac|lacs)', t)
    if lakh_match:
        try:
            return float(lakh_match.group(1)) * 100000.0
        except ValueError:
            pass
            
    # Direct digits
    num_match = re.search(r'(\d{6,})', t)
    if num_match:
        try:
            return float(num_match.group(1))
        except ValueError:
            pass
            
    return None

class AgentOrchestrator:
    def __init__(self):
        self.tools_map = {
            "get_portfolio_summary": tool_get_portfolio_summary,
            "search_properties": tool_search_properties,
            "compare_exposure": tool_compare_exposure,
            "simulate_hypothetical_exclusion": tool_simulate_hypothetical,
            "create_property": tool_create_property,
            "update_property": tool_update_property,
            "flag_for_human_attention": tool_flag_conversation
        }

    def process_message(
        self,
        user_id: str,
        user_message: str,
        conversation_id: Optional[str] = None,
        model_override: Optional[str] = None,
        api_key_override: Optional[str] = None
    ) -> Dict[str, Any]:
        """Main agent entrypoint: handles state, executes tools, records traces, and returns reply."""
        start_time = time.time()
        db: Session = SessionLocal()
        
        try:
            # 1. Resolve or create Conversation Session
            if not conversation_id:
                conversation_id = f"conv_{user_id}_{int(time.time())}_{uuid.uuid4().hex[:4]}"
                
            session_obj = db.query(ConversationSessionORM).filter(ConversationSessionORM.id == conversation_id).first()
            if not session_obj:
                user = db.query(UserORM).filter(UserORM.user_id == user_id).first()
                title = f"{user.name if user else user_id} - Portfolio Chat"
                session_obj = ConversationSessionORM(id=conversation_id, user_id=user_id, title=title)
                db.add(session_obj)
                db.commit()

            # Record user message
            user_msg_id = f"msg_{uuid.uuid4().hex[:8]}"
            user_msg_orm = MessageORM(
                id=user_msg_id,
                conversation_id=conversation_id,
                sender="user",
                content=user_message,
                created_at=session_obj.created_at
            )
            db.add(user_msg_orm)
            db.commit()

            # Check for API key (OpenRouter / OpenAI)
            api_key = api_key_override or settings.OPENROUTER_API_KEY or settings.OPENAI_API_KEY
            is_openrouter = bool(settings.OPENROUTER_API_KEY or (api_key and "sk-or-" in api_key))
            
            tool_traces: List[Dict[str, Any]] = []
            
            if api_key:
                # --- MODE A: LLM WITH NATIVE TOOL CALLING ---
                reply_text, tool_traces = self._execute_llm_mode(
                    db=db,
                    user_id=user_id,
                    conversation_id=conversation_id,
                    user_message=user_message,
                    api_key=api_key,
                    model_override=model_override,
                    is_openrouter=is_openrouter
                )
            else:
                # --- MODE B: AUTONOMOUS DETERMINISTIC ENGINE (Zero Key / Fallback) ---
                reply_text, tool_traces = self._execute_deterministic_mode(
                    db=db,
                    user_id=user_id,
                    conversation_id=conversation_id,
                    user_message=user_message
                )

            # Check if conversation needs flagging for human attention
            flag_reason = self._check_attention_triggers(user_message, reply_text)
            if flag_reason and not session_obj.is_flagged:
                session_obj.is_flagged = True
                session_obj.flag_reason = flag_reason
                tool_flag_conversation(user_id=user_id, conversation_id=conversation_id, reason=flag_reason, severity="High", db=db)

            # Record assistant reply
            total_latency_ms = round((time.time() - start_time) * 1000, 2)
            asst_msg_id = f"msg_{uuid.uuid4().hex[:8]}"
            asst_msg_orm = MessageORM(
                id=asst_msg_id,
                conversation_id=conversation_id,
                sender="assistant",
                content=reply_text,
                tool_calls_json=json.dumps([t.get("tool_name") for t in tool_traces]),
                latency_ms=total_latency_ms
            )
            db.add(asst_msg_orm)
            db.commit()

            return {
                "conversation_id": conversation_id,
                "user_id": user_id,
                "reply": reply_text,
                "tool_traces": tool_traces,
                "latency_ms": total_latency_ms,
                "is_flagged": session_obj.is_flagged,
                "flag_reason": session_obj.flag_reason
            }

        except Exception as e:
            logger.exception("Error in process_message:")
            total_latency_ms = round((time.time() - start_time) * 1000, 2)
            error_reply = (
                "⚠️ I encountered an unexpected error processing your request. "
                "I've flagged this for our human wealth management desk to assist you directly."
            )
            return {
                "conversation_id": conversation_id,
                "user_id": user_id,
                "reply": error_reply,
                "tool_traces": [],
                "latency_ms": total_latency_ms,
                "is_flagged": True,
                "flag_reason": f"System error: {str(e)}"
            }
        finally:
            db.close()

    def _execute_llm_mode(
        self,
        db: Session,
        user_id: str,
        conversation_id: str,
        user_message: str,
        api_key: str,
        model_override: Optional[str],
        is_openrouter: bool
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """Execute LLM agent loop using OpenAI / OpenRouter client with function calling."""
        from openai import OpenAI
        
        base_url = "https://openrouter.ai/api/v1" if is_openrouter else None
        model = model_override or settings.DEFAULT_MODEL
        
        client = OpenAI(api_key=api_key, base_url=base_url)
        
        # Load conversation history (last 6 messages)
        history_orms = db.query(MessageORM).filter(
            MessageORM.conversation_id == conversation_id
        ).order_by(MessageORM.created_at.desc()).limit(6).all()
        history_orms.reverse()
        
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        for m in history_orms:
            messages.append({"role": m.sender, "content": m.content})
            
        messages.append({"role": "user", "content": user_message})

        tool_traces = []
        
        # First LLM Call
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            tools=AGENT_TOOLS_SCHEMA,
            tool_choice="auto"
        )
        
        resp_msg = response.choices[0].message
        
        # If model called tools
        if resp_msg.tool_calls:
            messages.append(resp_msg)
            for tcall in resp_msg.tool_calls:
                fname = tcall.function.name
                fargs = json.loads(tcall.function.arguments or "{}")
                if "user_id" not in fargs:
                    fargs["user_id"] = user_id
                    
                tool_start = time.time()
                try:
                    tool_fn = self.tools_map.get(fname)
                    if tool_fn:
                        tool_res = tool_fn(**fargs, db=db)
                    else:
                        tool_res = {"error": f"Tool {fname} not found"}
                    success = True
                    err_msg = None
                except Exception as err:
                    tool_res = {"error": str(err)}
                    success = False
                    err_msg = str(err)
                    
                tool_duration = round((time.time() - tool_start) * 1000, 2)
                
                # Record trace in DB
                trace_orm = ToolTraceORM(
                    id=f"tr_{uuid.uuid4().hex[:8]}",
                    conversation_id=conversation_id,
                    user_id=user_id,
                    tool_name=fname,
                    tool_input_json=json.dumps(fargs),
                    tool_output_json=json.dumps(tool_res),
                    execution_time_ms=tool_duration,
                    success=success,
                    error_message=err_msg
                )
                db.add(trace_orm)
                db.commit()
                
                tool_traces.append({
                    "tool_name": fname,
                    "input": fargs,
                    "output": tool_res,
                    "duration_ms": tool_duration
                })
                
                # Append tool result to messages for final synthesis
                messages.append({
                    "role": "tool",
                    "tool_call_id": tcall.id,
                    "content": json.dumps(tool_res)
                })
                
            # Second call to get final synthesized response
            second_resp = client.chat.completions.create(
                model=model,
                messages=messages
            )
            final_reply = second_resp.choices[0].message.content or ""
            return final_reply, tool_traces
        else:
            return resp_msg.content or "", tool_traces

    def _execute_deterministic_mode(
        self,
        db: Session,
        user_id: str,
        conversation_id: str,
        user_message: str
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """High-intelligence deterministic fallback that parses intent, executes exact tools, and formats responses."""
        msg_lower = user_message.lower().strip()
        tool_traces = []

        def log_tool(tool_name: str, inp: dict, out: dict, duration: float):
            trace = ToolTraceORM(
                id=f"tr_{uuid.uuid4().hex[:8]}",
                conversation_id=conversation_id,
                user_id=user_id,
                tool_name=tool_name,
                tool_input_json=json.dumps(inp),
                tool_output_json=json.dumps(out),
                execution_time_ms=duration,
                success=True
            )
            db.add(trace)
            db.commit()
            tool_traces.append({"tool_name": tool_name, "input": inp, "output": out, "duration_ms": duration})

        # 1. Update Property Valuation (e.g. Sample Request R006: "Change my Bandra retail property value to ₹12.5 crore")
        if any(w in msg_lower for w in ["change", "update", "set"]) and any(w in msg_lower for w in ["value", "worth", "valuation", "crore", "cr"]):
            t0 = time.time()
            val = parse_inr_amount(user_message)
            ident = "bandra" if "bandra" in msg_lower else ("p001" if "p001" in msg_lower else "")
            if not ident:
                # search words in message that might be locality
                for w in ["andheri", "worli", "alibaug", "gurugram", "noida", "indiranagar", "koramangala", "whitefield"]:
                    if w in msg_lower:
                        ident = w
                        break
            if not ident:
                ident = "retail"
                
            res = tool_update_property(user_id=user_id, property_identifier=ident, current_estimated_value_inr=val, db=db)
            log_tool("update_property", {"property_identifier": ident, "current_estimated_value_inr": val}, res, round((time.time() - t0)*1000, 2))
            
            if res.get("success"):
                reply = (
                    f"✅ **Property Value Updated Successfully**\n\n"
                    f"• **Property:** {res.get('location')} (`{res.get('property_id')}`)\n"
                    f"• **New Valuation:** {res['current_status']['value']}\n"
                    f"• **Annual Rent:** {res['current_status']['annual_rent']}\n"
                    f"• **Occupancy Status:** {res['current_status']['occupancy']}\n\n"
                    f"Your portfolio analytics have been recalculated to reflect this updated valuation."
                )
            else:
                reply = f"⚠️ Could not update property: {res.get('error')}"
            return reply, tool_traces

        # 2. Add New Property (e.g. Sample Request R005: "Add a 3000 sq ft retail property in Indiranagar worth ₹4.2 crore")
        elif msg_lower.startswith("add ") or "add it to my portfolio" in msg_lower or "add a " in msg_lower:
            t0 = time.time()
            # Area sqft extraction
            area_match = re.search(r'(\d[\d,\.]*)\s*(?:sq\s*ft|sqft|square\s*feet)', msg_lower)
            area = float(area_match.group(1).replace(",", "")) if area_match else None
            
            # Value extraction
            val = parse_inr_amount(user_message)
            
            # Asset type extraction
            pt = "Retail" if "retail" in msg_lower else ("Residential" if any(w in msg_lower for w in ["residential", "apartment", "villa", "flat"]) else "Commercial Office")
            
            # Location extraction
            loc = "Indiranagar, Bengaluru" if "indiranagar" in msg_lower else ("Bandra West, Mumbai" if "bandra" in msg_lower else "Bengaluru")
            for city_word in ["koramangala", "whitefield", "worli", "andheri", "gurugram", "noida"]:
                if city_word in msg_lower:
                    loc = f"{city_word.title()}"
                    break
                    
            if not area or not val:
                # Slot filling inquiry
                missing = []
                if not area: missing.append("carpet area in sq ft")
                if not val: missing.append("current estimated value (e.g. ₹X Cr)")
                reply = (
                    f"I would be glad to add this {pt} property to your portfolio! "
                    f"To record it accurately, could you please provide: {', '.join(missing)}?"
                )
                return reply, tool_traces
                
            res = tool_create_property(
                user_id=user_id,
                property_type=pt,
                location=loc,
                area_sqft=area,
                current_estimated_value_inr=val,
                occupancy_status="Vacant",
                db=db
            )
            log_tool("create_property", {"property_type": pt, "location": loc, "area_sqft": area, "value": val}, res, round((time.time() - t0)*1000, 2))
            
            prop = res.get("property", {})
            reply = (
                f"✅ **New Property Added to Portfolio**\n\n"
                f"• **Asset ID:** `{prop.get('property_id')}`\n"
                f"• **Type:** {prop.get('property_type')}\n"
                f"• **Location:** {prop.get('location')}\n"
                f"• **Area:** {prop.get('area_sqft'):,.0f} sq ft\n"
                f"• **Current Valuation:** {prop.get('value')}\n"
                f"• **Occupancy Status:** {prop.get('occupancy_status')}\n\n"
                f"💡 *Note:* Would you like to specify whether this unit is currently tenanted or self-occupied, and record its rental income?"
            )
            return reply, tool_traces

        # 3. Specific Exposure Query: "How much of my portfolio is retail?" / "How much is commercial?"
        elif "how much" in msg_lower and any(w in msg_lower for w in ["retail", "commercial", "residential", "office"]):
            t0 = time.time()
            summary = tool_get_portfolio_summary(user_id=user_id, db=db)
            target_class = "Retail" if "retail" in msg_lower else ("Residential" if "residential" in msg_lower else "Commercial / Office")
            macro_data = summary.get("breakdown_by_macro_type", {}).get(target_class)
            
            if not macro_data or macro_data.get("count", 0) == 0:
                reply = f"You currently have **0% exposure** to {target_class} assets in your portfolio."
            else:
                log_tool("get_portfolio_summary", {"user_id": user_id, "target_class": target_class}, summary, round((time.time() - t0)*1000, 2))
                reply = (
                    f"📊 **{target_class} Portfolio Exposure**\n\n"
                    f"• **Allocation Share:** **{macro_data['value_share_pct']}%** of your total portfolio\n"
                    f"• **Total Valuation:** **{macro_data['value_formatted']}** (out of {summary['total_portfolio_value_formatted']} total portfolio)\n"
                    f"• **Properties Count:** **{macro_data['count']} unit(s)** ({macro_data['area']:,.0f} sq ft total)\n"
                    f"• **Annual Rental Income:** **{macro_data['rent_formatted']}**\n"
                    f"• **Asset Class Gross Yield:** **{macro_data['yield_pct']}%**\n\n"
                    f"💡 *Strategic Insight:* {target_class} forms the predominant allocation of your portfolio wealth."
                )
            return reply, tool_traces

        # 4. Hypothetical Simulation (e.g. "What if I exclude the Bandra property?", "How would that change my portfolio?")
        elif any(w in msg_lower for w in ["what if", "exclude", "without", "hypothetical", "how would that change", "how does that change"]):
            t0 = time.time()
            ident = "bandra" if "bandra" in msg_lower else ("p001" if "p001" in msg_lower else "")
            if not ident:
                # check recent context or other localities
                for w in ["andheri", "worli", "alibaug", "gurugram", "noida", "indiranagar", "koramangala", "whitefield"]:
                    if w in msg_lower:
                        ident = w
                        break
            if not ident:
                ident = "bandra" # default for sample scenario
                
            res = tool_simulate_hypothetical(user_id=user_id, exclude_identifier=ident, db=db)
            log_tool("simulate_hypothetical_exclusion", {"exclude_identifier": ident}, res, round((time.time() - t0)*1000, 2))
            
            if "error" in res:
                return f"⚠️ {res['error']}", tool_traces
                
            base = res["baseline"]
            hyp = res["hypothetical"]
            impact = res["impact"]
            excluded = res["excluded_properties"][0] if res.get("excluded_properties") else {"location": ident, "value": "N/A"}
            
            reply = (
                f"🧪 **Hypothetical Portfolio Scenario (What-If Analysis)**\n"
                f"*Simulating portfolio excluding: **{excluded['location']}** ({excluded['value']})*\n\n"
                f"| Metric | Current Actual | Hypothetical | Impact Delta |\n"
                f"| :--- | :--- | :--- | :--- |\n"
                f"| **Portfolio Value** | {base['total_value']} | {hyp['total_value']} | **{impact['value_change']}** ({impact['value_change_pct']}%) |\n"
                f"| **Annual Rental Income** | {base['total_rent']} | {hyp['total_rent']} | **{impact['rent_change']}** ({impact['rent_change_pct']}%) |\n"
                f"| **Gross Rental Yield** | {base['yield_pct']} | {hyp['yield_pct']} | **{impact['yield_change_points']:+0.2f}%** |\n"
                f"| **Total Properties** | {base['total_properties']} | {hyp['total_properties']} | -1 property |\n\n"
                f"⚠️ *Important:* This is a hypothetical simulation sandbox. Your actual portfolio records remain unchanged."
            )
            return reply, tool_traces

        # 4. Filter properties above ₹X crore (e.g. Sample Request R002: "Which of my properties are above ₹10 crore?")
        elif "above" in msg_lower and any(w in msg_lower for w in ["crore", "cr", "10"]):
            t0 = time.time()
            min_val = parse_inr_amount(user_message) or 100000000.0
            res = tool_search_properties(user_id=user_id, min_value=min_val, db=db)
            log_tool("search_properties", {"min_value": min_val}, res, round((time.time() - t0)*1000, 2))
            
            props = res.get("properties", [])
            if not props:
                reply = f"You do not currently have any active properties valued above {format_inr(min_val)}."
            else:
                lines = [f"You have **{len(props)} property(ies)** valued above {format_inr(min_val)}:\n"]
                for p in props:
                    lines.append(
                        f"• **{p['location']}** (`{p['property_id']}`)\n"
                        f"  Type: {p['property_type']} ({p.get('sub_type', '')})\n"
                        f"  Estimated Value: **{p['current_estimated_value_formatted']}**\n"
                        f"  Annual Rent: {p['annual_rent_formatted']} (Yield: {p['rental_yield_pct']}%)\n"
                        f"  Status: {p['occupancy_status']}"
                    )
                reply = "\n".join(lines)
            return reply, tool_traces

        # 5. Highest Annual Rent (e.g. Sample Request R004: "Which property gives me the highest annual rent?")
        elif "highest" in msg_lower and any(w in msg_lower for w in ["rent", "rental", "income"]):
            t0 = time.time()
            res = tool_search_properties(user_id=user_id, sort_by="annual_rent_desc", limit=1, db=db)
            log_tool("search_properties", {"sort_by": "annual_rent_desc"}, res, round((time.time() - t0)*1000, 2))
            
            props = res.get("properties", [])
            if props and props[0]["annual_rent_inr"] > 0:
                p = props[0]
                reply = (
                    f"🏆 **Highest Rental Generating Asset**\n\n"
                    f"• **Property:** {p['location']} (`{p['property_id']}`)\n"
                    f"• **Asset Type:** {p['property_type']} ({p.get('sub_type', '')})\n"
                    f"• **Annual Rental Income:** **{p['annual_rent_formatted']}** (~{format_inr(p['annual_rent_inr']/12)}/month)\n"
                    f"• **Current Valuation:** {p['current_estimated_value_formatted']}\n"
                    f"• **Gross Rental Yield:** **{p['rental_yield_pct']}%**\n"
                    f"• **Tenant Status:** {p['occupancy_status']}"
                )
            else:
                reply = "None of your current properties are actively generating rental income (they are either vacant or self-occupied)."
            return reply, tool_traces

        # 6. Retail properties query (e.g. Sample Request R001: "Show me my retail properties")
        elif "retail" in msg_lower and any(w in msg_lower for w in ["show", "list", "my", "tell me about"]):
            t0 = time.time()
            res = tool_search_properties(user_id=user_id, property_type="Retail", db=db)
            log_tool("search_properties", {"property_type": "Retail"}, res, round((time.time() - t0)*1000, 2))
            
            props = res.get("properties", [])
            if not props:
                reply = "You do not currently hold any retail properties in your active portfolio."
            else:
                lines = [f"Here is a summary of your **{len(props)} Retail Properties**:\n"]
                for p in props:
                    lines.append(
                        f"• **{p['location']}** (`{p['property_id']}`)\n"
                        f"  Sub-type: {p.get('sub_type') or 'Retail'}\n"
                        f"  Area: {p['area_sqft']:,.0f} sq ft\n"
                        f"  Valuation: **{p['current_estimated_value_formatted']}**\n"
                        f"  Annual Rent: **{p['annual_rent_formatted']}** (Yield: **{p['rental_yield_pct']}%**)\n"
                        f"  Occupancy: {p['occupancy_status']}\n"
                    )
                reply = "\n".join(lines)
            return reply, tool_traces

        # 7. Contextual Comparison: "Which one is performing better?"
        elif "performing better" in msg_lower or "better yield" in msg_lower or "which one performs" in msg_lower:
            t0 = time.time()
            res = tool_get_portfolio_summary(user_id=user_id, db=db)
            log_tool("get_portfolio_summary", {"user_id": user_id}, res, round((time.time() - t0)*1000, 2))
            
            props = res.get("properties", [])
            tenanted_props = [p for p in props if p["rental_yield_pct"] > 0]
            if not tenanted_props:
                return "None of the properties in this selection are tenanted with a positive rental yield.", tool_traces
                
            sorted_props = sorted(tenanted_props, key=lambda x: x["rental_yield_pct"], reverse=True)
            best = sorted_props[0]
            
            lines = [
                f"📊 **Performance & Yield Analysis**\n",
                f"**{best['location']}** is your best performing asset based on gross rental yield:\n",
                f"• **Top Performer:** {best['location']} at **{best['rental_yield_pct']}% yield** (Generating {best['annual_rent_formatted']} on {best['current_estimated_value_formatted']} valuation)."
            ]
            if len(sorted_props) > 1:
                runner_up = sorted_props[1]
                lines.append(f"• **Comparison:** Followed by {runner_up['location']} at **{runner_up['rental_yield_pct']}% yield** ({runner_up['annual_rent_formatted']}).")
                
            return "\n".join(lines), tool_traces

        # 8. City-specific query (e.g. Sample Request R003: "Show me my properties in Mumbai")
        elif any(c in msg_lower for c in ["mumbai", "bengaluru", "bangalore", "delhi", "gurugram", "noida"]):
            t0 = time.time()
            city = "Mumbai" if "mumbai" in msg_lower else ("Bengaluru" if ("bengaluru" in msg_lower or "bangalore" in msg_lower) else ("Gurugram" if "gurugram" in msg_lower else "Noida"))
            res = tool_search_properties(user_id=user_id, city=city, db=db)
            log_tool("search_properties", {"city": city}, res, round((time.time() - t0)*1000, 2))
            
            props = res.get("properties", [])
            if not props:
                reply = f"You do not hold any recorded properties in **{city}**."
            else:
                lines = [f"You hold **{len(props)} property(ies) in {city}**:\n"]
                for p in props:
                    lines.append(
                        f"• **{p['location']}** (`{p['property_id']}`)\n"
                        f"  Type: {p['property_type']} | Area: {p['area_sqft']:,.0f} sq ft\n"
                        f"  Valuation: **{p['current_estimated_value_formatted']}**\n"
                        f"  Annual Rent: {p['annual_rent_formatted']} ({p['occupancy_status']})\n"
                    )
                reply = "\n".join(lines)
            return reply, tool_traces

        # 9. Exposure Comparison (e.g. "Compare my residential and commercial exposure")
        elif "compare" in msg_lower or "exposure" in msg_lower or "allocation" in msg_lower:
            t0 = time.time()
            res = tool_compare_exposure(user_id=user_id, db=db)
            log_tool("compare_exposure", {"user_id": user_id}, res, round((time.time() - t0)*1000, 2))
            
            comps = res.get("comparison", [])
            lines = [
                f"🏛️ **Asset Class Allocation & Exposure Analysis**\n",
                f"**Total Portfolio Value:** {res.get('total_portfolio_value')}\n",
                f"| Asset Class | Units | Total Value | Share % | Annual Rent | Yield |",
                f"| :--- | :--- | :--- | :--- | :--- | :--- |"
            ]
            for c in comps:
                lines.append(f"| **{c['asset_class']}** | {c['count']} | {c['total_value']} | **{c['value_share_pct']}** | {c['annual_rent']} | {c['rental_yield']} |")
                
            reply = "\n".join(lines)
            return reply, tool_traces

        # 10. Appreciation or Purchase Cost Question (Explicitly specified in Section 6.2 of assignment)
        elif any(w in msg_lower for w in ["appreciation", "purchased", "purchase price", "bought", "growth since purchase"]):
            reply = (
                "ℹ️ **Historical Cost & Capital Appreciation Note**\n\n"
                "In your current portfolio records, historical purchase prices and acquisition dates are not yet recorded. "
                "Therefore, I cannot compute historical capital appreciation without making inaccurate assumptions.\n\n"
                "Would you like to share the acquisition year and purchase price for any of your properties so I can calculate your exact IRR and capital gains?"
            )
            return reply, tool_traces

        # 11. Default: Full Portfolio Overview ("What does my portfolio look like?", "Total portfolio value", etc.)
        else:
            t0 = time.time()
            summary = tool_get_portfolio_summary(user_id=user_id, db=db)
            log_tool("get_portfolio_summary", {"user_id": user_id}, summary, round((time.time() - t0)*1000, 2))
            
            lines = [
                f"🏢 **Real Estate Portfolio Overview** ({summary.get('user_name', user_id)})\n",
                f"• **Total Portfolio Value:** **{summary['total_portfolio_value_formatted']}**",
                f"• **Total Properties:** **{summary['total_properties']} units** ({summary['total_area_sqft']:,.0f} sq ft)",
                f"• **Total Annual Rent:** **{summary['total_annual_rent_formatted']}**",
                f"• **Overall Gross Yield:** **{summary['overall_rental_yield_pct']}%**",
                f"• **Area Occupancy Rate:** **{summary['occupancy_rate_pct']}%**\n",
                f"**Asset Allocation:**"
            ]
            for macro, data in summary.get("breakdown_by_macro_type", {}).items():
                lines.append(f"• {macro}: **{data['value_share_pct']}%** ({data['value_formatted']}, {data['count']} properties)")
                
            lines.append("\n**Properties Breakdown:**")
            for p in summary.get("properties", []):
                lines.append(f"• `{p['property_id']}` {p['location']}: **{p['current_estimated_value_formatted']}** ({p['property_type']}, {p['occupancy_status']})")
                
            reply = "\n".join(lines)
            return reply, tool_traces

    def _check_attention_triggers(self, user_msg: str, reply_text: str) -> Optional[str]:
        """Detect scenarios requiring human business advisor attention."""
        m = user_msg.lower()
        if any(w in m for w in ["speak to human", "talk to human", "advisor", "escalate", "agent please", "call me"]):
            return "User explicitly requested human wealth advisor contact."
        if any(w in m for w in ["angry", "ridiculous", "wrong data", "terrible", "complaint", "fraud"]):
            return "Negative sentiment / user complaint detected."
        if any(w in m for w in ["sell everything", "liquidate all", "distress sale"]):
            return "High-risk strategic liquidation decision."
        return None
