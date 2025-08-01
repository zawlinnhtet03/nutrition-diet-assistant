# NutriBench: Smart Nutrition and Diet Assistant

## Overview

NutriBench is a Streamlit-based web application that serves as a comprehensive nutrition and diet assistant. The application provides users with AI-powered nutrition advice, meal analysis capabilities, nutrition tracking dashboards, and report generation features. The system is designed with a modular architecture that separates authentication, database operations, and utility functions for maintainability and scalability.

## User Preferences

Preferred communication style: Simple, everyday language.

## System Architecture

The application follows a modular MVC-like architecture with clear separation of concerns:

- **Frontend**: Streamlit web interface with multiple tabs for different functionalities
- **Backend Logic**: Python modules handling authentication, database operations, and utilities
- **Data Storage**: Session-based storage (designed to be replaced with Supabase)
- **Visualization**: Plotly for interactive charts and graphs

## Key Components

### 1. Main Application (`app.py`)
- **Purpose**: Entry point and main UI orchestration
- **Features**: 
  - Multi-tab interface (Ask Anything, Meal Analyzer, Nutrition Dashboard, Export Report)
  - Session state management
  - Authentication integration
- **Architecture Decision**: Uses Streamlit's native tab system for clean UX separation

### 2. Authentication System (`auth.py`)
- **Purpose**: User registration and login management
- **Current Implementation**: SHA-256 password hashing with session-based storage
- **Future Integration**: Designed to be replaced with Supabase Auth
- **Security**: Basic password hashing (placeholder for production-grade auth)

### 3. Database Management (`database.py`)
- **Purpose**: Data persistence layer for chat history, meal logs, and nutrition analysis
- **Current Implementation**: Streamlit session state storage
- **Future Integration**: Designed for Supabase database integration
- **Features**: CRUD operations for chat messages and nutrition data

### 4. Chat Management (`chat_manager.py`)
- **Purpose**: ChatGPT-like conversation management with session handling
- **Features**:
  - Create/delete chat sessions with automatic title generation
  - Persistent chat history storage in Supabase database
  - Session switching and management
  - Conversation categorization and pinning capabilities
- **Architecture Decision**: Separate chat management for scalable conversation handling

### 5. Utilities (`utils.py`)
- **Purpose**: Helper functions for data generation and visualization
- **Features**:
  - Mock nutrition data generation
  - Plotly chart creation
  - Data processing utilities

## Data Flow

1. **User Authentication**: Login/signup through sidebar → AuthManager → Supabase Auth → User profile creation
2. **Chat Sessions**: New chat creation → ChatManager → Supabase database → Session management
3. **Chat Interactions**: User input → Mock RAG response → ChatManager → Persistent chat history
4. **Meal Analysis**: Meal description/photo → Placeholder analysis → Nutrition estimates
5. **Dashboard**: Retrieve user data → Generate visualizations → Display charts
6. **Export**: Compile user data → Generate report (future feature)

## External Dependencies

### Current Dependencies
- **Streamlit**: Web application framework
- **Plotly**: Interactive data visualization
- **Pandas**: Data manipulation and analysis
- **UUID**: Unique identifier generation
- **Hashlib**: Password hashing

### Planned Integrations
- **Supabase**: Database and authentication backend
- **Gemini API**: AI-powered meal analysis from images
- **RAG System**: Knowledge base for nutrition advice
- **ML/DL Models**: Nutrition prediction and diet recommendations

## Deployment Strategy

### Current Setup
- **Platform**: Designed for Replit deployment
- **Storage**: Supabase database with session fallback
- **Authentication**: Supabase Auth with secure email/password validation

### Production Considerations
- **Database Integration**: ✅ Completed - Supabase tables implemented
- **Authentication**: ✅ Completed - Supabase Auth integration
- **API Integration**: Mock responses → Real AI services (pending)
- **Chat History**: ✅ Completed - ChatGPT-like session management

### Key Architectural Decisions

1. **Modular Design**: Separated concerns into distinct modules for maintainability
   - **Rationale**: Easier testing, debugging, and future API integrations
   - **Alternative**: Monolithic single-file approach
   - **Pros**: Clean code organization, easier collaboration
   - **Cons**: Slightly more complex initial setup

2. **Session-Based Storage**: Using Streamlit session state for temporary data storage
   - **Rationale**: Rapid prototyping without external database setup
   - **Alternative**: Direct database integration from start
   - **Pros**: Quick development, no external dependencies
   - **Cons**: Data loss on session end, not production-ready

3. **Placeholder Architecture**: Mock implementations for AI services
   - **Rationale**: Focus on UI/UX before integrating expensive AI services
   - **Alternative**: Immediate API integration
   - **Pros**: Cost-effective development, faster iteration
   - **Cons**: Additional integration work later

4. **Tab-Based Navigation**: Using Streamlit tabs for feature separation
   - **Rationale**: Clean user experience with logical feature grouping
   - **Alternative**: Multi-page application
   - **Pros**: Single-page experience, faster navigation
   - **Cons**: Potential performance issues with complex tabs

## Recent Changes (January 2025)

### ChatGPT-like Chat History Implementation
- **Date**: January 31, 2025
- **Changes**: 
  - Implemented `chat_manager.py` for session-based conversation management
  - Added Supabase database schema with chat_sessions and chat_history tables
  - Enhanced authentication with proper Supabase Auth integration
  - Created ChatGPT-like interface with sidebar for chat session management
  - Added session switching, creation, and deletion functionality
- **Impact**: Users can now maintain multiple conversation histories like ChatGPT
- **Database Schema**: Includes chat_sessions, chat_history with auto-title generation

