import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import uuid
from datetime import datetime, timedelta
from auth import AuthManager
from database import DatabaseManager
from chat_manager import ChatManager
from utils import generate_mock_nutrition_data, create_nutrition_charts

# Page configuration
st.set_page_config(
    page_title="NutriBench", 
    layout="wide",
    page_icon="🥗"
)

# Initialize managers
# @st.cache_resource
# def init_managers():
#     auth_manager = AuthManager()
#     db_manager = DatabaseManager()
#     chat_manager = ChatManager()
#     return auth_manager, db_manager, chat_manager

# auth_manager, db_manager, chat_manager = init_managers()

if 'auth_manager' not in st.session_state:
    st.session_state.auth_manager = AuthManager()
if 'db_manager' not in st.session_state:
    st.session_state.db_manager = DatabaseManager()
if 'chat_manager' not in st.session_state:
    st.session_state.chat_manager = ChatManager()

auth_manager = st.session_state.auth_manager
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
            login_email = st.text_input("Email", key="login_email")
            login_password = st.text_input("Password", type="password", key="login_password")
 
            if st.button("Login", key="login_btn"):
                if login_email and login_password:
                    user_data = auth_manager.login(login_email, login_password)
                    if user_data:
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
            signup_email = st.text_input("Email", key="signup_email", placeholder="your@email.com")
            signup_password = st.text_input("Password", type="password", key="signup_password", 
                                          help="Password must be at least 6 characters")
            full_name = st.text_input("Full Name", key="signup_name", placeholder="Your Full Name")
            
            if st.button("Sign Up", key="signup_btn", type="primary"):
                if signup_email and signup_password and full_name:
                    if len(signup_password) < 6:
                        st.error("Password must be at least 6 characters long")
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
            st.session_state.authenticated = False
            st.session_state.user_data = None
            st.session_state.chat_messages = []
            st.rerun()
        
        st.divider()
        st.subheader("⚙️ Settings")
        st.info("User preferences and settings will be available here in future updates.")

