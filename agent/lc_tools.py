"""
LangChain-compatible tool wrappers.

Each function is decorated with @tool so LangGraph's ToolNode can
discover, call, and handle them automatically.

The actual business logic lives in agent/executor.py — these are
thin adapters that serialize/deserialize JSON for the LangChain layer.
"""
import json
from langchain_core.tools import tool

from agent.executor import execute_tool as _run


def _safe_run(tool_name: str, args: dict):
    """Run executor with structured error handling.

    Returns a dict: {"success": bool, "result"|"error": ...}
    """
    try:
        res = _run(tool_name, args)
        return {"success": True, "result": res}
    except Exception as e:
        # Try to extract structured info from the exception if present
        err = {"type": e.__class__.__name__, "message": str(e)}
        try:
            if len(e.args) == 1 and isinstance(e.args[0], dict):
                err.update(e.args[0])
        except Exception:
            pass
        return {"success": False, "error": err}


@tool
def search_customer(query: str) -> str:
    """
    Search the CRM database for a customer.
    Accepts a customer name, email address, phone number, or customer ID (e.g. C001).
    Returns matching profile(s) or a not-found message.
    """
    result = _safe_run("search_customer", {"query": query})
    return json.dumps(result)


@tool
def get_order_details(order_id: str = "", customer_id: str = "") -> str:
    """
    Retrieve order information.
    - Provide order_id (e.g. ORD-1001) to get a specific order.
    - Provide customer_id to list all orders for that customer.
    At least one argument must be supplied.
    """
    args = {}
    if order_id:
        args["order_id"] = order_id
    if customer_id:
        args["customer_id"] = customer_id
    if not args:
        return json.dumps({"success": False, "error": {"message": "Provide order_id or customer_id."}})
    result = _safe_run("get_order_details", args)
    return json.dumps(result)


@tool
def validate_refund_eligibility(
    customer_id: str,
    order_id: str,
    customer_reason: str,
) -> str:
    """
    Run the full refund policy engine against a customer + order pair.
    Returns:
      - eligible (bool)
      - blocking_issues: list of policy violations that prevent a refund
      - advisory_notes: warnings (fraud flags, high-value, photo required, etc.)
      - days_since_delivery, return_window_days, is_defective
      - should_escalate (bool) — true when manager review is required
    """
    result = _safe_run("validate_refund_eligibility", {
        "customer_id":     customer_id,
        "order_id":        order_id,
        "customer_reason": customer_reason,
    })
    return json.dumps(result)


@tool
def process_refund_decision(
    customer_id: str,
    order_id: str,
    decision: str,
    policy_rationale: str,
    refund_amount: float = 0.0,
) -> str:
    """
    Commit the final refund decision to the system.
    decision must be one of: APPROVED, DENIED, ESCALATED.
    - APPROVED  → refund is granted; provide refund_amount.
    - DENIED    → refund is rejected; cite policy_rationale (§1, §4, etc.).
    - ESCALATED → needs manager review (orders >$500 or flagged accounts).
    Returns a confirmation with refund_id or escalation_id.
    """
    args: dict = {
        "customer_id":      customer_id,
        "order_id":         order_id,
        "decision":         decision,
        "policy_rationale": policy_rationale,
    }
    decision_upper = decision.upper() if isinstance(decision, str) else ""
    if decision_upper not in {"APPROVED", "DENIED", "ESCALATED"}:
        return json.dumps({"success": False, "error": {"message": "Invalid decision. Must be one of APPROVED, DENIED, ESCALATED."}})
    if decision_upper == "APPROVED":
        try:
            amt = float(refund_amount)
        except Exception:
            return json.dumps({"success": False, "error": {"message": "Invalid refund_amount; must be numeric."}})
        if amt <= 0:
            return json.dumps({"success": False, "error": {"message": "refund_amount must be greater than 0 for APPROVED decisions."}})
        args["refund_amount"] = amt

    result = _safe_run("process_refund_decision", args)
    return json.dumps(result)


# Exported list used by ChatOpenAI.bind_tools() and ToolNode
LANGCHAIN_TOOLS = [
    search_customer,
    get_order_details,
    validate_refund_eligibility,
    process_refund_decision,
]
