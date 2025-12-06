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

logging.basicConfig(level=logging.INFO)
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
    auth_status: Optional[str] = None
    is_authenticated: Optional[bool] = None


def get_initial_state() -> dict:
    """Create initial state for new session"""
    return {
        "messages": [],
        "user_message": None,
        "intent": None,
        "intent_confidence": None,
        "sub_intent": None,
        "sub_intent_confidence": None,
        "sub_intent_detail": None,
        "sub_intent_detail_confidence": None,
        "needs_confirmation": None,
        "confirmation_level": None,
        "intent_result": None,
        "conversation_context": None,
        "pending_actions": None,
        "nik": None,
        "is_authenticated": None,
        "auth_status": None,
        "ktp_image": None,
        "extracted_nik": None,
        "extracted_data": None,
        "nik_confirmed": None,
        "resident_data": None,
        "next_action": None
    }


@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Handle chat messages"""
    try:
        session_id = request.session_id or f"session_{len(sessions)}"
        
        # Initialize session if not exists
        if session_id not in sessions:
            sessions[session_id] = get_initial_state()
        
        state = sessions[session_id].copy()
        
        # Add user message
        user_message = HumanMessage(content=request.message)
        state["messages"] = state.get("messages", []) + [user_message]
        state["user_message"] = request.message
        
        # Config for LangGraph
        config = {"configurable": {"thread_id": session_id}}
        
        logger.info(f"[CHAT] Session: {session_id}, Message: {request.message[:50]}, Auth Status: {state.get('auth_status')}")
        
        # Invoke graph
        result = graph_app.invoke(state, config)
        
        # Update session
        sessions[session_id] = result
        
        # Extract AI response (last AIMessage)
        ai_response = "Maaf, tidak ada respon dari agent."
        for msg in reversed(result.get("messages", [])):
            if isinstance(msg, AIMessage):
                ai_response = msg.content if hasattr(msg, 'content') else str(msg)
                break
        
        logger.info(f"[CHAT] Response: {ai_response[:50]}, Auth Status: {result.get('auth_status')}")
        
        return ChatResponse(
            response=ai_response,
            session_id=session_id,
            auth_status=result.get("auth_status"),
            is_authenticated=result.get("is_authenticated")
        )
        
    except Exception as e:
        logger.error(f"[CHAT] Error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@app.post("/api/upload-ktp")
async def upload_ktp(session_id: str = Form(...), file: UploadFile = File(...)):
    """Handle KTP image upload"""
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
        
        # Update session state with KTP image
        state = sessions[session_id].copy()
        state["ktp_image"] = tmp_file_path
        
        logger.info(f"[UPLOAD_KTP] Session: {session_id}, File: {tmp_file_path}, Auth Status: {state.get('auth_status')}")
        
        # Config for LangGraph
        config = {"configurable": {"thread_id": session_id}}
        
        # Invoke graph with KTP image
        result = graph_app.invoke(state, config)
        
        # Update session
        sessions[session_id] = result
        
        # Extract AI response
        ai_response = "KTP berhasil diupload, sedang diproses..."
        for msg in reversed(result.get("messages", [])):
            if isinstance(msg, AIMessage):
                ai_response = msg.content if hasattr(msg, 'content') else str(msg)
                break
        
        logger.info(f"[UPLOAD_KTP] Response: {ai_response[:50]}, Auth Status: {result.get('auth_status')}")
        
        return JSONResponse(content={
            "success": True,
            "message": "KTP uploaded successfully",
            "response": ai_response,
            "auth_status": result.get("auth_status"),
            "extracted_nik": result.get("extracted_nik")
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[UPLOAD_KTP] Error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error uploading KTP: {str(e)}")


@app.get("/api/clear-session/{session_id}")
async def clear_session(session_id: str):
    """Clear session and cleanup"""
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


@app.get("/", response_class=HTMLResponse)
async def get_ui():
    """Simple chat UI for testing"""
    html_content = """
