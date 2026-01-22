import streamlit as st

st.set_page_config(
    page_title="Nutrion",
    layout="wide",
    page_icon="🥗",
)
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import uuid
from datetime import datetime, timedelta

from auth import AuthManager
from database import DatabaseManager
from chat_manager import ChatManager
from utils import (
    generate_mock_nutrition_data,
    create_nutrition_charts,
    extract_ingredients_free_text,
    compute_nutrition,
)
import os
import sys
from dotenv import load_dotenv
import asyncio
import json
from PIL import Image
from food_vision import NutriNetVision
from services.rag_service import init_rag
from services.agent_service import build_agent
from components.agent_trace import render_agent_trace
from ui_pages.plan_page import render_plan_page
from ui_pages.analyzer_page import render_analyzer_page
from ui_pages.dashboard_page import render_dashboard_page
from ui_pages.chat_page import render_chat_page
from agents.orchestrator import AgentOrchestrator
from agents.tools import make_retrieval_tool, make_macro_calculator_tool
from agents.verifier import basic_verifier

load_dotenv()

try:
    if hasattr(st, "secrets") and st.secrets:
        for k, v in st.secrets.items():
            # Only map flat key/value pairs; skip nested tables
            if isinstance(v, (dict, list)):
                continue
            os.environ.setdefault(k, str(v))
except Exception:
    # Secrets may not be available locally; ignore
    pass

os.environ.setdefault(
    "USER_AGENT",
    "Nutrion/0.1 (https://github.com/zawlinnhtet03/nutrition-diet-assistant)",
)

# Hide native browser overlays only (keep Streamlit's show-password toggle visible)
st.markdown(
    """
    <style>
      /* Edge/IE native reveal & clear icons */
      input[type="password"]::-ms-reveal,
      input[type="password"]::-ms-clear { display: none; }
    </style>
    """,
    unsafe_allow_html=True,
)

from meal import get_plan_json

# Make local RAG package importable
RAG_SRC = os.path.join(os.path.dirname(__file__), "rag", "src")
if RAG_SRC not in sys.path:
    sys.path.insert(0, RAG_SRC)

# Ensure an event loop exists in Streamlit's worker thread (fixes: 'There is no current event loop')
try:
    asyncio.get_running_loop()
except RuntimeError:
    asyncio.set_event_loop(asyncio.new_event_loop())

# Windows-specific: use selector policy for broader compatibility
if sys.platform.startswith("win") and hasattr(
    asyncio, "WindowsSelectorEventLoopPolicy"
):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# RAG imports (Gemini-based)
try:
    from config_loader import load_config
    from embedding_model import get_gemini_embeddings
    from llm_model import get_gemini_llm
    from vector_store import get_vector_store
    from rag_chain import build_rag_chain
except Exception:
    # Defer import errors to UI when initializing RAG
    pass

# Page configuration moved to top to satisfy Streamlit requirement

# Initialize managers
if "auth_manager" not in st.session_state:
    st.session_state.auth_manager = AuthManager()
if "db_manager" not in st.session_state:
    st.session_state.db_manager = DatabaseManager()
if "chat_manager" not in st.session_state:
    st.session_state.chat_manager = ChatManager()

auth_manager = st.session_state.auth_manager
db_manager = st.session_state.db_manager
# If code changed and the cached instance lacks new methods, refresh it
if not hasattr(db_manager, "save_user_preferences"):
    st.session_state.db_manager = DatabaseManager()
    db_manager = st.session_state.db_manager
chat_manager = st.session_state.chat_manager

# Initialize session state
if "login_time" not in st.session_state:
    st.session_state.login_time = None
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "user_data" not in st.session_state:
    st.session_state.user_data = None
if "chat_messages" not in st.session_state:
    st.session_state.chat_messages = []
if "current_session_id" not in st.session_state:
    st.session_state.current_session_id = None
if "chat_sessions" not in st.session_state:
    st.session_state.chat_sessions = []
if "editing_session_id" not in st.session_state:
    st.session_state.editing_session_id = None
if "rag_initialized" not in st.session_state:
    st.session_state.rag_initialized = False
if "qa_chain" not in st.session_state:
    st.session_state.qa_chain = None
