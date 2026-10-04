import sys
sys.stdout.reconfigure(encoding='utf-8')

import json
from app.core.database import seed_database_if_empty, SessionLocal
from app.core.models import UserORM, PropertyORM, ConversationSessionORM, MessageORM, ToolTraceORM
from app.agent.orchestrator import AgentOrchestrator
from app.analytics.portfolio_engine import PortfolioEngine, format_inr

def test_full_system():
    print("=== 1. TESTING DATABASE SEEDING ===")
    seed_database_if_empty(force_reset=True)
    db = SessionLocal()
    users = db.query(UserORM).all()
    props = db.query(PropertyORM).all()
    print(f"Users seeded: {len(users)} (Expected: 4)")
    print(f"Properties seeded: {len(props)} (Expected: 12)")
    assert len(users) == 4, "Users count mismatch"
    assert len(props) == 12, "Properties count mismatch"

    orchestrator = AgentOrchestrator()
    conv_id = "test_conv_u001"

    print("\n=== 2. TESTING SAMPLE REQUEST R001: Show me my retail properties (U001) ===")
    r1 = orchestrator.process_message(user_id="U001", user_message="Show me my retail properties", conversation_id=conv_id)
    print("Reply:\n", r1["reply"])
    print("Latency:", r1["latency_ms"], "ms")
    print("Tools:", [t["tool_name"] for t in r1["tool_traces"]])
    assert "Bandra" in r1["reply"] and "Lower Parel" in r1["reply"]

    print("\n=== 3. TESTING SAMPLE REQUEST R002: Properties above ₹10 crore (U001) ===")
    r2 = orchestrator.process_message(user_id="U001", user_message="Which of my properties are above ₹10 crore?", conversation_id=conv_id)
    print("Reply:\n", r2["reply"])
    print("Latency:", r2["latency_ms"], "ms")
    assert "Bandra" in r2["reply"]

    print("\n=== 4. TESTING SAMPLE REQUEST R003: Properties in Mumbai (U002) ===")
    r3 = orchestrator.process_message(user_id="U002", user_message="Show me my properties in Mumbai")
    print("Reply:\n", r3["reply"])
    print("Latency:", r3["latency_ms"], "ms")
    assert "Worli" in r3["reply"] or "Bandra" in r3["reply"]

    print("\n=== 5. TESTING SAMPLE REQUEST R004: Highest annual rent (U003) ===")
    r4 = orchestrator.process_message(user_id="U003", user_message="Which property gives me the highest annual rent?")
    print("Reply:\n", r4["reply"])
    print("Latency:", r4["latency_ms"], "ms")
    assert "Golf Course Road" in r4["reply"]

    print("\n=== 6. TESTING WHAT-IF HYPOTHETICAL EXCLUSION: What if I exclude the Bandra property? (U001) ===")
    r_hyp = orchestrator.process_message(user_id="U001", user_message="What if I exclude the Bandra property?", conversation_id=conv_id)
    print("Reply:\n", r_hyp["reply"])
    print("Latency:", r_hyp["latency_ms"], "ms")
    assert "Hypothetical Portfolio Scenario" in r_hyp["reply"]

    print("\n=== 6b. TESTING MULTI-TURN WHAT-IF FOLLOW-UP: How would that change my portfolio? ===")
    r_hyp2 = orchestrator.process_message(user_id="U001", user_message="How would that change my portfolio?", conversation_id=conv_id)
    print("Reply:\n", r_hyp2["reply"])
    assert "Hypothetical Portfolio Scenario" in r_hyp2["reply"]

    print("\n=== 7. TESTING SPECIFIC EXPOSURE QUERY: How much of my portfolio is retail? (U001) ===")
    r_ret = orchestrator.process_message(user_id="U001", user_message="How much of my portfolio is retail?", conversation_id=conv_id)
    print("Reply:\n", r_ret["reply"])
    assert "71.38%" in r_ret["reply"] and "₹21.20 Cr" in r_ret["reply"]

    print("\n=== 7b. TESTING ASSET EXPOSURE COMPARISON (U001) ===")
    r_exp = orchestrator.process_message(user_id="U001", user_message="Compare my residential and commercial exposure", conversation_id=conv_id)
    print("Reply:\n", r_exp["reply"])

    print("\n=== 8. TESTING MISSING HISTORICAL PURCHASE PRICE (Section 6.2) ===")
    r_app = orchestrator.process_message(user_id="U001", user_message="What is my appreciation since purchase?", conversation_id=conv_id)
    print("Reply:\n", r_app["reply"])
    assert "historical purchase" in r_app["reply"].lower()

    print("\n=== 9. TESTING DATA MUTATION R006: Update Bandra property value to ₹12.5 crore ===")
    r6 = orchestrator.process_message(user_id="U001", user_message="Change my Bandra retail property value to ₹12.5 crore", conversation_id=conv_id)
    print("Reply:\n", r6["reply"])
    db.expire_all()
    prop = db.query(PropertyORM).filter(PropertyORM.property_id == "P001").first()
    print("Updated P001 Value in DB:", prop.current_estimated_value_inr)
    assert prop.current_estimated_value_inr == 125000000.0

    print("\n=== 10. TESTING ADD PROPERTY R005: Add retail in Indiranagar worth ₹4.2 crore (U004) ===")
    r5 = orchestrator.process_message(user_id="U004", user_message="Add a 3000 sq ft retail property in Indiranagar worth ₹4.2 crore")
    print("Reply:\n", r5["reply"])
    p_new = db.query(PropertyORM).filter(PropertyORM.location.ilike("%Indiranagar%"), PropertyORM.user_id == "U004").first()
    assert p_new is not None
    print("New Property in DB:", p_new.property_id, p_new.location, p_new.current_estimated_value_inr)

    print("\n=== 11. TESTING HUMAN ESCALATION / ATTENTION TRIGGER ===")
    r_esc = orchestrator.process_message(user_id="U001", user_message="I am unhappy with this report, connect me to a human wealth advisor", conversation_id=conv_id)
    print("Is Flagged:", r_esc["is_flagged"])
    print("Flag Reason:", r_esc["flag_reason"])
    assert r_esc["is_flagged"] is True

    print("\n=== ALL 11 TEST VERIFICATIONS PASSED SUCCESSFULLY! ===")
    db.close()

if __name__ == "__main__":
    test_full_system()
