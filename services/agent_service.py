from typing import Any, Dict, Optional

from agents.orchestrator import AgentOrchestrator
from agents.tools import make_retrieval_tool, make_macro_calculator_tool
from agents.verifier import basic_verifier


def build_agent(
    qa_chain: Optional[Any],
    extract_ingredients_fn,
    compute_nutrition_fn,
) -> AgentOrchestrator:
    tools: Dict[str, Any] = {}
    # Only include retrieval tool when a retriever/qa_chain is available
    if qa_chain is not None:
        tools["retrieval"] = make_retrieval_tool(qa_chain)
    tools["macro_calculator"] = make_macro_calculator_tool(
        extract_ingredients_fn, compute_nutrition_fn
    )
    return AgentOrchestrator(tools=tools, verifier=basic_verifier)


def run_agent(agent: AgentOrchestrator, query: str) -> Dict[str, Any]:
    return agent.run(query)
