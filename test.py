# test.py - Interactive Graph Flow Testing
import sys
import os
import json
import httpx
from typing import List, Dict, Any
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.graph import app
from src.state import AgentState
from langchain_core.messages import HumanMessage, AIMessage

# ============================================================================
# KTP FILE PATH RESOLUTION
# ============================================================================
KTP_FILE = None
if os.path.exists("KTP Example.png"):
    KTP_FILE = os.path.abspath("KTP Example.png")
elif os.path.exists("/app/KTP Example.png"):
    KTP_FILE = "/app/KTP Example.png"
else:
    for root, dirs, files in os.walk("."):
        if "KTP Example.png" in files:
            KTP_FILE = os.path.abspath(os.path.join(root, "KTP Example.png"))
            break

if not KTP_FILE:
    print("❌ ERROR: KTP Example.png tidak ditemukan!")
    sys.exit(1)

print(f"✅ KTP File: {KTP_FILE}\n")

# ============================================================================
# HTTP REQUEST/RESPONSE TRACKING
# ============================================================================
api_calls: List[Dict[str, Any]] = []

# Enable httpx logging untuk track API calls
import logging
logging.basicConfig(level=logging.INFO)
httpx_logger = logging.getLogger("httpx")
httpx_logger.setLevel(logging.DEBUG)

# ============================================================================
# PRINTING FUNCTIONS
# ============================================================================
def print_separator(title="", char="=", width=100):
    """Print separator dengan title"""
    if title:
        print("\n" + char * width)
        print(f"  {title}")
        print(char * width)
    else:
        print(char * width)

def print_state_complete(state: AgentState, title: str = "STATE"):
    """Print SEMUA state fields dengan lengkap"""
    print(f"\n📊 {title}:")
    print(f"  {'═' * 98}")
    
    # === AUTHENTICATION & VALIDATION ===
    print(f"  🔐 AUTHENTICATION & VALIDATION:")
    print(f"     auth_status: {state.get('auth_status')}")
    print(f"     is_authenticated: {state.get('is_authenticated')}")
    print(f"     nik: {state.get('nik')}")
    print(f"     extracted_nik: {state.get('extracted_nik')}")
    print(f"     nik_confirmed: {state.get('nik_confirmed')}")
    print(f"     ktp_image: {state.get('ktp_image')}")
    print(f"     extracted_data: {state.get('extracted_data')}")
    print(f"     resident_data: {state.get('resident_data')}")
    
    # === INTENT CLASSIFICATION ===
    print(f"  🎯 INTENT CLASSIFICATION:")
    print(f"     intent: {state.get('intent')}")
    print(f"     intent_confidence: {state.get('intent_confidence')}")
    print(f"     sub_intent: {state.get('sub_intent')}")
    print(f"     sub_intent_confidence: {state.get('sub_intent_confidence')}")
    print(f"     sub_intent_detail: {state.get('sub_intent_detail')}")
    print(f"     sub_intent_detail_confidence: {state.get('sub_intent_detail_confidence')}")
    print(f"     needs_confirmation: {state.get('needs_confirmation')}")
    print(f"     confirmation_level: {state.get('confirmation_level')}")
    if state.get('intent_result'):
        print(f"     intent_result: {json.dumps(state.get('intent_result'), indent=8, ensure_ascii=False)}")
    
    # === CONVERSATION ===
    print(f"  💬 CONVERSATION:")
    print(f"     user_message: {state.get('user_message')}")
    print(f"     conversation_context: {state.get('conversation_context')}")
    print(f"     pending_actions: {state.get('pending_actions')}")
    
    # === LETTER PROCESSING ===
    print(f"  📄 LETTER PROCESSING:")
    print(f"     letter_status: {state.get('letter_status')}")
    if state.get('letter_custom_data'):
        print(f"     letter_custom_data: {json.dumps(state.get('letter_custom_data'), indent=8, ensure_ascii=False)}")
    if state.get('letter_data'):
        print(f"     letter_data: {json.dumps(state.get('letter_data'), indent=8, ensure_ascii=False)}")
    print(f"     letter_number: {state.get('letter_number')}")
    print(f"     download_url_pdf: {state.get('download_url_pdf')}")
    
    # === FLOW CONTROL ===
    print(f"  🔄 FLOW CONTROL:")
    print(f"     next_action: {state.get('next_action')}")
    
    print(f"  {'═' * 98}")

def print_conversation_history(state: AgentState, title: str = "RIWAYAT PERCAKAPAN"):
    """Print riwayat percakapan lengkap (USER & AI)"""
    print(f"\n💬 {title}:")
    print(f"  {'═' * 98}")
    
    messages = state.get('messages', [])
    if not messages:
        print("  (Belum ada percakapan)")
        return
    
    for i, msg in enumerate(messages, 1):
        if isinstance(msg, HumanMessage):
            role = "👤 USER"
            content = msg.content if hasattr(msg, 'content') else str(msg)
        elif isinstance(msg, AIMessage):
            role = "🤖 AI"
            content = msg.content if hasattr(msg, 'content') else str(msg)
        else:
            role = "❓ UNKNOWN"
            content = str(msg)
        
        print(f"  {i}. {role}:")
        print(f"     {content}")
        print()