# st.write("AUTH:", st.session_state.get("authenticated"))
# st.write("USER:", st.session_state.get("user_data"))


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
    tab1, tab2, tab3, tab4 = st.tabs(["🧠 Ask Anything", "🍽 Meal Analyzer", "📊 Nutrition Dashboard", "📝 Export Report"])
    
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
            if not st.session_state.chat_sessions and st.session_state.user_data:
                st.session_state.chat_sessions = chat_manager.get_user_chat_sessions(
                    st.session_state.user_data['id']
                )

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
                        col_a, col_b = st.columns(2)
                        with col_a:
                            if st.button("✏️", key=f"edit_{session_id}", help="Edit title"):
                                pass
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
                </div>
            """, unsafe_allow_html=True)

            # Check if chat session is selected
            if not st.session_state.current_session_id:
                st.info("👈 Start a new chat session to begin asking questions!")
            else:
                # 1. Render chat history ABOVE the input
                current_messages = chat_manager.get_chat_history(st.session_state.current_session_id)
                for idx, message in enumerate(current_messages):
                    with st.chat_message("user"):
                        st.markdown(f"""
                            <div style="background-color:#e0f7fa;padding:12px;border-radius:10px;">
                                {message['user_message']}
                            </div>
                        """, unsafe_allow_html=True)
                        st.caption(f"📅 {message['created_at']}")

                    with st.chat_message("assistant"):
                        st.markdown(f"""
                            <div style="background-color:#f3f4f6;padding:12px;border-radius:10px;">
                                {message['assistant_response']}
                            </div>
                        """, unsafe_allow_html=True)

                # 2. THEN show input box BELOW
                with st._bottom:
                    prompt = st.chat_input("Ask me about the loaded data...")
                    if prompt:
                        if st.session_state.user_data:
                            with st.spinner("Thinking..."):
                                assistant_response = "Thank you for your question about nutrition. This is a placeholder response for now."

                                chat_manager.add_message_to_chat(
                                    st.session_state.current_session_id,
                                    st.session_state.user_data['id'],
                                    prompt,
                                    assistant_response
                                )
                                st.rerun()  # To show the updated message list          
                        else:
                            st.error("Please log in to start chatting!")



    # Tab 2: Meal Analyzer
    with tab2:
        st.header("🍽 Meal Analyzer")
        st.markdown("Analyze your meals for nutrition content and get personalized recommendations")
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.subheader("📝 Meal Description")
            meal_description = st.text_area(
                "Describe your meal:",
                placeholder="e.g., 1 bowl of chicken curry with rice and salad",
                height=100
            )
            
            st.subheader("📸 Meal Photo")
            uploaded_file = st.file_uploader(
                "Upload a photo of your meal (optional)",
                type=['png', 'jpg', 'jpeg'],
                help="This will be analyzed by AI in future updates"
            )
            
            if uploaded_file is not None:
                st.image(uploaded_file, caption="Uploaded meal photo", use_column_width=True)
        
        with col2:
            st.subheader("👤 Personal Information")
            age = st.number_input("Age", min_value=1, max_value=120, value=25)
            weight = st.number_input("Weight (kg)", min_value=1.0, max_value=300.0, value=70.0, step=0.1)
            height = st.number_input("Height (cm)", min_value=50, max_value=250, value=170)
            
            gender = st.selectbox("Gender", ["Male", "Female", "Other"])
            activity_level = st.selectbox(
                "Activity Level",
                ["Sedentary", "Lightly Active", "Moderately Active", "Very Active", "Extremely Active"]
            )
            
            st.subheader("🎯 Health Goals")
            health_goal = st.selectbox(
                "Primary Goal",
                ["Weight Loss", "Weight Gain", "Muscle Gain", "Maintenance", "General Health"]
            )
            
            # Health condition inputs for future ML predictions
            st.subheader("🏥 Health Monitoring")
            diabetes_risk = st.selectbox("Diabetes Risk Assessment", ["Low", "Medium", "High", "Unknown"])
            heart_disease_risk = st.selectbox("Heart Disease Risk", ["Low", "Medium", "High", "Unknown"])
        
        st.divider()
        
        # Analysis button and results
        if st.button("🔍 Analyze Meal", type="primary"):
            if meal_description:
                with st.spinner("Analyzing your meal..."):
                    # Placeholder analysis results
                    st.info("🍽️ **Estimated Nutrition:** 500 kcal, 30g protein, 12g fat, 45g carbs, 8g fiber")
                    st.success("✅ **Recommended Diet:** Low Carb based on your profile")
                    
                    # Additional recommendations
                    st.markdown("### 📋 Personalized Recommendations")
                    recommendations = [
                        f"Based on your {health_goal.lower()} goal and {activity_level.lower()} lifestyle:",
                        "• Consider adding more vegetables for fiber",
                        "• Your protein intake looks good for muscle maintenance",
                        "• Try to drink more water with this meal",
                        f"• This meal fits well with your {diabetes_risk.lower()} diabetes risk profile"
                    ]
                    
                    for rec in recommendations:
                        st.markdown(rec)
                    
                    # Save meal log to database
                    if st.session_state.user_data:
                        meal_log_id = db_manager.save_meal_log(
                            st.session_state.user_data['id'],
                            meal_description,
                            uploaded_file.name if uploaded_file else None
                        )
                        
                        # Save nutrition analysis
                        db_manager.save_nutrition_analysis(
                            meal_log_id,
                            calories=500,
                            protein=30,
                            carbs=45,
                            fat=12,
                            recommendation="Low Carb diet recommended"
                        )
            else:
                st.error("Please describe your meal first!")
    
    # Tab 3: Nutrition Dashboard
    with tab3:
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
        st.subheader("📅 Weekly Nutrition Trends")
        dates = pd.date_range(start='2024-01-01', periods=7, freq='D')
        weekly_data = pd.DataFrame({
            'Date': dates,
            'Calories': [2100, 2200, 1950, 2300, 2000, 2400, 2150],
            'Protein': [110, 120, 100, 130, 115, 140, 125],
            'Carbs': [230, 250, 200, 280, 220, 290, 240]
        })
        
        fig_line = px.line(
            weekly_data,
            x='Date',
            y=['Calories', 'Protein', 'Carbs'],
            title="7-Day Nutrition Trends",
            markers=True
        )
        st.plotly_chart(fig_line, use_container_width=True)
        
        # Nutrition goals progress
        st.subheader("🎯 Goals Progress")
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Daily Calories", "2,200", "50 under goal")
        with col2:
            st.metric("Protein", "120g", "20g over goal")
        with col3:
            st.metric("Water", "2.1L", "0.4L to goal")
        with col4:
            st.metric("Steps", "8,500", "1,500 to goal")
    
    # Tab 4: Export Report
    with tab4:
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