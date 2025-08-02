import streamlit as st
import uuid
import os
from datetime import datetime
from typing import List, Dict, Optional
import sqlalchemy as sa
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

class DatabaseManager:
    def __init__(self):
        self.database_url = os.getenv('DATABASE_URL')
        if self.database_url:
            self.engine = create_engine(self.database_url)
        else:
            self.engine = None
            # Initialize session state for simulating database storage
            if 'chat_history' not in st.session_state:
                st.session_state.chat_history = []
            if 'meal_logs' not in st.session_state:
                st.session_state.meal_logs = []
            if 'nutrition_analysis' not in st.session_state:
                st.session_state.nutrition_analysis = []
    
    def save_chat_message(self, user_id: str, user_message: str, assistant_response: str, session_id: str) -> bool:
        """Save chat message to database"""
        try:
            if self.engine:
                # Use Supabase database
                with self.engine.connect() as conn:
                    conn.execute(
                        text("""
                            INSERT INTO chat_history (id, user_id, user_message, assistant_response, session_id, created_at)
                            VALUES (:id, :user_id, :user_message, :assistant_response, :session_id, NOW())
                        """),
                        {
                            "id": str(uuid.uuid4()),
                            "user_id": user_id,
                            "user_message": user_message,
                            "assistant_response": assistant_response,
                            "session_id": session_id
                        }
                    )
                    conn.commit()
                    return True
            else:
                # Fallback to session state
                chat_record = {
                    'id': str(uuid.uuid4()),
                    'user_id': user_id,
                    'user_message': user_message,
                    'assistant_response': assistant_response,
                    'session_id': session_id,
                    'created_at': datetime.now().isoformat()
                }
                
                st.session_state.chat_history.append(chat_record)
                return True
            
        except Exception as e:
            st.error(f"Error saving chat message: {str(e)}")
            return False
    
    def get_chat_history(self, user_id: str, session_id: Optional[str] = None) -> List[Dict]:
        """Retrieve chat history for a user"""
        try:
            if self.engine:
                # Use Supabase database
                with self.engine.connect() as conn:
                    if session_id:
                        result = conn.execute(
                            text("""
                                SELECT id, user_id, user_message, assistant_response, session_id, created_at
                                FROM chat_history 
                                WHERE user_id = :user_id AND session_id = :session_id
                                ORDER BY created_at
                            """),
                            {"user_id": user_id, "session_id": session_id}
                        )
                    else:
                        result = conn.execute(
                            text("""
                                SELECT id, user_id, user_message, assistant_response, session_id, created_at
                                FROM chat_history 
                                WHERE user_id = :user_id
                                ORDER BY created_at
                            """),
                            {"user_id": user_id}
                        )
                    
                    return [
                        {
                            'id': str(row[0]),
                            'user_id': str(row[1]),
                            'user_message': row[2],
                            'assistant_response': row[3],
                            'session_id': row[4],
                            'created_at': row[5].isoformat() if hasattr(row[5], 'isoformat') else str(row[5])
                        }
                        for row in result
                    ]
            else:
                # Fallback to session state
                chat_history = st.session_state.chat_history
                
                # Filter by user_id
                user_chats = [chat for chat in chat_history if chat['user_id'] == user_id]
                
                # Filter by session_id if provided
                if session_id:
                    user_chats = [chat for chat in user_chats if chat['session_id'] == session_id]
                
                return sorted(user_chats, key=lambda x: x['created_at'])
            
        except Exception as e:
            st.error(f"Error retrieving chat history: {str(e)}")
            return []
    
    def get_user_chat_sessions(self, user_id: str) -> List[Dict]:
        """Get all chat sessions for a user"""
        try:
            chat_history = st.session_state.chat_history
            user_chats = [chat for chat in chat_history if chat['user_id'] == user_id]
            
            # Group by session_id
            sessions = {}
            for chat in user_chats:
                session_id = chat['session_id']
                if session_id not in sessions:
                    sessions[session_id] = {
                        'session_id': session_id,
                        'created_at': chat['created_at'],
                        'message_count': 0,
                        'last_message': ''
                    }
                
                sessions[session_id]['message_count'] += 1
                sessions[session_id]['last_message'] = chat['user_message'][:50] + '...'
            
            return list(sessions.values())
            
        except Exception as e:
            st.error(f"Error retrieving chat sessions: {str(e)}")
            return []
    
    def save_meal_log(self, user_id: str, meal_description: str, image_path: Optional[str] = None) -> str:
        """Save meal log to database"""
        try:
            meal_log_id = str(uuid.uuid4())
            
            if self.engine:
                # Use Supabase database
                with self.engine.connect() as conn:
                    conn.execute(
                        text("""
                            INSERT INTO meal_logs (id, user_id, meal_description, meal_time, image_path, created_at)
                            VALUES (:id, :user_id, :meal_description, NOW(), :image_path, NOW())
                        """),
                        {
                            "id": meal_log_id,
                            "user_id": user_id,
                            "meal_description": meal_description,
                            "image_path": image_path
                        }
                    )
                    conn.commit()
                    return meal_log_id
            else:
                # Fallback to session state
                meal_record = {
                    'id': meal_log_id,
                    'user_id': user_id,
                    'meal_description': meal_description,
                    'meal_time': datetime.now().isoformat(),
                    'image_path': image_path,
                    'created_at': datetime.now().isoformat()
                }
                
                st.session_state.meal_logs.append(meal_record)
                return meal_log_id
            
        except Exception as e:
            st.error(f"Error saving meal log: {str(e)}")
            return ""
    
    def save_nutrition_analysis(self, meal_log_id: str, calories: float, protein: float, 
                               carbs: float, fat: float, recommendation: str) -> bool:
        """Save nutrition analysis results"""
        try:
            if self.engine:
                # Use Supabase database
                with self.engine.connect() as conn:
                    conn.execute(
                        text("""
                            INSERT INTO nutrition_analysis (id, meal_log_id, calories, protein_g, carbs_g, fat_g, sugar_g, fiber_g, recommendation, created_at)
                            VALUES (:id, :meal_log_id, :calories, :protein_g, :carbs_g, :fat_g, :sugar_g, :fiber_g, :recommendation, NOW())
                        """),
                        {
                            "id": str(uuid.uuid4()),
                            "meal_log_id": meal_log_id,
                            "calories": calories,
                            "protein_g": protein,
                            "carbs_g": carbs,
                            "fat_g": fat,
                            "sugar_g": 0,  # Placeholder
                            "fiber_g": 0,  # Placeholder
                            "recommendation": recommendation
                        }
                    )
                    conn.commit()
                    return True
            else:
                # Fallback to session state
                analysis_record = {
                    'id': str(uuid.uuid4()),
                    'meal_log_id': meal_log_id,
                    'calories': calories,
                    'protein_g': protein,
                    'carbs_g': carbs,
                    'fat_g': fat,
                    'sugar_g': 0,  # Placeholder
                    'fiber_g': 0,  # Placeholder
                    'recommendation': recommendation,
                    'created_at': datetime.now().isoformat()
                }
                
                st.session_state.nutrition_analysis.append(analysis_record)
                return True
            
        except Exception as e:
            st.error(f"Error saving nutrition analysis: {str(e)}")
            return False
    
    def get_user_meal_logs(self, user_id: str, limit: int = 10) -> List[Dict]:
        """Get recent meal logs for a user"""
        try:
            if self.engine:
                # Use Supabase database
                with self.engine.connect() as conn:
                    result = conn.execute(
                        text("""
                            SELECT id, user_id, meal_description, meal_time, image_path, created_at
                            FROM meal_logs 
                            WHERE user_id = :user_id
                            ORDER BY created_at DESC
                            LIMIT :limit
                        """),
                        {"user_id": user_id, "limit": limit}
                    )
                    
                    return [
                        {
                            'id': str(row[0]),
                            'user_id': str(row[1]),
                            'meal_description': row[2],
                            'meal_time': row[3].isoformat() if hasattr(row[3], 'isoformat') else str(row[3]),
                            'image_path': row[4],
                            'created_at': row[5].isoformat() if hasattr(row[5], 'isoformat') else str(row[5])
                        }
                        for row in result
                    ]
            else:
                # Fallback to session state
                meal_logs = st.session_state.meal_logs
                user_meals = [meal for meal in meal_logs if meal['user_id'] == user_id]
                
                # Sort by created_at and limit results
                user_meals = sorted(user_meals, key=lambda x: x['created_at'], reverse=True)
                return user_meals[:limit]
            
        except Exception as e:
            st.error(f"Error retrieving meal logs: {str(e)}")
            return []
    
    def get_nutrition_analysis_by_meal(self, meal_log_id: str) -> Optional[Dict]:
        """Get nutrition analysis for a specific meal"""
        try:
            analyses = st.session_state.nutrition_analysis
            for analysis in analyses:
                if analysis['meal_log_id'] == meal_log_id:
                    return analysis
            return None
            
        except Exception as e:
            st.error(f"Error retrieving nutrition analysis: {str(e)}")
            return None
    
    def get_user_nutrition_summary(self, user_id: str, days: int = 7) -> Dict:
        """Get nutrition summary for the last N days"""
        try:
            # This would be a complex query in real implementation
            # For now, return mock summary data
            return {
                'total_meals': 21,
                'avg_calories': 2100,
                'avg_protein': 120,
                'avg_carbs': 240,
                'avg_fat': 70,
                'days': days
            }
            
        except Exception as e:
            st.error(f"Error retrieving nutrition summary: {str(e)}")
            return {}