def print_node_execution(node_name: str, node_state: AgentState, step_num: int):
    """Print detail lengkap node execution"""
    print(f"\n  🔄 STEP {step_num}: NODE '{node_name}'")
    print(f"     {'─' * 94}")
    print_state_complete(node_state, f"NODE STATE: {node_name}")
    
    # Print latest message if any
    messages = node_state.get('messages', [])
    if messages:
        latest_msg = messages[-1]
        msg_type = "👤 USER" if isinstance(latest_msg, HumanMessage) else "🤖 AI"
        content = latest_msg.content if hasattr(latest_msg, 'content') else str(latest_msg)
        print(f"\n     📝 LATEST MESSAGE ({msg_type}):")
        print(f"        {content}")
    
    print(f"     {'─' * 94}")

# ============================================================================
# INTERACTIVE TEST FUNCTION
# ============================================================================
def interactive_test():
    """Interactive test - user ketik manual, script print semua info"""
    
    print_separator("🧪 INTERACTIVE GRAPH FLOW TESTING", "=", 100)
    print("\n📝 INSTRUKSI:")
    print("  - Ketik pesan user (contoh: 'hei, bisa buatin sktm?')")
    print("  - Untuk upload KTP, ketik: 'upload_ktp'")
    print("  - Ketik 'exit' atau 'quit' untuk keluar")
    print("  - Ketik 'clear' untuk reset state")
    print()
    
    # Initialize state
    current_state: AgentState = {
        "messages": [],
        "user_message": None,
        "intent": None,
        "intent_confidence": None,
        "sub_intent": None,
        "sub_intent_confidence": None,
        "sub_intent_detail": None,
        "sub_intent_detail_confidence": None,
        "is_authenticated": None,
        "auth_status": None,
        "ktp_image": None,
        "extracted_nik": None,
        "nik": None,
        "nik_confirmed": None,
        "needs_confirmation": None,
        "confirmation_level": None,
        "intent_result": None,
        "conversation_context": None,
        "pending_actions": None,
        "extracted_data": None,
        "resident_data": None,
        "letter_custom_data": None,
        "letter_status": None,
        "letter_data": None,
        "download_url_pdf": None,
        "letter_number": None,
        "next_action": None
    }
    
    step_counter = 0
    
    while True:
        try:
            # Get user input
            print("\n" + "─" * 100)
            user_input = input("\n👤 USER: ").strip()
            
            if not user_input:
                continue
            
            if user_input.lower() in ['exit', 'quit', 'q']:
                print("\n👋 Keluar dari test...")
                break
            
            if user_input.lower() == 'clear':
                current_state = {
                    "messages": [],
                    "user_message": None,
                    "intent": None,
                    "intent_confidence": None,
                    "sub_intent": None,
                    "sub_intent_confidence": None,
                    "sub_intent_detail": None,
                    "sub_intent_detail_confidence": None,
                    "is_authenticated": None,
                    "auth_status": None,
                    "ktp_image": None,
                    "extracted_nik": None,
                    "nik": None,
                    "nik_confirmed": None,
                    "needs_confirmation": None,
                    "confirmation_level": None,
                    "intent_result": None,
                    "conversation_context": None,
                    "pending_actions": None,
                    "extracted_data": None,
                    "resident_data": None,
                    "letter_custom_data": None,
                    "letter_status": None,
                    "letter_data": None,
                    "download_url_pdf": None,
                    "letter_number": None,
                    "next_action": None
                }
                step_counter = 0
                print("✅ State di-reset!")
                continue
            
            # Handle upload KTP
            if user_input.lower() == 'upload_ktp':
                current_state["ktp_image"] = KTP_FILE
                current_state["user_message"] = "KTP berhasil diupload"
                current_state["messages"] = current_state.get("messages", []) + [HumanMessage(content="KTP berhasil diupload")]
                print(f"✅ KTP file di-set: {KTP_FILE}")
            else:
                # Normal message
                current_state["user_message"] = user_input
                current_state["messages"] = current_state.get("messages", []) + [HumanMessage(content=user_input)]
            
            # Print initial state
            print_separator(f"EXECUTING GRAPH (Step {step_counter + 1})", "-", 100)
            print_state_complete(current_state, "INPUT STATE")
            
            # Execute graph
            print("\n🔄 EXECUTING GRAPH...")
            states = []
            try:
                for state in app.stream(current_state):
                    states.append(state)
                    for node_name, node_state in state.items():
                        print_node_execution(node_name, node_state, len(states))
                
                # Get final state
                final_state = states[-1][list(states[-1].keys())[0]] if states else None
                
                if final_state:
                    # Update current state dengan final state
                    current_state.update(final_state)
                    
                    # Print final state
                    print_separator("FINAL STATE", "-", 100)
                    print_state_complete(final_state, "FINAL STATE")
                    
                    # Print conversation history
                    print_conversation_history(final_state, "RIWAYAT PERCAKAPAN")
                    
                    # Print AI response (latest AI message)
                    messages = final_state.get('messages', [])
                    ai_messages = [msg for msg in messages if isinstance(msg, AIMessage)]
                    if ai_messages:
                        latest_ai = ai_messages[-1]
                        content = latest_ai.content if hasattr(latest_ai, 'content') else str(latest_ai)
                        print(f"\n🤖 AI: {content}\n")
                    
                    step_counter += 1
                else:
                    print("\n⚠️  Tidak ada final state yang dihasilkan")
                    
            except Exception as e:
                print(f"\n❌ ERROR: {type(e).__name__}: {e}")
                import traceback
                traceback.print_exc()
                
        except KeyboardInterrupt:
            print("\n\n👋 Keluar dari test...")
            break
        except EOFError:
            print("\n\n👋 Keluar dari test...")
            break
    
    print_separator("TEST COMPLETED", "=", 100)

if __name__ == "__main__":
    interactive_test()