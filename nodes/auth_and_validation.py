import os
import httpx
from typing import Optional
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from src.state import AgentState
from langchain_ollama import ChatOllama

# Backend API URL dari environment variable
BACKEND_API_URL = os.getenv("BACKEND_API_URL", "http://localhost:8001/api")

# Timeout untuk HTTP requests
HTTP_TIMEOUT = 30.0
llm = ChatOllama(
    model="qwen3:8b",
    base_url=os.getenv("OLLAMA_BASE_URL", "http://192.168.18.115:11434")
)


def extract_user_message(state: AgentState) -> str:
    """Extract user message from state"""
    if state.get("user_message"):
        return state["user_message"]
    
    messages = state.get("messages", [])
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            return msg.content if hasattr(msg, 'content') else str(msg)
        elif hasattr(msg, 'content'):
            return msg.content if isinstance(msg.content, str) else str(msg)
    
    return ""


def check_token_valid() -> bool:
    """Check if token is valid via API"""
    try:
        with httpx.Client(timeout=HTTP_TIMEOUT) as client:
            response = client.get(
                f"{BACKEND_API_URL}/check-token",
            )
            if response.status_code == 200:
                data = response.json()
                return data.get("success", False) and data.get("data", {}).get("valid", False)
    except Exception as e:
        return False

def login_by_nik(nik: str) -> bool:
    """Login using NIK, return True if successful, False if failed"""
    try:
        with httpx.Client(timeout=HTTP_TIMEOUT) as client:
            response = client.post(
                f"{BACKEND_API_URL}/login-by-nik",
                json={"nik": nik}
            )
            if response.status_code == 200:
                data = response.json()
                if data.get("success", False):
                    return True  # Login berhasil
            return False  # Login gagal
    except Exception as e:
        return False

def upload_ktp_for_ocr(ktp_image_path: str) -> Optional[dict]:
    """Upload KTP image for OCR processing
    
    Returns:
        dict: {"nik": "..."} if successful, None if failed
    """
    try:
        with httpx.Client(timeout=HTTP_TIMEOUT * 2) as client:  # OCR might take longer
            with open(ktp_image_path, "rb") as f:
                files = {"ktpImage": (os.path.basename(ktp_image_path), f, "image/jpeg")}
                response = client.post(
                    f"{BACKEND_API_URL}/upload-ktp",
                    files=files
                )
                if response.status_code == 200:
                    data = response.json()
                    if data.get("success", False):
                        return {
                            "nik": data.get("data", {}).get("nik")
                        }
    except FileNotFoundError:
        return None
    except Exception as e:
        return None


def check_resident(nik: str) -> bool:
    """Check if resident exists in database via API
    
    Returns:
        True: if API response success == true
        False: if API response success != true or error occurred
    """
    try:
        with httpx.Client(timeout=HTTP_TIMEOUT) as client:
            response = client.get(f"{BACKEND_API_URL}/resident/{nik}")
            if response.status_code == 200:
                data = response.json()
                if data.get("success", False):
                    return True
            return False
    except Exception as e:
        return False


