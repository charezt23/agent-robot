# src/graph.py
from langgraph.graph import StateGraph, END, START
from src.state import AgentState
from nodes.intentclassification import (
    check_intent, 
    handle_ambiguity, 
    finalize_intent, 
    should_confirm
)
from nodes.auth_and_validation import (
    check_token_valid,
    upload_ktp_for_ocr,
    handle_nik_confirmation,
    check_resident,
    login_by_nik,
    should_trigger_auth,
    should_route_after_check_token,
    should_route_after_upload_ktp,
    should_route_after_nik_confirmation,
    should_route_after_check_resident,
    should_route_after_login,
    should_route_from_start
)

# Graph terintegrasi
graph = StateGraph(AgentState)

# Intent classification nodes
graph.add_node("check_intent", check_intent)
graph.add_node("handle_ambiguity", handle_ambiguity)
graph.add_node("finalize_intent", finalize_intent)

# Auth & validation nodes
graph.add_node("check_token_valid", check_token_valid)
graph.add_node("upload_ktp_for_ocr", upload_ktp_for_ocr)
graph.add_node("handle_nik_confirmation", handle_nik_confirmation)
graph.add_node("check_resident", check_resident)
graph.add_node("login_by_nik", login_by_nik)

# START routing: conditional - check if in auth flow or go to intent classification
graph.add_conditional_edges(
    START,
    should_route_from_start,
    {
        "check_intent": "check_intent",
        "handle_nik_confirmation": "handle_nik_confirmation",
        "check_resident": "check_resident",
        "upload_ktp_for_ocr": "upload_ktp_for_ocr"
    }
)

# Conditional routing: check_intent -> handle_ambiguity or finalize_intent
graph.add_conditional_edges(
    "check_intent",
    should_confirm,
    {
        "confirm": "handle_ambiguity",
        "finalize": "finalize_intent"
    }
)

# Conditional routing: finalize_intent -> check_token_valid (if trigger) or END
graph.add_conditional_edges(
    "finalize_intent",
    should_trigger_auth,
    {
        "auth_flow": "check_token_valid",
        "handle_nik_confirmation": "handle_nik_confirmation",
        "end": END
    }
)

# Conditional routing: check_token_valid -> upload_ktp_for_ocr or END
graph.add_conditional_edges(
    "check_token_valid",
    should_route_after_check_token,
    {
        "upload_ktp_for_ocr": "upload_ktp_for_ocr",
        "end": END
    }
)

# Conditional routing: upload_ktp_for_ocr -> handle_nik_confirmation or END
graph.add_conditional_edges(
    "upload_ktp_for_ocr",
    should_route_after_upload_ktp,
    {
        "handle_nik_confirmation": "handle_nik_confirmation",
        "end": END
    }
)

# Conditional routing: handle_nik_confirmation -> check_resident or END
graph.add_conditional_edges(
    "handle_nik_confirmation",
    should_route_after_nik_confirmation,
    {
        "check_resident": "check_resident",
        "end": END
    }
)

# Conditional routing: check_resident -> login_by_nik or END
graph.add_conditional_edges(
    "check_resident",
    should_route_after_check_resident,
    {
        "login_by_nik": "login_by_nik",
        "end": END
    }
)

# Conditional routing: login_by_nik -> END
graph.add_edge("login_by_nik", END)

# All nodes end at END
graph.add_edge("handle_ambiguity", END)

app = graph.compile()