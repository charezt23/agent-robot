import os
import httpx
import json
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


def check_token_valid(state: AgentState) -> dict:
    """Check if token is valid via API and update is_authenticated in state"""
    from src.state_utils import preserve_state
    try:
        with httpx.Client(timeout=HTTP_TIMEOUT) as client:
            response = client.get(
                f"{BACKEND_API_URL}/check-token",
            )
            if response.status_code == 200:
                data = response.json()
                if data.get("success", False):
                    valid = data.get("data", {}).get("valid", False)
                    if valid:
                        return preserve_state(state, {
                            "is_authenticated": True,
                            "auth_status": "authenticated"
                        })
                    else:
                        message = generate_auth_message("token_invalid", state)
                        return preserve_state(state, {
                            "is_authenticated": False,
                            "auth_status": "needs_ktp",
                            "messages": [AIMessage(content=message)]
                        })
            return preserve_state(state, {
                "is_authenticated": False,
                "auth_status": "failed"
            })
    except Exception as e:
        return preserve_state(state, {
            "is_authenticated": False,
            "auth_status": "failed"
        })

def login_by_nik(state: AgentState) -> dict:
    """Login using NIK from state, return is_authenticated and auth_status"""
    from src.state_utils import preserve_state
    nik = state.get("nik")
    
    if not nik:
        return preserve_state(state, {
            "is_authenticated": False,
            "auth_status": "failed"
        })
    
    try:
        with httpx.Client(timeout=HTTP_TIMEOUT) as client:
            response = client.post(
                f"{BACKEND_API_URL}/login-by-nik",
                json={"nik": nik}
            )
            if response.status_code == 200:
                data = response.json()
                if data.get("success", False):
                    message = generate_auth_message("auth_success", state)
                    return preserve_state(state, {
                        "is_authenticated": True,
                        "auth_status": "authenticated",
                        "messages": [AIMessage(content=message)]
                    })
            # status_code != 200 atau success != true → error dari API
            message = generate_auth_message("auth_failed", state)
            return preserve_state(state, {
                "is_authenticated": False,
                "auth_status": "failed",
                "messages": [AIMessage(content=message)]
            })
    except Exception as e:
        # Exception → error sistem
        message = generate_auth_message("system_error", state)
        return preserve_state(state, {
            "is_authenticated": False,
            "auth_status": "failed",
            "messages": [AIMessage(content=message)]
        })

def upload_ktp_for_ocr(state: AgentState) -> dict:
    """Upload KTP image for OCR processing, return state with extracted_nik and auth_status"""
    from src.state_utils import preserve_state
    ktp_image = state.get("ktp_image")
    
    if not ktp_image:
        return preserve_state(state, {
            "auth_status": "needs_ktp",
            "extracted_nik": None
        })
    
    try:
        with httpx.Client(timeout=HTTP_TIMEOUT * 2) as client:
            # Pastikan file bisa dibuka
            try:
                with open(ktp_image, "rb") as f:
                    files = {"ktpImage": (os.path.basename(ktp_image), f, "image/jpeg")}
                    response = client.post(
                        f"{BACKEND_API_URL}/upload-ktp",
                        files=files
                    )
                    if response.status_code == 200:
                        data = response.json()
                        if data.get("success", False):
                            extracted_nik = data.get("data", {}).get("nik")
                            
                            # Cek apakah extracted_nik valid
                            if extracted_nik and extracted_nik.strip():
                                message = generate_auth_message("nik_confirmation", state, {"nik": extracted_nik})
                                return preserve_state(state, {
                                    "extracted_nik": extracted_nik,
                                    "auth_status": "needs_nik_confirmation",
                                    "messages": [AIMessage(content=message)],
                                    "ktp_image": None  # ← CLEAR ktp_image setelah OCR selesai
                                })
                            else:
                                # OCR berhasil tapi NIK tidak terdeteksi
                                message = generate_auth_message("ocr_failed", state)
                                return preserve_state(state, {
                                    "auth_status": "failed",
                                    "extracted_nik": None,
                                    "messages": [AIMessage(content=message)]
                                })
                    # OCR gagal dari API
                    message = generate_auth_message("ocr_failed", state)
                    return preserve_state(state, {
                        "auth_status": "failed",
                        "extracted_nik": None,
                        "messages": [AIMessage(content=message)]
                    })
            except FileNotFoundError:
                # File tidak ditemukan
                message = generate_auth_message("ocr_failed", state)
                return preserve_state(state, {
                    "auth_status": "failed",
                    "extracted_nik": None,
                    "messages": [AIMessage(content=message)]
                })
    except Exception as e:
        # Exception lainnya
        message = generate_auth_message("ocr_failed", state)
        return preserve_state(state, {
            "auth_status": "failed",
            "extracted_nik": None,
            "messages": [AIMessage(content=message)]
        })