def surat_auth_flow(state: AgentState) -> dict:
    """
    Auth flow untuk surat (SKTM, SKDP, SKU)
    Flow: check_token → upload_ktp → check_resident → login_by_nik
    """
    sub_intent = state.get("sub_intent")
    sub_intent_detail = state.get("sub_intent_detail")
    
    # Trigger: sub_intent == "Surat" AND sub_intent_detail in ["SKTM", "SKDP", "SKU"]
    if sub_intent != "Surat":
        return {"auth_status": "skipped"}
    
    if sub_intent_detail not in ["SKTM", "SKDP", "SKU"]:
        return {"auth_status": "skipped"}
    
    # Step 1: Check token
    token_valid = check_token_valid()
    
    if token_valid:
        return {
            "is_authenticated": True,
            "auth_status": "authenticated",
            "next_action": "surat_processing"
        }
    
    # Step 2: Upload KTP (jika token invalid)
    ktp_image = state.get("ktp_image")
    
    if not ktp_image:
        message = generate_auth_message("token_invalid")
        return {
            "messages": [AIMessage(content=message)],
            "auth_status": "needs_ktp"
        }
    
    # Process OCR
    ocr_result = upload_ktp_for_ocr(ktp_image)
    
    if not ocr_result or not ocr_result.get("nik"):
        message = generate_auth_message("ocr_failed")
        return {
            "messages": [AIMessage(content=message)],
            "auth_status": "failed"
        }
    
    extracted_nik = ocr_result["nik"]
    
    # Step 3: Check resident
    resident_exists = check_resident(extracted_nik)
    
    if not resident_exists:
        message = generate_auth_message("resident_not_found")
        return {
            "messages": [AIMessage(content=message)],
            "auth_status": "failed"
        }
    
    # Step 4: Login by NIK
    login_success = login_by_nik(extracted_nik)
    
    if login_success:
        message = generate_auth_message("auth_success", {"nik": extracted_nik})
        return {
            "nik": extracted_nik,
            "is_authenticated": True,
            "auth_status": "authenticated",
            "next_action": "surat_processing",
            "messages": [AIMessage(content=message)]
        }
    else:
        return {
            "messages": [AIMessage(
                content="Maaf, terjadi kesalahan saat melakukan autentikasi."
            )],
            "auth_status": "failed"
        }

def should_trigger_auth(state: AgentState) -> str:
    """Check if should trigger auth flow"""
    sub_intent = state.get("sub_intent")
    sub_intent_detail = state.get("sub_intent_detail")
    
    if sub_intent == "Surat" and sub_intent_detail in ["SKTM", "SKDP", "SKU"]:
        return "auth_flow"
    return "end"


def generate_auth_message(context: str, data: dict = None) -> str:
    """
    Generate response message menggunakan LLM berdasarkan context
    
    Args:
        context: Context message (e.g., "token_invalid", "ocr_success", "auth_success")
        data: Additional data (e.g., {"nik": "..."})
    
    Returns:
        str: Generated message from LLM
    """
    system_prompt = """Anda adalah asisten yang ramah di kantor kelurahan.
Berikan respon yang natural, ramah, dan profesional dalam bahasa Indonesia.
Jangan terlalu formal, tapi tetap sopan."""
    data = data or {}
    context_prompts = {
        "token_invalid": "User perlu upload KTP untuk autentikasi. Berikan pesan yang ramah meminta upload KTP.",
        "ocr_success": f"OCR berhasil membaca KTP. NIK yang terdeteksi: {data.get('nik', 'N/A')}. Minta konfirmasi dari user apakah NIK sudah benar.",
        "ocr_failed": "OCR gagal membaca KTP. Minta user upload ulang dengan pesan yang ramah.",
        "resident_not_found": "NIK tidak terdaftar di sistem. Berikan pesan yang ramah dan informatif.",
        "auth_success": "Autentikasi berhasil. Berikan pesan sukses yang ramah dan informatif bahwa user sudah bisa membuat surat.",
        "auth_failed": "Autentikasi gagal. Berikan pesan yang ramah dan informatif."
    }
    
    user_prompt = context_prompts.get(context, "Berikan respon yang sesuai.")
    
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt)
    ]
    
    try:
        response = llm.invoke(messages)
        return response.content if hasattr(response, 'content') else str(response)
    except Exception as e:
        # Fallback ke hardcoded message jika LLM error
        fallback_messages = {
            "token_invalid": "Token tidak valid. Silakan upload foto KTP Anda untuk autentikasi.",
            "ocr_success": f"Terima kasih, saya sedang memproses KTP Anda...\n\nNIK yang terdeteksi: {data.get('nik', 'N/A')}\n\nApakah NIK ini sudah benar?",
            "ocr_failed": "Maaf, saya tidak dapat membaca KTP Anda. Silakan upload ulang.",
            "resident_not_found": "Maaf, NIK Anda belum terdaftar di sistem kami.",
            "auth_success": "✅ Autentikasi berhasil! Sekarang saya bisa membantu Anda membuat surat.",
            "auth_failed": "Maaf, terjadi kesalahan saat melakukan autentikasi."
        }
        return fallback_messages.get(context, "Terjadi kesalahan.")