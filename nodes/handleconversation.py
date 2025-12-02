import os
import logging
from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from src.state import AgentState

# Setup logging (console only)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Initialize ChatOllama with model and base URL from environment
llm = ChatOllama(
    model="qwen3:8b",
    base_url=os.getenv("OLLAMA_BASE_URL", "http://192.168.18.115:11434")
)

# System prompts untuk conversation handling
CHITCHAT_PROMPT = """Anda adalah asisten yang ramah dan membantu di kantor kelurahan.
User sedang ngobrol dengan Anda. Berikan respon yang natural, ramah, dan sopan.
Jangan terlalu formal, tapi tetap profesional.
Jika user bertanya tentang layanan, arahkan mereka untuk menyebutkan layanan yang diinginkan."""

GREETING_PROMPT = """Anda adalah asisten yang ramah di kantor kelurahan.
User sedang menyapa Anda. Berikan respon sapaan yang hangat, ramah, dan sopan.
Sambut mereka dengan baik dan tanyakan bagaimana Anda bisa membantu hari ini.
Respon harus singkat (1-2 kalimat)."""

FAREWELL_PROMPT = """Anda adalah asisten yang ramah di kantor kelurahan.
User sedang mengucapkan selamat tinggal atau terima kasih.
Berikan respon yang hangat dan sopan, ucapkan terima kasih kembali.
Respon harus singkat (1-2 kalimat)."""

CONVERSATION_TYPE_DETECTION_PROMPT = """Tentukan tipe percakapan dari pesan user:
1. "greeting" - jika user menyapa (halo, selamat pagi, dll)
2. "farewell" - jika user mengucapkan selamat tinggal atau terima kasih
3. "chitchat" - jika user sedang ngobrol biasa

Respon HANYA dengan satu kata: "greeting", "farewell", atau "chitchat"."""

# Fallback templates
FALLBACK_CHITCHAT = "Maaf, saya tidak yakin bagaimana merespons. Ada yang bisa saya bantu hari ini?"
FALLBACK_GREETING = "Halo! Selamat datang. Ada yang bisa saya bantu hari ini?"
FALLBACK_FAREWELL = "Terima kasih! Semoga hari Anda menyenangkan. Sampai jumpa!"


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


def get_recent_messages(state: AgentState, limit: int = 5) -> list:
    """Get recent messages untuk context (ambil 3-5 messages terakhir)"""
    messages = state.get("messages", [])
    return messages[-limit:] if len(messages) > limit else messages


def detect_conversation_type(user_message: str) -> str:
    """Detect conversation type (greeting, farewell, chitchat) menggunakan LLM"""
    try:
        messages = [
            SystemMessage(content=CONVERSATION_TYPE_DETECTION_PROMPT),
            HumanMessage(content=f"Pesan user: {user_message}\n\nTentukan tipe percakapan.")
        ]
        
        response = llm.invoke(messages)
        response_text = response.content if hasattr(response, 'content') else str(response)
        response_text = response_text.strip().lower()
        
        if "greeting" in response_text:
            return "greeting"
        elif "farewell" in response_text:
            return "farewell"
        else:
            return "chitchat"
    except Exception as e:
        logger.error(f"Error detecting conversation type: {e}", exc_info=True)
        # Fallback: simple pattern matching
        user_lower = user_message.lower()
        greeting_words = ["halo", "hai", "selamat pagi", "selamat siang", "selamat sore", "selamat malam"]
        farewell_words = ["terima kasih", "makasih", "sampai jumpa", "bye", "dadah", "selamat tinggal"]
        
        if any(word in user_lower for word in greeting_words):
            return "greeting"
        elif any(word in user_lower for word in farewell_words):
            return "farewell"
        else:
            return "chitchat"


def handle_chitchat(state: AgentState) -> dict:
    """Handle chitchat conversation dengan LLM-based response"""
    try:
        user_message = extract_user_message(state)
        recent_messages = get_recent_messages(state, limit=5)
        
        if not user_message:
            logger.warning("No user message found in state for chitchat")
            return {
                "messages": [AIMessage(content=FALLBACK_CHITCHAT)],
                "conversation_context": {"last_type": "chitchat", "error": "no_message"}
            }
        
        # Prepare messages untuk LLM
        llm_messages = [SystemMessage(content=CHITCHAT_PROMPT)]
        
        # Add recent messages untuk context (max 5)
        for msg in recent_messages[-5:]:
            llm_messages.append(msg)
        
        # Add current user message
        llm_messages.append(HumanMessage(content=user_message))
        
        # Invoke LLM
        response = llm.invoke(llm_messages)
        response_text = response.content if hasattr(response, 'content') else str(response)
        
        logger.info(f"Chitchat response generated for message: {user_message[:50]}...")
        
        return {
            "messages": [AIMessage(content=response_text)],
            "conversation_context": {
                "last_type": "chitchat",
                "user_message": user_message[:100]  # Store truncated for context
            }
        }
        
    except Exception as e:
        logger.error(f"Error in handle_chitchat: {e}", exc_info=True, extra={
            "user_message": extract_user_message(state),
            "state_keys": list(state.keys())
        })
        return {
            "messages": [AIMessage(content=FALLBACK_CHITCHAT)],
            "conversation_context": {"last_type": "chitchat", "error": str(e)}
        }


