from langgraph.graph import END, StateGraph

from advisor_agents.state import AdvisorState


def portfolio_analyst(state: AdvisorState) -> AdvisorState:
    state["findings"].append(
        {
            "agent": "Portfolio Analyst",
            "summary": "Initial scaffold: analyze concentration, allocation, strengths, and weaknesses.",
            "confidence_score": 0.0,
            "risk_score": 0.0,
        }
    )
    return state


def build_advisor_graph():
    graph = StateGraph(AdvisorState)
    graph.add_node("portfolio_analyst", portfolio_analyst)
    graph.set_entry_point("portfolio_analyst")
    graph.add_edge("portfolio_analyst", END)
    return graph.compile()
