import os
import json
import re
from typing import Tuple
from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from src.state import AgentState


# Initialize ChatOllama with model and base URL from environment
llm = ChatOllama(
    model="qwen3:8b",
    base_url=os.getenv("OLLAMA_BASE_URL", "http://192.168.18.115:11434")
)

# Intent classification prompt dengan multi-level classification
INTENT_CLASSIFICATION_PROMPT = """Anda adalah agent yang ahli dalam mengklasifikasikan intent dari pesan user.

Klasifikasikan intent dengan struktur hierarki berikut:

LEVEL 1: Intent Utama
- "Layanan" - jika user meminta layanan
- "Ngobrol" - jika user hanya ngobrol/chat biasa

LEVEL 2: Sub-Intent (hanya jika Level 1 = "Layanan")
- "Surat" - layanan surat (SKTM, SKDP, SKU, SPKTP)
- "Non-Surat" - layanan non-surat (BukuTamu)

LEVEL 3: Detail (hanya jika Level 2 = "Surat")
- "SKTM" - Surat Keterangan Tidak Mampu
- "SKDP" - Surat Keterangan Domisili Penduduk
- "SKU" - Surat Keterangan Usaha
- "SPKTP" - Surat Pengantar KTP

Contoh klasifikasi:
- "Saya butuh SKTM" → intent: "Layanan", sub_intent: "Surat", sub_intent_detail: "SKTM"
- "Mau buat surat keterangan tidak mampu" → intent: "Layanan", sub_intent: "Surat", sub_intent_detail: "SKTM"
- "Saya perlu surat domisili" → intent: "Layanan", sub_intent: "Surat", sub_intent_detail: "SKDP"
- "Saya mau isi buku tamu" → intent: "Layanan", sub_intent: "Non-Surat", sub_intent_detail: null
- "Saya butuh surat" → intent: "Layanan", sub_intent: "Surat", sub_intent_detail: null (ambiguous)
- "Halo" → intent: "Ngobrol", sub_intent: null, sub_intent_detail: null
- "Terima kasih" → intent: "Ngobrol", sub_intent: null, sub_intent_detail: null

Respon Anda HARUS dalam format JSON berikut:
{
    "intent": "Layanan" | "Ngobrol",
    "intent_confidence": 0.0-1.0,
    "sub_intent": "Surat" | "Non-Surat" | null,
    "sub_intent_confidence": 0.0-1.0 | null,
    "sub_intent_detail": "SKTM" | "SKDP" | "SKU" | "SPKTP" | null,
    "sub_intent_detail_confidence": 0.0-1.0 | null
}

Jika tidak bisa klasifikasi level tertentu, set null dan confidence rendah (< 0.7).
Berikan confidence yang akurat untuk setiap level."""


def extract_user_message(state: AgentState) -> str:
    """Extract user message from state (flexible: from user_message or messages)"""
    # Priority 1: dari user_message field
    if state.get("user_message"):
        return state["user_message"]
    
    # Priority 2: dari messages (ambil HumanMessage terakhir)
    messages = state.get("messages", [])
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            return msg.content if hasattr(msg, 'content') else str(msg)
    
    return ""


def parse_llm_response(response_text: str) -> dict:
    """Parse LLM response to extract JSON dengan struktur multi-level"""
    # Try to extract JSON from response (improved pattern untuk nested JSON)
    json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', response_text, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass
    
    # Fallback: try to parse entire response as JSON
    try:
        return json.loads(response_text.strip())
    except json.JSONDecodeError:
        pass
    
    # Last resort: return default
    return {
        "intent": "Ngobrol",
        "intent_confidence": 0.0,
        "sub_intent": None,
        "sub_intent_confidence": None,
        "sub_intent_detail": None,
        "sub_intent_detail_confidence": None
    }


def determine_confirmation_level(state: AgentState) -> Tuple[bool, str]:
    """
    Determine apakah perlu konfirmasi dan level mana yang perlu konfirmasi
    Sequential: cek Level 1 dulu, baru Level 2, baru Level 3
    """
    threshold = 0.7
    
    intent_conf = state.get("intent_confidence", 0.0)
    intent = state.get("intent")
    
    # Level 1: Cek intent dulu
    if intent_conf < threshold or intent is None:
        return (True, "intent")
    
    # Jika Level 1 jelas dan "Ngobrol", tidak perlu cek level lain
    if intent == "Ngobrol":
        return (False, None)
    
    # Level 2: Cek sub_intent (hanya jika intent = "Layanan")
    if intent == "Layanan":
        sub_intent_conf = state.get("sub_intent_confidence", 0.0)
        sub_intent = state.get("sub_intent")
        
        if sub_intent_conf < threshold or sub_intent is None:
            return (True, "sub_intent")
        
        # Level 3: Cek sub_intent_detail (hanya jika sub_intent = "Surat")
        if sub_intent == "Surat":
            detail_conf = state.get("sub_intent_detail_confidence", 0.0)
            detail = state.get("sub_intent_detail")
            
            if detail_conf < threshold or detail is None:
                return (True, "sub_intent_detail")
    
    # Semua level sudah jelas
    return (False, None)


