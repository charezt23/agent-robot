# src/state_utils.py
"""
Helper utilities untuk preserve state fields secara otomatis.
Gunakan function ini untuk wrap return value dari node function.
"""
from typing import Dict, Any
from src.state import AgentState


def preserve_state(state: AgentState, updates: Dict[str, Any]) -> Dict[str, Any]:
    """
    Preserve semua field penting dari state yang tidak ada di updates.
    
    Args:
        state: Current state dari node
        updates: Field yang ingin di-update (hanya field yang diubah)
        
    Returns:
        Dict dengan updates + preserved fields dari state sebelumnya
        
    Contoh penggunaan:
        return preserve_state(state, {
            "auth_status": "needs_ktp",
            "messages": [AIMessage(content="...")]
        })
        # Field lain seperti intent, nik, dll akan otomatis di-preserve
    """
    # List semua field yang harus di-preserve jika tidak ada di updates
    important_fields = [
        # Intent fields
        "intent",
        "intent_confidence",
        "sub_intent",
        "sub_intent_confidence",
        "sub_intent_detail",
        "sub_intent_detail_confidence",
        "needs_confirmation",
        "confirmation_level",
        "intent_result",
        # Auth fields
        "nik",
        "is_authenticated",
        "auth_status",
        "extracted_nik",
        "extracted_data",
        "nik_confirmed",
        "resident_data",
        # Letter fields
        "letter_custom_data",
        "letter_status",
        "letter_data",
        "download_url_pdf",
        "letter_number",
        # Conversation fields
        "conversation_context",
        "pending_actions",
        "next_action",
        "user_message",
    ]
    
    # Preserve field yang tidak ada di updates
    preserved = {}
    for field in important_fields:
        if field not in updates and field in state:
            preserved[field] = state[field]
    
    # Merge preserved fields dengan updates (updates priority lebih tinggi)
    return {**preserved, **updates}

