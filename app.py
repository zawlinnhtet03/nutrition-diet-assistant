import streamlit as st
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

# Load .env and set env defaults BEFORE importing any RAG modules
load_dotenv()
os.environ.setdefault("USER_AGENT", "NutriBench/0.1 (https://github.com/zawlinnhtet03/nutrition-diet-assistant)")
# Strongly disable Chroma telemetry at process start
os.environ.setdefault("CHROMA_TELEMETRY_DISABLED", "1")
os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")
os.environ.setdefault("CHROMA_TELEMETRY_IMPLEMENTATION", "noop")

# Import Mistral-based planner AFTER env is loaded
from test import get_plan_json

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
if sys.platform.startswith("win") and hasattr(asyncio, "WindowsSelectorEventLoopPolicy"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# RAG imports (Gemini-based)
try:
    from config_loader import load_config
    from embedding_model import get_gemini_embeddings
    from llm_model import get_gemini_llm
    from vector_store import get_chroma_vector_store
    from rag_chain import build_rag_chain
except Exception:
    # Defer import errors to UI when initializing RAG
    pass

# Page configuration
st.set_page_config(
    page_title="NutriBench", 
    layout="wide",
    page_icon="🥗"
)

# Initialize managers
if 'auth_manager' not in st.session_state:
    st.session_state.auth_manager = AuthManager()
if 'db_manager' not in st.session_state:
    st.session_state.db_manager = DatabaseManager()
if 'chat_manager' not in st.session_state:
    st.session_state.chat_manager = ChatManager()

auth_manager = st.session_state.auth_manager
db_manager = st.session_state.db_manager
# If code changed and the cached instance lacks new methods, refresh it
if not hasattr(db_manager, 'save_user_preferences'):
    st.session_state.db_manager = DatabaseManager()
    db_manager = st.session_state.db_manager
chat_manager = st.session_state.chat_manager

# Initialize session state
if 'login_time' not in st.session_state:
    st.session_state.login_time = None
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'user_data' not in st.session_state:
    st.session_state.user_data = None
if 'chat_messages' not in st.session_state:
    st.session_state.chat_messages = []
if 'current_session_id' not in st.session_state:
    st.session_state.current_session_id = None
if 'chat_sessions' not in st.session_state:
    st.session_state.chat_sessions = []
if 'editing_session_id' not in st.session_state:
    st.session_state.editing_session_id = None
if 'rag_initialized' not in st.session_state:
    st.session_state.rag_initialized = False
if 'qa_chain' not in st.session_state:
    st.session_state.qa_chain = None
if 'rag_error' not in st.session_state:
    st.session_state.rag_error = None
if 'llm' not in st.session_state:
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
                login_password = st.text_input("Password", type="password", key="login_password")
                login_submitted = st.form_submit_button("Login", use_container_width=True)
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
                signup_email = st.text_input("Email", key="signup_email", placeholder="your@email.com")
                signup_password = st.text_input("Password", type="password", key="signup_password", 
                                              help="Password must be at least 6 characters")
                full_name = st.text_input("Full Name", key="signup_name", placeholder="Your Full Name")
                signup_submitted = st.form_submit_button("Sign Up", use_container_width=True)
            if signup_submitted:
                if signup_email and signup_password and full_name:
                    if len(signup_password) < 8:
                        st.error("Password must be at least 8 characters long")
                    elif "@" not in signup_email or "." not in signup_email:
                        st.error("Please enter a valid email address")
                    else:
                        with st.spinner("Creating account..."):
                            success = auth_manager.signup(signup_email, signup_password, full_name)
                            # Note: success message is handled in auth_manager.signup()
                else:
                    st.error("Please fill in all fields")
    else:
        user_name = st.session_state.user_data['full_name'] if st.session_state.user_data else 'User'
        st.success(f"Welcome, {user_name}!")
        if st.button("Logout"):
            # Clear all session state related to the current user
            st.session_state.authenticated = False
            st.session_state.user_data = None
            st.session_state.chat_messages = []
            st.session_state.chat_sessions = []
            st.session_state.current_session_id = None
            st.session_state.login_time = None
            if hasattr(st.session_state, '_last_user_id'):
                del st.session_state._last_user_id
            st.rerun()
        
        st.divider()
        st.subheader("⚙️ Settings")
        st.info("User preferences and settings will be available here in future updates.")

# Main app content
if st.session_state.authenticated:
    # App title
    st.markdown(
        """
        <div style="text-align: center;">
            <h3>🥗 <b>NutriBench: Smart Nutrition and Diet Assistant</b> 🥗</h3>
            <p style="font-size: 15px; color: #666;">Your personal nutrition companion powered by AI</p>
        </div>
        """, 
        unsafe_allow_html=True
    )
    st.markdown("---")
    
    # Create tabs
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["🧠 Ask Anything", "Nutrition Plan", "🍽 Meal Analyzer", "📊 Nutrition Dashboard", "📝 Export Report", "🎙️ Talk to Me"])
    
    # Tab 1: Ask Anything (ChatGPT-like Interface)
    with tab1:
        # Create two columns for chat sessions and chat interface
        col1, col2 = st.columns([0.6, 3.4], gap="medium")

        with col1:
            st.subheader("💬 Chat Sessions")

            # New chat button
            if st.button("+ New Chat", type="primary", use_container_width=True):
                if st.session_state.user_data:
                    new_session_id = chat_manager.create_new_chat_session(
                        st.session_state.user_data['id']
                    )
                    if new_session_id:
                        st.session_state.current_session_id = new_session_id
                        st.session_state.chat_sessions = chat_manager.get_user_chat_sessions(
                            st.session_state.user_data['id']
                        )
                        st.rerun()
                        
            # Load user's chat sessions
            if st.session_state.user_data:
                # Check if we need to reload sessions (either no sessions or user changed)
                current_user_id = st.session_state.user_data['id']
                if (not st.session_state.chat_sessions or 
                    not hasattr(st.session_state, '_last_user_id') or 
                    st.session_state._last_user_id != current_user_id):
                    
                    st.session_state.chat_sessions = chat_manager.get_user_chat_sessions(current_user_id)
                    st.session_state._last_user_id = current_user_id
                    
                    # Debug: Show current user info
                    # if st.session_state.chat_sessions:
                    #     # st.info(f"Loaded {len(st.session_state.chat_sessions)} chat sessions for user: {current_user_id}")
                    #     st.info(f"Loaded {len(st.session_state.chat_sessions)} messages")
                    # else:
                    #     st.info(f"No chat sessions found for user: {current_user_id}")
                    st.info("Loaded messages")
            # Display chat sessions
            if st.session_state.chat_sessions:
                st.write("**Recent Chats:**")
                for session in st.session_state.chat_sessions:
                    session_id = session['id']
                    title = session['title']
                    is_current = session_id == st.session_state.current_session_id

                    # Session button with styling
                    button_type = "primary" if is_current else "secondary"
                    if st.button(
                        f"{'🟢 ' if is_current else '💬 '}{title[:25]}" + ("..." if len(title) > 25 else ""),
                        key=f"session_{session_id}",
                        type=button_type,
                        use_container_width=True
                    ):
                        st.session_state.current_session_id = session_id
                        st.rerun()

                    # Show edit/delete options
                    if is_current:
                        # If this session is in edit mode, show input + actions
                        if st.session_state.editing_session_id == session_id:
                            with st.form(key=f"edit_form_{session_id}", clear_on_submit=False):
                                new_title = st.text_input(
                                    "Edit title",
                                    value=title,
                                    key=f"title_edit_{session_id}"
                                )
                                save_pressed = st.form_submit_button("Save", use_container_width=True)

                                cancel_pressed = st.form_submit_button("Cancel", use_container_width=True)
                                if cancel_pressed:
                                    st.session_state.editing_session_id = None
                                    st.rerun()
                            # col_cancel, _ = st.columns(2)
                            # with col_cancel:
                            #     if st.button("Cancel", key=f"cancel_{session_id}"):
                            #         st.session_state.editing_session_id = None
                            #         st.rerun()
                            if save_pressed:
                                if st.session_state.user_data and new_title.strip():
                                    updated = chat_manager.update_chat_session_title(
                                        session_id,
                                        st.session_state.user_data['id'],
                                        new_title.strip()
                                    )
                                    if updated:
                                        # Refresh sessions and exit edit mode
                                        st.session_state.chat_sessions = chat_manager.get_user_chat_sessions(
                                            st.session_state.user_data['id']
                                        )
                                        st.session_state.editing_session_id = None
                                        st.rerun()
                                    else:
                                        st.error("Failed to update title")
                                else:
                                    st.warning("Title cannot be empty")
                        else:
                            col_a, col_b = st.columns(2)
                            with col_a:
                                if st.button("✏️", key=f"edit_{session_id}", help="Edit title"):
                                    st.session_state.editing_session_id = session_id
                                    st.rerun()
                            with col_b:
                                if st.button("🗑️", key=f"delete_{session_id}", help="Delete chat"):
                                    if st.session_state.user_data and chat_manager.delete_chat_session(session_id, st.session_state.user_data['id']):
                                        st.session_state.chat_sessions = chat_manager.get_user_chat_sessions(
                                            st.session_state.user_data['id']
                                        )
                                        st.session_state.current_session_id = None
                                        st.rerun()
            else:
                st.info("No chat sessions yet. Start a new chat!")

        
        with col2:            
            # --- Header ---
            st.markdown("""
                <div style='text-align:center'>
                    <h4><b>NutriBench AI Chat Assistant</b></h4>
                    <p style="color:gray;">Ask anything about nutrition, meals, or health goals</p>
                    <br>
                </div>
            """, unsafe_allow_html=True)
            

            # Initialize Gemini RAG (once per session)
            if not st.session_state.rag_initialized and st.session_state.rag_error is None:
                try:
                    # Ensure an event loop exists in the current Streamlit run context
                    try:
                        asyncio.get_running_loop()
                    except RuntimeError:
                        asyncio.set_event_loop(asyncio.new_event_loop())

                    cfg_path = os.path.join(os.path.dirname(__file__), 'rag', 'config.yaml')
                    cfg = load_config(cfg_path)
                    emb = get_gemini_embeddings(model_name=cfg['gemini']['embedding_model'])
                    vs = get_chroma_vector_store(
                        persist_directory=cfg['data_ingestion']['vector_store']['persist_directory'],
                        collection_name=cfg['data_ingestion']['vector_store']['collection_name'],
                        embedding_function=emb,
                    )
                    retriever = vs.as_retriever(search_kwargs={"k": cfg['rag']['retrieval_k']})
                    llm = get_gemini_llm(model_name=cfg['gemini']['llm_model'])
                    st.session_state.qa_chain = build_rag_chain(
                        llm=llm,
                        retriever=retriever,
                        chain_type=cfg['rag']['chain_type'],
                        return_source_documents=True,
                    )
                    # Diagnostics: show collection stats and DB location
                    try:
                        collection_count = vs._collection.count()
                    except Exception:
                        collection_count = "unknown"
                    db_path = getattr(vs, "_persist_directory", None) or cfg['data_ingestion']['vector_store']['persist_directory']
                    st.info(f"Vector store ready. Docs: {collection_count} • DB: {os.path.abspath(db_path)}")
                    # Store LLM for generic fallback answers when no context is retrieved
                    st.session_state.llm = llm
                    st.session_state.rag_initialized = True
                except Exception as e:
                    st.session_state.rag_error = str(e)

            if st.session_state.rag_error:
                st.error(f"RAG initialization failed: {st.session_state.rag_error}")
                with st.expander("Details / Fix"):
                    st.write("- Ensure GOOGLE_API_KEY is set in your .env or environment")
                    st.write("- Ensure ingestion has run to populate the Chroma store")
                if st.button("↻ Retry RAG init", type="primary"):
                    st.session_state.rag_error = None
                    st.session_state.rag_initialized = False
                    st.session_state.qa_chain = None
                    st.rerun()

            # Check if chat session is selected
            if not st.session_state.current_session_id:
                st.info("Start a new chat session to begin asking questions!")
            else:
                # 1. Render chat history ABOVE the input
                current_messages = chat_manager.get_chat_history(
                    st.session_state.current_session_id,
                    st.session_state.user_data['id'] if st.session_state.user_data else None
                )
                
                # Debug: Show chat history info
                if current_messages:
                    # st.info(f"Loaded {len(current_messages)} messages for session: {st.session_state.current_session_id}")
                    # st.info(f"Loaded {len(current_messages)} messages")
                    st.info("Loaded messages")
                else:
                    st.info(f"No messages found for session: {st.session_state.current_session_id}")
                for idx, message in enumerate(current_messages):
                    with st.chat_message("user"):
                        st.markdown(f"""
                            <div style="background-color:#e0f7fa;padding:12px;border-radius:10px;">
                                {message['user_message']}
                            </div>
                        """, unsafe_allow_html=True)
                        # st.caption(f"📅 {message['created_at']}")

                    with st.chat_message("assistant"):
                        st.markdown(f"""
                            <div style="background-color:#f3f4f6;padding:12px;border-radius:10px;">
                                {message['assistant_response']}
                            </div>
                        """, unsafe_allow_html=True)

                # 2. THEN show input box BELOW
                prompt = st.chat_input("Ask me about the loaded data...")
                if prompt:
                    if st.session_state.user_data:
                        with st.spinner("Thinking..."):
                            assistant_response = ""
                            try:
                                if st.session_state.qa_chain is None:
                                    raise RuntimeError("RAG is not initialized. Check your GOOGLE_API_KEY and vector store.")
                                result = st.session_state.qa_chain.invoke({"query": prompt})
                                # Default response from RAG
                                assistant_response = result.get("result") if isinstance(result, dict) else str(result)

                                # If no sources were retrieved, fall back to a general LLM answer
                                source_docs = []
                                if isinstance(result, dict):
                                    source_docs = result.get("source_documents") or []

                                if not source_docs:
                                    try:
                                        llm = st.session_state.get("llm")
                                        if llm is None:
                                            raise RuntimeError("LLM not available for fallback.")
                                        # Enforce concise fallback: one short, direct sentence
                                        brief_prompt = (
                                            "Answer in ONE short, direct sentence (<=20 words). "
                                            f"Question: {prompt}"
                                        )
                                        generic = llm.invoke(brief_prompt)
                                        if hasattr(generic, "content") and generic.content:
                                            assistant_response = generic.content
                                        else:
                                            assistant_response = str(generic)
                                        # Trim to one sentence and cap length for safety
                                        assistant_response = assistant_response.strip().split("\n")[0]
                                        if "." in assistant_response:
                                            assistant_response = assistant_response.split(".")[0] + "."
                                        assistant_response = assistant_response[:200]
                                        assistant_response += "\n\n(Note: No relevant documents were found; this is a brief general answer.)"
                                    except Exception as e_fallback:
                                        assistant_response = f"RAG returned no sources and fallback failed: {e_fallback}"
                                if not isinstance(assistant_response, str):
                                    assistant_response = str(assistant_response)
                            except Exception as e:
                                assistant_response = f"RAG error: {e}"

                            chat_manager.add_message_to_chat(
                                st.session_state.current_session_id,
                                st.session_state.user_data['id'],
                                prompt,
                                assistant_response
                            )
                            st.rerun()  # To show the updated message list          
                    else:
                        st.error("Please log in to start chatting!")

    # Tab 2: AI Nutrition Plan (moved here)
    with tab2:
        st.header("🧠 AI Nutrition Plan")
        st.markdown("Fill in your details to generate a personalized daily nutrition plan.")

        # Section: Personal Info
        st.markdown("### 👤 Personal Information")
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            age = st.number_input("Age", min_value=10, max_value=100, value=25, key="plan_age")
        with c2:
            gender = st.selectbox("Gender", ["Male", "Female", "Other"], key="plan_gender")
        with c3:
            height = st.number_input("Height (cm)", min_value=120, max_value=220, value=170, key="plan_height")
        with c4:
            weight = st.number_input("Weight (kg)", min_value=35.0, max_value=250.0, value=70.0, step=0.1, key="plan_weight")

        bmi_val = round(weight/((height/100)**2), 1) if height else ""
        st.caption(f"Computed BMI: {bmi_val}")

        # Section: Lifestyle
        st.markdown("### 🏃 Lifestyle")
        l1, l2, l3 = st.columns(3)
        with l1:
            activity_level_plan = st.selectbox(
                "Activity Level",
                ["Sedentary", "Lightly Active", "Moderately Active", "Very Active", "Extremely Active"],
                key="plan_activity_level",
            )
        with l2:
            steps = st.number_input("Daily Steps", min_value=0, value=5000, step=500, key="plan_steps")
        with l3:
            sleep_hours = st.number_input("Sleep Hours", min_value=0.0, max_value=24.0, value=7.0, step=0.5, key="plan_sleep")

        # Section: Goals
        st.markdown("### 🎯 Goals")
        g1, = st.columns(1)
        with g1:
            health_goal_plan = st.selectbox(
                "Primary Goal",
                ["Weight Loss", "Weight Gain", "Muscle Gain", "Maintenance", "General Health"],
                key="plan_goal",
            )

        # Section: Preferences
        st.markdown("### 🍽️ Preferences")
        p1, p2, p3, p4 = st.columns(4)
        with p1:
            allergies = st.text_input("Allergies", placeholder="e.g., peanuts, lactose", key="plan_allergies")
        with p2:
            dietary_prefs = st.text_input("Dietary Preferences", placeholder="e.g., Low-Carb, Vegan", key="plan_dietary")
        with p3:
            cuisine = st.text_input("Preferred Cuisine", placeholder="e.g., Burmese", key="plan_cuisine")
        with p4:
            aversions = st.text_input("Food Aversions", placeholder="e.g., bitter greens", key="plan_aversions")

        # Section: Health Metrics
        st.markdown("### 🏥 Health Metrics (Optional)")
        h1, h2, h3, h4 = st.columns(4)
        with h1:
            chronic = st.text_input("Chronic Disease", placeholder="e.g., None", key="plan_chronic")
        with h2:
            bp = st.text_input("Blood Pressure", placeholder="e.g., Normal", key="plan_bp")
        with h3:
            cholesterol = st.text_input("Cholesterol Level", placeholder="e.g., Normal", key="plan_chol")
        with h4:
            blood_sugar = st.text_input("Blood Sugar Level", placeholder="e.g., Normal", key="plan_bs")

        # Save preferences action
        save_col1, save_col2 = st.columns([1, 3])
        with save_col1:
            save_prefs = st.button("💾 Save Data", use_container_width=True)
        if save_prefs:
            if not st.session_state.user_data:
                st.error("Please log in to save preferences.")
            else:
                prefs = {
                    "Age": age,
                    "Gender": gender,
                    "Height_cm": height,
                    "Weight_kg": weight,
                    "BMI": bmi_val,
                    "Allergies": allergies or "None",
                    "Daily_Steps": int(steps),
                    "Sleep_Hours": sleep_hours,
                    "Current_Goals": health_goal_plan,
                    "Dietary_Preferences": dietary_prefs or "",
                    "Exercise_Frequency": activity_level_plan,
                    "Preferred_Cuisine": cuisine or "",
                    "Food_Aversions": aversions or "",
                    "Chronic_Disease": chronic or "",
                    "Blood_Pressure": bp or "",
                    "Cholesterol_Level": cholesterol or "",
                    "Blood_Sugar_Level": blood_sugar or "",
                }
                # Attach latest generated plan macros if available
                macros = st.session_state.get("plan_macros")
                if isinstance(macros, dict):
                    prefs["Plan_Macros"] = macros
                ok = db_manager.save_user_preferences(st.session_state.user_data['id'], prefs)
                if ok:
                    st.success("Preferences saved.")
                else:
                    st.error("Failed to save preferences.")

        st.divider()

        if st.button("✨ Generate Plan", type="primary"):
            with st.spinner("Generating personalized plan..."):
                try:
                    fields = {
                        "Age": age,
                        "Gender": gender,
                        "Height_cm": height,
                        "Weight_kg": weight,
                        "BMI": bmi_val,
                        "Allergies": allergies or "None",
                        "Daily_Steps": int(steps),
                        "Sleep_Hours": sleep_hours,
                        "Current_Goals": health_goal_plan,
                        "Dietary_Preferences": dietary_prefs or "",
                        "Exercise_Frequency": activity_level_plan,
                        "Preferred_Cuisine": cuisine or "",
                        "Food_Aversions": aversions or "",
                        "Chronic_Disease": chronic or "",
                        "Blood_Pressure": bp or "",
                        "Cholesterol_Level": cholesterol or "",
                        "Blood_Sugar_Level": blood_sugar or "",
                    }
                    plan_json = get_plan_json(fields)
                    if isinstance(plan_json, dict) and all(k in plan_json for k in ["calories","protein_g","carbs_g","fats_g","meals"]):
                        st.success("Plan generated")
                        st.markdown("### 📋 Suggested Plan")
                        st.markdown(f"- Calories: {plan_json.get('calories')} kcal")
                        st.markdown(f"- Protein: {plan_json.get('protein_g')} g")
                        st.markdown(f"- Carbs: {plan_json.get('carbs_g')} g")
                        st.markdown(f"- Fats: {plan_json.get('fats_g')} g")
                        # Save macros to session for later persistence on Save Data
                        st.session_state.plan_macros = {
                            "calories": plan_json.get("calories"),
                            "protein_g": plan_json.get("protein_g"),
                            "carbs_g": plan_json.get("carbs_g"),
                            "fat_g": plan_json.get("fats_g"),
                        }
                        meals = plan_json.get("meals") or {}
                        if isinstance(meals, dict):
                            st.markdown("#### Meals")
                            st.markdown(f"- Breakfast: {meals.get('breakfast','-')}")
                            st.markdown(f"- Lunch: {meals.get('lunch','-')}")
                            st.markdown(f"- Snack: {meals.get('snack','-')}")
                            st.markdown(f"- Dinner: {meals.get('dinner','-')}")
                        notes = plan_json.get("notes")
                        if notes:
                            st.markdown("#### Notes")
                            st.markdown(notes)
                    else:
                        st.warning("Model did not return structured JSON. Showing raw output.")
                        st.write(plan_json)
                except Exception as e:
                    st.error(f"Plan generation failed: {e}. Ensure MISTRAL_API_KEY is set in your environment.")

    # Tab 3: Meal Analyzer (moved from tab2)
    with tab3:
        st.header("🍽 Meal Analyzer")
        st.markdown("Analyze your meals for nutrition content and get personalized recommendations")
        
        # col1, col2 = st.columns([2, 1])
        
        # with col1:
        st.subheader("📝 Meal Description")
        meal_description = st.text_area(
            "Describe your meal(What do you eat today):",
            placeholder="e.g., 1 bowl of chicken curry with rice and salad",
            height=100
        )
        
        st.subheader("📸 Meal Photo (coming soon)")
        uploaded_file = st.file_uploader(
            "Upload a photo of your meal (optional)",
            type=['png', 'jpg', 'jpeg'],
            help="Image upload is disabled for now. Analysis coming soon.",
            disabled=True
        )
        
        if uploaded_file is not None:
            st.image(uploaded_file, caption="Uploaded meal photo", use_column_width=True)
        
        
        st.divider()
        
        # Analysis buttons and results
        btn_col1, btn_col2 = st.columns([1,1])
        analyze_text = btn_col1.button("🔍 Analyze Text", type="primary")
        analyze_image = btn_col2.button("🖼️ Analyze Image (coming soon)", disabled=True)

        if analyze_text:
            if meal_description:
                # with st.spinner("Analyzing your meal (text)..."):
                    # 1) Extract structured ingredients (Mistral -> JSON)
                    extraction = extract_ingredients_free_text(meal_description)
                    # Alert if LLM unavailable or errored
                    if isinstance(extraction, dict):
                        note = extraction.get("notes", "")
                        if note in ("llm_unavailable", "llm_error"):
                            st.error("Text parsing requires Mistral. Please set MISTRAL_API_KEY and try again.")
                            st.stop()
                    items = extraction.get("items", []) if isinstance(extraction, dict) else []
                    if not items:
                        st.warning("Couldn't parse ingredients. Try listing items with quantities, e.g., '150g chicken, 1 cup rice'.")
                        st.stop()

                    # 2) Compute nutrition via USDA (if key present) or local fallback
                    result = compute_nutrition(items)
                    # Alert if USDA FDC unavailable
                    if isinstance(result, dict) and result.get("notes") == "fdc_unavailable":
                        st.error("Nutrition lookup requires USDA FDC. Please set FDC_API_KEY and try again.")
                        st.stop()
                    totals = result.get("totals", {})
                    details = result.get("details", [])
                    if not details or all(v == 0 for v in totals.values()):
                        st.warning("No recognizable foods found. Please refine your description.")
                        st.stop()

                    # 3) Render details per item
                    st.subheader("🧾 Parsed Ingredients")
                    rows = []
                    for d in details:
                        it = d.get("item", {})
                        nut = d.get("nutrients", {})
                        rows.append({
                            "Item": it.get("name","-"),
                            "Qty": it.get("quantity","-"),
                            "Unit": it.get("unit","-"),
                            "kcal": nut.get("calories",0),
                            "Protein(g)": nut.get("protein_g",0),
                            "Carbs(g)": nut.get("carbs_g",0),
                            "Fat(g)": nut.get("fat_g",0),
                            "Fiber(g)": nut.get("fiber_g",0),
                            "Sugar(g)": nut.get("sugar_g",0),
                        })
                    st.dataframe(rows, use_container_width=True)

                    # 4) Totals
                    st.subheader("📊 Estimated Totals")
                    st.info(
                        f"Calories: {totals.get('calories',0)} kcal | "
                        f"Protein: {totals.get('protein_g',0)} g | "
                        f"Carbs: {totals.get('carbs_g',0)} g | "
                        f"Fat: {totals.get('fat_g',0)} g | "
                        f"Fiber: {totals.get('fiber_g',0)} g | "
                        f"Sugar: {totals.get('sugar_g',0)} g"
                    )

                    # # 5) Generic recommendations
                    # st.markdown("### 📋 Recommendations")
                    # for rec in [
                    #     "• Consider adding more vegetables for fiber",
                    #     "• Your protein intake looks good for muscle maintenance",
                    #     "• Try to drink more water with this meal",
                    #     "• If monitoring carbs, adjust portion of rice/bread/pasta",
                    # ]:
                    #     st.markdown(rec)

                    # 6) Persist
                    if st.session_state.user_data and details:
                        meal_log_id = db_manager.save_meal_log(
                            st.session_state.user_data['id'],
                            meal_description,
                            uploaded_file.name if uploaded_file else None
                        )
                        db_manager.save_nutrition_analysis(
                            meal_log_id,
                            calories=totals.get('calories',0),
                            protein=totals.get('protein_g',0),
                            carbs=totals.get('carbs_g',0),
                            fat=totals.get('fat_g',0),
                            recommendation="Auto-estimated from ingredients",
                            sugar=totals.get('sugar_g', 0),
                            fiber=totals.get('fiber_g', 0),
                        )
            else:
                st.error("Please describe your meal first!")

        if analyze_image:
            if uploaded_file is None:
                st.warning("Upload a meal photo first.")
            else:
                st.info("Image-based nutrition analysis will be available in a future update.")

        # Removed inline AI Nutrition Plan; now in separate tab
    
    # Tab 4: Nutrition Dashboard
    with tab4:
        st.header("📊 Nutrition Dashboard")
        st.markdown("Visualize your nutrition data and track your progress")
        
        # Generate mock data for visualization
        nutrition_data = generate_mock_nutrition_data()
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("📈 Daily Nutrition Breakdown")
            fig_bar = px.bar(
                x=["Calories", "Protein (g)", "Fat (g)", "Carbs (g)"],
                y=[2200, 120, 70, 250],
                title="Today's Nutrition Intake",
                color=["Calories", "Protein (g)", "Fat (g)", "Carbs (g)"],
                color_discrete_sequence=px.colors.qualitative.Set2
            )
            fig_bar.update_layout(showlegend=False)
            st.plotly_chart(fig_bar, use_container_width=True)
        
        with col2:
            st.subheader("🥧 Macronutrient Distribution")
            fig_pie = px.pie(
                values=[30, 25, 45],
                names=["Protein", "Fat", "Carbohydrates"],
                title="Macronutrient Breakdown (%)",
                color_discrete_sequence=px.colors.qualitative.Pastel
            )
            st.plotly_chart(fig_pie, use_container_width=True)
        
        st.divider()
        
        # Weekly trend (mock data)
        # st.subheader("📅 Weekly Nutrition Trends")
        # dates = pd.date_range(start='2024-01-01', periods=7, freq='D')
        # weekly_data = pd.DataFrame({
        #     'Date': dates,
        #     'Calories': [2100, 2200, 1950, 2300, 2000, 2400, 2150],
        #     'Protein': [110, 120, 100, 130, 115, 140, 125],
        #     'Carbs': [230, 250, 200, 280, 220, 290, 240]
        # })
        
        # fig_line = px.line(
        #     weekly_data,
        #     x='Date',
        #     y=['Calories', 'Protein', 'Carbs'],
        #     title="7-Day Nutrition Trends",
        #     markers=True
        # )
        # st.plotly_chart(fig_line, use_container_width=True)
        
        # Nutrition goals progress
        st.subheader("🎯 Goals Progress")
        col1, col2 = st.columns(2)
        
        with col1:
            st.metric("Daily Calories", "2,200", "50 under goal")
        with col2:
            st.metric("Protein", "120g", "20g over goal")
    
    
    # Tab 4: Export Report
    with tab5:
        st.header("📝 Export Report")
        st.markdown("Generate and download comprehensive nutrition reports")
        
        st.info("🚧 **Coming Soon!** This feature is under development.")
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.markdown("""
            ### 📄 What will be included in your report:
            
            - **🍽️ Meal Analysis History:** Complete log of analyzed meals with nutrition breakdowns
            - **💬 Chat Conversations:** Your nutrition Q&A sessions with the AI assistant  
            - **📊 Visual Charts:** Nutrition trends, macronutrient distributions, and progress tracking
            - **🎯 Goal Progress:** How well you're meeting your nutrition and health goals
            - **💡 Personalized Recommendations:** Tailored advice based on your profile and preferences
            - **📈 Weekly/Monthly Summaries:** Comprehensive overview of your nutrition journey
            
            ### 🎨 Report Formats (Future):
            - **PDF Report:** Professional, printable format
            - **Interactive Dashboard:** Shareable web version
            - **CSV Data Export:** Raw data for your own analysis
            """)
        
        with col2:
            st.markdown("### 🔧 Export Options")
            
            report_type = st.selectbox(
                "Report Type",
                ["Weekly Summary", "Monthly Report", "Custom Date Range", "Complete History"]
            )
            
            if report_type == "Custom Date Range":
                start_date = st.date_input("Start Date")
                end_date = st.date_input("End Date")
            
            include_charts = st.checkbox("Include Charts & Visualizations", value=True)
            include_chat = st.checkbox("Include Chat History", value=True)
            include_photos = st.checkbox("Include Meal Photos", value=False)
            
            st.markdown("---")
            
            if st.button("📄 Download Nutrition Report (Coming soon!)", type="primary", disabled=True):
                st.info("This feature will be available in the next update!")
            
            st.markdown("""
            <div style="background-color: #f0f2f6; padding: 15px; border-radius: 10px; margin-top: 20px;">
                <h4>📧 Get Notified</h4>
                <p>Want to be the first to know when report generation is ready? 
                We'll notify you via email when this feature launches!</p>
            </div>
            """, unsafe_allow_html=True)

            # Tab 5: Talk to Me (Voice Interface)
    with tab6:
        st.header("🎙️ Talk to Me")
        # st.markdown(
        #     "Have a natural conversation with your nutrition assistant using voice"
        # )

        # Voice interface layout
        col1, col2 = st.columns([1, 1])

        with col1:
            st.markdown(
                """
                <div style="text-align: center; padding: 30px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 15px; color: white; margin-bottom: 20px;">
                    <h3>🎤 Voice Input</h3>
                    <p>Click the microphone to start speaking</p>
                </div>
            """,
                unsafe_allow_html=True,
            )

            # Voice input controls
            voice_col1, voice_col2, voice_col3 = st.columns([1, 2, 1])
            with voice_col2:
                if st.button(
                    "🎤 Start Recording", type="primary", use_container_width=True
                ):
                    st.info("🎙️ Voice recording feature coming soon!")

                if st.button("⏹️ Stop Recording", use_container_width=True):
                    st.info("Recording stopped")

                if st.button("▶️ Play Recording", use_container_width=True):
                    st.info("Playing your recording...")

            st.markdown("---")

            # Voice settings
            st.subheader("⚙️ Voice Settings")
            voice_language = st.selectbox(
                "Language",
                [
                    "English (US)",
                    "English (UK)",
                    "Spanish",
                    "French",
                    "German",
                    "Italian",
                ],
                help="Select your preferred language for voice interaction",
            )

            voice_speed = st.slider(
                "Speech Speed",
                min_value=0.5,
                max_value=2.0,
                value=1.0,
                step=0.1,
                help="Adjust the speed of AI voice responses",
            )

            voice_pitch = st.selectbox(
                "Voice Type",
                ["Natural", "Friendly", "Professional", "Calm"],
                help="Choose the tone of the AI voice",
            )

        with col2:
            st.markdown(
                """
                <div style="text-align: center; padding: 30px; background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%); border-radius: 15px; color: white; margin-bottom: 20px;">
                    <h3>🔊 AI Response</h3>
                    <p>Listen to personalized nutrition advice</p>
                </div>
            """,
                unsafe_allow_html=True,
            )

            # AI Response area
            with st.container():
                st.markdown(
                    """
                    <div style="background-color: #f8f9fa; padding: 20px; border-radius: 10px; border-left: 4px solid #28a745; min-height: 200px;">
                        <h5>💬 AI Assistant Response:</h5>
                        <p style="color: #6c757d; font-style: italic;">
                            Your AI nutrition assistant will respond here with personalized advice based on your voice input.
                        </p>
                        <div style="margin-top: 20px;">
                            <p><strong>🎯 Example Topics You Can Ask About:</strong></p>
                            <ul>
                                <li>🥗 "What should I eat for breakfast?"</li>
                                <li>💪 "How much protein do I need daily?"</li>
                                <li>🏃 "Pre-workout meal suggestions?"</li>
                                <li>😴 "Foods that help with sleep?"</li>
                                <li>🎂 "Healthy dessert alternatives?"</li>
                            </ul>
                        </div>
                    </div>
                """,
                unsafe_allow_html=True,
            )

            st.markdown("---")

            # Voice response controls
            response_col1, response_col2 = st.columns(2)
            with response_col1:
                if st.button(
                    "🔊 Play AI Response", type="secondary", use_container_width=True
                ):
                    st.info("🔊 AI voice response feature coming soon!")

            with response_col2:
                if st.button("📋 Save Conversation", use_container_width=True):
                    st.success("Conversation saved to your chat history!")

        st.markdown("---")

        # Conversation history for voice interactions
        st.subheader("📜 Voice Conversation History")

        # Mock conversation history
        with st.expander("🗣️ Recent Voice Conversations", expanded=False):
            conversation_history = [
                {
                    "timestamp": "2024-01-15 14:30",
                    "user_input": "What's a good post-workout meal?",
                    "ai_response": "For post-workout recovery, I recommend a combination of protein and carbohydrates. Try grilled chicken with quinoa and vegetables, or a protein smoothie with banana and Greek yogurt.",
                },
                {
                    "timestamp": "2024-01-15 10:15",
                    "user_input": "How much water should I drink daily?",
                    "ai_response": "Generally, aim for 8-10 glasses of water daily, but this can vary based on your activity level, climate, and body size. If you're active, you'll need more to replace fluids lost through sweat.",
                },
                {
                    "timestamp": "2024-01-14 16:45",
                    "user_input": "Are there any healthy midnight snack options?",
                    "ai_response": "For late-night snacking, choose light, easily digestible options like Greek yogurt with berries, a small handful of nuts, or herbal tea with a piece of fruit.",
                },
            ]

            for i, conv in enumerate(conversation_history):
                with st.container():
                    st.markdown(
                        f"""
                        <div style="background-color: #f1f3f4; padding: 15px; border-radius: 8px; margin-bottom: 10px;">
                            <p style="color: #666; font-size: 12px; margin-bottom: 8px;">📅 {conv['timestamp']}</p>
                            <div style="background-color: #e3f2fd; padding: 10px; border-radius: 5px; margin-bottom: 8px;">
                                <strong>🗣️ You:</strong> {conv['user_input']}
                            </div>
                            <div style="background-color: #f3e5f5; padding: 10px; border-radius: 5px;">
                                <strong>🤖 AI:</strong> {conv['ai_response']}
                            </div>
                        </div>
                    """,
                        unsafe_allow_html=True,
                    )

        # Feature information
        st.markdown("---")
        st.info(
            """
            🚧 **Voice Features Coming Soon!**
            
            This voice interface will include:
            - 🎤 **Real-time voice recognition** - Speak naturally to ask nutrition questions
            - 🔊 **AI voice responses** - Hear personalized advice in natural speech
            - 🌐 **Multi-language support** - Communicate in your preferred language
            - 💾 **Voice conversation history** - All voice interactions saved automatically
            - 🎯 **Context awareness** - AI remembers your preferences and dietary needs
            - 📱 **Mobile optimized** - Perfect for hands-free nutrition guidance
        """
        )
        
    # Tab 6: Talk to Me (no additional content here; Talk to Me content is under tab5)
