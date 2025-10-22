"""
AI Therapy Chatbot - Gradio Frontend
Connects to FastAPI backend for session management and chat
Now supports email and name inputs
"""

import gradio as gr
import requests
from typing import List, Dict
import uuid

# ============================================
# Configuration
# ============================================

API_BASE_URL = "http://localhost:8000"  # FastAPI backend URL

# ============================================
# Global State Variables
# ============================================

current_user_id = None
current_session_id = None
current_session_name = None

# ============================================
# Helper Functions
# ============================================

def generate_session_id() -> str:
    """Generate a unique session ID"""
    return f"sess_{uuid.uuid4().hex[:8]}"

def check_backend_health() -> bool:
    """Check if backend is running"""
    try:
        response = requests.get(f"{API_BASE_URL}/", timeout=2)
        return response.status_code == 200
    except:
        return False

# ============================================
# API Communication Functions
# ============================================

def create_new_session(user_id: str, name: str) -> tuple:
    """
    Create a new chat session
    Returns: (session_id, session_name, error_message)
    """
    try:
        response = requests.post(
            f"{API_BASE_URL}/sessions/new",
            json={"user_id": user_id, "name": name},
            timeout=5
        )
        
        if response.status_code == 200:
            data = response.json()
            return data["session_id"], data["session_name"], None
        else:
            return None, None, f"Error: {response.status_code}"
    
    except requests.exceptions.ConnectionError:
        return None, None, "Cannot connect to backend. Is the FastAPI server running?"
    except Exception as e:
        return None, None, f"Error: {str(e)}"

