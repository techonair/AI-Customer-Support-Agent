"""
Tool executor — runs each tool function locally against mock data.
No LLM calls here; this is pure deterministic business logic.
"""
import re
import random
from datetime import date, datetime

from data.customers import CUSTOMERS
from data.orders import ORDERS
from data.policy import TODAY


def _days_since(delivery_date_str: str) -> int:
    today = datetime.strptime(TODAY, "%Y-%m-%d").date()
    delivery = datetime.strptime(delivery_date_str, "%Y-%m-%d").date()
    return (today - delivery).days


def _return_window(category: str) -> int:
    if category == "Electronics":
        return 15
    if category in ("Health", "Beauty", "Food", "Perishables"):
        return 7
    return 30


def _is_defective(condition: str) -> bool:
    patterns = r"defect|not charge|will not|dead pixel|double.fir|motor|allergic|broken|no audio"
    return bool(re.search(patterns, condition, re.IGNORECASE))


# ──────────────────────────────────────────────
# Tool: search_customer
# ──────────────────────────────────────────────
def search_customer(query: str) -> dict:
    q = query.lower().strip()
    results = [
        c for c in CUSTOMERS.values()
        if q in c["id"].lower()
        or q in c["name"].lower()
        or q in c["email"].lower()
        or q in c["phone"]
    ]
    if not results:
        return {"found": False, "message": f'No customer found matching "{query}"'}
    return {"found": True, "count": len(results), "customers": results}


# ──────────────────────────────────────────────
# Tool: get_order_details
# ──────────────────────────────────────────────
def get_order_details(order_id: str = None, customer_id: str = None) -> dict:
    if order_id:
        order = ORDERS.get(order_id)
        if not order:
            return {"found": False, "message": f"Order {order_id} not found"}
        customer = CUSTOMERS.get(order["customer_id"])
        return {"found": True, "order": order, "customer": customer}

    if customer_id:
        orders = [o for o in ORDERS.values() if o["customer_id"] == customer_id]
        return {"found": len(orders) > 0, "count": len(orders), "orders": orders}

    return {"error": "Provide order_id or customer_id"}


# ──────────────────────────────────────────────
# Tool: validate_refund_eligibility
# ──────────────────────────────────────────────
def validate_refund_eligibility(customer_id: str, order_id: str, customer_reason: str) -> dict:
    customer = CUSTOMERS.get(customer_id)
    order = ORDERS.get(order_id)

    if not customer:
        return {"eligible": False, "blocking_issues": ["Customer ID not found in CRM"], "advisory_notes": []}
    if not order:
        return {"eligible": False, "blocking_issues": ["Order ID not found in system"], "advisory_notes": []}

    blocking = []
    advisory = []

    # §1 Digital products
    if order["is_digital"]:
        blocking.append("§1: Digital downloads are non-refundable under any circumstances")

    # §4 Final sale
    if order["is_sale_item"]:
        blocking.append("§4: Item is marked FINAL SALE — no returns or refunds permitted")

    # §4 Customized
    if order["is_customized"]:
        blocking.append("§4: Customized/personalized items cannot be returned")

    # §3 Refund limit
    if customer["refunds_this_year"] >= 2:
        blocking.append(
            f"§3: Annual refund limit reached — customer has used {customer['refunds_this_year']}/2 refunds this year"
        )

    # §5 Flagged account
    if customer["flagged"]:
        blocking.append("§5: Account is flagged — mandatory manager escalation required")

    # §1 Return window
    days_since = _days_since(order["delivery_date"])
    window = _return_window(order["category"])
    defective = _is_defective(order["condition"])

    if days_since > window:
        if defective:
            advisory.append(
                f"§1: {days_since} days since delivery (>{window}d window for {order['category']}), "
                "but defective items qualify regardless of return window"
            )
        else:
            blocking.append(
                f"§1: Return window expired — {days_since} days since delivery "
                f"({order['category']} limit is {window} days)"
            )

    # §3 High-value escalation
    should_escalate = order["price"] > 500 or customer["flagged"]
    if order["price"] > 500:
        advisory.append(f"§3: High-value order (${order['price']:.2f}) — manager escalation required per policy")

    # §5 Fraud risk
    if customer["refunds_this_year"] >= 3:
        advisory.append(
            f"§5: FRAUD ALERT — customer has {customer['refunds_this_year']} refunds in 12 months, "
            "flag for fraud review team"
        )

    # §2 Photo verification
    if defective and order["price"] > 300:
        advisory.append("§2: Defective item over $300 — photo/video verification required before approval")

    return {
        "eligible": len(blocking) == 0,
        "should_escalate": should_escalate,
        "blocking_issues": blocking,
        "advisory_notes": advisory,
        "days_since_delivery": days_since,
        "return_window_days": window,
        "is_defective": defective,
        "summary": {
            "customer_name": customer["name"],
            "tier": customer["tier"],
            "refunds_this_year": customer["refunds_this_year"],
            "product": order["product"],
            "price": order["price"],
            "condition": order["condition"],
        },
    }


# ──────────────────────────────────────────────
# Tool: process_refund_decision
# ──────────────────────────────────────────────
def process_refund_decision(
    customer_id: str,
    order_id: str,
    decision: str,
    policy_rationale: str,
    refund_amount: float = None,
) -> dict:
    customer = CUSTOMERS.get(customer_id)
    order = ORDERS.get(order_id)

    if not customer or not order:
        return {"success": False, "error": "Invalid customer_id or order_id"}

    refund_id = f"REF-{random.randint(10000, 99999)}" if decision == "APPROVED" else None
    escalation_id = f"ESC-{random.randint(1000, 9999)}" if decision == "ESCALATED" else None

    return {
        "success": True,
        "decision": decision,
        "refund_id": refund_id,
        "escalation_id": escalation_id,
        "customer_name": customer["name"],
        "product": order["product"],
        "amount": refund_amount if refund_amount else (order["price"] if decision == "APPROVED" else 0),
        "policy_rationale": policy_rationale,
        "processing_time": "5–7 business days" if decision == "APPROVED" else None,
        "timestamp": TODAY,
    }


# ──────────────────────────────────────────────
# Router — maps tool name → function
# ──────────────────────────────────────────────
def execute_tool(name: str, args: dict) -> dict:
    dispatch = {
        "search_customer": lambda a: search_customer(**a),
        "get_order_details": lambda a: get_order_details(**a),
        "validate_refund_eligibility": lambda a: validate_refund_eligibility(**a),
        "process_refund_decision": lambda a: process_refund_decision(**a),
    }
    handler = dispatch.get(name)
    if not handler:
        return {"error": f"Unknown tool: {name}"}
    try:
        return handler(args)
    except TypeError as e:
        return {"error": f"Tool argument error: {e}"}
