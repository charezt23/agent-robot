import os
import json
import httpx
from typing import Optional, Dict, Any
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from src.state import AgentState
from langchain_ollama import ChatOllama
from nodes.auth_and_validation import extract_user_message

BACKEND_API_URL = os.getenv("BACKEND_API_URL", "http://localhost:8001/api")

HTTP_TIMEOUT = 30.0

llm = ChatOllama(
    model="qwen3:8b",
    base_url=os.getenv("OLLAMA_BASE_URL", "http://192.168.18.115:11434")
)


def create_letter_via_api(letter_type_id: int, custom_data: Dict[str, Any]) -> Optional[dict]:
    """
    Create letter via API
    
    Args:
        letter_type_id: 1 for SKTM, 3 for SKDP, 4 for SKU
        custom_data: Custom data sesuai jenis surat
    
    Returns:
        dict: Response dari API jika berhasil, None jika gagal
    """
    try:
        with httpx.Client(timeout=HTTP_TIMEOUT) as client:
            response = client.post(
                f"{BACKEND_API_URL}/create-letter",
                json={
                    "letter_type_id": letter_type_id,
                    "custom_data": custom_data
                }
            )
            if response.status_code == 200:
                data = response.json()
                if data.get("success", False):
                    return data.get("data", {})
            return None
    except Exception as e:
        return None


def extract_custom_data_from_message(user_message: str, sub_intent_detail: str) -> Dict[str, Any]:
    """
    Extract custom_data dari user message menggunakan LLM
    
    Args:
        user_message: User message
        sub_intent_detail: "SKTM", "SKDP", atau "SKU"
    
    Returns:
        dict: Custom data yang sudah di-extract
    """
    system_prompt = """Anda adalah asisten yang membantu mengekstrak informasi dari pesan user untuk membuat surat.
Ekstrak informasi yang relevan dan kembalikan dalam format JSON yang sesuai.

Untuk SKTM dan SKDP, ekstrak:
- keterangan: keterangan untuk surat (contoh: "Beasiswa Anak", "Kuliah", "KTP", dll)

Untuk SKU, ekstrak:
- nama_usaha: nama usaha
- jenis_usaha: jenis usaha (contoh: "Perdagangan", "Jasa", "Makanan", dll)
- lokasi_usaha: alamat lokasi usaha

Jika informasi tidak lengkap tanyakan ke user.
Kembalikan HANYA JSON, tanpa penjelasan tambahan."""

    if sub_intent_detail == "SKU":
        user_prompt = f"""Dari pesan berikut, ekstrak informasi untuk membuat SKU:
"{user_message}"

Kembalikan JSON dengan format:
{{
    "nama_usaha": "...",
    "jenis_usaha": "...",
    "lokasi_usaha": "..."
}}"""
    else:  # SKTM atau SKDP
        user_prompt = f"""Dari pesan berikut, ekstrak informasi untuk membuat {sub_intent_detail}:
"{user_message}"

Kembalikan JSON dengan format:
{{
    "keterangan": "..."
}}"""

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt)
    ]

    try:
        response = llm.invoke(messages)
        content = response.content if hasattr(response, 'content') else str(response)
        
        # Parse JSON dari response
        # Coba extract JSON dari response
        content = content.strip()
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()
        
        custom_data = json.loads(content)
        return custom_data
    except Exception as e:
        return None


