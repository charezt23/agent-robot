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
    is_authenticated: Optional[bool]  # Status autentikasi
    auth_status: Optional[str]  # "checking", "needs_ktp", "processing_ocr", "validating", "authenticated", "failed", "skipped"
    
    # OCR fields
    ktp_image: Optional[str]  # Path/file KTP yang diupload
    extracted_nik: Optional[str]  # NIK hasil OCR
    extracted_data: Optional[dict]  # Data KTP hasil OCR (nama, tempat_lahir, dll)
    nik_confirmed: Optional[bool]  # Apakah user sudah konfirmasi NIK
    
    # Resident data
    resident_data: Optional[dict]  # Data resident dari API
    
    # Letter processing fields
    letter_custom_data: Optional[dict]  # Custom data untuk surat (keterangan untuk SKTM/SKDP, atau nama_usaha/jenis_usaha/lokasi_usaha untuk SKU)
    letter_status: Optional[str]  # Status pembuatan surat: "needs_custom_data", "success", "failed", "skipped"
    letter_data: Optional[dict]  # Data surat hasil dari API
    download_url_pdf: Optional[str]  # URL untuk download PDF surat
    letter_number: Optional[str]  # Nomor surat
    
    # Flow control
    next_action: Optional[str]  # Next action: "surat_processing", "end", "auth_required", dll


