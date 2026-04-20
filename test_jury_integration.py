#!/usr/bin/env python3
"""
Integration test for the Redaction Reliability Comparison System.
Tests the /sanitize endpoint with the jury system.
"""

import json
import tempfile
from pathlib import Path

# Create a temporary audit database for testing
test_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
test_db_path = Path(test_db.name)
test_db.close()

# Mock the database path
import sys
sys.path.insert(0, '/home/mas/pcd')
from unittest.mock import patch

with patch('app.audit.DB_PATH', test_db_path):
    from app import create_app
    from app.audit import get_manager
    import datetime

    # Create Flask app
    app = create_app()

    # Initialize audit manager with test DB
    audit_mgr = get_manager()

    with app.test_client() as client:
        print("=" * 80)
        print("INTEGRATION TEST: Redaction Jury System")
        print("=" * 80)
        print()

        # Test 1: Request with Malaysian IC and Phone
        print("TEST 1: Malaysian IC & Phone Detection")
        print("-" * 80)
        
        request_1 = {
            "role": "admin",
            "prompt": "Contact Hassan at +60123456789. ID: 850315-01-1234"
        }
        
        print(f"Request: {json.dumps(request_1, indent=2)}")
        response_1 = client.post('/sanitize', json=request_1)
        data_1 = response_1.get_json()
        
        print(f"Status Code: {response_1.status_code}")
        print(f"Response: {json.dumps(data_1, indent=2)}")
        
        assert response_1.status_code == 200
        assert data_1['status'] == 'sanitized'
        assert 'winning_tool' in data_1['reliability_summary']
        assert 'tool_comparison' in data_1['reliability_summary']
        print("✅ TEST 1 PASSED\n")

        # Test 2: Request with names and locations
        print("TEST 2: Names & Locations Detection")
        print("-" * 80)
        
        request_2 = {
            "role": "client",
            "prompt": "Ahmad works in Kuala Lumpur. Siti is in Selangor. Email: siti@company.com"
        }
        
        print(f"Request: {json.dumps(request_2, indent=2)}")
        response_2 = client.post('/sanitize', json=request_2)
        data_2 = response_2.get_json()
        
        print(f"Status Code: {response_2.status_code}")
        print(f"Response: {json.dumps(data_2, indent=2)}")
        
        assert response_2.status_code == 200
        assert data_2['status'] == 'sanitized'
        assert data_2['reliability_summary']['winning_tool'] == 'B'
        print("✅ TEST 2 PASSED\n")

        # Test 3: Verify audit logs were recorded
        print("TEST 3: Audit Logging Verification")
        print("-" * 80)
        
        conn = audit_mgr._connect()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM audit_events WHERE event_type = ?", ("PII_REDACTED_JURY",))
        count = cur.fetchone()[0]
        conn.close()
        
        print(f"Audit records created: {count}")
        assert count >= 2, f"Expected at least 2 audit records, got {count}"
        print("✅ TEST 3 PASSED\n")

        # Test 4: Verify database schema
        print("TEST 4: Database Schema Verification")
        print("-" * 80)
        
        conn = audit_mgr._connect()
        cur = conn.cursor()
        cur.execute("PRAGMA table_info(audit_events)")
        columns = {row[1] for row in cur.fetchall()}
        conn.close()
        
        required_columns = {'winning_tool', 'tool_a_counts', 'tool_b_counts', 'tool_c_counts'}
        missing = required_columns - columns
        
        print(f"Found columns: {columns}")
        assert not missing, f"Missing columns: {missing}"
        print("✅ TEST 4 PASSED\n")

        # Test 5: Verify audit record contents
        print("TEST 5: Audit Record Contents Verification")
        print("-" * 80)
        
        conn = audit_mgr._connect()
        cur = conn.cursor()
        cur.execute("""
            SELECT winning_tool, tool_a_counts, tool_b_counts, tool_c_counts 
            FROM audit_events 
            WHERE event_type = ? 
            ORDER BY id DESC 
            LIMIT 1
        """, ("PII_REDACTED_JURY",))
        row = cur.fetchone()
        conn.close()
        
        if row:
            winning_tool, a_counts, b_counts, c_counts = row
            print(f"Winning tool: {winning_tool}")
            print(f"Tool A counts: {a_counts}")
            print(f"Tool B counts: {b_counts}")
            print(f"Tool C counts: {c_counts}")
            
            assert winning_tool in ['A', 'B', 'C'], f"Invalid winning tool: {winning_tool}"
            
            # Verify counts are valid JSON
            import json
            json.loads(a_counts) if a_counts else None
            json.loads(b_counts) if b_counts else None
            json.loads(c_counts) if c_counts else None
            
            print("✅ TEST 5 PASSED\n")

        print("=" * 80)
        print("ALL TESTS PASSED ✅")
        print("=" * 80)
        print()
        print("Summary:")
        print("- Jury system is functioning correctly")
        print("- Tool comparison and winner selection working")
        print("- Audit logging capturing all jury data")
        print("- Database schema properly extended")
        print("- API responses include reliability summary")

# Cleanup
test_db_path.unlink(missing_ok=True)
