from typing import Any
import os
import asyncio
import json
import streamlit as st

from services.rag_service import init_rag
 
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
    """Render the Ask Anything page (General, User Coach, Agent).
    NOTE: Not used yet. Call from app.py when ready to migrate.
    """
    col1, col2 = st.columns([0.6, 3.4], gap="medium")

    with col1:
        st.subheader("💬 Chat Sessions")
        if "chat_mode" not in st.session_state:
            st.session_state.chat_mode = "General"
        st.radio(
            "Mode",
            options=["General", "User Coach", "Agent"],
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
                category = session.get("category") or "General"
                is_current = session_id == st.session_state.current_session_id
                button_type = "primary" if is_current else "secondary"
                label = f"{'🟢 ' if is_current else '💬 '}{title[:25]}" + (
                    "..." if len(title) > 25 else ""
                )
                if category == "User Coach":
                    badge = " [Coach]"
                elif category == "Agent":
                    badge = " [Agent]"
                else:
                    badge = " [General]"
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
                # Determine session mode (category) first
                current_mode = "General"
                for s in st.session_state.chat_sessions or []:
                    if s.get("id") == st.session_state.current_session_id:
                        current_mode = s.get("category") or "General"
                        break
                # Only require RAG init for non-Agent modes
                if current_mode != "Agent" and st.session_state.qa_chain is None:
                    raise RuntimeError(
                        "RAG is not initialized. Check your OpenRouter LLM and vector store."
                    )

                original_query = prompt
                if current_mode == "Agent":
                    # Rewritten Agent mode: pure LLM responder that always answers in Burmese.
                    if get_llm is None:
                        raise RuntimeError("Agent mode requires llm_model module.")
                    if not st.session_state.get("agent_llm"):
                        agent_model = os.getenv("AGENT_LLM_MODEL", "google/gemini-2.5-flash-lite")
                        st.session_state.agent_llm = get_llm(model_name=agent_model)
                    # Detect Myanmar script
                    def _is_mm(text: str) -> bool:
                        try:
                            return any(0x1000 <= ord(ch) <= 0x109F or 0xAA60 <= ord(ch) <= 0xAA7F for ch in text)
                        except Exception:
                            return False
                    is_mm = _is_mm(original_query)
                    # Compose a direct instruction to always answer in Burmese
                    system_prefix = (
                        "အသုံးပြုသူ၏ မေးခွန်းကို မြန်မာဘာသာဖြင့်သာ ပြန်လည်ဖြေကြားပါ။ နေ့စဉ် အာဟာရ/စားစရာ အကြံပြုရန် တောင်းခံပါက ၂–၃ မျိုး အကြံပြုပြီး ကယ်လိုရီ/ပရိုတင်း/ကာဗို/အဆီ ခန့်မှန်းချက်ကို ရိုးရှင်းစွာ ထည့်သွင်းဖော်ပြပါ။ "
                    )
                    prompt_text = f"{system_prefix}\nမေးခွန်း: {original_query}"
                    resp = st.session_state.agent_llm.invoke(prompt_text)
                    assistant_response = resp.content if (hasattr(resp, "content") and resp.content) else str(resp)
                    assistant_response = assistant_response.strip()
                    # If the user typed non-Burmese, still translate to Burmese
                    if not is_mm:
                        try:
                            trans = st.session_state.agent_llm.invoke("Translate the following answer to natural Burmese. Keep numbers/units unchanged.\n" + assistant_response)
                            tr = trans.content if (hasattr(trans, "content") and trans.content) else str(trans)
                            assistant_response = (tr or assistant_response).strip()
                        except Exception:
                            pass
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
                        "You are a personal nutrition coach for this user.                  Use the USER PROFILE JSON below together with retrieved documents. "
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
                # Skip this note and fallback message in Agent mode to avoid confusing UX
                if current_mode != "Agent":
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
                            # assistant_response += "\n\n(Note: No relevant documents were found; this is a brief general answer.)"
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

        # No agent trace rendering in simplified Agent mode
