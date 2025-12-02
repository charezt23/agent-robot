import logging
from langchain_core.messages import AIMessage
from src.state import AgentState

# Setup logging (console only)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)


def process_layanan(state: AgentState) -> dict:
    """
    Process layanan request
    Routes to auth if needed, or directly to surat processing
    """
    try:
        intent = state.get("intent", "Unknown")
        user_message = state.get("user_message", "")
        
        logger.info(f"Processing layanan request: {intent} for message: {user_message[:50] if user_message else 'N/A'}...")
        
        # Determine if auth is needed
        NEEDS_AUTH = ["SKTM", "SKDP", "SKU", "SPKTP"]
        NO_AUTH = ["BukuTamu"]
        
        if intent in NO_AUTH:
            # Skip auth, go directly to surat processing
            logger.info(f"Intent {intent} does not require auth")
            return {
                "next_action": "surat_processing",
                "pending_actions": []
            }
        
        if intent in NEEDS_AUTH:
            # Need auth, route to auth_and_validation
            logger.info(f"Intent {intent} requires auth, routing to auth flow")
            return {
                "next_action": "auth_required",
                "pending_actions": []
            }
        
        # Unknown intent or not a service
        response_message = f"Layanan {intent} belum diimplementasikan. Fitur ini sedang dalam pengembangan."
        
        return {
            "messages": [AIMessage(content=response_message)],
            "pending_actions": [],
            "next_action": "end"
        }
        
    except Exception as e:
        logger.error(f"Error in process_layanan: {e}", exc_info=True, extra={
            "intent": state.get("intent"),
            "user_message": state.get("user_message")
        })
        
        return {
            "messages": [AIMessage(content="Maaf, terjadi kesalahan saat memproses layanan. Silakan coba lagi.")],
            "pending_actions": [],
            "next_action": "end"
        }

