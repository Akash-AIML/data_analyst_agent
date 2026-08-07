# test_analysis.py
"""Standalone test for Analysis Agent — uses mock profile from Member 1."""

import json
import sys
import os

# Add both the project root and parent to path so imports work under any launch context
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.dirname(project_root))

from agents.analysis_agent import planner_node, executor_node, reflector_node

def create_mock_state():
    """Creates a state object matching what Member 1 would produce."""
    with open("mocks/mock_profile.json", "r") as f:
        mock = json.load(f)
    
    state = {
        "csv_path": mock["csv_path"],
        "profile": mock["profile"],
        "profile_report_path": mock["profile_report_path"],
        "analysis_plan": None,
        "analysis_results": None,
        "generated_files": None,
        "execution_log": None,
        "reflection_notes": None,
        "validation_report": None,
        "insights": None,
        "recommendations": None,
        "report_path": None,
        "error_log": [],
        "status": "running"
    }
    return state

def test_planner():
    print("\n" + "="*50)
    print("TEST 1: PLANNER NODE")
    print("="*50)
    
    state = create_mock_state()
    state = planner_node(state)
    
    assert state["analysis_plan"] is not None, "Plan should not be None"
    assert len(state["analysis_plan"]) > 0, "Plan should have at least 1 task"
    
    for task in state["analysis_plan"]:
        assert "task_id" in task
        assert "task_name" in task
        assert "status" in task
        assert task["status"] == "pending"
    
    print(f"[OK] Planner created {len(state['analysis_plan'])} tasks:")
    for t in state["analysis_plan"]:
        print(f"   {t['task_id']}: {t['task_name']}")
    
    return state

def test_executor(state):
    print("\n" + "="*50)
    print("TEST 2: EXECUTOR NODE")
    print("="*50)
    
    # Run executor on first task
    state = executor_node(state)
    
    execution_log = state.get("execution_log", [])
    assert len(execution_log) > 0, "Should have at least 1 log entry"
    
    last_log = execution_log[-1]
    print(f"   Task: {last_log['task_name']}")
    print(f"   Attempt: {last_log['attempt']}")
    print(f"   Success: {last_log['success']}")
    
    if last_log["success"]:
        print(f"   [OK] Task completed")
        print(f"   Output preview: {last_log['stdout'][:200].strip()}")
    else:
        print(f"   [WARN] Task failed: {last_log.get('error', 'Unknown')[:200].strip()}")
    
    # Run executor until all tasks done or failed
    max_iterations = len(state["analysis_plan"]) * 4  # max 4 attempts per task
    for _ in range(max_iterations):
        pending = [t for t in state["analysis_plan"] if t["status"] == "pending"]
        if not pending:
            break
        state = executor_node(state)
    
    return state

def test_reflector(state):
    print("\n" + "="*50)
    print("TEST 3: REFLECTOR NODE")
    print("="*50)
    
    state = reflector_node(state)
    
    notes = state.get("reflection_notes", [])
    assert len(notes) > 0, "Should have reflection notes"
    
    print("   Reflection notes:")
    for note in notes:
        print(f"   • {note}")
    
    # Summary
    plan = state["analysis_plan"]
    completed = [t for t in plan if t["status"] == "completed"]
    failed = [t for t in plan if t["status"] == "failed"]
    pending = [t for t in plan if t["status"] == "pending"]
    
    print(f"\n   Summary: {len(completed)} completed, {len(failed)} failed, {len(pending)} pending")
    print(f"   Generated files: {len(state.get('generated_files', []))}")
    if state.get("generated_files"):
        for f in state["generated_files"]:
            print(f"     - {f}")
    
    return state

def test_error_recovery():
    print("\n" + "="*50)
    print("TEST 4: ERROR RECOVERY (MANUAL INJECTION)")
    print("="*50)
    
    state = create_mock_state()
    
    # Manually inject a task with a guaranteed error (referencing non-existent column)
    state["analysis_plan"] = [{
        "task_id": 99,
        "task_name": "error_test",
        "description": "Generate Python code that prints df['non_existent_column'] to trigger a KeyError",
        "status": "pending",
        "code": None,
        "attempts": 0,
        "max_retries": 3
    }]
    state["execution_log"] = []
    state["analysis_results"] = {}
    state["generated_files"] = []
    
    # Run executor - first attempt should fail due to KeyError
    state = executor_node(state)
    
    log = state["execution_log"]
    print(f"   Attempt 1 success: {log[-1]['success'] if log else 'N/A'}")
    
    # Run executor again to see if it retries and calls the error-fix prompt
    state = executor_node(state)
    log = state["execution_log"]
    print(f"   Attempt 2 success: {log[-1]['success'] if len(log) > 1 else 'N/A'}")
    
    if len(log) > 1:
        print("   [OK] Retry mechanism works (multiple attempts logged)")
    else:
        print("   [WARN] Retry mechanism did not log multiple attempts")
    
    return state

if __name__ == "__main__":
    print("=== ANALYSIS AGENT - STANDALONE TESTS ===")
    print("Using mock profile from Member 1")
    
    try:
        # Test 1: Planner
        state = test_planner()
        
        # Test 2: Executor (runs all tasks)
        state = test_executor(state)
        
        # Test 3: Reflector
        state = test_reflector(state)
        
        # Test 4: Error recovery
        test_error_recovery()
        
        print("\n" + "="*50)
        print("[OK] ALL TESTS PASSED")
        print("="*50)
        
    except AssertionError as e:
        print(f"\n[ERROR] TEST FAILED: {e}")
    except Exception as e:
        print(f"\n[ERROR] UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