def handle_greeting(state: AgentState) -> dict:
    """Handle greeting dengan LLM-based response"""
    try:
        user_message = extract_user_message(state)
        recent_messages = get_recent_messages(state, limit=3)
        
        if not user_message:
            logger.warning("No user message found in state for greeting")
            return {
                "messages": [AIMessage(content=FALLBACK_GREETING)],
                "conversation_context": {"last_type": "greeting", "error": "no_message"}
            }
        
        # Prepare messages untuk LLM
        llm_messages = [SystemMessage(content=GREETING_PROMPT)]
        
        # Add recent messages untuk context (max 3 untuk greeting)
        for msg in recent_messages[-3:]:
            llm_messages.append(msg)
        
        # Add current user message
        llm_messages.append(HumanMessage(content=user_message))
        
        # Invoke LLM
        response = llm.invoke(llm_messages)
        response_text = response.content if hasattr(response, 'content') else str(response)
        
        logger.info(f"Greeting response generated for message: {user_message[:50]}...")
        
        return {
            "messages": [AIMessage(content=response_text)],
            "conversation_context": {
                "last_type": "greeting",
                "user_message": user_message[:100]
            }
        }
        
    except Exception as e:
        logger.error(f"Error in handle_greeting: {e}", exc_info=True, extra={
            "user_message": extract_user_message(state),
            "state_keys": list(state.keys())
        })
        return {
            "messages": [AIMessage(content=FALLBACK_GREETING)],
            "conversation_context": {"last_type": "greeting", "error": str(e)}
        }


def handle_farewell(state: AgentState) -> dict:
    """Handle farewell dengan LLM-based response"""
    try:
        user_message = extract_user_message(state)
        recent_messages = get_recent_messages(state, limit=3)
        
        if not user_message:
            logger.warning("No user message found in state for farewell")
            return {
                "messages": [AIMessage(content=FALLBACK_FAREWELL)],
                "conversation_context": {"last_type": "farewell", "error": "no_message"}
            }
        
        # Prepare messages untuk LLM
        llm_messages = [SystemMessage(content=FAREWELL_PROMPT)]
        
        # Add recent messages untuk context (max 3 untuk farewell)
        for msg in recent_messages[-3:]:
            llm_messages.append(msg)
        
        # Add current user message
        llm_messages.append(HumanMessage(content=user_message))
        
        # Invoke LLM
        response = llm.invoke(llm_messages)
        response_text = response.content if hasattr(response, 'content') else str(response)
        
        logger.info(f"Farewell response generated for message: {user_message[:50]}...")
        
        return {
            "messages": [AIMessage(content=response_text)],
            "conversation_context": {
                "last_type": "farewell",
                "user_message": user_message[:100]
            }
        }
        
    except Exception as e:
        logger.error(f"Error in handle_farewell: {e}", exc_info=True, extra={
            "user_message": extract_user_message(state),
            "state_keys": list(state.keys())
        })
        return {
            "messages": [AIMessage(content=FALLBACK_FAREWELL)],
            "conversation_context": {"last_type": "farewell", "error": str(e)}
        }


def route_conversation(state: AgentState) -> str:
    """Route conversation berdasarkan intent dan conversation type"""
    try:
        intent = state.get("intent", "Ngobrol")
        user_message = extract_user_message(state)
        
        # Jika intent adalah layanan, route ke process_layanan
        if intent in ["SKTM", "SKDP", "SKU", "BukuTamu", "SPKTP"]:
            logger.info(f"Routing to process_layanan for intent: {intent}")
            return "process_layanan"
        
        # Jika intent adalah Ngobrol, detect conversation type
        if intent == "Ngobrol" and user_message:
            conversation_type = detect_conversation_type(user_message)
            logger.info(f"Detected conversation type: {conversation_type} for message: {user_message[:50]}...")
            
            if conversation_type == "greeting":
                return "greeting"
            elif conversation_type == "farewell":
                return "farewell"
            else:
                return "chitchat"
        
        # Default: chitchat
        logger.info("Default routing to chitchat")
        return "chitchat"
        
    except Exception as e:
        logger.error(f"Error in route_conversation: {e}", exc_info=True, extra={
            "intent": state.get("intent"),
            "user_message": extract_user_message(state)
        })
        # Fallback: route ke chitchat
        return "chitchat"

