# api_server.py
import os
import tempfile
import logging
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
from typing import Optional
from langchain_core.messages import HumanMessage, AIMessage
from src.graph import app as graph_app
from src.state import AgentState

logger = logging.getLogger(__name__)

app = FastAPI(title="LangGraph Chat Agent API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

sessions = {}


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    response: str
    session_id: str
    intent: Optional[str] = None
    confidence: Optional[float] = None


@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    try:
        session_id = request.session_id or f"session_{len(sessions)}"
        
        if session_id not in sessions:
            sessions[session_id] = {
                "messages": [],
                "user_message": None,
                "intent": None,
                "confidence": None,
                "needs_confirmation": None,
                "intent_result": None,
                "conversation_context": None,
                "pending_actions": None,
                "nik": None,
                # Auth fields
                "token": None,
                "is_authenticated": False,
                "auth_status": None,
                "ktp_image": None,
                "extracted_nik": None,
                "extracted_data": None,
                "nik_confirmed": False,
                "resident_data": None,
                "next_action": None
            }
        
        state = sessions[session_id]
        user_message = HumanMessage(content=request.message)
        state["messages"].append(user_message)
        state["user_message"] = request.message
        
        # Config untuk LangGraph (optional untuk in-memory, tapi lebih baik ada)
        config = {"configurable": {"thread_id": session_id}}
        
        # Log state sebelum invoke untuk debugging
        logger.info(f"[CHAT] Before invoke - auth_status: {state.get('auth_status')}, user_message: {request.message[:50]}")
        
        result = graph_app.invoke(state, config)
        
        # LangGraph return complete merged state, jadi replace bukan update
        sessions[session_id] = result
        
        # Log state setelah invoke untuk debugging
        logger.info(f"[CHAT] After invoke - auth_status: {result.get('auth_status')}, next_action: {result.get('next_action')}")
        
        # Extract AI response - PERBAIKAN: pakai isinstance
        ai_response = "Maaf, tidak ada respon dari agent."
        for msg in reversed(result.get("messages", [])):
            if isinstance(msg, AIMessage):  # ← PERBAIKAN: pakai isinstance
                ai_response = msg.content if hasattr(msg, 'content') else str(msg)
                break
        
        return ChatResponse(
            response=ai_response,
            session_id=session_id,
            intent=result.get("intent"),
            confidence=result.get("confidence")
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@app.get("/api/clear-session/{session_id}")
async def clear_session(session_id: str):
    if session_id in sessions:
        # Clean up KTP image file if exists
        ktp_image = sessions[session_id].get("ktp_image")
        if ktp_image and os.path.exists(ktp_image):
            try:
                os.remove(ktp_image)
            except Exception as e:
                logger.error(f"Error removing KTP image: {e}")
        
        del sessions[session_id]
    return {"success": True, "message": "Session cleared"}


@app.post("/api/upload-ktp")
async def upload_ktp(session_id: str = Form(...), file: UploadFile = File(...)):
    """
    Handle KTP image upload from frontend
    Store file temporarily and update session state
    """
    try:
        if session_id not in sessions:
            raise HTTPException(status_code=404, detail="Session not found")
        
        # Validate file type
        if not file.content_type or not file.content_type.startswith("image/"):
            raise HTTPException(status_code=400, detail="File must be an image")
        
        # Save file temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp_file:
            content = await file.read()
            tmp_file.write(content)
            tmp_file_path = tmp_file.name
        
        # Update session state
        sessions[session_id]["ktp_image"] = tmp_file_path
        sessions[session_id]["auth_status"] = "processing_ocr"
        
        # Trigger graph processing with the uploaded file
        # Note: route_from_start() will detect auth_status="processing_ocr" 
        # and route directly to auth_and_validation (skip check_intent)
        state = sessions[session_id]
        config = {"configurable": {"thread_id": session_id}}
        
        logger.info(f"[UPLOAD_KTP] Before invoke - auth_status: {state.get('auth_status')}, ktp_image: {tmp_file_path}")
        result = graph_app.invoke(state, config)
        
        # LangGraph return complete merged state, jadi replace bukan update
        sessions[session_id] = result
        
        logger.info(f"[UPLOAD_KTP] After invoke - auth_status: {result.get('auth_status')}, next_action: {result.get('next_action')}")
        
        # Extract AI response
        ai_response = "KTP berhasil diupload, sedang diproses..."
        for msg in reversed(result.get("messages", [])):
            if isinstance(msg, AIMessage):
                ai_response = msg.content if hasattr(msg, 'content') else str(msg)
                break
        
        return JSONResponse(content={
            "success": True,
            "message": "KTP uploaded successfully",
            "response": ai_response,
            "file_path": tmp_file_path
        })
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error uploading KTP: {str(e)}")


# ... (HTML UI tetap sama, tidak perlu diubah)


@app.get("/", response_class=HTMLResponse)
async def get_ui():
    html_content = """
<!DOCTYPE html>
<html lang="id">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Chat Agent</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background: #f7f7f8;
            height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
        }
        
        .chat-container {
            background: white;
            width: 100%;
            max-width: 800px;
            height: 100vh;
            max-height: 900px;
            display: flex;
            flex-direction: column;
            box-shadow: 0 0 20px rgba(0,0,0,0.1);
        }
        
        .chat-header {
            padding: 16px 20px;
            border-bottom: 1px solid #e5e5e5;
            background: white;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .chat-header h1 {
            font-size: 18px;
            font-weight: 600;
            color: #202123;
        }
        
        .clear-btn {
            background: none;
            border: none;
            color: #666;
            cursor: pointer;
            font-size: 14px;
            padding: 4px 8px;
        }
        
        .clear-btn:hover {
            color: #202123;
        }
        
        .chat-messages {
            flex: 1;
            overflow-y: auto;
            padding: 20px;
            background: #f7f7f8;
        }
        
        .message {
            margin-bottom: 24px;
            display: flex;
            animation: fadeIn 0.3s;
        }
        
        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(5px); }
            to { opacity: 1; transform: translateY(0); }
        }
        
        .message.user {
            justify-content: flex-end;
        }
        
        .message.agent {
            justify-content: flex-start;
        }
        
        .message-content {
            max-width: 85%;
            padding: 12px 16px;
            border-radius: 18px;
            word-wrap: break-word;
            line-height: 1.5;
            white-space: pre-wrap;
        }
        
        .message.user .message-content {
            background: #19c37d;
            color: white;
        }
        
        .message.agent .message-content {
            background: white;
            color: #374151;
            box-shadow: 0 1px 2px rgba(0,0,0,0.05);
        }
        
        .chat-input-container {
            padding: 16px 20px;
            background: white;
            border-top: 1px solid #e5e5e5;
        }
        
        .chat-input-form {
            display: flex;
            gap: 8px;
            align-items: flex-end;
        }
        
        .chat-input {
            flex: 1;
            padding: 12px 16px;
            border: 1px solid #d1d5db;
            border-radius: 24px;
            font-size: 16px;
            outline: none;
            resize: none;
            max-height: 200px;
            font-family: inherit;
            line-height: 1.5;
        }
        
        .chat-input:focus {
            border-color: #19c37d;
            box-shadow: 0 0 0 3px rgba(25, 195, 125, 0.1);
        }
        
        .send-button {
            padding: 12px 24px;
            background: #19c37d;
            color: white;
            border: none;
            border-radius: 24px;
            font-size: 16px;
            font-weight: 500;
            cursor: pointer;
            transition: background 0.2s;
            height: 48px;
        }
        
        .send-button:hover:not(:disabled) {
            background: #16a085;
        }
        
        .send-button:disabled {
            opacity: 0.6;
            cursor: not-allowed;
        }
        
        .upload-button {
            padding: 12px 16px;
            background: #f0f0f0;
            color: #666;
            border: 1px solid #d1d5db;
            border-radius: 24px;
            font-size: 20px;
            cursor: pointer;
            transition: all 0.2s;
            height: 48px;
            min-width: 48px;
            display: none;
        }
        
        .upload-button:hover {
            background: #e0e0e0;
            border-color: #19c37d;
        }
        
        .upload-button:active {
            transform: scale(0.95);
        }
        
        .file-preview {
            padding: 8px 12px;
            margin: 8px 0;
            background: #f0f9ff;
            border: 1px solid #bae6fd;
            border-radius: 8px;
            font-size: 14px;
            color: #0369a1;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        
        .file-preview img {
            max-width: 100px;
            max-height: 100px;
            border-radius: 4px;
            object-fit: cover;
        }
        
        .loading {
            display: inline-block;
            width: 16px;
            height: 16px;
            border: 2px solid #e5e5e5;
            border-top: 2px solid #19c37d;
            border-radius: 50%;
            animation: spin 0.8s linear infinite;
        }
        
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        
        .empty-state {
            text-align: center;
            color: #9ca3af;
            padding: 40px 20px;
            font-size: 14px;
        }
    </style>
</head>
<body>
    <div class="chat-container">
        <div class="chat-header">
            <h1>Chat Agent</h1>
            <button class="clear-btn" onclick="clearSession()">Clear</button>
        </div>
        <div class="chat-messages" id="chatMessages">
            <div class="empty-state">Mulai percakapan...</div>
        </div>
        <div class="chat-input-container">
            <form class="chat-input-form" onsubmit="sendMessage(event)" id="chatForm">
                <!-- File upload input (hidden, akan muncul saat perlu) -->
                <input 
                    type="file" 
                    id="ktpFileInput" 
                    accept="image/*" 
                    style="display: none;"
                    onchange="handleKTPUpload(event)"
                >
                
                <textarea 
                    class="chat-input" 
                    id="messageInput" 
                    placeholder="Ketik pesan..."
                    rows="1"
                    oninput="autoResize(this)"
                ></textarea>
                
                <!-- Upload button (akan muncul saat agent minta KTP) -->
                <button 
                    type="button" 
                    class="upload-button" 
                    id="uploadButton"
                    onclick="document.getElementById('ktpFileInput').click()"
                    title="Upload KTP"
                >
                    📷
                </button>
                
                <button type="submit" class="send-button" id="sendButton">Kirim</button>
            </form>
        </div>
    </div>

    <script>
        let sessionId = null;
        let waitingForKTP = false;
        
        function autoResize(textarea) {
            textarea.style.height = 'auto';
            textarea.style.height = Math.min(textarea.scrollHeight, 200) + 'px';
        }
        
        function checkIfNeedsKTP(responseText) {
            // Deteksi jika agent meminta KTP upload
            const ktpKeywords = [
                'kirimkan ktp',
                'upload ktp',
                'foto ktp',
                'ktp anda',
                'membawa ktp',
                'silakan upload',
                'kirimkan foto',
                'kirim ktp',
                'upload foto ktp'
            ];
            
            const lowerText = responseText.toLowerCase();
            return ktpKeywords.some(keyword => lowerText.includes(keyword));
        }
        
        function showUploadButton() {
            const uploadBtn = document.getElementById('uploadButton');
            if (uploadBtn) {
                uploadBtn.style.display = 'block';
                waitingForKTP = true;
            }
        }
        
        function hideUploadButton() {
            const uploadBtn = document.getElementById('uploadButton');
            if (uploadBtn) {
                uploadBtn.style.display = 'none';
                waitingForKTP = false;
            }
        }
        
        async function handleKTPUpload(event) {
            const file = event.target.files[0];
            if (!file) return;
            
            if (!sessionId) {
                alert('Session tidak ditemukan. Silakan kirim pesan terlebih dahulu.');
                return;
            }
            
            // Validate file type
            if (!file.type.startsWith('image/')) {
                alert('File harus berupa gambar!');
                return;
            }
            
            // Validate file size (max 5MB)
            if (file.size > 5 * 1024 * 1024) {
                alert('Ukuran file terlalu besar. Maksimal 5MB.');
                return;
            }
            
            // Show loading
            const loadingId = addMessage('Mengupload KTP...', 'agent', true);
            
            try {
                const formData = new FormData();
                formData.append('session_id', sessionId);
                formData.append('file', file);
                
                const response = await fetch('/api/upload-ktp', {
                    method: 'POST',
                    body: formData
                });
                
                const data = await response.json();
                
                removeMessage(loadingId);
                
                if (response.ok && data.success) {
                    // Show file preview
                    const reader = new FileReader();
                    reader.onload = function(e) {
                        const previewHtml = `
                            <div class="file-preview">
                                <img src="${e.target.result}" alt="KTP Preview">
                                <span>KTP berhasil diupload</span>
                            </div>
                        `;
                        addMessage(previewHtml, 'user', false, true);
                    };
                    reader.readAsDataURL(file);
                    
                    // Show agent response
                    if (data.response) {
                        addMessage(data.response, 'agent');
                        
                        // Check if still waiting for confirmation
                        if (checkIfNeedsKTP(data.response) || data.response.includes('benar')) {
                            // Still in KTP flow, keep button visible
                        } else {
                            hideUploadButton();
                        }
                    }
                    
                    // Hide upload button if auth is complete
                    if (data.response && (data.response.includes('Autentikasi berhasil') || data.response.includes('berhasil'))) {
                        hideUploadButton();
                    }
                } else {
                    addMessage('Maaf, gagal mengupload KTP. Silakan coba lagi.', 'agent');
                }
            } catch (error) {
                removeMessage(loadingId);
                addMessage('Maaf, terjadi kesalahan saat mengupload KTP.', 'agent');
                console.error('Error uploading KTP:', error);
            } finally {
                // Reset file input
                event.target.value = '';
            }
        }
        
        async function sendMessage(event) {
            event.preventDefault();
            
            const input = document.getElementById('messageInput');
            const message = input.value.trim();
            
            if (!message) return;
            
            input.disabled = true;
            document.getElementById('sendButton').disabled = true;
            
            // Remove empty state
            const emptyState = document.querySelector('.empty-state');
            if (emptyState) emptyState.remove();
            
            addMessage(message, 'user');
            input.value = '';
            input.style.height = 'auto';
            
            const loadingId = addMessage('', 'agent', true);
            
            try {
                const response = await fetch('/api/chat', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        message: message,
                        session_id: sessionId
                    })
                });
                
                const data = await response.json();
                
                if (data.session_id) {
                    sessionId = data.session_id;
                }
                
                removeMessage(loadingId);
                
                if (data.response) {
                    addMessage(data.response, 'agent');
                    
                    // Check if agent is asking for KTP upload
                    if (checkIfNeedsKTP(data.response)) {
                        showUploadButton();
                    } else {
                        hideUploadButton();
                    }
                }
                
            } catch (error) {
                removeMessage(loadingId);
                addMessage('Maaf, terjadi kesalahan. Silakan coba lagi.', 'agent');
                console.error('Error:', error);
            } finally {
                input.disabled = false;
                document.getElementById('sendButton').disabled = false;
                input.focus();
            }
        }
        
        function addMessage(text, type, isLoading = false, isHTML = false) {
            const messagesDiv = document.getElementById('chatMessages');
            const messageDiv = document.createElement('div');
            messageDiv.className = `message ${type}`;
            
            const contentDiv = document.createElement('div');
            contentDiv.className = 'message-content';
            
            if (isLoading) {
                contentDiv.innerHTML = '<div class="loading"></div>';
                messageDiv.id = 'loading-message';
            } else if (isHTML) {
                contentDiv.innerHTML = text;
            } else {
                contentDiv.textContent = text;
            }
            
            messageDiv.appendChild(contentDiv);
            messagesDiv.appendChild(messageDiv);
            messagesDiv.scrollTop = messagesDiv.scrollHeight;
            
            return messageDiv.id || null;
        }
        
        function removeMessage(messageId) {
            const message = document.getElementById(messageId);
            if (message) message.remove();
        }
        
        async function clearSession() {
            if (sessionId) {
                try {
                    await fetch(`/api/clear-session/${sessionId}`);
                } catch (error) {
                    console.error('Error:', error);
                }
            }
            
            sessionId = null;
            waitingForKTP = false;
            hideUploadButton();
            document.getElementById('chatMessages').innerHTML = 
                '<div class="empty-state">Mulai percakapan...</div>';
        }
        
        document.getElementById('messageInput').focus();
    </script>
</body>
</html>
    """
    return HTMLResponse(content=html_content)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)