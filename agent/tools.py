"""
OpenAI function-calling tool definitions.
Each tool maps to an executor function in executor.py.
"""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_customer",
            "description": (
                "Search the CRM database for a customer by name, email address, "
                "phone number, or customer ID. Returns all matching profiles."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search term: customer name, email, phone, or customer ID (e.g. C001)"
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_order_details",
            "description": (
                "Retrieve full order information. "
                "Provide order_id to get a specific order, "
                "or customer_id to list all orders belonging to that customer."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {
                        "type": "string",
                        "description": "A specific order ID, e.g. ORD-1001"
                    },
                    "customer_id": {
                        "type": "string",
                        "description": "Customer ID to retrieve all their orders, e.g. C001"
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "validate_refund_eligibility",
            "description": (
                "Run the refund policy engine against a specific customer and order. "
                "Returns: eligible (bool), blocking_issues (list of policy violations), "
                "advisory_notes (warnings), days_since_delivery, is_defective, should_escalate."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_id": {
                        "type": "string",
                        "description": "The customer's ID"
                    },
                    "order_id": {
                        "type": "string",
                        "description": "The order ID to evaluate"
                    },
                    "customer_reason": {
                        "type": "string",
                        "description": "The customer's stated reason for requesting the refund"
                    }
                },
                "required": ["customer_id", "order_id", "customer_reason"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "process_refund_decision",
            "description": (
                "Commit the final refund decision to the system after eligibility has been checked. "
                "Use APPROVED when policy allows the refund, DENIED when it does not, "
                "and ESCALATED when manager review is required (orders >$500 or flagged accounts)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_id": {"type": "string"},
                    "order_id": {"type": "string"},
                    "decision": {
                        "type": "string",
                        "enum": ["APPROVED", "DENIED", "ESCALATED"],
                        "description": "The final decision"
                    },
                    "policy_rationale": {
                        "type": "string",
                        "description": "Which policy sections (§1, §3, etc.) justify this decision"
                    },
                    "refund_amount": {
                        "type": "number",
                        "description": "Dollar amount to refund — required when decision is APPROVED"
                    }
                },
                "required": ["customer_id", "order_id", "decision", "policy_rationale"]
            }
        }
    }
]
