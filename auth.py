import streamlit as st
import hashlib
import uuid
import os
import sqlalchemy as sa
from sqlalchemy import create_engine, text
from database import DatabaseManager
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()


class AuthManager:
    def __init__(self):
        self.db = DatabaseManager()
        self.database_url = os.getenv('DATABASE_URL')
        self.supabase_url = os.getenv('SUPABASE_URL')
        self.supabase_key = os.getenv('SUPABASE_ANON_KEY')
        
        if self.database_url:
            self.engine = create_engine(self.database_url)
        else:
            self.engine = None
            
        # Initialize Supabase client for authentication
        if self.supabase_url and self.supabase_key:
            self.supabase = create_client(self.supabase_url, self.supabase_key)
        else:
            self.supabase = None
    
    def hash_password(self, password: str) -> str:
        """Hash password using SHA-256"""
        return hashlib.sha256(password.encode()).hexdigest()
    
    def signup(self, email: str, password: str, full_name: str) -> bool:
        """Register a new user"""
        try:
            if self.supabase:
                # Use Supabase Auth API for proper user registration
                try:
                    # First attempt to sign up the user
                    response = self.supabase.auth.sign_up({
                        "email": email,
                        "password": password,
                        "options": {
                            "data": {
                                "full_name": full_name
                            }
                        }
                    })
                    
                    if response.user:
                        user_id = response.user.id
                        user_email = response.user.email
                        
                        # Create user profile in our users table
                        if self.engine:
                            with self.engine.connect() as conn:
                                # Check if user profile already exists by email or id
                                existing_user = conn.execute(
                                    text("SELECT id FROM users WHERE id = :user_id OR email = :email"),
                                    {"user_id": user_id, "email": user_email}
                                ).fetchone()
                                
                                if not existing_user:
                                    conn.execute(
                                        text("""
                                            INSERT INTO users (id, email, full_name, created_at, updated_at)
                                            VALUES (:id, :email, :full_name, NOW(), NOW())
                                            ON CONFLICT (email) DO UPDATE SET
                                                full_name = EXCLUDED.full_name,
                                                updated_at = NOW()
                                        """),
                                        {
                                            "id": user_id,
                                            "email": user_email,
                                            "full_name": full_name
                                        }
                                    )
                                    conn.commit()
                        
                        # Check if email confirmation is required
                        if hasattr(response.user, 'email_confirmed_at') and response.user.email_confirmed_at is None:
                            st.success("Account created successfully! If email confirmation is enabled, please check your email to verify your account before logging in.")
                        else:
                            st.success("Account created successfully! You can now log in.")
                        return True
                    else:
                        st.error("Failed to create account - no user returned")
                        return False
                        
                except Exception as signup_error:
                    error_msg = str(signup_error)
                    print(f"Signup error: {error_msg}")  # Debug log
                    if "already registered" in error_msg.lower() or "already exists" in error_msg.lower() or "email address not valid" in error_msg.lower():
                        st.error("Email already registered or invalid")
                    elif "password" in error_msg.lower():
                        st.error("Password must be at least 6 characters long")
                    else:
                        st.error(f"Failed to create account: {error_msg}")
                    return False
            
            elif self.engine:
                # Fallback to local database
                # Generate user ID
                user_id = str(uuid.uuid4())
                
                with self.engine.connect() as conn:
                    # Check if user already exists
                    result = conn.execute(
                        text("SELECT id FROM users WHERE email = :email"),
                        {"email": email}
                    )
                    if result.fetchone():
                        st.error("Email already registered")
                        return False
                    
                    # Insert new user
                    conn.execute(
                        text("""
                            INSERT INTO users (id, email, full_name, created_at, updated_at)
                            VALUES (:id, :email, :full_name, NOW(), NOW())
                        """),
                        {
                            "id": user_id,
                            "email": email,
                            "full_name": full_name
                        }
                    )
                    conn.commit()
                    return True
            else:
                # Fallback to session state for development
                # Hash the password
                hashed_password = self.hash_password(password)
                
                # Generate user ID
                user_id = str(uuid.uuid4())
                
                user_data = {
                    'id': user_id,
                    'email': email,
                    'password_hash': hashed_password,
                    'full_name': full_name
                }
                
                # Store in session state (simulating database storage)
                if 'registered_users' not in st.session_state:
                    st.session_state.registered_users = {}
                
                # Check if user already exists
                if email in st.session_state.registered_users:
                    return False
                
                st.session_state.registered_users[email] = user_data
                return True
            
        except Exception as e:
            st.error(f"Error during signup: {str(e)}")
            return False
    
    def login(self, email: str, password: str) -> dict | None:
        """Authenticate user and return user data"""
        try:
            if self.supabase:
                # Use Supabase Auth API for proper authentication
                try:
                    response = self.supabase.auth.sign_in_with_password({
                        "email": email,
                        "password": password
                    })
                    
                    if response.user:
                        user_id = response.user.id
                        user_email = response.user.email
                        
                        # Check if user profile exists in our users table
                        if self.engine:
                            with self.engine.connect() as conn:
                                profile_result = conn.execute(
                                    text("SELECT id, email, full_name FROM users WHERE id = :user_id"),
                                    {"user_id": user_id}
                                )
                                profile_user = profile_result.fetchone()
                                
                                if profile_user:
                                    # Return existing profile
                                    return {
                                        'id': str(profile_user[0]),
                                        'email': profile_user[1],
                                        'full_name': profile_user[2]
                                    }
                                else:
                                    # Create profile for authenticated user
                                    full_name = user_email.split('@')[0] if user_email else "User"  # Default name from email
                                    conn.execute(
                                        text("""
                                            INSERT INTO users (id, email, full_name, created_at, updated_at)
                                            VALUES (:id, :email, :full_name, NOW(), NOW())
                                        """),
                                        {
                                            "id": user_id,
                                            "email": user_email,
                                            "full_name": full_name
                                        }
                                    )
                                    conn.commit()
                                    
                                    return {
                                        'id': user_id,
                                        'email': user_email,
                                        'full_name': full_name
                                    }
                        else:
                            # Fallback without database
                            return {
                                'id': user_id,
                                'email': user_email,
                                'full_name': user_email.split('@')[0] if user_email else "User"
                            }
                    
                    return None
                    
                except Exception as auth_error:
                    # Authentication failed - invalid credentials
                    st.error("Invalid email or password")
                    return None
            
            elif self.engine:
                # Fallback to session state authentication for development
                # Hash the provided password
                hashed_password = self.hash_password(password)
                
                # Get registered users from session state
                if 'registered_users' not in st.session_state:
                    st.session_state.registered_users = {}
                
                # Check if user exists and password matches
                if email in st.session_state.registered_users:
                    user_data = st.session_state.registered_users[email]
                    if user_data['password_hash'] == hashed_password:
                        # Return user data without password hash
                        return {
                            'id': user_data['id'],
                            'email': user_data['email'],
                            'full_name': user_data['full_name']
                        }
                
                return None
            else:
                # Fallback to session state for development
                # Hash the provided password
                hashed_password = self.hash_password(password)
                
                # Get registered users from session state
                if 'registered_users' not in st.session_state:
                    st.session_state.registered_users = {}
                
                # Check if user exists and password matches
                if email in st.session_state.registered_users:
                    user_data = st.session_state.registered_users[email]
                    if user_data['password_hash'] == hashed_password:
                        # Return user data without password hash
                        return {
                            'id': user_data['id'],
                            'email': user_data['email'],
                            'full_name': user_data['full_name']
                        }
                
                return None
            
        except Exception as e:
            st.error(f"Error during login: {str(e)}")
            return None
    
    def get_user_preferences(self, user_id: str) -> dict:
        """Get user preferences from database"""
        try:
            # In real implementation, this would query Supabase
            # For now, return default preferences
            return {
                'age': None,
                'gender': None,
                'weight_kg': None,
                'height_cm': None,
                'activity_level': 'moderately_active',
                'health_goal': 'maintenance',
                'dietary_restrictions': []
            }
        except Exception as e:
            st.error(f"Error fetching user preferences: {str(e)}")
            return {}
    
    def update_user_preferences(self, user_id: str, preferences: dict) -> bool:
        """Update user preferences in database"""
        try:
            # In real implementation, this would update Supabase
            # For now, store in session state
            if 'user_preferences' not in st.session_state:
                st.session_state.user_preferences = {}
            
            st.session_state.user_preferences[user_id] = preferences
            return True
            
        except Exception as e:
            st.error(f"Error updating user preferences: {str(e)}")
            return False
