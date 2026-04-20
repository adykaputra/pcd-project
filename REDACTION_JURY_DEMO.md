#!/usr/bin/env python3
"""
Demonstration of the Redaction Reliability Comparison System
Shows how the /sanitize endpoint uses the Redaction Jury.
"""

import json

# Example 1: Request with Malaysian IC and Phone
example_1 = {
    "endpoint": "POST /sanitize",
    "request": {
        "role": "analyst",
        "prompt": "Customer John calls from +6012 3456789. His ID is 850315-01-1234."
    }
}

example_1_response = {
    "status": "sanitized",
    "sanitized_prompt": "Customer John calls from [REDACTED_PHONE]. His ID is [REDACTED_ID].",
    "reliability_summary": {
        "winning_tool": "C",
        "tool_comparison": {
            "Tool_A_Regex_Count": 1,
            "Tool_B_Dictionary_Count": 0,
            "Tool_C_MockAI_Count": 2
        },
        "detailed_counts": {
            "Tool_A": {"id": 0, "phone": 1, "email": 0},
            "Tool_B": {"id": 0, "phone": 0, "email": 0},
            "Tool_C": {"id": 1, "phone": 1, "email": 0}
        }
    }
}

# Example 2: Request with names and locations
example_2 = {
    "endpoint": "POST /sanitize",
    "request": {
        "role": "manager",
        "prompt": "Contact Ahmad in Kuala Lumpur or Siti in Selangor. Email: ahmad@company.com"
    }
}

example_2_response = {
    "status": "sanitized",
    "sanitized_prompt": "Contact [REDACTED_NAME] in [REDACTED_LOCATION] or [REDACTED_NAME] in [REDACTED_LOCATION]. Email: [REDACTED_NAME]@company.com",
    "reliability_summary": {
        "winning_tool": "B",
        "tool_comparison": {
            "Tool_A_Regex_Count": 1,
            "Tool_B_Dictionary_Count": 4,
            "Tool_C_MockAI_Count": 1
        },
        "detailed_counts": {
            "Tool_A": {"id": 0, "phone": 0, "email": 1},
            "Tool_B": {"id": 2, "phone": 2, "email": 0},
            "Tool_C": {"id": 0, "phone": 0, "email": 1}
        }
    }
}

print("=" * 80)
print("REDACTION RELIABILITY COMPARISON SYSTEM - EXAMPLES")
print("=" * 80)
print()

print("EXAMPLE 1: Malaysian IC & Phone Detection")
print("-" * 80)
print("REQUEST:")
print(json.dumps(example_1["request"], indent=2))
print()
print("RESPONSE:")
print(json.dumps(example_1_response, indent=2))
print()
print("EXPLANATION:")
print("  - Tool A (Regex): Detected 1 phone number (Malaysian pattern matching)")
print("  - Tool B (Dictionary): Found 0 items (no names/locations in input)")
print("  - Tool C (Mock AI): Detected 2 items (more aggressive pattern matching)")
print("  - WINNER: Tool C with highest detection count (2 items)")
print("  - Audit logged: Event type 'PII_REDACTED_JURY', winning_tool='C'")
print()
print()

print("EXAMPLE 2: Name & Location Detection")
print("-" * 80)
print("REQUEST:")
print(json.dumps(example_2["request"], indent=2))
print()
print("RESPONSE:")
print(json.dumps(example_2_response, indent=2))
print()
print("EXPLANATION:")
print("  - Tool A (Regex): Detected 1 email (email pattern matching)")
print("  - Tool B (Dictionary): Detected 4 items (2 names + 2 locations)")
print("  - Tool C (Mock AI): Detected 1 item (limited dictionary coverage)")
print("  - WINNER: Tool B with highest detection count (4 items)")
print("  - Audit logged: Event type 'PII_REDACTED_JURY', winning_tool='B'")
print()
print()

print("SYSTEM ARCHITECTURE")
print("-" * 80)
print("1. THREE TOOLS RUNNING IN PARALLEL:")
print("   - Tool A: Advanced Regex Patterns (Malaysian IC, Phone, Email)")
print("   - Tool B: Keyword-based Dictionary (Names, Locations)")
print("   - Tool C: Mock AI/NLP Layer (Broader pattern detection)")
print()
print("2. RELIABILITY SCORING:")
print("   - Each tool independently processes the same input text")
print("   - Counts are tallied: {id, phone, email} detections")
print("   - Score = sum of all detected items")
print()
print("3. WINNER SELECTION:")
print("   - Tool with highest total detection count wins")
print("   - Winning tool's output is returned to the user")
print()
print("4. AUDIT LOGGING:")
print("   - Event type: 'PII_REDACTED_JURY'")
print("   - Columns logged:")
print("     * winning_tool: A, B, or C")
print("     * tool_a_counts: JSON {'id': X, 'phone': Y, 'email': Z}")
print("     * tool_b_counts: JSON {'id': X, 'phone': Y, 'email': Z}")
print("     * tool_c_counts: JSON {'id': X, 'phone': Y, 'email': Z}")
print()
print("5. DASHBOARD VISUALIZATION:")
print("   - /audit/dashboard displays all jury comparisons")
print("   - Shows which tool won each comparison")
print("   - Compares detection capabilities across tools")
print()

print("=" * 80)
print("API ENDPOINTS")
print("=" * 80)
print()
print("POST /sanitize")
print("  Input: {role, prompt}")
print("  Output: {status, sanitized_prompt, reliability_summary}")
print("  Reliability summary includes tool comparison scores")
print()
print("GET /audit/dashboard")
print("  Displays Redaction Reliability Comparison Dashboard")
print("  Shows all jury results and tool performance metrics")
print()
print("GET /audit/summary")
print("  Admin endpoint for audit statistics")
print("  Shows total redacted PII and system integrity")
print()
