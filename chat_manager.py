import os
import uuid
from datetime import datetime
from typing import List, Dict, Optional, Union
import streamlit as st
from sqlalchemy import create_engine, text

class ChatManager:
    def __init__(self):
        self.database_url = os.getenv('DATABASE_URL')
        if self.database_url:
            self.engine = create_engine(self.database_url)
        else:
            self.engine = None
    
    def create_new_chat_session(self, user_id: str, title: str = "New Chat", category: Optional[str] = None) -> Optional[str]:
        """Create a new chat session and return session ID"""
        if not self.engine:
            # Fallback to session state
            session_id = str(uuid.uuid4())
            if 'chat_sessions' not in st.session_state:
                st.session_state.chat_sessions = {}
            
            st.session_state.chat_sessions[session_id] = {
                'id': session_id,
                'user_id': user_id,
                'title': title,
                'category': category,
                'created_at': datetime.now(),
                'messages': []
            }
            return session_id
        
        try:
            with self.engine.connect() as conn:
                session_id = str(uuid.uuid4())
                conn.execute(
                    text("""
                        INSERT INTO chat_sessions (id, user_id, title, category, created_at, updated_at)
                        VALUES (:id, :user_id, :title, :category, NOW(), NOW())
                    """),
                    {
                        "id": session_id,
                        "user_id": user_id,
                        "title": title,
                        "category": category
                    }
                )
                conn.commit()
                return session_id
        except Exception as e:
            st.error(f"Failed to create chat session: {e}")
            return None
    
    def get_user_chat_sessions(self, user_id: str) -> List[Dict]:
        """Get all chat sessions for a user"""
        if not self.engine:
            # Fallback to session state
            if 'chat_sessions' not in st.session_state:
                return []
            
            sessions = []
            for session_id, session_data in st.session_state.chat_sessions.items():
                if session_data['user_id'] == user_id:
                    sessions.append(session_data)
            
            return sorted(sessions, key=lambda x: x['created_at'], reverse=True)
        
        try:
            with self.engine.connect() as conn:
                result = conn.execute(
                    text("""
                        SELECT id, title, category, created_at, updated_at, is_pinned
                        FROM chat_sessions 
                        WHERE user_id = :user_id 
                        ORDER BY is_pinned DESC, updated_at DESC
                    """),
                    {"user_id": user_id}
                )
                
                sessions = []
                for row in result:
                    sessions.append({
                        'id': str(row[0]),
                        'title': row[1],
                        'category': row[2],
                        'created_at': row[3],
                        'updated_at': row[4],
                        'is_pinned': row[5]
                    })
                
                return sessions
        except Exception as e:
            st.error(f"Failed to load chat sessions: {e}")
            return []
    
    def get_chat_history(self, session_id: str) -> List[Dict]:
        """Get chat history for a specific session"""
        if not self.engine:
            # Fallback to session state
            if 'chat_sessions' not in st.session_state:
                return []
            
            session_data = st.session_state.chat_sessions.get(session_id, {})
            return session_data.get('messages', [])
        
        try:
            with self.engine.connect() as conn:
                result = conn.execute(
                    text("""
                        SELECT user_message, assistant_response, created_at, feedback
                        FROM chat_history 
                        WHERE session_id = :session_id 
                        ORDER BY created_at ASC
                    """),
                    {"session_id": session_id}
                )
                
                messages = []
                for row in result:
                    messages.append({
                        'id': str(uuid.uuid4()),  # Generate unique ID for frontend
                        'user_message': row[0],
                        'assistant_response': row[1],
                        'created_at': row[2],
                        'feedback': row[3]
                    })
                
                return messages
        except Exception as e:
            st.error(f"Failed to load chat history: {e}")
            return []
    
    def add_message_to_chat(self, session_id: str, user_id: str, user_message: str, assistant_response: str) -> bool:
        """Add a new message to chat history"""
        if not self.engine:
            # Fallback to session state
            if 'chat_sessions' not in st.session_state:
                st.session_state.chat_sessions = {}
            
            if session_id not in st.session_state.chat_sessions:
                return False
            
            message = {
                'id': str(uuid.uuid4()),
                'user_message': user_message,
                'assistant_response': assistant_response,
                'created_at': datetime.now(),
                'feedback': None
            }
            
            st.session_state.chat_sessions[session_id]['messages'].append(message)
            return True
        
        try:
            with self.engine.connect() as conn:
                conn.execute(
                    text("""
                        INSERT INTO chat_history (session_id, user_id, user_message, assistant_response, created_at)
                        VALUES (:session_id, :user_id, :user_message, :assistant_response, NOW())
                    """),
                    {
                        "session_id": session_id,
                        "user_id": user_id,
                        "user_message": user_message,
                        "assistant_response": assistant_response
                    }
                )
                conn.commit()
                return True
        except Exception as e:
            st.error(f"Failed to save message: {e}")
            return False
    
    def delete_chat_session(self, session_id: str, user_id: str) -> bool:
        """Delete a chat session and all its messages"""
        if not self.engine:
            # Fallback to session state
            if 'chat_sessions' in st.session_state and session_id in st.session_state.chat_sessions:
                if st.session_state.chat_sessions[session_id]['user_id'] == user_id:
                    del st.session_state.chat_sessions[session_id]
                    return True
            return False
        
        try:
            with self.engine.connect() as conn:
                # Delete chat session (messages will be deleted by CASCADE)
                result = conn.execute(
                    text("""
                        DELETE FROM chat_sessions 
                        WHERE id = :session_id AND user_id = :user_id
                    """),
                    {"session_id": session_id, "user_id": user_id}
                )
                conn.commit()
                return result.rowcount > 0
        except Exception as e:
            st.error(f"Failed to delete chat session: {e}")
            return False
    
    def update_chat_session_title(self, session_id: str, user_id: str, new_title: str) -> bool:
        """Update chat session title"""
        if not self.engine:
            # Fallback to session state
            if 'chat_sessions' in st.session_state and session_id in st.session_state.chat_sessions:
                if st.session_state.chat_sessions[session_id]['user_id'] == user_id:
                    st.session_state.chat_sessions[session_id]['title'] = new_title
                    return True
            return False
        
        try:
            with self.engine.connect() as conn:
                result = conn.execute(
                    text("""
                        UPDATE chat_sessions 
                        SET title = :title, updated_at = NOW()
                        WHERE id = :session_id AND user_id = :user_id
                    """),
                    {"title": new_title, "session_id": session_id, "user_id": user_id}
                )
                conn.commit()
                return result.rowcount > 0
        except Exception as e:
            st.error(f"Failed to update chat title: {e}")
            return False
    
    def pin_chat_session(self, session_id: str, user_id: str, pin: bool = True) -> bool:
        """Pin or unpin a chat session"""
        if not self.engine:
            # Session state doesn't support pinning in this implementation
            return False
        
        try:
            with self.engine.connect() as conn:
                result = conn.execute(
                    text("""
                        UPDATE chat_sessions 
                        SET is_pinned = :pin, updated_at = NOW()
                        WHERE id = :session_id AND user_id = :user_id
                    """),
                    {"pin": pin, "session_id": session_id, "user_id": user_id}
                )
                conn.commit()
                return result.rowcount > 0
        except Exception as e:
            st.error(f"Failed to pin/unpin chat: {e}")
            return False