def check_resident(state: AgentState) -> dict:
    """Check if resident exists in database via API, return state with auth_status"""
    from src.state_utils import preserve_state
    nik = state.get("nik")
    nik_confirmed = state.get("nik_confirmed")
    
    if not nik:
        return preserve_state(state, {
            "auth_status": "failed"
        })
    
    try:
        with httpx.Client(timeout=HTTP_TIMEOUT) as client:
            response = client.get(f"{BACKEND_API_URL}/resident/{nik}")
            if response.status_code == 200:
                data = response.json()
                if data.get("success", False):
                    resident_data = data.get("data", {})
                    return preserve_state(state, {
                        "auth_status": "resident_found",
                        "nik": nik,
                        "nik_confirmed": nik_confirmed,
                        "resident_data": resident_data
                    })
            message = generate_auth_message("resident_not_found", state)
            return preserve_state(state, {
                "auth_status": "resident_not_found",
                "messages": [AIMessage(content=message)],
                "nik": nik,
                "nik_confirmed": nik_confirmed
            })
    except Exception as e:
        return preserve_state(state, {
            "auth_status": "failed",
            "nik": nik,
            "nik_confirmed": nik_confirmed
        })

def should_trigger_auth(state: AgentState) -> str:
    """Check if should trigger auth flow"""
    auth_status = state.get("auth_status")
    
    # Jika sudah ada auth_status "needs_nik_confirmation", route ke handle_nik_confirmation
    if auth_status == "needs_nik_confirmation":
        return "handle_nik_confirmation"  # ← TAMBAHKAN INI!
    
    sub_intent = state.get("sub_intent")
    sub_intent_detail = state.get("sub_intent_detail")
    
    if sub_intent == "Surat" and sub_intent_detail in ["SKTM", "SKDP", "SKU"]:
        return "auth_flow"
    return "end"