if "rag_error" not in st.session_state:
    st.session_state.rag_error = None
if "llm" not in st.session_state:
    st.session_state.llm = None

if st.session_state.authenticated and st.session_state.login_time:
    if datetime.now() - st.session_state.login_time > timedelta(minutes=30):
        st.session_state.authenticated = False
        st.session_state.user_data = None
        st.session_state.login_time = None
        st.warning("Session expired. Please log in again.")
        st.stop()

# Sidebar for authentication
with st.sidebar:
    st.header("🔐 Authentication")

    if not st.session_state.authenticated:
        auth_tab1, auth_tab2 = st.tabs(["Login", "Sign Up"])

        with auth_tab1:
            st.subheader("Login")
            with st.form(key="login_form", clear_on_submit=False):
                login_email = st.text_input("Email", key="login_email")
                login_password = st.text_input(
                    "Password", type="password", key="login_password"
                )
                login_submitted = st.form_submit_button(
                    "Login", width='stretch'
                )
            if login_submitted:
                if login_email and login_password:
                    user_data = auth_manager.login(login_email, login_password)
                    if user_data:
                        # Clear any existing session data from previous users
                        st.session_state.chat_sessions = []
                        st.session_state.current_session_id = None
                        st.session_state.chat_messages = []

                        st.session_state.authenticated = True
                        st.session_state.user_data = user_data
                        st.session_state.login_time = datetime.now()
                        st.success("Login successful!")
                        st.rerun()
                    else:
                        st.error("Invalid credentials")
                else:
                    st.error("Please fill in all fields")

        with auth_tab2:
            st.subheader("Sign Up")
            st.info("Create a new account to start tracking your nutrition")
            with st.form(key="signup_form", clear_on_submit=False):
                signup_email = st.text_input(
                    "Email", key="signup_email", placeholder="your@email.com"
                )
                signup_password = st.text_input(
                    "Password",
                    type="password",
                    key="signup_password",
                    help="Password must be at least 6 characters",
                )
                full_name = st.text_input(
                    "Full Name", key="signup_name", placeholder="Your Full Name"
                )
                signup_submitted = st.form_submit_button(
                    "Sign Up", width='stretch'
                )
            if signup_submitted:
                if signup_email and signup_password and full_name:
                    if len(signup_password) < 8:
                        st.error("Password must be at least 8 characters long")
                    elif "@" not in signup_email or "." not in signup_email:
                        st.error("Please enter a valid email address")
                    else:
                        with st.spinner("Creating account..."):
                            success = auth_manager.signup(
                                signup_email, signup_password, full_name
                            )
                            # Note: success message is handled in auth_manager.signup()
                else:
                    st.error("Please fill in all fields")
    else:
        user_name = (
            st.session_state.user_data["full_name"]
            if st.session_state.user_data
            else "User"
        )
        st.success(f"Welcome, {user_name}!")
        if st.button("Logout"):
            # Clear all session state related to the current user
            st.session_state.authenticated = False
            st.session_state.user_data = None
            st.session_state.chat_messages = []
            st.session_state.chat_sessions = []
            st.session_state.current_session_id = None
            st.session_state.login_time = None
            if hasattr(st.session_state, "_last_user_id"):
                del st.session_state._last_user_id
            st.rerun()

        st.divider()