<!DOCTYPE html>
<html lang="id">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Chat Agent - Testing</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #f5f5f5;
            height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
        }
        .container {
            background: white;
            width: 100%;
            max-width: 800px;
            height: 100vh;
            max-height: 900px;
            display: flex;
            flex-direction: column;
            box-shadow: 0 0 20px rgba(0,0,0,0.1);
        }
        .header {
            padding: 16px 20px;
            border-bottom: 1px solid #e5e5e5;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .header h1 { font-size: 18px; font-weight: 600; }
        .clear-btn {
            background: none;
            border: none;
            color: #666;
            cursor: pointer;
            font-size: 14px;
            padding: 4px 8px;
        }
        .clear-btn:hover { color: #000; }
        .messages {
            flex: 1;
            overflow-y: auto;
            padding: 20px;
            background: #f7f7f8;
        }
        .message {
            margin-bottom: 16px;
            display: flex;
        }
        .message.user { justify-content: flex-end; }
        .message.agent { justify-content: flex-start; }
        .message-content {
            max-width: 70%;
            padding: 12px 16px;
            border-radius: 12px;
            word-wrap: break-word;
            line-height: 1.5;
        }
        .message.user .message-content {
            background: #19c37d;
            color: white;
        }
        .message.agent .message-content {
            background: white;
            color: #333;
            box-shadow: 0 1px 2px rgba(0,0,0,0.1);
        }
        .input-area {
            padding: 16px 20px;
            background: white;
            border-top: 1px solid #e5e5e5;
        }
        .input-form {
            display: flex;
            gap: 8px;
            align-items: flex-end;
        }
        .input {
            flex: 1;
            padding: 12px 16px;
            border: 1px solid #d1d5db;
            border-radius: 24px;
            font-size: 16px;
            outline: none;
            resize: none;
            max-height: 120px;
        }
        .input:focus { border-color: #19c37d; }
        .upload-btn {
            padding: 12px 16px;
            background: #f0f0f0;
            border: 1px solid #d1d5db;
            border-radius: 24px;
            cursor: pointer;
            font-size: 20px;
            height: 48px;
            min-width: 48px;
            display: none;
        }
        .upload-btn:hover { background: #e0e0e0; }
        .send-btn {
            padding: 12px 24px;
            background: #19c37d;
            color: white;
            border: none;
            border-radius: 24px;
            font-size: 16px;
            font-weight: 500;
            cursor: pointer;
            height: 48px;
        }
        .send-btn:hover:not(:disabled) { background: #16a085; }
        .send-btn:disabled { opacity: 0.6; cursor: not-allowed; }
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
        .empty { text-align: center; color: #999; padding: 40px; }
        .file-input { display: none; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Chat Agent - Testing</h1>
            <button class="clear-btn" onclick="clearSession()">Clear</button>
        </div>
        <div class="messages" id="messages">
            <div class="empty">Mulai percakapan...</div>
        </div>
        <div class="input-area">
            <form class="input-form" onsubmit="sendMessage(event)">
                <input type="file" id="fileInput" class="file-input" accept="image/*" onchange="uploadKTP(event)">
                <button type="button" class="upload-btn" id="uploadBtn" onclick="document.getElementById('fileInput').click()">📷</button>
                <textarea class="input" id="messageInput" placeholder="Ketik pesan..." rows="1" oninput="autoResize(this)"></textarea>
                <button type="submit" class="send-btn" id="sendBtn">Kirim</button>
            </form>
        </div>
    </div>

    <script>
        let sessionId = null;
        
        function autoResize(el) {
            el.style.height = 'auto';
            el.style.height = Math.min(el.scrollHeight, 120) + 'px';
        }
        
        function showUploadBtn() {
            document.getElementById('uploadBtn').style.display = 'block';
        }
        
        function hideUploadBtn() {
            document.getElementById('uploadBtn').style.display = 'none';
        }
        
        function needsKTP(text) {
            const keywords = ['ktp', 'upload', 'foto', 'kirimkan', 'kirim'];
            const lower = text.toLowerCase();
            return keywords.some(k => lower.includes(k));
        }
        
        async function uploadKTP(event) {
            const file = event.target.files[0];
            if (!file || !sessionId) return;
            
            if (!file.type.startsWith('image/')) {
                alert('File harus gambar!');
                return;
            }
            
            addMessage('Mengupload KTP...', 'agent', true);
            
            const formData = new FormData();
            formData.append('session_id', sessionId);
            formData.append('file', file);
            
            try {
                const res = await fetch('/api/upload-ktp', {
                    method: 'POST',
                    body: formData
                });
                const data = await res.json();
                
                removeLastMessage();
                
                if (data.success) {
                    addMessage('KTP berhasil diupload', 'user');
                    if (data.response) {
                        addMessage(data.response, 'agent');
                        if (needsKTP(data.response) || data.response.includes('benar')) {
                            showUploadBtn();
                        } else {
                            hideUploadBtn();
                        }
                    }
                } else {
                    addMessage('Gagal upload KTP', 'agent');
                }
            } catch (error) {
                removeLastMessage();
                addMessage('Error: ' + error.message, 'agent');
            }
            
            event.target.value = '';
        }
        
        async function sendMessage(event) {
            event.preventDefault();
            const input = document.getElementById('messageInput');
            const msg = input.value.trim();
            if (!msg) return;
            
            input.disabled = true;
            document.getElementById('sendBtn').disabled = true;
            
            document.querySelector('.empty')?.remove();
            addMessage(msg, 'user');
            input.value = '';
            input.style.height = 'auto';
            addMessage('', 'agent', true);
            
            try {
                const res = await fetch('/api/chat', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ message: msg, session_id: sessionId })
                });
                const data = await res.json();
                
                if (data.session_id) sessionId = data.session_id;
                
                removeLastMessage();
                if (data.response) {
                    addMessage(data.response, 'agent');
                    if (needsKTP(data.response)) {
                        showUploadBtn();
                    } else {
                        hideUploadBtn();
                    }
                }
            } catch (error) {
                removeLastMessage();
                addMessage('Error: ' + error.message, 'agent');
            } finally {
                input.disabled = false;
                document.getElementById('sendBtn').disabled = false;
                input.focus();
            }
        }
        
        function addMessage(text, type, loading = false) {
            const div = document.createElement('div');
            div.className = `message ${type}`;
            const content = document.createElement('div');
            content.className = 'message-content';
            if (loading) {
                content.innerHTML = '<div class="loading"></div>';
                div.id = 'loading-msg';
            } else {
                content.textContent = text;
            }
            div.appendChild(content);
            document.getElementById('messages').appendChild(div);
            document.getElementById('messages').scrollTop = document.getElementById('messages').scrollHeight;
        }
        
        function removeLastMessage() {
            const el = document.getElementById('loading-msg');
            if (el) el.remove();
        }
        
        async function clearSession() {
            if (sessionId) {
                try {
                    await fetch(`/api/clear-session/${sessionId}`);
                } catch (e) {}
            }
            sessionId = null;
            hideUploadBtn();
            document.getElementById('messages').innerHTML = '<div class="empty">Mulai percakapan...</div>';
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
