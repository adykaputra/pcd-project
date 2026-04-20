"""
REDACTION JURY SYSTEM - DATA FLOW DOCUMENTATION

This document shows the complete flow of data through the system.
"""

# ============================================================================
# FLOW 1: USER REQUEST PROCESSING
# ============================================================================

USER_REQUEST = {
    "role": "admin",
    "prompt": "Contact Ahmad at 0123456789. ID: 850315-01-1234"
}

# Step 1: Flask receives POST /sanitize request
# Step 2: Authorization check (is_authorized checks role policies)
# Step 3: Call run_redaction_jury(prompt)

# ============================================================================
# FLOW 2: JURY EXECUTION (PARALLEL PROCESSING)
# ============================================================================

# TOOL A: REGEX DETECTION
tool_a_input = "Contact Ahmad at 0123456789. ID: 850315-01-1234"
tool_a_detections = {
    "id_matches": ["850315-01-1234"],          # 1 Malaysian IC
    "phone_matches": ["0123456789"],           # 1 Phone
    "email_matches": []                        # 0 Emails
}
tool_a_output = {
    "redacted": "Contact Ahmad at [REDACTED_PHONE]. ID: [REDACTED_ID]",
    "counts": {"id": 1, "phone": 1, "email": 0},
    "score": 2
}

# TOOL B: DICTIONARY DETECTION
tool_b_input = "Contact Ahmad at 0123456789. ID: 850315-01-1234"
tool_b_detections = {
    "names": ["Ahmad"],                        # 1 Name
    "locations": [],                           # 0 Locations
    "other": []
}
tool_b_output = {
    "redacted": "Contact [REDACTED_NAME] at 0123456789. ID: 850315-01-1234",
    "counts": {"id": 1, "phone": 0, "email": 0},
    "score": 1
}

# TOOL C: MOCK AI DETECTION
tool_c_input = "Contact Ahmad at 0123456789. ID: 850315-01-1234"
tool_c_detections = {
    "id_patterns": ["850315-01-1234"],         # 1 ID-like pattern
    "phone_patterns": ["0123456789"],          # 1 Phone pattern
    "email_patterns": []                       # 0 Email patterns
}
tool_c_output = {
    "redacted": "Contact Ahmad at [REDACTED_PHONE]. ID: [REDACTED_ID]",
    "counts": {"id": 1, "phone": 1, "email": 0},
    "score": 2
}

# ============================================================================
# FLOW 3: JURY VERDICT
# ============================================================================

JURY_SCORES = {
    "A": 2,  # Tool A total detections
    "B": 1,  # Tool B total detections  
    "C": 2   # Tool C total detections
}

JURY_VERDICT = {
    "winning_tool": "A",  # First tool to reach max score (deterministic)
    "selected_output": tool_a_output["redacted"],
    "tool_scores": JURY_SCORES,
    "all_tool_outputs": {
        "A": tool_a_output,
        "B": tool_b_output,
        "C": tool_c_output
    }
}

# ============================================================================
# FLOW 4: API RESPONSE
# ============================================================================

API_RESPONSE = {
    "status": "sanitized",
    "sanitized_prompt": "Contact Ahmad at [REDACTED_PHONE]. ID: [REDACTED_ID]",
    "reliability_summary": {
        "winning_tool": "A",
        "tool_comparison": {
            "Tool_A_Regex_Count": 2,
            "Tool_B_Dictionary_Count": 1,
            "Tool_C_MockAI_Count": 2
        },
        "detailed_counts": {
            "Tool_A": {"id": 1, "phone": 1, "email": 0},
            "Tool_B": {"id": 1, "phone": 0, "email": 0},
            "Tool_C": {"id": 1, "phone": 1, "email": 0}
        }
    }
}

# ============================================================================
# FLOW 5: AUDIT LOGGING
# ============================================================================

AUDIT_EVENT = {
    "ts": "2026-03-12T07:15:23.456789Z",
    "event_type": "PII_REDACTED_JURY",
    "request_id": "abc-def-ghi-jkl",
    "user_role": "admin",
    "endpoint": "/sanitize",
    "message": "PII detected and redacted using Redaction Jury. Winner: Tool A",
    
    # From winning tool (Tool A)
    "count_id": 1,
    "count_phone": 1,
    "count_email": 0,
    
    # Jury comparison data
    "winning_tool": "A",
    "tool_a_counts": '{"id": 1, "phone": 1, "email": 0}',
    "tool_b_counts": '{"id": 1, "phone": 0, "email": 0}',
    "tool_c_counts": '{"id": 1, "phone": 1, "email": 0}',
    
    # Additional metadata
    "metadata": {
        "original_prompt_sample": "Contact Ahmad at 0123456789. ID: 8503...",
        "tool_scores": {"A": 2, "B": 1, "C": 2}
    },
    
    # Integrity verification
    "signature": "a3f7b2e9c1d4f5a8b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3"
}

# ============================================================================
# FLOW 6: DATABASE PERSISTENCE
# ============================================================================