def generate_auth_message(context: str, state: AgentState, data: dict = None) -> str:
    """
    Generate response message menggunakan LLM berdasarkan context, state, dan conversation history
    
    Args:
        context: Context message (e.g., "token_invalid", "ocr_success", "auth_success")
        state: AgentState yang berisi conversation history dan current context
        data: Additional data (e.g., {"nik": "..."})
    
    Returns:
        str: Generated message from LLM
    """
    data = data or {}
    
    # Extract conversation history (minimal 10 messages terakhir)
    messages_history = state.get("messages", [])
    recent_messages = messages_history[-10:] if len(messages_history) > 10 else messages_history
    
    # Extract current state context
    auth_status = state.get("auth_status")
    intent = state.get("intent")
    sub_intent = state.get("sub_intent")
    sub_intent_detail = state.get("sub_intent_detail")
    is_authenticated = state.get("is_authenticated", False)
    extracted_nik = state.get("extracted_nik")
    nik_confirmed = state.get("nik_confirmed")
    
    # Build context summary
    context_summary = f"""KONTEKS SAAT INI:
- Status Autentikasi: {auth_status or 'belum ada'}
- Intent User: {intent or 'belum diketahui'}
- Sub Intent: {sub_intent or 'belum diketahui'}
- Detail: {sub_intent_detail or 'belum diketahui'}
- Sudah Authenticated: {is_authenticated}
- NIK yang terdeteksi: {extracted_nik or 'belum ada'}
- NIK sudah dikonfirmasi: {nik_confirmed or False}
"""
    
    # Build conversation history string
    conversation_history = ""
    if recent_messages:
        conversation_history = "\nRIWAYAT PERCAKAPAN:\n"
        for msg in recent_messages:
            if hasattr(msg, 'content'):
                role = "User" if isinstance(msg, HumanMessage) else "AI"
                conversation_history += f"{role}: {msg.content}\n"
    
    system_prompt = """Anda adalah asisten yang ramah di kantor kelurahan.
Berikan respon yang natural, mengalir, dan seperti obrolan sehari-hari dalam bahasa Indonesia.
Gunakan bahasa yang casual tapi tetap sopan. Boleh pakai "kamu" atau "Anda" tergantung konteks.

PENTING:
- Respon harus SINGKAT, natural, dan langsung to the point (maksimal 2-3 kalimat)
- Respon HARUS mengalir dengan percakapan sebelumnya (lihat riwayat percakapan)
- Respon HARUS sesuai dengan konteks saat ini (lihat status autentikasi, intent, dll)
- Hindari kalimat yang terlalu formal atau bertele-tele
- Buat seperti sedang ngobrol dengan teman, tapi tetap profesional
- Jika user sudah bilang sesuatu sebelumnya, jangan ulang-ulang, langsung lanjutkan ke langkah berikutnya"""
    
    context_prompts = {
        "token_invalid": "User minta buat surat tapi belum authenticated. Respon dengan natural dan friendly, minta scan/upload KTP. Lihat riwayat percakapan untuk tahu user minta surat apa. Contoh: 'bisa, silahkan scan ktp ya, pastikan gambar jelas, kalau tidak saya tidak bisa memproses suratnya'. Buat variasi yang natural sesuai konteks percakapan.",
        "ocr_success": f"KTP berhasil di-scan. NIK yang terdeteksi: {data.get('nik', extracted_nik or 'N/A')}. Minta konfirmasi dengan cara yang natural dan friendly. Lihat riwayat percakapan untuk konteks. Contoh: 'NIK yang terdeteksi **{data.get('nik', extracted_nik or 'N/A')}**. Sudah benar belum?'",
        "nik_confirmation": f"KTP berhasil di-scan. NIK yang terdeteksi: {data.get('nik', extracted_nik or 'N/A')}. Minta konfirmasi dengan cara yang natural dan friendly. Lihat riwayat percakapan untuk konteks. Contoh: 'NIK yang terdeteksi **{data.get('nik', extracted_nik or 'N/A')}**. Sudah benar belum?'",
        "ocr_failed": "KTP tidak bisa dibaca dengan jelas. Minta upload ulang dengan cara yang natural dan friendly. Lihat riwayat percakapan untuk konteks. Contoh: 'maaf, KTP-nya kurang jelas nih. Bisa upload ulang dengan gambar yang lebih jelas?'",
        "resident_not_found": "NIK tidak terdaftar di sistem. Berikan pesan yang natural dan informatif. Lihat riwayat percakapan untuk konteks.",
        "auth_success": "Autentikasi berhasil. Berikan pesan sukses yang natural dan friendly. Lihat riwayat percakapan untuk tahu user minta surat apa, lalu lanjutkan ke langkah berikutnya. Contoh: 'oke, autentikasi berhasil! Sekarang saya bisa bantu buat suratnya'",
        "auth_failed": "Autentikasi gagal. Berikan pesan yang natural dan informatif. Lihat riwayat percakapan untuk konteks.",
        "system_error": "Terjadi kesalahan sistem. Berikan pesan yang natural dan informatif. Lihat riwayat percakapan untuk konteks."
    }
    
    user_prompt = f"""{context_summary}

{conversation_history}

{context_prompts.get(context, "Berikan respon yang sesuai.")}

Berdasarkan konteks dan riwayat percakapan di atas, berikan respon yang natural, mengalir, dan sesuai dengan situasi saat ini."""
    
    messages_for_llm = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt)
    ]
    
    try:
        response = llm.invoke(messages_for_llm)
        return response.content if hasattr(response, 'content') else str(response)
    except Exception as e:
        # Fallback messages yang natural dan mengalir
        fallback_messages = {
            "token_invalid": "Bisa, silahkan scan KTP ya. Pastikan gambar jelas, kalau tidak saya tidak bisa memproses suratnya.",
            "ocr_success": f"Oke, KTP-nya sudah saya scan. NIK yang terdeteksi **{data.get('nik', extracted_nik or 'N/A')}**. Sudah benar belum?",
            "nik_confirmation": f"Oke, KTP-nya sudah saya scan. NIK yang terdeteksi **{data.get('nik', extracted_nik or 'N/A')}**. Sudah benar belum?",
            "ocr_failed": "Maaf, KTP-nya kurang jelas nih. Bisa upload ulang dengan gambar yang lebih jelas?",
            "resident_not_found": "Maaf, NIK kamu belum terdaftar di sistem kami. Silakan hubungi admin ya.",
            "auth_success": "Oke, autentikasi berhasil! Sekarang saya bisa bantu buat suratnya.",
            "auth_failed": "Maaf, ada masalah saat autentikasi. Coba lagi ya.",
            "system_error": "Maaf, ada masalah di sistem kami. Tim sedang memperbaikinya, coba lagi nanti ya."
        }
        return fallback_messages.get(context, "Terjadi kesalahan.")

