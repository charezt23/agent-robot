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
    surat_auth_flow,
    should_trigger_auth
)

# Graph terintegrasi (BENAR)
# Graph terintegrasi (BENAR)
graph = StateGraph(AgentState)

# Intent classification nodes
graph.add_node("check_intent", check_intent)
graph.add_node("handle_ambiguity", handle_ambiguity)
graph.add_node("finalize_intent", finalize_intent)
graph.add_node("surat_auth_flow", surat_auth_flow)  # ← Tambahkan node ini

# Flow: START -> check_intent
graph.add_edge(START, "check_intent")

# Conditional routing: check_intent -> handle_ambiguity or finalize_intent
graph.add_conditional_edges(
    "check_intent",
    should_confirm,
    {
        "confirm": "handle_ambiguity",
        "finalize": "finalize_intent"
    }
)

# Conditional routing: finalize_intent -> surat_auth_flow (if trigger) or END
graph.add_conditional_edges(
    "finalize_intent",
    should_trigger_auth,  # ← Gunakan function ini
    {
        "auth_flow": "surat_auth_flow",
        "end": END
    }
)

# All nodes end at END
graph.add_edge("handle_ambiguity", END)
graph.add_edge("surat_auth_flow", END)

app = graph.compile()