def generate_letter_message(context: str, data: dict = None) -> str:
    """
    Generate response message menggunakan LLM berdasarkan context
    
    Args:
        context: Context message (e.g., "letter_success", "letter_failed", "needs_data")
        data: Additional data (e.g., {"letter_number": "...", "download_url": "..."})
    
    Returns:
        str: Generated message from LLM
    """
    system_prompt = """Anda adalah asisten yang ramah di kantor kelurahan.
Berikan respon yang natural, ramah, dan profesional dalam bahasa Indonesia.
Jangan terlalu formal, tapi tetap sopan."""
    
    data = data or {}
    letter_type = data.get('letter_type', 'surat')
    missing_fields = data.get('missing_fields', [])
    
    # Build prompt untuk needs_data berdasarkan missing fields
    if missing_fields:
        if letter_type == "SKU":
            field_names = {
                "nama_usaha": "nama usaha",
                "jenis_usaha": "jenis usaha",
                "lokasi_usaha": "lokasi/alamat usaha"
            }
            missing_names = [field_names.get(f, f) for f in missing_fields]
            needs_data_prompt = f"Untuk membuat {letter_type}, saya perlu informasi berikut: {', '.join(missing_names)}. Berikan pesan yang ramah meminta informasi tersebut."
        else:
            needs_data_prompt = f"Untuk membuat {letter_type}, saya perlu keterangan/alasan surat. Berikan pesan yang ramah meminta keterangan tersebut."
    else:
        needs_data_prompt = f"Perlu informasi tambahan untuk membuat {letter_type}. Berikan pesan yang ramah meminta informasi yang diperlukan."
    
    context_prompts = {
        "letter_success": f"Surat berhasil dibuat! Nomor surat: {data.get('letter_number', 'N/A')}. Berikan pesan sukses yang ramah dan informatif, termasuk informasi tentang download URL jika tersedia.",
        "letter_failed": "Gagal membuat surat. Berikan pesan yang ramah dan informatif, minta user untuk mencoba lagi atau hubungi admin.",
        "needs_data": needs_data_prompt,
        "needs_auth": "User perlu melakukan autentikasi terlebih dahulu sebelum membuat surat. Berikan pesan yang ramah meminta user untuk melakukan autentikasi.",
        "invalid_letter_type": "Jenis surat tidak valid. Berikan pesan yang ramah dan informatif."
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
        # Build fallback message untuk needs_data
        letter_type = data.get('letter_type', 'surat')
        missing_fields = data.get('missing_fields', [])
        if missing_fields and letter_type == "SKU":
            field_names = {
                "nama_usaha": "nama usaha",
                "jenis_usaha": "jenis usaha",
                "lokasi_usaha": "lokasi/alamat usaha"
            }
            missing_names = [field_names.get(f, f) for f in missing_fields]
            fields_list = "\n".join([f"- {name}" for name in missing_names])
            needs_data_msg = f"Untuk membuat {letter_type}, saya perlu informasi berikut:\n{fields_list}\n\nSilakan berikan informasi tersebut."
        elif missing_fields:
            needs_data_msg = f"Untuk membuat {letter_type}, saya perlu keterangan/alasan surat. Silakan berikan keterangan tersebut."
        else:
            needs_data_msg = f"Untuk membuat {letter_type}, saya perlu informasi tambahan. Silakan berikan detail yang diperlukan."
        
        fallback_messages = {
            "letter_success": f"✅ Surat berhasil dibuat!\n\nNomor surat: {data.get('letter_number', 'N/A')}\n\nSurat Anda sudah siap diunduh.",
            "letter_failed": "Maaf, terjadi kesalahan saat membuat surat. Silakan coba lagi atau hubungi admin.",
            "needs_data": needs_data_msg,
            "needs_auth": "Untuk membuat surat, Anda perlu melakukan autentikasi terlebih dahulu. Silakan upload foto KTP Anda.",
            "invalid_letter_type": "Maaf, jenis surat yang Anda minta tidak valid."
        }
        return fallback_messages.get(context, "Terjadi kesalahan.")


def check_custom_data_complete(custom_data: dict, sub_intent_detail: str) -> bool:
    """
    Check apakah custom_data sudah lengkap sesuai jenis surat
    
    Args:
        custom_data: Custom data yang sudah ada
        sub_intent_detail: "SKTM", "SKDP", atau "SKU"
    
    Returns:
        bool: True jika lengkap, False jika belum
    """
    if not custom_data:
        return False
    
    if sub_intent_detail == "SKU":
        required_fields = ["nama_usaha", "jenis_usaha", "lokasi_usaha"]
        return all(field in custom_data and custom_data.get(field) for field in required_fields)
    else:  # SKTM atau SKDP
        return "keterangan" in custom_data and custom_data.get("keterangan")


def surat_processing_flow(state: AgentState) -> dict:
    """
    Flow untuk memproses pembuatan surat (SKTM, SKDP, SKU)
    Flow: check custom_data → jika belum ada, tanya user → create_letter_via_api → return result
    """
    sub_intent_detail = state.get("sub_intent_detail")
    
    # Check authentication
    is_authenticated = state.get("is_authenticated", False)
    if not is_authenticated:
        message = generate_letter_message("needs_auth")
        return {
            "messages": [AIMessage(content=message)],
            "letter_status": "needs_auth"
        }
    
    # Check apakah custom_data sudah ada di state
    custom_data = state.get("letter_custom_data")
    
    # Jika custom_data belum ada atau belum lengkap, extract dari user message atau tanya user
    if not check_custom_data_complete(custom_data, sub_intent_detail):
        user_message = extract_user_message(state)
        
        # Coba extract dari user message
        extracted_data = extract_custom_data_from_message(user_message, sub_intent_detail)
        
        # Check lagi apakah setelah extract sudah lengkap
        if check_custom_data_complete(extracted_data, sub_intent_detail):
            # Jika lengkap, simpan ke state dan lanjutkan
            custom_data = extracted_data
        else:
            # Jika masih belum lengkap, tanya user
            message = generate_letter_message("needs_data", {
                "letter_type": sub_intent_detail,
                "missing_fields": get_missing_fields(extracted_data, sub_intent_detail)
            })
            return {
                "messages": [AIMessage(content=message)],
                "letter_status": "needs_custom_data",
                "letter_custom_data": extracted_data  # Simpan partial data
            }
    
    # Map sub_intent_detail ke letter_type_id
    letter_type_map = {
        "SKTM": 1,
        "SKDP": 3,
        "SKU": 4
    }
    
    letter_type_id = letter_type_map.get(sub_intent_detail)
    if not letter_type_id:
        message = generate_letter_message("invalid_letter_type")
        return {
            "messages": [AIMessage(content=message)],
            "letter_status": "failed"
        }
    
    # Create letter via API
    api_result = create_letter_via_api(letter_type_id, custom_data)
    
    if not api_result:
        message = generate_letter_message("letter_failed")
        return {
            "messages": [AIMessage(content=message)],
            "letter_status": "failed"
        }
    
    # Success
    letter_data = api_result.get("letter", {})
    letter_number = letter_data.get("number", "N/A")
    download_url = api_result.get("download_url_pdf", "")
    
    message = generate_letter_message("letter_success", {
        "letter_number": letter_number,
        "download_url": download_url,
        "letter_type": sub_intent_detail
    })
    
    return {
        "messages": [AIMessage(content=message)],
        "letter_status": "success",
        "letter_data": letter_data,
        "download_url_pdf": download_url,
        "letter_number": letter_number
    }


def get_missing_fields(custom_data: dict, sub_intent_detail: str) -> list:
    """
    Get list of missing fields untuk custom_data
    
    Args:
        custom_data: Custom data yang sudah ada
        sub_intent_detail: "SKTM", "SKDP", atau "SKU"
    
    Returns:
        list: List of missing field names
    """
    missing = []
    
    if sub_intent_detail == "SKU":
        required_fields = ["nama_usaha", "jenis_usaha", "lokasi_usaha"]
        for field in required_fields:
            if field not in custom_data or not custom_data.get(field):
                missing.append(field)
    else:  # SKTM atau SKDP
        if "keterangan" not in custom_data or not custom_data.get("keterangan"):
            missing.append("keterangan")
    
    return missing


def generate_letter(state: AgentState) -> dict:
    """
    Generate letter based on user request
    Wrapper function yang memanggil surat_processing_flow
    """
    return surat_processing_flow(state)

def should_trigger_letter_processing(state: AgentState) -> str:
    """Check if should trigger letter processing flow"""
    auth_status = state.get("auth_status")
    next_action = state.get("next_action")
    
    # Jika auth berhasil dan next_action adalah surat_processing
    if auth_status == "authenticated" and next_action == "surat_processing":
        return "letter_processing"
    return "end"

def should_skip_intent_check(state: AgentState) -> str:
    """Check if should skip intent check and go directly to letter processing"""
    sub_intent = state.get("sub_intent")
    sub_intent_detail = state.get("sub_intent_detail")
    is_authenticated = state.get("is_authenticated", False)
    
    # Jika sudah authenticated, sub_intent = "Surat", dan sub_intent_detail sudah ada
    # berarti user sudah dalam flow surat, skip intent check
    if (is_authenticated and 
        sub_intent == "Surat" and 
        sub_intent_detail is not None and 
        sub_intent_detail in ["SKTM", "SKDP", "SKU"]):
        return "letter_processing"
    
    return "check_intent"