def handle_nik_confirmation(state: AgentState) -> dict:
    """Handle user confirmation untuk NIK yang terdeteksi menggunakan LLM"""
    from src.state_utils import preserve_state
    user_message = extract_user_message(state)
    extracted_nik = state.get("extracted_nik")
    
    if not extracted_nik:
        message = generate_auth_message("ocr_failed", state)
        return preserve_state(state, {
            "messages": [AIMessage(content=message)],
            "auth_status": "needs_ktp",
            "nik_confirmed": False
        })
    
    # Gunakan LLM untuk menentukan apakah user mengkonfirmasi
    system_prompt = """Anda adalah asisten yang membantu menentukan apakah user mengkonfirmasi atau tidak.
User akan memberikan respon terhadap pertanyaan konfirmasi NIK.
Tugas Anda adalah menentukan apakah respon user menunjukkan KONFIRMASI (ya/benar/setuju/sejenisnya yang memiliki arti ya) atau TIDAK KONFIRMASI (tidak/salah/bukan/sejenisnya yang memiliki arti tidak).

PENTING: Kata-kata seperti "sudah", "sudah benar", "sudah betul", "sudah oke" adalah KONFIRMASI (confirmed: true).

Respon dengan format JSON:
{
    "confirmed": true/false,
    "reason": "alasan singkat"
}

Contoh KONFIRMASI (confirmed: true):
- "ya", "benar", "ok", "setuju", "betul", "iya", "yes", "true"
- "sudah", "sudah benar", "sudah betul", "sudah oke", "sudah cocok"
- "iya benar", "betul itu", "cocok"

Contoh TIDAK KONFIRMASI (confirmed: false):
- "tidak", "salah", "bukan", "no", "false"
- "bukan itu", "salah NIK-nya", "tidak benar"
- "bukan NIK saya", "salah nomornya\""""

    user_prompt = f"""User memberikan respon: "{user_message}"

NIK yang ditanyakan: {extracted_nik}

Apakah user mengkonfirmasi bahwa NIK tersebut benar? Respon dengan JSON format."""

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt)
    ]
    
    try:
        response = llm.invoke(messages)
        response_text = response.content if hasattr(response, 'content') else str(response)
        
        # Parse JSON response
        if "{" in response_text and "}" in response_text:
            json_start = response_text.find("{")
            json_end = response_text.rfind("}") + 1
            json_str = response_text[json_start:json_end]
            result = json.loads(json_str)
            
            is_confirmed = result.get("confirmed", False)
        else:
            # Fallback: cek keyword jika LLM tidak return JSON
            confirmation_keywords = ["ya", "benar", "ok", "setuju", "betul", "iya", "yes", "true", "sudah", "sudah benar", "sudah betul", "sudah oke", "sudah cocok"]
            user_message_lower = user_message.lower().strip()
            is_confirmed = any(keyword in user_message_lower for keyword in confirmation_keywords)
    except Exception as e:
        # Fallback ke keyword matching jika LLM error
        confirmation_keywords = ["ya", "benar", "ok", "setuju", "betul", "iya", "yes", "true", "sudah", "sudah benar", "sudah betul", "sudah oke", "sudah cocok"]
        user_message_lower = user_message.lower().strip()
        is_confirmed = any(keyword in user_message_lower for keyword in confirmation_keywords)
    
    if is_confirmed:
        # User konfirmasi, lanjutkan ke check resident
        message = generate_auth_message("auth_success", state)
        return preserve_state(state, {
            "nik": extracted_nik,  # Pindahkan extracted_nik ke nik (yang sudah dikonfirmasi)
            "nik_confirmed": True,
            "auth_status": "validating",  # Status untuk check resident
            "messages": [AIMessage(content=message)]
        })
    else:
        # User tidak konfirmasi atau minta upload ulang
        message = generate_auth_message("ocr_failed", state)
        return preserve_state(state, {
            "messages": [AIMessage(content=message)],
            "auth_status": "needs_ktp",
            "nik_confirmed": False
        })

