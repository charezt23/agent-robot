from typing import Annotated, Optional
from typing_extensions import TypedDict
from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    user_message: Optional[str]  # Original user message
    intent: Optional[str]  # Level 1: "Layanan" | "Ngobrol"
    intent_confidence: Optional[float]  # Confidence score Level 1 (0.0 - 1.0)
    sub_intent: Optional[str]  # Level 2: "Surat" | "Non-Surat" | null (jika intent = "Layanan")
    sub_intent_confidence: Optional[float]  # Confidence score Level 2 (0.0 - 1.0)
    sub_intent_detail: Optional[str]  # Level 3: "SKTM" | "SKDP" | "SKU" | "SPKTP" | null (jika sub_intent = "Surat")
    sub_intent_detail_confidence: Optional[float]  # Confidence score Level 3 (0.0 - 1.0)
    needs_confirmation: Optional[bool]  # True if ambiguous and needs user confirmation
    confirmation_level: Optional[str]  # Level yang perlu konfirmasi: "intent" | "sub_intent" | "sub_intent_detail" | null
    intent_result: Optional[dict]  # Final JSON result with all levels and confidence
    conversation_context: Optional[dict]  # Context untuk conversation (greeting, farewell, dll)
    pending_actions: Optional[list]  # Actions yang perlu di-handle (e.g., collect_slot)
    nik: Optional[str]  # NIK pengguna
    
    # Auth & Validation fields
    token: Optional[str]  # Token dari login
    is_authenticated: Optional[bool]  # Status autentikasi
    auth_status: Optional[str]  # "checking", "needs_ktp", "processing_ocr", "validating", "authenticated", "failed", "skipped"
    
    # OCR fields
    ktp_image: Optional[str]  # Path/file KTP yang diupload
    extracted_nik: Optional[str]  # NIK hasil OCR
    extracted_data: Optional[dict]  # Data KTP hasil OCR (nama, tempat_lahir, dll)
    nik_confirmed: Optional[bool]  # Apakah user sudah konfirmasi NIK
    
    # Resident data
    resident_data: Optional[dict]  # Data resident dari API
    
    # Flow control
    next_action: Optional[str]  # Next action: "surat_processing", "end", "auth_required", dll


