from typing import Any
import os
import asyncio
import json
import streamlit as st

from services.rag_service import init_rag
from services.agent_service import build_agent
from components.agent_trace import render_agent_trace
 
# For building an Agent-specific chain with a different LLM
RAG_SRC = os.path.join(os.path.dirname(__file__), "..", "rag", "src")
if RAG_SRC not in os.sys.path:
    os.sys.path.insert(0, RAG_SRC)
try:
    from llm_model import get_llm  # type: ignore
    from rag_chain import build_rag_chain  # type: ignore
except Exception:
    get_llm = None  # type: ignore
    build_rag_chain = None  # type: ignore

# Functions below mirror the logic currently in app.py's Chat tab
# This file is not wired yet to avoid behavior changes. You can swap it in later.

def render_chat_page(db_manager: Any, chat_manager: Any):
    """Render the Ask Anything page (RAG Q&A, User Coach, Agent).
    NOTE: Not used yet. Call from app.py when ready to migrate.
    """
    col1, col2 = st.columns([0.6, 3.4], gap="medium")

    with col1:
        st.subheader("💬 Chat Sessions")
        if "chat_mode" not in st.session_state:
            st.session_state.chat_mode = "RAG Q&A"
        st.radio(
            "Mode",
            options=["RAG Q&A", "User Coach", "Agent"],
            horizontal=True,
            key="chat_mode",
        )

        if st.button("+ New Chat", type="primary", width='stretch'):
            if st.session_state.user_data:
                new_session_id = chat_manager.create_new_chat_session(
                    st.session_state.user_data["id"],
                    category=st.session_state.chat_mode,
                )
                if new_session_id:
                    st.session_state.current_session_id = new_session_id
                    st.session_state.chat_sessions = (
                        chat_manager.get_user_chat_sessions(
                            st.session_state.user_data["id"]
                        )
                    )
                    st.rerun()

        if st.session_state.user_data:
            current_user_id = st.session_state.user_data["id"]
            if (
                not st.session_state.chat_sessions
                or not hasattr(st.session_state, "_last_user_id")
                or st.session_state._last_user_id != current_user_id
            ):
                st.session_state.chat_sessions = (
                    chat_manager.get_user_chat_sessions(current_user_id)
                )
                st.session_state._last_user_id = current_user_id

        if st.session_state.chat_sessions:
            st.write("**Recent Chats:**")
            for session in st.session_state.chat_sessions:
                session_id = session["id"]
                title = session["title"]
                category = session.get("category") or "RAG Q&A"
                is_current = session_id == st.session_state.current_session_id
                button_type = "primary" if is_current else "secondary"
                label = f"{'🟢 ' if is_current else '💬 '}{title[:25]}" + (
                    "..." if len(title) > 25 else ""
                )
                badge = " [Coach]" if category == "User Coach" else " [RAG]"
                if st.button(
                    label + badge,
                    key=f"session_{session_id}",
                    type=button_type,
                    width='stretch',
                ):
                    st.session_state.current_session_id = session_id
                    st.rerun()

                if is_current:
                    col_a, col_b = st.columns(2)
                    with col_a:
                        if st.button("✏️", key=f"edit_{session_id}", help="Edit title"):
                            st.session_state.editing_session_id = session_id
                            st.rerun()
                    with col_b:
                        if st.button("🗑️", key=f"delete_{session_id}", help="Delete chat"):
                            if (
                                st.session_state.user_data
                                and chat_manager.delete_chat_session(
                                    session_id, st.session_state.user_data["id"]
                                )
                            ):
                                st.session_state.chat_sessions = (
                                    chat_manager.get_user_chat_sessions(
                                        st.session_state.user_data["id"]
                                    )
                                )
                                st.session_state.current_session_id = None
                                st.rerun()
        else:
            st.info("No chat sessions yet. Start a new chat!")

    with col2:
        st.markdown(
            """
            <div style='text-align:center'>
                <h4><b>Nutrion AI Chat Assistant</b></h4>
                <p style="color:gray;">Ask anything about nutrition, meals, or health goals</p>
                <br>
            </div>
        """,
            unsafe_allow_html=True,
        )

        # Optionally disable RAG completely via env (avoids Gemini calls)
        if os.getenv("DISABLE_RAG", "").lower() in ("1", "true", "yes"):
            st.info("RAG is disabled for this session. You can still use Nutrition Plan, Meal Analyzer, and Dashboard.")
            # Short-circuit chat behavior to avoid any LLM usage
            prompt = st.chat_input("RAG disabled. You can still ask about app usage…")
            if prompt:
                st.warning("RAG is disabled (no Gemini calls). Enable it by unsetting DISABLE_RAG and restarting.")
            return

        # Lazy RAG init (mirrors app.py)
        if not st.session_state.rag_initialized and st.session_state.rag_error is None:
            try:
                try:
                    asyncio.get_running_loop()
                except RuntimeError:
                    asyncio.set_event_loop(asyncio.new_event_loop())
                cfg_path = os.path.join(os.path.dirname(__file__), "..", "rag", "config.yaml")
                rag_ctx = init_rag(os.path.abspath(cfg_path))
                st.session_state.qa_chain = rag_ctx["qa_chain"]
                st.session_state.llm = rag_ctx["llm"]
                st.session_state.retriever = rag_ctx.get("retriever")
                st.session_state.rag_initialized = True
            except Exception as e:
                st.session_state.rag_error = str(e)

        if st.session_state.rag_error:
            st.error(f"RAG initialization failed: {st.session_state.rag_error}")
            if st.button("↻ Retry RAG init", type="primary"):
                st.session_state.rag_error = None
                st.session_state.rag_initialized = False
                st.session_state.qa_chain = None
                st.rerun()

        if not st.session_state.current_session_id:
            st.info("Start a new chat session to begin asking questions!")
            return

        current_messages = chat_manager.get_chat_history(
            st.session_state.current_session_id,
            (st.session_state.user_data["id"] if st.session_state.user_data else None),
        )
        for idx, message in enumerate(current_messages):
            with st.chat_message("user"):
                st.markdown(
                    f"""
                    <div style="background-color:#e0f7fa;padding:12px;border-radius:10px;">
                        {message['user_message']}
                    </div>
                """,
                    unsafe_allow_html=True,
                )
            with st.chat_message("assistant"):
                st.markdown(
                    f"""
                    <div style="background-color:#f3f4f6;padding:12px;border-radius:10px;">
                        {message['assistant_response']}
                    </div>
                """,
                    unsafe_allow_html=True,
                )

        prompt = st.chat_input("Ask me about the loaded data...")
        if not prompt:
            return

        if not st.session_state.user_data:
            st.error("Please log in to start chatting!")
            return

        with st.spinner("Thinking..."):
            assistant_response = ""
            try:
                if st.session_state.qa_chain is None:
                    raise RuntimeError(
                        "RAG is not initialized. Check your GOOGLE_API_KEY and vector store."
                    )
                # Determine session mode (category)
                current_mode = "RAG Q&A"
                for s in st.session_state.chat_sessions or []:
                    if s.get("id") == st.session_state.current_session_id:
                        current_mode = s.get("category") or "RAG Q&A"
                        break

                original_query = prompt
                if current_mode == "Agent":
                    # Build or reuse an Agent-specific chain using a separate LLM model
                    if get_llm is None or build_rag_chain is None:
                        raise RuntimeError("Agent mode requires llm_model and rag_chain modules.")
                    if not st.session_state.get("agent_chain"):
                        retriever = st.session_state.get("retriever")
                        if retriever is None:
                            raise RuntimeError("Retriever not available for Agent mode.")
                        agent_model = os.getenv("AGENT_LLM_MODEL", "google/gemini-2.5-flash-lite")
                        agent_llm = get_llm(model_name=agent_model)
                        st.session_state.agent_chain = build_rag_chain(
                            llm=agent_llm,
                            retriever=retriever,
                            chain_type="stuff",
                            return_source_documents=True,
                        )
                    if not st.session_state.get("agent_orchestrator"):
                        st.session_state.agent_orchestrator = build_agent(
                            st.session_state.agent_chain,
                            st.session_state.get("extract_ingredients_fn") or (lambda x: {"items": [], "notes": "llm_unavailable"}),
                            st.session_state.get("compute_nutrition_fn") or (lambda items: {"totals": {}, "details": []}),
                        )
                    agent = st.session_state.agent_orchestrator
                    agent_out = agent.run(original_query)
                    assistant_response = agent_out.get("answer", "")
                    st.session_state.last_agent_trace = agent_out.get("trace", [])
                    result = {"result": assistant_response, "source_documents": []}
                elif current_mode == "User Coach":
                    # Fetch user preferences
                    prefs = (
                        db_manager.get_user_preferences(
                            st.session_state.user_data["id"]
                        )
                        or {}
                    )
                    if not prefs:
                        assistant_response = "I need your saved profile to personalize advice. Go to Nutrition Plan, fill the form, and click 'Save Data'."
                        raise Exception("no_user_prefs")
                    # Compose a concise user profile JSON with macros if available
                    try:
                        prefs_json = json.dumps(prefs, ensure_ascii=False)
                    except Exception:
                        prefs_json = str(prefs)

                    # First retrieve documents using the original query
                    retrieval_docs = st.session_state.qa_chain.retriever.get_relevant_documents(
                        original_query
                    )

                    # Then create the coach-specific prompt with user profile
                    coach_preamble = (
                        "You are a personal nutrition coach for this user. Use the USER PROFILE JSON below together with retrieved documents. "
                        "Prioritize user's constraints (allergies, preferences, goals). Be concise and actionable.\n"
                        f"USER PROFILE: {prefs_json}\n"
                    )
                    coach_query = coach_preamble + f"Question: {original_query}"

                    # Use the chain with retrieved documents and coach query
                    result = st.session_state.qa_chain._call(
                        {
                            "query": coach_query,
                            "input_documents": retrieval_docs,
                        }
                    )
                else:
                    result = st.session_state.qa_chain.invoke({"query": original_query})

                assistant_response = (
                    result.get("result") if isinstance(result, dict) else str(result)
                )

                # Fallback: if no sources, provide a brief general answer
                source_docs = []
                if isinstance(result, dict):
                    source_docs = result.get("source_documents") or []
                if not source_docs:
                    try:
                        llm = st.session_state.get("llm")
                        if llm is None:
                            raise RuntimeError("LLM not available for fallback.")
                        if current_mode == "User Coach":
                            brief_prompt = (
                                "Answer in ONE short sentence tailored to the USER PROFILE. "
                                f"USER PROFILE: {prefs_json if 'prefs_json' in locals() else '{}'}\n"
                                f"Question: {prompt}"
                            )
                        else:
                            brief_prompt = (
                                "Answer in ONE short, direct sentence (<=20 words). "
                                f"Question: {prompt}"
                            )
                        generic = llm.invoke(brief_prompt)
                        assistant_response = (
                            generic.content if (hasattr(generic, "content") and generic.content) else str(generic)
                        )
                        assistant_response = assistant_response.strip().split("\n")[0]
                        if "." in assistant_response:
                            assistant_response = assistant_response.split(".")[0] + "."
                        assistant_response = assistant_response[:200]
                        assistant_response += "\n\n(Note: No relevant documents were found; this is a brief general answer.)"
                    except Exception as e_fallback:
                        assistant_response = f"RAG returned no sources and fallback failed: {e_fallback}"
            except Exception as e:
                assistant_response = f"RAG error: {e}"

            chat_manager.add_message_to_chat(
                st.session_state.current_session_id,
                st.session_state.user_data["id"],
                prompt,
                assistant_response,
            )
            st.rerun()

        if st.session_state.get("chat_mode") == "Agent":
            trace = st.session_state.get("last_agent_trace") or []
            render_agent_trace(trace)