def check_intent(state: AgentState) -> dict:
    """Check intent dari user message menggunakan LLM - multi-level classification"""
    user_message = extract_user_message(state)
    
    if not user_message:
        return {
            "intent": "Ngobrol",
            "intent_confidence": 0.0,
            "sub_intent": None,
            "sub_intent_confidence": None,
            "sub_intent_detail": None,
            "sub_intent_detail_confidence": None,
            "intent_result": {
                "intent": "Ngobrol",
                "intent_confidence": 0.0
            },
            "needs_confirmation": False,
            "confirmation_level": None
        }
    
    # Prepare messages untuk LLM
    messages = [
        SystemMessage(content=INTENT_CLASSIFICATION_PROMPT),
        HumanMessage(content=f"Pesan user: {user_message}\n\nKlasifikasikan intent dari pesan ini dengan struktur hierarki.")
    ]
    
    # Invoke LLM
    response = llm.invoke(messages)
    response_text = response.content if hasattr(response, 'content') else str(response)
    
    # Parse response
    result = parse_llm_response(response_text)
    
    # Extract values dengan default
    intent = result.get("intent", "Ngobrol")
    intent_conf = float(result.get("intent_confidence", 0.0))
    sub_intent = result.get("sub_intent")
    sub_intent_conf = float(result.get("sub_intent_confidence", 0.0)) if result.get("sub_intent_confidence") is not None else None
    sub_intent_detail = result.get("sub_intent_detail")
    detail_conf = float(result.get("sub_intent_detail_confidence", 0.0)) if result.get("sub_intent_detail_confidence") is not None else None
    
    # Determine confirmation level (sequential check)
    needs_confirmation, confirmation_level = determine_confirmation_level({
        "intent": intent,
        "intent_confidence": intent_conf,
        "sub_intent": sub_intent,
        "sub_intent_confidence": sub_intent_conf,
        "sub_intent_detail": sub_intent_detail,
        "sub_intent_detail_confidence": detail_conf
    })
    
    # Calculate overall confidence (minimum dari semua level yang ada)
    confidences = [intent_conf]
    if sub_intent_conf is not None:
        confidences.append(sub_intent_conf)
    if detail_conf is not None:
        confidences.append(detail_conf)
    overall_confidence = min(confidences) if confidences else 0.0
    
    # Prepare intent_result JSON
    intent_result = {
        "intent": intent,
        "intent_confidence": round(intent_conf, 2),
        "sub_intent": sub_intent,
        "sub_intent_confidence": round(sub_intent_conf, 2) if sub_intent_conf is not None else None,
        "sub_intent_detail": sub_intent_detail,
        "sub_intent_detail_confidence": round(detail_conf, 2) if detail_conf is not None else None,
        "confidence": round(overall_confidence, 2)  # Overall confidence
    }
    
    return {
        "user_message": user_message,
        "intent": intent,
        "intent_confidence": intent_conf,
        "sub_intent": sub_intent,
        "sub_intent_confidence": sub_intent_conf,
        "sub_intent_detail": sub_intent_detail,
        "sub_intent_detail_confidence": detail_conf,
        "needs_confirmation": needs_confirmation,
        "confirmation_level": confirmation_level,
        "intent_result": intent_result
    }


def handle_ambiguity(state: AgentState) -> dict:
    """Handle ambiguous intent dengan meminta konfirmasi ke user - berbeda per level"""
    confirmation_level = state.get("confirmation_level")
    intent = state.get("intent", "Ngobrol")
    intent_conf = state.get("intent_confidence", 0.0)
    sub_intent = state.get("sub_intent")
    sub_intent_conf = state.get("sub_intent_confidence", 0.0)
    sub_intent_detail = state.get("sub_intent_detail")
    
    confirmation_message = ""
    
    # Level 1: Konfirmasi Layanan vs Ngobrol
    if confirmation_level == "intent":
        confirmation_message = """Saya tidak yakin apakah pesan Anda terkait dengan layanan atau hanya ngobrol.

Apakah Anda ingin:
- **Layanan** - jika Anda membutuhkan salah satu layanan (surat atau non-surat)
- **Ngobrol** - jika Anda hanya ingin ngobrol/chat biasa

Silakan balas dengan "Layanan" atau "Ngobrol"."""
    
    # Level 2: Konfirmasi Surat vs Non-Surat
    elif confirmation_level == "sub_intent":
        confirmation_message = """Saya mengerti Anda membutuhkan layanan. Namun, saya tidak yakin jenis layanan yang Anda inginkan.

Apakah Anda ingin:
- **Surat** - layanan surat (SKTM, SKDP, SKU, SPKTP)
- **Non-Surat** - layanan non-surat (BukuTamu)

Silakan balas dengan "Surat" atau "Non-Surat"."""
    
    # Level 3: Konfirmasi detail surat
    elif confirmation_level == "sub_intent_detail":
        confirmation_message = """Saya mengerti Anda membutuhkan layanan surat. Namun, saya tidak yakin surat apa yang Anda butuhkan.

Surat apa yang Anda inginkan?
- **SKTM** - Surat Keterangan Tidak Mampu
- **SKDP** - Surat Keterangan Domisili Penduduk
- **SKU** - Surat Keterangan Usaha
- **SPKTP** - Surat Pengantar KTP

Silakan balas dengan nama surat yang Anda inginkan (SKTM, SKDP, SKU, atau SPKTP)."""
    
    # Fallback (shouldn't happen, but just in case)
    else:
        confirmation_message = "Maaf, saya tidak yakin dengan maksud Anda. Bisakah Anda jelaskan lebih detail?"
    
    return {
        "messages": [AIMessage(content=confirmation_message)],
        "needs_confirmation": True
    }


def should_confirm(state: AgentState) -> str:
    """Conditional function untuk routing: apakah perlu konfirmasi?"""
    needs_confirmation = state.get("needs_confirmation", False)
    return "confirm" if needs_confirmation else "finalize"


def finalize_intent(state: AgentState) -> dict:
    """Finalize intent result (tidak perlu konfirmasi)"""
    # Intent sudah jelas, tidak perlu response message
    return {
        "needs_confirmation": False
    }