else:
    # Welcome screen for non-authenticated users
    st.markdown(
        """
        <div style="text-align: center; padding: 50px;">
            <h2>🥗 <b>Welcome to NutriBench</b> 🥗</h2>
            <h4>Smart Nutrition and Diet Assistant</h4>
            <p style="font-size: 15px; color: #666; margin: 30px 0;">
                Your personal AI-powered nutrition companion for healthier eating habits
            </p>
        </div>
        """, 
        unsafe_allow_html=True
    )
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("""
            <div style="background: linear-gradient(90deg, #667eea 0%, #764ba2 100%); padding: 20px; border-radius: 10px; color: white;">
                <div style="text-align:center;">
                    <h4>✨ Features</h4>
                </div>
                <p>  
                    🧠 AI-powered nutrition Q&A: Ask questions and get expert advice
                    <br><br>🍽️ Smart meal analysis: Analyze meals with photos and descriptions 
                    <br><br>📊 Interactive dashboards: Track your progress with beautiful charts
                    <br><br>📝 Comprehensive reports: Generate comprehensive nutrition reports
                    <br><br>🔐 Secure & Personal: Your data is safe and private
                 </p>
            </div>
            <br>
        """, unsafe_allow_html=True)
        st.markdown("""
        ### 🚀 Get Started:
        **Please login or sign up using the sidebar to access all features!**
        """)
    
    st.markdown("---")
    st.markdown(
        "<div style='text-align: center; color: #888;'>Powered by AI • Built with ❤️ for better health</div>",
        unsafe_allow_html=True
    )