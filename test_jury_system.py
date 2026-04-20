#!/usr/bin/env python3
"""Quick test of the Redaction Jury System."""

from app.module2.logic import run_redaction_jury

# Test 1: Text with Malaysian IC numbers
test_text_1 = "Contact John at 123456-12-5678 or call 0123456789 for more info."
print("Test 1: Malaysian IC and Phone")
print(f"Input: {test_text_1}")
result_1 = run_redaction_jury(test_text_1)
print(f"Sanitized: {result_1['sanitized_prompt']}")
print(f"Winner: Tool {result_1['winning_tool']}")
print(f"Scores: {result_1['tool_scores']}")
print(f"Tool Counts: {result_1['tool_counts']}")
print()

# Test 2: Text with names and locations
test_text_2 = "Ahmad from Kuala Lumpur sent an email to fatimah@example.com about the Selangor project."
print("Test 2: Names and Locations")
print(f"Input: {test_text_2}")
result_2 = run_redaction_jury(test_text_2)
print(f"Sanitized: {result_2['sanitized_prompt']}")
print(f"Winner: Tool {result_2['winning_tool']}")
print(f"Scores: {result_2['tool_scores']}")
print(f"Tool Counts: {result_2['tool_counts']}")
print()

# Test 3: Text with multiple PII types
test_text_3 = "Hassan (ID: 850315-01-1234) lives in Penang. Phone: +60123456789, Email: hassan@business.my"
print("Test 3: Multiple PII Types")
print(f"Input: {test_text_3}")
result_3 = run_redaction_jury(test_text_3)
print(f"Sanitized: {result_3['sanitized_prompt']}")
print(f"Winner: Tool {result_3['winning_tool']}")
print(f"Scores: {result_3['tool_scores']}")
print(f"Tool Counts: {result_3['tool_counts']}")
print()

# Test 4: Empty text
test_text_4 = ""
print("Test 4: Empty Text")
print(f"Input: '{test_text_4}'")
result_4 = run_redaction_jury(test_text_4)
print(f"Sanitized: '{result_4['sanitized_prompt']}'")
print(f"Winner: {result_4['winning_tool']}")
print(f"Scores: {result_4['tool_scores']}")