# Main app content
if st.session_state.authenticated:
    # App title
    st.markdown(
        """
        <div style="text-align: center;">
            <h3>🍚 <b>Nutrion: Smart Nutrition and Diet Assistant</b> 🥗</h3>
            <p style="font-size: 15px; color: #666;">Your personal nutrition companion powered by AI</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown("---")

    tab1, tab2, tab3, tab4= st.tabs(
        [
            "⚖️ Nutrition Plan",
            "🧠 Ask Anything",
            "🍽 Meal Analyzer",
            "📊 Nutrition Dashboard",
            # "🎙️ Voice Assistant",
        ]
    )

    # Tab 1: AI Nutrition Plan
    with tab1:
        render_plan_page(db_manager)

    # Tab 2: Ask Anything 
    with tab2:
        render_chat_page(db_manager, chat_manager)

    # Tab 3: Meal Analyzer (moved from tab2)
    with tab3:
        render_analyzer_page(db_manager)

    # Tab 4: Nutrition Dashboard
    with tab4:
        render_dashboard_page(db_manager)

else:
    # Welcome screen for non-authenticated users
    st.markdown(
        """
        <div style="text-align: center; padding: 50px;">
            <h2>🍚 <b>Welcome to Nutrion</b> 🥗</h2>
            <h4>Smart Nutrition and Diet Assistant</h4>
            <p style="font-size: 15px; color: #666; margin: 30px 0;">
                Your personal AI-powered nutrition companion for healthier eating habits
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown(
            """
            <div style="background: linear-gradient(90deg, #667eea 0%, #764ba2 100%); padding: 20px; border-radius: 10px; color: white;">
                <div style="text-align:center;">
                    <h4>✨ Features</h4>
                </div>
                <p>  
                    🧠 Ask Anything: General, User Coach, and Agent with trace
                    <br><br>⚖️ Personalized Plan: daily macros and meal suggestions from your profile  
                    <br><br>🍽️ Meal Analyzer: parse free‑text or photo; nutrition via USDA FDC 
                    <br><br>📊 Dashboard: today’s intake vs targets and macro breakdown
                    <br><br>🔐 Secure & Personal: Your data is safe and private
                 </p>
            </div>
            <br>
        """,
            unsafe_allow_html=True,
        )
        st.markdown(
            """
        ### 🚀 Get Started:
        **Please login or sign up using the sidebar to access all features!**
        """
        )

    st.markdown("---")
    st.markdown(
        "<div style='text-align: center; color: #888;'>Powered by AI</div>",
        unsafe_allow_html=True,
    )




    # # Tab 5: Voice Assistant
    # with tab5:
    #     st.header("🎙️ Talk to Me")
    #     st.markdown(
    #         "Have a natural conversation with your nutrition assistant using voice"
    #     )

    #     # Import voice assistant components
    #     try:
    #         import sys
    #         import os
    #         import subprocess
    #         import threading
    #         import time

    #         # Import the voice assistant module
    #         from assembly_nutrition_assistant import AssemblyNutritionAssistant

    #         # Voice interface layout
    #         col1, col2 = st.columns([1, 1])

    #         with col1:
    #             st.markdown(
    #                 """
    #                 <div style="text-align: center; padding: 30px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 15px; color: white; margin-bottom: 20px;">
    #                     <h3>🎤 Voice Input</h3>
    #                     <p>Click the microphone to start speaking</p>
    #                 </div>
    #             """,
    #                 unsafe_allow_html=True,
    #             )

    #             # Voice input controls
    #             voice_col1, voice_col2, voice_col3 = st.columns([1, 2, 1])

    #             # Initialize voice assistant in session state
    #             if "voice_assistant" not in st.session_state:
    #                 st.session_state.voice_assistant = None
    #                 st.session_state.voice_running = False
    #                 st.session_state.voice_output = ""
    #                 st.session_state.voice_logs = []
    #                 st.session_state.selected_device = 0

    #             # Device selection
    #             st.subheader("🎧 Audio Device Selection")
    #             available_devices = [
    #                 "MacBook Pro Microphone (Device 0)",
    #                 "Microsoft Teams Audio (Device 2)",
    #                 "Messenger Loopback Audio (Device 3)",
    #                 "ZoomAudioDevice (Device 4)",
    #             ]
    #             device_names = [
    #                 d.split("(Device ")[0].strip() for d in available_devices
    #             ]
    #             device_indices = [0, 2, 3, 4]

    #             selected_device_name = st.selectbox(
    #                 "Select your microphone:",
    #                 device_names,
    #                 index=0,
    #                 help="Choose the microphone you want to use for voice input",
    #             )
    #             selected_device_index = device_indices[
    #                 device_names.index(selected_device_name)
    #             ]
    #             st.session_state.selected_device = selected_device_index

    #             with voice_col2:
    #                 # Voice assistant status indicator
    #                 if st.session_state.voice_running:
    #                     st.markdown(
    #                         """
    #                         <div style="text-align: center; padding: 20px; background: linear-gradient(135deg, #4CAF50 0%, #45a049 100%); border-radius: 15px; color: white; margin-bottom: 20px;">
    #                             <h3>🎤 Voice Assistant Active</h3>
    #                             <div style="display: flex; justify-content: center; align-items: center; margin: 10px 0;">
    #                                 <div class="wave" style="display: inline-block; width: 4px; height: 20px; background: white; margin: 0 2px; animation: wave 1s infinite ease-in-out;"></div>
    #                                 <div class="wave" style="display: inline-block; width: 4px; height: 20px; background: white; margin: 0 2px; animation: wave 1s infinite ease-in-out; animation-delay: 0.1s;"></div>
    #                                 <div class="wave" style="display: inline-block; width: 4px; height: 20px; background: white; margin: 0 2px; animation: wave 1s infinite ease-in-out; animation-delay: 0.2s;"></div>
    #                                 <div class="wave" style="display: inline-block; width: 4px; height: 20px; background: white; margin: 0 2px; animation: wave 1s infinite ease-in-out; animation-delay: 0.3s;"></div>
    #                                 <div class="wave" style="display: inline-block; width: 4px; height: 20px; background: white; margin: 0 2px; animation: wave 1s infinite ease-in-out; animation-delay: 0.4s;"></div>
    #                             </div>
    #                             <p>Say "RYAN" followed by your question</p>
    #                         </div>
    #                         <style>
    #                         @keyframes wave {
    #                             0%, 100% { transform: scaleY(1); }
    #                             50% { transform: scaleY(1.5); }
    #                         }
    #                         </style>
    #                         """,
    #                         unsafe_allow_html=True,
    #                     )
    #                 else:
    #                     st.markdown(
    #                         """
    #                         <div style="text-align: center; padding: 20px; background: linear-gradient(135deg, #f0f0f0 0%, #e0e0e0 100%); border-radius: 15px; color: #666; margin-bottom: 20px;">
    #                             <h3>🎤 Voice Assistant Inactive</h3>
    #                             <p>Click "Start Voice Assistant" to begin</p>
    #                         </div>
    #                         """,
    #                         unsafe_allow_html=True,
    #                     )

    #                 if st.button(
    #                     "🎤 Start Voice Assistant",
    #                     type="primary",
    #                     width='stretch',
    #                 ):
    #                     if not st.session_state.voice_running:
    #                         try:
    #                             # Set up environment variable for AssemblyAI
    #                             os.environ["ASSEMBLYAI_API_KEY"] = (
    #                                 "32a11032d56d438497638cd2b8e6fd5a"
    #                             )

    #                             # Initialize voice assistant
    #                             model_path = os.path.join(
    #                                 os.path.dirname(__file__),
    #                                 "vosk-model-small-en-us-0.15",
    #                                 "vosk-model-small-en-us-0.15",
    #                             )

    #                             # Define log callback function
    #                             def log_callback(message, log_type):
    #                                 if "voice_logs" not in st.session_state:
    #                                     st.session_state.voice_logs = []
    #                                 st.session_state.voice_logs.append(
    #                                     {
    #                                         "message": message,
    #                                         "type": log_type,
    #                                         "timestamp": datetime.now().strftime(
    #                                             "%H:%M:%S"
    #                                         ),
    #                                     }
    #                                 )

    #                             st.session_state.voice_assistant = (
    #                                 AssemblyNutritionAssistant(
    #                                     model_path=model_path,
    #                                     assembly_key="32a11032d56d438497638cd2b8e6fd5a",
    #                                     nutrition_kb_path=os.path.join(
    #                                         os.path.dirname(__file__),
    #                                         "models",
    #                                         "accurate_nutrition_kb.json",
    #                                     ),
    #                                     device_index=st.session_state.selected_device,
    #                                     log_callback=log_callback,
    #                                 )
    #                             )

    #                             # Start listening in a separate thread
    #                             if st.session_state.voice_assistant.start_listening():
    #                                 st.session_state.voice_running = True
    #                                 st.success(
    #                                     "🎤 Voice assistant started! Say 'RYAN' followed by your question."
    #                                 )
    #                                 st.rerun()
    #                             else:
    #                                 st.error(
    #                                     "Failed to start audio listening. Check your microphone permissions."
    #                                 )
    #                         except Exception as e:
    #                             st.error(f"Failed to start voice assistant: {e}")
    #                     else:
    #                         st.info("Voice assistant is already running!")

    #                 if st.button("⏹️ Stop Voice Assistant", width='stretch'):
    #                     if st.session_state.voice_running:
    #                         st.session_state.voice_running = False
    #                         if st.session_state.voice_assistant:
    #                             st.session_state.voice_assistant.stop_listening()
    #                             st.session_state.voice_assistant.cleanup()
    #                         st.success("Voice assistant stopped")
    #                         st.rerun()
    #                     else:
    #                         st.info("Voice assistant is not running")

    #             # Voice logs display
    #             if st.session_state.voice_logs:
    #                 st.subheader("📝 Voice Conversation Log")
    #                 with st.expander("View Voice Logs", expanded=True):
    #                     for log in reversed(
    #                         st.session_state.voice_logs[-10:]
    #                     ):  # Show last 10 logs
    #                         if log["type"] == "user":
    #                             st.markdown(f"**👤 You:** {log['message']}")
    #                         elif log["type"] == "assistant":
    #                             st.markdown(f"**🤖 Assistant:** {log['message']}")
    #                         elif log["type"] == "system":
    #                             st.markdown(f"**⚙️ System:** {log['message']}")
    #                         elif log["type"] == "tts":
    #                             st.markdown(f"**🔊 Speaking:** {log['message']}")
    #                         elif log["type"] == "error":
    #                             st.markdown(f"**❌ Error:** {log['message']}")
    #                         st.markdown("---")

    #             st.markdown("---")

    #             # Voice settings
    #             st.subheader("⚙️ Voice Settings")
    #             voice_language = st.selectbox(
    #                 "Language",
    #                 [
    #                     "English (US)",
    #                     "English (UK)",
    #                     "Spanish",
    #                     "French",
    #                     "German",
    #                     "Italian",
    #                 ],
    #                 help="Select your preferred language for voice interaction",
    #             )

    #             voice_speed = st.slider(
    #                 "Speech Speed",
    #                 min_value=0.5,
    #                 max_value=2.0,
    #                 value=1.0,
    #                 step=0.1,
    #                 help="Adjust the speed of AI voice responses",
    #             )

    #             voice_pitch = st.selectbox(
    #                 "Voice Type",
    #                 ["Natural", "Friendly", "Professional", "Calm"],
    #                 help="Choose the tone of the AI voice",
    #             )

    #         with col2:
    #             st.markdown(
    #                 """
    #                 <div style="text-align: center; padding: 30px; background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%); border-radius: 15px; color: white; margin-bottom: 20px;">
    #                     <h3>🔊 AI Response</h3>
    #                     <p>Listen to personalized nutrition advice</p>
    #                 </div>
    #             """,
    #                 unsafe_allow_html=True,
    #             )

    #             # AI Response area
    #             with st.container():
    #                 if st.session_state.voice_running:
    #                     st.markdown(
    #                         """
    #                         <div style="background-color: #f8f9fa; padding: 20px; border-radius: 10px; border-left: 4px solid #28a745; min-height: 200px;">
    #                             <h5>💬 AI Assistant Response:</h5>
    #                             <p style="color: #6c757d; font-style: italic;">
    #                                 🎤 Voice assistant is active! Say 'RYAN' followed by your nutrition question.
    #                             </p>
    #                             <div style="margin-top: 20px;">
    #                                 <p><strong>🎯 Example Topics You Can Ask About:</strong></p>
    #                                 <ul>
    #                                     <li>🥗 "RYAN, what should I eat for breakfast?"</li>
    #                                     <li>💪 "RYAN, how much protein do I need daily?"</li>
    #                                     <li>🏃 "RYAN, pre-workout meal suggestions?"</li>
    #                                     <li>😴 "RYAN, foods that help with sleep?"</li>
    #                                     <li>🎂 "RYAN, healthy dessert alternatives?"</li>
    #                                 </ul>
    #                             </div>
    #                         </div>
    #                     """,
    #                         unsafe_allow_html=True,
    #                     )
    #                 else:
    #                     st.markdown(
    #                         """
    #                         <div style="background-color: #f8f9fa; padding: 20px; border-radius: 10px; border-left: 4px solid #6c757d; min-height: 200px;">
    #                             <h5>💬 AI Assistant Response:</h5>
    #                             <p style="color: #6c757d; font-style: italic;">
    #                                 Click "Start Voice Assistant" to begin voice interaction with your nutrition assistant.
    #                             </p>
    #                         </div>
    #                     """,
    #                         unsafe_allow_html=True,
    #                     )

    #             st.markdown("---")

    #             # Voice response controls
    #             response_col1, response_col2 = st.columns(2)
    #             with response_col1:
    #                 if st.button(
    #                     "🔊 Test Voice", type="secondary", width='stretch'
    #                 ):
    #                     if st.session_state.voice_assistant:
    #                         try:
    #                             st.session_state.voice_assistant.tts.speak(
    #                                 "Hello! I'm your nutrition assistant. Say RYAN followed by your question."
    #                             )
    #                             st.success("Voice test completed!")
    #                         except Exception as e:
    #                             st.error(f"Voice test failed: {e}")
    #                     else:
    #                         st.warning("Please start the voice assistant first!")

    #             with response_col2:
    #                 if st.button("📋 Save Conversation", width='stretch'):
    #                     st.success("Conversation saved to your chat history!")

    #         st.markdown("---")

    #         # Instructions
    #         st.subheader("📜 How to Use Voice Assistant")
    #         with st.expander("🗣️ Voice Assistant Instructions", expanded=True):
    #             st.markdown(
    #                 """
    #             **Getting Started:**
    #             1. Click "Start Voice Assistant" to initialize the voice system
    #             2. Wait for the confirmation message
    #             3. Say "RYAN" followed by your nutrition question
    #             4. The assistant will respond with voice and text
    #             5. Say "stop listening" to end the session
                
    #             **Example Commands:**
    #             - "RYAN, how many calories in an apple?"
    #             - "RYAN, what's a good post-workout meal?"
    #             - "RYAN, create a 7-day meal plan"
    #             - "RYAN, how much protein do I need?"
                
    #             **Troubleshooting:**
    #             - Make sure your microphone is working
    #             - Speak clearly and wait for the wake word "RYAN"
    #             - If the assistant doesn't respond, try saying "RYAN" again
    #             - Check that your AssemblyAI API key is set correctly
    #             """
    #             )

    #         # Feature information
    #         st.markdown("---")
    #         st.info(
    #             """
    #             🎙️ **Voice Assistant Features:**
                
    #             - 🎤 **Real-time voice recognition** - Speak naturally to ask nutrition questions
    #             - 🔊 **AI voice responses** - Hear personalized advice in natural speech
    #             - 🧠 **Smart nutrition knowledge** - Powered by AssemblyAI and nutrition database
    #             - 💾 **Voice conversation history** - All voice interactions can be saved
    #             - 🎯 **Context awareness** - AI remembers your preferences and dietary needs
    #             - 📱 **Hands-free operation** - Perfect for cooking or exercising
    #             """
    #         )

    #     except ImportError as e:
    #         st.error(f"Voice assistant dependencies not installed: {e}")
    #         st.info(
    #             "Please install the required packages: pip install vosk sounddevice pyttsx3 assemblyai"
    #         )
    #     except Exception as e:
    #         st.error(f"Voice assistant error: {e}")
    #         st.info("Please check your microphone and audio settings.")

    # with tab5:
    #     st.header("📝 Export Report")
    #     st.markdown("Generate and download comprehensive nutrition reports")

    #     st.info("🚧 **Coming Soon!** This feature is under development.")

    #     col1, col2 = st.columns([2, 1])

    #     with col1:
    #         st.markdown("""
    #         ### 📄 What will be included in your report:

    #         - **🍽️ Meal Analysis History:** Complete log of analyzed meals with nutrition breakdowns
    #         - **💬 Chat Conversations:** Your nutrition Q&A sessions with the AI assistant
    #         - **📊 Visual Charts:** Nutrition trends, macronutrient distributions, and progress tracking
    #         - **🎯 Goal Progress:** How well you're meeting your nutrition and health goals
    #         - **💡 Personalized Recommendations:** Tailored advice based on your profile and preferences
    #         - **📈 Weekly/Monthly Summaries:** Comprehensive overview of your nutrition journey

    #         ### 🎨 Report Formats (Future):
    #         - **PDF Report:** Professional, printable format
    #         - **Interactive Dashboard:** Shareable web version
    #         - **CSV Data Export:** Raw data for your own analysis
    #         """)

    #     with col2:
    #         st.markdown("### 🔧 Export Options")

    #         report_type = st.selectbox(
    #             "Report Type",
    #             ["Weekly Summary", "Monthly Report", "Custom Date Range", "Complete History"]
    #         )

    #         if report_type == "Custom Date Range":
    #             start_date = st.date_input("Start Date")
    #             end_date = st.date_input("End Date")

    #         include_charts = st.checkbox("Include Charts & Visualizations", value=True)
    #         include_chat = st.checkbox("Include Chat History", value=True)
    #         include_photos = st.checkbox("Include Meal Photos", value=False)

    #         st.markdown("---")

    #         if st.button("📄 Download Nutrition Report (Coming soon!)", type="primary", disabled=True):
    #             st.info("This feature will be available in the next update!")

    #         st.markdown("""
    #         <div style="background-color: #f0f2f6; padding: 15px; border-radius: 10px; margin-top: 20px;">
    #             <h4>📧 Get Notified</h4>
    #             <p>Want to be the first to know when report generation is ready?
    #             We'll notify you via email when this feature launches!</p>
    #         </div>
    #         """, unsafe_allow_html=True)

    # with tab6:
    #     st.header("🎙️ Talk to Me")
    #     # st.markdown(
    #     #     "Have a natural conversation with your nutrition assistant using voice"
    #     # )

    #     # Voice interface layout
    #     col1, col2 = st.columns([1, 1])

    #     with col1:
    #         st.markdown(
    #             """
    #             <div style="text-align: center; padding: 30px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 15px; color: white; margin-bottom: 20px;">
    #                 <h3>🎤 Voice Input</h3>
    #                 <p>Click the microphone to start speaking</p>
    #             </div>
    #         """,
    #             unsafe_allow_html=True,
    #         )

    #         # Voice input controls
    #         voice_col1, voice_col2, voice_col3 = st.columns([1, 2, 1])
    #         with voice_col2:
    #             if st.button(
    #                 "🎤 Start Recording", type="primary", use_container_width=True
    #             ):
    #                 st.info("🎙️ Voice recording feature coming soon!")

    #             if st.button("⏹️ Stop Recording", use_container_width=True):
    #                 st.info("Recording stopped")

    #             if st.button("▶️ Play Recording", use_container_width=True):
    #                 st.info("Playing your recording...")

    #         st.markdown("---")

    #         # Voice settings
    #         st.subheader("⚙️ Voice Settings")
    #         voice_language = st.selectbox(
    #             "Language",
    #             [
    #                 "English (US)",
    #                 "English (UK)",
    #                 "Spanish",
    #                 "French",
    #                 "German",
    #                 "Italian",
    #             ],
    #             help="Select your preferred language for voice interaction",
    #         )

    #         voice_speed = st.slider(
    #             "Speech Speed",
    #             min_value=0.5,
    #             max_value=2.0,
    #             value=1.0,
    #             step=0.1,
    #             help="Adjust the speed of AI voice responses",
    #         )

    #         voice_pitch = st.selectbox(
    #             "Voice Type",
    #             ["Natural", "Friendly", "Professional", "Calm"],
    #             help="Choose the tone of the AI voice",
    #         )

    #     with col2:
    #         st.markdown(
    #             """
    #             <div style="text-align: center; padding: 30px; background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%); border-radius: 15px; color: white; margin-bottom: 20px;">
    #                 <h3>🔊 AI Response</h3>
    #                 <p>Listen to personalized nutrition advice</p>
    #             </div>
    #         """,
    #             unsafe_allow_html=True,
    #         )

    #         # AI Response area
    #         with st.container():
    #             st.markdown(
    #                 """
    #                 <div style="background-color: #f8f9fa; padding: 20px; border-radius: 10px; border-left: 4px solid #28a745; min-height: 200px;">
    #                     <h5>💬 AI Assistant Response:</h5>
    #                     <p style="color: #6c757d; font-style: italic;">
    #                         Your AI nutrition assistant will respond here with personalized advice based on your voice input.
    #                     </p>
    #                     <div style="margin-top: 20px;">
    #                         <p><strong>🎯 Example Topics You Can Ask About:</strong></p>
    #                         <ul>
    #                             <li>🥗 "What should I eat for breakfast?"</li>
    #                             <li>💪 "How much protein do I need daily?"</li>
    #                             <li>🏃 "Pre-workout meal suggestions?"</li>
    #                             <li>😴 "Foods that help with sleep?"</li>
    #                             <li>🎂 "Healthy dessert alternatives?"</li>
    #                         </ul>
    #                     </div>
    #                 </div>
    #             """,
    #             unsafe_allow_html=True,
    #         )

    #         st.markdown("---")

    #         # Voice response controls
    #         response_col1, response_col2 = st.columns(2)
    #         with response_col1:
    #             if st.button(
    #                 "🔊 Play AI Response", type="secondary", use_container_width=True
    #             ):
    #                 st.info("🔊 AI voice response feature coming soon!")

    #         with response_col2:
    #             if st.button("📋 Save Conversation", use_container_width=True):
    #                 st.success("Conversation saved to your chat history!")

    #     st.markdown("---")

    #     # Conversation history for voice interactions
    #     st.subheader("📜 Voice Conversation History")

    #     # Mock conversation history
    #     with st.expander("🗣️ Recent Voice Conversations", expanded=False):
    #         conversation_history = [
    #             {
    #                 "timestamp": "2024-01-15 14:30",
    #                 "user_input": "What's a good post-workout meal?",
    #                 "ai_response": "For post-workout recovery, I recommend a combination of protein and carbohydrates. Try grilled chicken with quinoa and vegetables, or a protein smoothie with banana and Greek yogurt.",
    #             },
    #             {
    #                 "timestamp": "2024-01-15 10:15",
    #                 "user_input": "How much water should I drink daily?",
    #                 "ai_response": "Generally, aim for 8-10 glasses of water daily, but this can vary based on your activity level, climate, and body size. If you're active, you'll need more to replace fluids lost through sweat.",
    #             },
    #             {
    #                 "timestamp": "2024-01-14 16:45",
    #                 "user_input": "Are there any healthy midnight snack options?",
    #                 "ai_response": "For late-night snacking, choose light, easily digestible options like Greek yogurt with berries, a small handful of nuts, or herbal tea with a piece of fruit.",
    #             },
    #         ]

    #         for i, conv in enumerate(conversation_history):
    #             with st.container():
    #                 st.markdown(
    #                     f"""
    #                     <div style="background-color: #f1f3f4; padding: 15px; border-radius: 8px; margin-bottom: 10px;">
    #                         <p style="color: #666; font-size: 12px; margin-bottom: 8px;">📅 {conv['timestamp']}</p>
    #                         <div style="background-color: #e3f2fd; padding: 10px; border-radius: 5px; margin-bottom: 8px;">
    #                             <strong>🗣️ You:</strong> {conv['user_input']}
    #                         </div>
    #                         <div style="background-color: #f3e5f5; padding: 10px; border-radius: 5px;">
    #                             <strong>🤖 AI:</strong> {conv['ai_response']}
    #                         </div>
    #                     </div>
    #                 """,
    #                     unsafe_allow_html=True,
    #                 )

    #     # Feature information
    #     st.markdown("---")
    #     st.info(
    #         """
    #         🚧 **Voice Features Coming Soon!**

    #         This voice interface will include:
    #         - 🎤 **Real-time voice recognition** - Speak naturally to ask nutrition questions
    #         - 🔊 **AI voice responses** - Hear personalized advice in natural speech
    #         - 🌐 **Multi-language support** - Communicate in your preferred language
    #         - 💾 **Voice conversation history** - All voice interactions saved automatically
    #         - 🎯 **Context awareness** - AI remembers your preferences and dietary needs
    #         - 📱 **Mobile optimized** - Perfect for hands-free nutrition guidance
    #     """
    #     )