def send_message_to_api(user_id: str, session_id: str, message: str) -> tuple:
    """
    Send message to backend and get AI response
    Returns: (ai_response, error_message)
    """
    try:
        response = requests.post(
            f"{API_BASE_URL}/chat",
            json={
                "user_id": user_id,
                "session_id": session_id,
                "message": message
            },
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            return data["ai_response"], None
        else:
            return None, f"Error: {response.status_code} - {response.text}"
    
    except requests.exceptions.ConnectionError:
        return None, "Cannot connect to backend. Is the FastAPI server running?"
    except requests.exceptions.Timeout:
        return None, "Request timed out. Please try again."
    except Exception as e:
        return None, f"Error: {str(e)}"

def get_user_sessions(user_id: str) -> tuple:
    """
    Get all sessions for a user
    Returns: (sessions_list, error_message)
    """
    try:
        response = requests.get(
            f"{API_BASE_URL}/users/{user_id}/sessions",
            timeout=5
        )
        
        if response.status_code == 200:
            sessions = response.json()
            return sessions, None
        else:
            return [], f"Error: {response.status_code}"
    
    except Exception as e:
        return [], f"Error: {str(e)}"

def get_conversation(user_id: str, session_id: str) -> tuple:
    """
    Get full conversation for a session
    Returns: (messages, session_name, error_message)
    """
    try:
        response = requests.get(
            f"{API_BASE_URL}/conversations/{session_id}",
            params={"user_id": user_id},
            timeout=5
        )
        
        if response.status_code == 200:
            data = response.json()
            return data["messages"], data["session_name"], None
        else:
            return [], None, f"Error: {response.status_code}"
    
    except Exception as e:
        return [], None, f"Error: {str(e)}"

# ============================================
# UI Event Handlers
# ============================================

def start_session(email: str, name: str):
    """
    Handle user login/start with email and name
    """
    global current_user_id, current_session_id, current_session_name
    
    # Validate email
    if not email or email.strip() == "":
        return gr.update(visible=True), gr.update(visible=False), "Please enter your email"
    
    # Validate name
    if not name or name.strip() == "":
        return gr.update(visible=True), gr.update(visible=False), "Please enter your name"
    
    # Basic email validation
    if "@" not in email or "." not in email:
        return gr.update(visible=True), gr.update(visible=False), "Please enter a valid email address"
    
    # Check if backend is running
    if not check_backend_health():
        return gr.update(visible=True), gr.update(visible=False), "⚠️ Backend server is not running! Please start the FastAPI server first."
    
    # Clean the email
    current_user_id = email.strip().lower()
    
    # Create first session automatically
    session_id, session_name, error = create_new_session(current_user_id, name.strip())
    
    if error:
        return gr.update(visible=True), gr.update(visible=False), f"Error: {error}"
    
    current_session_id = session_id
    current_session_name = session_name
    
    # Hide login screen, show chat screen
    return gr.update(visible=False), gr.update(visible=True), ""

def handle_new_chat():
    """
    Handle "New Chat" button click
    """
    global current_session_id, current_session_name
    
    if not current_user_id:
        return [], "Error: No user logged in", gr.update(choices=[])
    
    # Create new session (name is already stored in database)
    session_id, session_name, error = create_new_session(current_user_id, "")
    
    if error:
        return [], f"Error creating session: {error}", gr.update(choices=[])
    
    current_session_id = session_id
    current_session_name = session_name
    
    # Get updated session list
    sessions, _ = get_user_sessions(current_user_id)
    session_choices = [f"{s['session_name']}" for s in sessions]
    
    # Clear chat and update session list
    return [], f"✅ Started {session_name}", gr.update(choices=session_choices, value=session_name)

def load_past_session(session_name: str):
    """
    Load a past session when user clicks on it in sidebar
    """
    global current_session_id, current_session_name
    
    if not session_name or not current_user_id:
        return [], "Please select a session"
    
    # Get all sessions to find the session_id
    sessions, error = get_user_sessions(current_user_id)
    
    if error:
        return [], f"Error loading sessions: {error}"
    
    # Find the session_id for this session_name
    session_id = None
    for s in sessions:
        if s["session_name"] == session_name:
            session_id = s["session_id"]
            break
    
    if not session_id:
        return [], f"Session '{session_name}' not found"
    
    # Get conversation
    messages, sess_name, error = get_conversation(current_user_id, session_id)
    
    if error:
        return [], f"Error loading conversation: {error}"
    
    # Update current session
    current_session_id = session_id
    current_session_name = sess_name
    
    # Convert messages to Gradio chat format
    chat_history = []
    for msg in messages:
        if msg["role"] == "student":
            chat_history.append({"role": "user", "content": msg["content"]})
        else:
            chat_history.append({"role": "assistant", "content": msg["content"]})
    
    return chat_history, f"📂 Loaded {sess_name}"

def chat_with_pritam(message: str, history: List[Dict]):
    """
    Main chat function - sends message and gets AI response
    This is called every time user sends a message
    """
    global current_user_id, current_session_id
    
    if not current_user_id or not current_session_id:
        # Add user message first, then error
        history.append({"role": "user", "content": message})
        history.append({"role": "assistant", "content": "Error: No active session"})
        yield history
        return
    
    # Add user message to history FIRST
    history.append({"role": "user", "content": message})
    yield history
    
    # Send message to backend
    ai_response, error = send_message_to_api(current_user_id, current_session_id, message)
    
    if error:
        # Add error message
        history.append({"role": "assistant", "content": f"⚠️ Error: {error}"})
        yield history
        return
    
    # Add AI response
    history.append({"role": "assistant", "content": ai_response})
    yield history

def refresh_session_list():
    """
    Refresh the session list in sidebar
    """
    if not current_user_id:
        return gr.update(choices=[])
    
    sessions, error = get_user_sessions(current_user_id)
    
    if error:
        return gr.update(choices=[])
    
    session_choices = [s["session_name"] for s in sessions]
    return gr.update(choices=session_choices)

# ============================================
# Build Gradio Interface
# ============================================

with gr.Blocks(title="AI Therapy Practice", theme=gr.themes.Soft()) as demo:
    
    # ============================================
    # Login Screen
    # ============================================
    
    with gr.Column(visible=True) as login_screen:
        gr.Markdown("# 🧠 AI Therapy Client Simulator")
        gr.Markdown("### Practice your therapy skills with Pritam, an AI client")
        gr.Markdown("---")
        
        with gr.Row():
            with gr.Column(scale=1):
                pass  # Empty column for centering
            
            with gr.Column(scale=2):
                gr.Markdown("### Welcome! Please enter your details to begin:")
                email_input = gr.Textbox(
                    label="Your Email",
                    placeholder="e.g., john@gmail.com",
                    lines=1
                )
                name_input = gr.Textbox(
                    label="Your Name",
                    placeholder="e.g., John Smith",
                    lines=1
                )
                login_error = gr.Markdown("")
                start_button = gr.Button("Start Practicing", variant="primary", size="lg")
            
            with gr.Column(scale=1):
                pass  # Empty column for centering
    
    # ============================================
    # Main Chat Screen
    # ============================================
    
    with gr.Column(visible=False) as chat_screen:
        
        gr.Markdown("# 💬 Chat with Pritam")
        
        with gr.Row():
            
            # Left Sidebar
            with gr.Column(scale=1):
                gr.Markdown("### 📚 Your Sessions")
                
                new_chat_btn = gr.Button("➕ New Chat", variant="primary")
                
                session_list = gr.Dropdown(
                    label="Past Sessions",
                    choices=[],
                    interactive=True,
                    container=True
                )
                
                status_message = gr.Markdown("")
                
                gr.Markdown("---")
                gr.Markdown("**Current User:**")
                user_display = gr.Markdown("")
                
                refresh_btn = gr.Button("🔄 Refresh Sessions", size="sm")
            
            # Main Chat Area
            with gr.Column(scale=3):
                
                gr.Markdown("### Pritam - 20-year-old from Mumbai")
                gr.Markdown("*Recently broke up with his girlfriend. Reserved and hesitant to open up.*")
                
                chatbot = gr.Chatbot(
                    type="messages",
                    height=500,
                    show_copy_button=True,
                    avatar_images=(None, "🧑")  # User has no avatar, AI has emoji
                )
                
                with gr.Row():
                    msg_input = gr.Textbox(
                        label="",
                        placeholder="Type your message as a therapist...",
                        lines=2,
                        scale=4
                    )
                    send_btn = gr.Button("Send", variant="primary", scale=1)
                
                gr.Markdown("---")
                gr.Markdown("💡 **Tip:** Be empathetic, ask open-ended questions, and give Pritam space to share.")
    
    # ============================================
    # Event Handlers / Interactions
    # ============================================
    
    # Login button
    start_button.click(
        fn=start_session,
        inputs=[email_input, name_input],
        outputs=[login_screen, chat_screen, login_error]
    ).then(
        fn=lambda: gr.update(value=f"👤 {current_user_id}"),
        outputs=[user_display]
    ).then(
        fn=refresh_session_list,
        outputs=[session_list]
    )
    
    # New chat button
    new_chat_btn.click(
        fn=handle_new_chat,
        outputs=[chatbot, status_message, session_list]
    )
    
    # Session dropdown - load past session
    session_list.change(
        fn=load_past_session,
        inputs=[session_list],
        outputs=[chatbot, status_message]
    )
    
    # Send message (both button click and Enter key)
    msg_input.submit(
        fn=chat_with_pritam,
        inputs=[msg_input, chatbot],
        outputs=[chatbot]
    ).then(
        fn=lambda: "",
        outputs=[msg_input]
    )
    
    send_btn.click(
        fn=chat_with_pritam,
        inputs=[msg_input, chatbot],
        outputs=[chatbot]
    ).then(
        fn=lambda: "",
        outputs=[msg_input]
    )
    
    # Refresh button
    refresh_btn.click(
        fn=refresh_session_list,
        outputs=[session_list]
    )

# ============================================
# Launch the App
# ============================================

if __name__ == "__main__":
    print("=" * 50)
    print("🚀 Starting AI Therapy Chatbot Frontend")
    print("=" * 50)
    print()
    print("⚠️  IMPORTANT: Make sure FastAPI backend is running!")
    print("   Start backend with: python backend.py")
    print()
    print("=" * 50)
    
    demo.launch(
        server_name="0.0.0.0",
        server_port=7860,
        show_error=True,
        share=False
    )