SQL_INSERT = """
INSERT INTO audit_events (
    ts, event_type, request_id, user_role, endpoint, message,
    count_id, count_phone, count_email,
    winning_tool, tool_a_counts, tool_b_counts, tool_c_counts,
    metadata, signature
) VALUES (
    '2026-03-12T07:15:23.456789Z',
    'PII_REDACTED_JURY',
    'abc-def-ghi-jkl',
    'admin',
    '/sanitize',
    'PII detected and redacted using Redaction Jury. Winner: Tool A',
    1, 1, 0,
    'A',
    '{"id": 1, "phone": 1, "email": 0}',
    '{"id": 1, "phone": 0, "email": 0}',
    '{"id": 1, "phone": 1, "email": 0}',
    '{"original_prompt_sample": "...", "tool_scores": {...}}',
    'a3f7b2e9c1d4f5a8b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3'
)
"""

DATABASE_RECORD = {
    "id": 42,
    "ts": "2026-03-12T07:15:23.456789Z",
    "event_type": "PII_REDACTED_JURY",
    "request_id": "abc-def-ghi-jkl",
    "user_role": "admin",
    "endpoint": "/sanitize",
    "message": "PII detected and redacted using Redaction Jury. Winner: Tool A",
    "count_id": 1,
    "count_phone": 1,
    "count_email": 0,
    "winning_tool": "A",
    "tool_a_counts": '{"id": 1, "phone": 1, "email": 0}',
    "tool_b_counts": '{"id": 1, "phone": 0, "email": 0}',
    "tool_c_counts": '{"id": 1, "phone": 1, "email": 0}',
    "metadata": '{"original_prompt_sample": "...", "tool_scores": {...}}',
    "signature": "a3f7b2e9c1d4f5a8b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3"
}

# ============================================================================
# FLOW 7: DASHBOARD VISUALIZATION
# ============================================================================

DASHBOARD_DISPLAY = {
    "page_title": "Redaction Reliability Comparison Dashboard",
    "jury_system_overview": {
        "Tool_A": "Advanced Regex Pattern Matching",
        "Tool_B": "Keyword-based Dictionary Matching",
        "Tool_C": "Mock AI NLP Detection"
    },
    "audit_logs_table": [
        {
            "id": 42,
            "ts": "2026-03-12T07:15:23Z",
            "event_type": "PII_REDACTED_JURY",
            "user_role": "admin",
            "winning_tool": "A",
            "items_detected": "ID: 1, Phone: 1, Email: 0",
            "signature": "a3f7b2e9..."
        }
    ],
    "reliability_summary_table": [
        {
            "event_id": 42,
            "tool_a_detections": "1 ID, 1 Phone",
            "tool_b_detections": "1 ID, 0 Phone",
            "tool_c_detections": "1 ID, 1 Phone",
            "winner": "Tool A"
        }
    ]
}

# ============================================================================
# FLOW 8: ADMIN SUMMARY API
# ============================================================================

ADMIN_SUMMARY = {
    "status": "ok",
    "summary": {
        "total_blocked_last_24h": 5,
        "pii_redacted_last_24h": {
            "malaysian_ic": 12,
            "emails": 8
        },
        "frequent_forbidden_intents": [
            ("access_other_users_data", 3),
            ("exfiltrate_sensitive_data", 2)
        ],
        "integrity_ok": True,
        "tampered_ids": []
    }
}

# ============================================================================
# SYSTEM ARCHITECTURE DIAGRAM
# ============================================================================

"""
                         USER REQUEST
                              |
                              v
                     ┌─────────────────┐
                     │ Flask /sanitize │
                     └─────────────────┘
                              |
                              v
                      ┌──────────────────┐
                      │ Authorization    │
                      │ Check (is_auth)  │
                      └──────────────────┘
                              |
                ┌─────────────┼─────────────┐
                v             v             v
          ┌──────────┐   ┌──────────┐   ┌──────────┐
          │ TOOL A   │   │ TOOL B   │   │ TOOL C   │
          │ Regex    │   │Dictionary│   │ Mock AI  │
          └──────────┘   └──────────┘   └──────────┘
                |             |             |
                v             v             v
          [Regex A output] [Dict B output] [AI C output]
                            +            +
                            |            |
                            v            v
                      ┌─────────────────┐
                      │ Score Comparison│
                      │ A:2, B:1, C:2   │
                      └─────────────────┘
                              |
                              v
                      ┌─────────────────┐
                      │ Winner = Tool A │
                      └─────────────────┘
                              |
                ┌─────────────┼─────────────┐
                v             v             v
           API Response  Audit Log    Dashboard
           (with summary) (persisted)  (visualization)
"""

# ============================================================================
# CODE EXECUTION TRACE
# ============================================================================