def should_route_after_upload_ktp(state: AgentState) -> str:
    """Route after upload_ktp_for_ocr node"""
    auth_status = state.get("auth_status")
    
    # Setelah upload KTP, jika sudah dapat NIK, langsung END (tunggu user konfirmasi)
    # handle_nik_confirmation akan dipanggil ketika user mengirim pesan baru (via START routing)
    if auth_status == "needs_nik_confirmation":
        return "end"  # ← UBAH: Langsung END, tunggu user konfirmasi
    elif auth_status == "needs_ktp":
        return "end"
    elif auth_status == "failed":
        return "end"  # → END (error)
    return "end"  # Default

def should_route_after_nik_confirmation(state: AgentState) -> str:
    """Route after handle_nik_confirmation node"""
    auth_status = state.get("auth_status")
    
    if auth_status == "validating":
        return "check_resident"  # → check_resident node
    elif auth_status == "needs_ktp":
        return "end"  # → END (tunggu user upload KTP baru)
    return "end"  # Default

def should_route_after_check_resident(state: AgentState) -> str:
    """Route after check_resident node"""
    auth_status = state.get("auth_status")
    
    if auth_status == "resident_found":
        return "login_by_nik"  # → login_by_nik node
    elif auth_status == "resident_not_found":
        return "end"  # → END (error)
    elif auth_status == "failed":
        return "end"  # → END (error)
    return "end"  # Default

def should_route_after_login(state: AgentState) -> str:
    """Route after login_by_nik node"""
    auth_status = state.get("auth_status")
    
    if auth_status == "authenticated":
        return "end"  # ← UBAH: Login berhasil, langsung END (surat_processing_flow sudah dihapus untuk isolasi)
    elif auth_status == "failed":
        return "end"
    return "end"

def should_route_after_check_token(state: AgentState) -> str:
    """Route after check_token_valid node"""
    auth_status = state.get("auth_status")
    ktp_image = state.get("ktp_image")  # ← CEK KTP IMAGE
    
    if auth_status == "authenticated":
        return "end"  # ← UBAH: Token valid, langsung END (surat_processing_flow sudah dihapus untuk isolasi)
    elif auth_status == "needs_ktp":
        if ktp_image:  # ← Hanya route ke upload_ktp jika ktp_image ada
            return "upload_ktp_for_ocr"
        else:
            return "end"  # ← STOP, tunggu user upload KTP
    elif auth_status == "failed":
        return "end"
    return "end"

def should_route_from_start(state: AgentState) -> str:
    """Route from START: check if we're in the middle of auth flow"""
    auth_status = state.get("auth_status")
    ktp_image = state.get("ktp_image")
    
    # PRIORITAS 1: Jika sedang menunggu konfirmasi NIK (cek auth_status dulu!)
    if auth_status == "needs_nik_confirmation":
        return "handle_nik_confirmation"
    
    # PRIORITAS 2: Jika sedang dalam proses validasi
    if auth_status == "validating":
        return "check_resident"
    
    # PRIORITAS 3: Jika ada ktp_image DAN auth_status adalah needs_ktp (baru upload)
    if ktp_image and auth_status == "needs_ktp":
        return "upload_ktp_for_ocr"
    
    # PRIORITAS 4: Jika ada ktp_image tapi auth_status bukan needs_ktp (sudah diproses)
    # Jangan route ke upload_ktp_for_ocr lagi, langsung ke check_intent
    if ktp_image:
        return "check_intent"  # ← UBAH: Jangan upload lagi jika sudah diproses
    
    # Default: route ke check_intent
    return "check_intent"