"""
EXECUTION FLOW:

1. POST /sanitize
   └─→ app/module2/routes.py:sanitize()
       ├─→ is_authorized(role, prompt)
       ├─→ run_redaction_jury(prompt)
       │   ├─→ _tool_a_regex_redaction(prompt)
       │   │   ├─→ MALAYSIAN_IC_RE.findall(text)
       │   │   ├─→ PHONE_RE.findall(text)
       │   │   ├─→ EMAIL_RE.findall(text)
       │   │   ├─→ MALAYSIAN_IC_RE.subn(...)
       │   │   ├─→ PHONE_RE.subn(...)
       │   │   ├─→ EMAIL_RE.subn(...)
       │   │   └─→ return (redacted_text, counts)
       │   │
       │   ├─→ _tool_b_dictionary_redaction(prompt)
       │   │   ├─→ for each name in COMMON_NAMES: regex match and replace
       │   │   ├─→ for each location in COMMON_LOCATIONS: regex match/replace
       │   │   └─→ return (redacted_text, counts)
       │   │
       │   ├─→ _tool_c_mock_ai_redaction(prompt)
       │   │   ├─→ ID pattern detection and redaction
       │   │   ├─→ Phone pattern detection and redaction
       │   │   ├─→ Email pattern detection and redaction
       │   │   └─→ return (redacted_text, counts)
       │   │
       │   ├─→ Calculate scores (sum of all counts)
       │   ├─→ Determine winner (max score)
       │   ├─→ Select winning output
       │   └─→ return jury_result dict
       │
       ├─→ get_manager().record_event({
       │       ts, event_type="PII_REDACTED_JURY",
       │       request_id, user_role, endpoint, message,
       │       count_id, count_phone, count_email (from winner),
       │       winning_tool, tool_a_counts, tool_b_counts, tool_c_counts,
       │       metadata, signature
       │   })
       │
       └─→ return jsonify({
               status: "sanitized",
               sanitized_prompt: (from winner),
               reliability_summary: {
                   winning_tool, tool_comparison, detailed_counts
               }
           })

2. Audit Recording (async via audit handler)
   └─→ app/audit.py:AuditManager.record_event()
       ├─→ Build canonical payload
       ├─→ Calculate HMAC signature
       └─→ INSERT into audit_events table

3. Dashboard Rendering
   └─→ GET /audit/dashboard
       └─→ app/module4/routes.py:dashboard()
           ├─→ SELECT last 100 records from audit_events
           ├─→ Parse JSON tool_counts fields
           └─→ Render DASHBOARD_HTML with parsed data
"""

# ============================================================================
# TOOL COMPARISON MATRIX
# ============================================================================

COMPARISON_MATRIX = {
    "Malaysian IC Numbers": {
        "Tool A (Regex)": "✓ Excellent - Precise pattern matching",
        "Tool B (Dictionary)": "✗ No - No IC in dictionary",
        "Tool C (Mock AI)": "✓ Good - Flexible pattern detection"
    },
    "Phone Numbers": {
        "Tool A (Regex)": "✓ Excellent - Strict +60/01x validation",
        "Tool B (Dictionary)": "✗ No - No phone patterns",
        "Tool C (Mock AI)": "✓ Good - Broader digit pattern detection"
    },
    "Email Addresses": {
        "Tool A (Regex)": "✓ Good - Standard email regex",
        "Tool B (Dictionary)": "✗ No - No email in dictionary",
        "Tool C (Mock AI)": "✓ Good - Email variations supported"
    },
    "Names (Ahmad, Muhammad, etc.)": {
        "Tool A (Regex)": "✗ No - No semantic understanding",
        "Tool B (Dictionary)": "✓ Excellent - 19 common names",
        "Tool C (Mock AI)": "✗ No - Limited semantic awareness"
    },
    "Locations (KL, Selangor, etc.)": {
        "Tool A (Regex)": "✗ No - No location knowledge",
        "Tool B (Dictionary)": "✓ Excellent - 16 common locations",
        "Tool C (Mock AI)": "✗ No - Limited semantic awareness"
    }
}

# ============================================================================
# EXPECTED OUTCOMES BY SCENARIO
# ============================================================================

SCENARIOS = {
    "Scenario 1: Technical Customer Support": {
        "Input": "Customer John (ID: 850315-01-1234) called about order XYZ",
        "Tool A Score": 1,
        "Tool B Score": 0,
        "Tool C Score": 1,
        "Winner": "A (first to max)",
        "Best For": "Structured PII like IDs"
    },
    "Scenario 2: Human Relations": {
        "Input": "Ahmad from Kuala Lumpur discussed with Siti from Selangor",
        "Tool A Score": 0,
        "Tool B Score": 4,
        "Tool C Score": 0,
        "Winner": "B",
        "Best For": "Names and locations"
    },
    "Scenario 3: Mixed Information": {
        "Input": "Contact Ahmad (ID: 850315-01-1234) at +60123456789 in KL",
        "Tool A Score": 2,
        "Tool B Score": 3,
        "Tool C Score": 2,
        "Winner": "B",
        "Best For": "Diverse PII types"
    },
    "Scenario 4: Email Heavy": {
        "Input": "Send to ahmad@company.com and siti@business.my",
        "Tool A Score": 2,
        "Tool B Score": 0,
        "Tool C Score": 2,
        "Winner": "A",
        "Best For": "Email detection"
    }
}

print(__doc__)
