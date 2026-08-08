# agents/analysis_agent.py

from typing import Dict, Any, List
import os
import json
import time
from dotenv import load_dotenv
load_dotenv(override=True)
from langchain_openai import ChatOpenAI
from langchain_groq import ChatGroq
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.prompts import ChatPromptTemplate
from state import AgentState


from agents.analysis.prompts import (
    PLANNER_SYSTEM_PROMPT,
    CODE_GENERATION_PROMPT,
    ERROR_FIX_PROMPT,
    REFLECTION_PROMPT
)

from tools.python_executor import execute_code

# LLM Configuration: Check OPENAI_API_KEY, GROQ_API_KEY, or GEMINI_API_KEY from .env
class ResilientFallbackModel(BaseChatModel):
    primary: Any
    fallback: Any

    def _generate(self, messages: Any, stop: Any = None, **kwargs: Any) -> Any:
        try:
            return self.primary._generate(messages, stop=stop, **kwargs)
        except Exception:
            for attempt in range(1, 4):
                try:
                    return self.fallback._generate(messages, stop=stop, **kwargs)
                except Exception as fb_err:
                    if attempt < 3:
                        time.sleep(3.0)
                    else:
                        raise fb_err

    def with_structured_output(self, schema: Any, **kwargs: Any) -> Any:
        try:
            return self.primary.with_structured_output(schema, **kwargs)
        except Exception:
            for attempt in range(1, 4):
                try:
                    return self.fallback.with_structured_output(schema, **kwargs)
                except Exception as fb_err:
                    if attempt < 3:
                        time.sleep(3.0)
                    else:
                        raise fb_err

    @property
    def _llm_type(self) -> str:
        return "resilient_fallback"


from tools.llm_factory import get_ordered_llm


def _build_analysis_llm():
    """Instantiate ordered LLM chain: Groq -> Gemini -> OpenAI."""
    return get_ordered_llm(temperature=0.1)


llm = _build_analysis_llm()



MAX_RETRIES = 3


def planner_node(state: AgentState) -> AgentState:
    """Creates analysis plan based on dataset profile."""
    
    profile = state.get("profile", {})
    if not profile:
        if state.get("error_log") is None:
            state["error_log"] = []
        state["error_log"].append("Planner: No profile found in state")
        state["status"] = "failed"
        return state
    
    # Build prompt
    prompt = ChatPromptTemplate.from_messages([
        ("system", PLANNER_SYSTEM_PROMPT),
        ("user", "Here is the dataset profile:\n{profile_json}\n\nCreate an analysis plan.")
    ])
    
    # Call LLM
    plan_text = ""
    try:
        response = llm.invoke(
            prompt.format_messages(profile_json=json.dumps(profile, indent=2))
        )
        
        # Parse the JSON response
        plan_text = response.content.strip()
        
        # Clean up — remove markdown code blocks if present
        if plan_text.startswith("```"):
            plan_text = plan_text.split("```")[1]
            if plan_text.startswith("json"):
                plan_text = plan_text[4:]
        plan_text = plan_text.strip()
        
        analysis_plan = json.loads(plan_text)
        
        # Add tracking fields to each task
        for task in analysis_plan:
            task["status"] = "pending"
            task["code"] = None
            task["attempts"] = 0
            task["max_retries"] = MAX_RETRIES
        
        state["analysis_plan"] = analysis_plan
        state["analysis_results"] = {}
        state["execution_log"] = []
        state["generated_files"] = []
        
        print(f"[PLANNER] Created plan with {len(analysis_plan)} tasks")
        for t in analysis_plan:
            print(f"  - {t['task_id']}: {t['task_name']}")
        
    except json.JSONDecodeError as e:
        if state.get("error_log") is None:
            state["error_log"] = []
        state["error_log"].append(f"Planner: Failed to parse LLM output as JSON: {e}")
        state["error_log"].append(f"Raw output: {plan_text[:500]}")
        state["analysis_plan"] = []
        state["status"] = "failed"
    except Exception as e:
        if state.get("error_log") is None:
            state["error_log"] = []
        state["error_log"].append(f"Planner: Unexpected error: {e}")
        state["analysis_plan"] = []
        state["status"] = "failed"
    
    return state


def executor_node(state: AgentState) -> AgentState:
    """Executes the next pending task in the analysis plan."""
    
    analysis_plan = state.get("analysis_plan") or []

    profile = state.get("profile", {})
    csv_path = state.get("csv_path", "")
    
    # Find first pending task
    pending_task = None
    for task in analysis_plan:
        if task["status"] == "pending" and task["attempts"] < task["max_retries"]:
            pending_task = task
            break
    
    if not pending_task:
        print("[EXECUTOR] No pending tasks to execute")
        if state.get("execution_log") is None:
            state["execution_log"] = []
        return state
    
    task_id = pending_task["task_id"]
    task_name = pending_task["task_name"]
    task_desc = pending_task["description"]
    attempt = pending_task["attempts"] + 1
    pending_task["attempts"] = attempt
    
    print(f"[EXECUTOR] Executing task {task_id}: {task_name} (attempt {attempt}/{MAX_RETRIES})")

    
    # Generate code
    numeric_cols = profile.get("numeric_columns", [])
    categorical_cols = profile.get("categorical_columns", [])
    
    # Use error-fix prompt if retrying, else use normal code generation
    if attempt > 1 and pending_task.get("last_error"):
        prompt = ChatPromptTemplate.from_messages([
            ("system", ERROR_FIX_PROMPT),
            ("user", "Fix this code.")
        ])
        prompt_input = {
            "original_code": pending_task.get("code", ""),
            "error_message": pending_task.get("last_error", ""),
            "stdout": pending_task.get("last_stdout", ""),
            "numeric_columns": numeric_cols,
            "categorical_columns": categorical_cols
        }
    else:
        prompt = ChatPromptTemplate.from_messages([
            ("system", CODE_GENERATION_PROMPT),
            ("user", "Generate code for: {task_description}")
        ])
        prompt_input = {
            "task_description": task_desc,
            "numeric_columns": numeric_cols,
            "categorical_columns": categorical_cols
        }
    
    try:
        response = llm.invoke(prompt.format_messages(**prompt_input))
        code = response.content.strip()
        
        # Clean code — remove markdown code blocks
        if code.startswith("```"):
            code_lines = code.split("\n")
            # Remove first line (```python) and last line (```)
            if code_lines[0].startswith("```"):
                code_lines = code_lines[1:]
            if code_lines and code_lines[-1].strip() == "```":
                code_lines = code_lines[:-1]
            code = "\n".join(code_lines)
        
        # Save code to task
        pending_task["code"] = code
        
        # Execute
        result = execute_code(code, csv_path)
        
        # Log the attempt
        log_entry = {
            "task_id": task_id,
            "task_name": task_name,
            "attempt": attempt,
            "code": code[:500],  # Truncate for log
            "success": result["success"],
            "stdout": result["stdout"][:500],
            "stderr": result["stderr"][:500],
            "error": result.get("error")
        }
        if state.get("execution_log") is None:
            state["execution_log"] = []
        state["execution_log"].append(log_entry)
        
        if result["success"]:
            # Task completed
            pending_task["status"] = "completed"
            
            # Store results
            if state.get("analysis_results") is None:
                state["analysis_results"] = {}
            state["analysis_results"][task_name] = {
                "stdout": result["stdout"],
                "completed_at_attempt": attempt
            }
            
            # Track generated files
            if result.get("generated_files"):
                if state.get("generated_files") is None:
                    state["generated_files"] = []
                state["generated_files"].extend(result["generated_files"])
            
            print(f"[EXECUTOR] Task {task_id} completed successfully")
            
        else:
            # Task failed
            pending_task["last_error"] = result.get("error", "Unknown error")
            pending_task["last_stdout"] = result.get("stdout", "")
            pending_task["attempts"] = attempt
            
            if attempt >= MAX_RETRIES:
                pending_task["status"] = "failed"
                print(f"[EXECUTOR] Task {task_id} failed after {MAX_RETRIES} attempts")
            else:
                print(f"[EXECUTOR] Task {task_id} failed, will retry (attempt {attempt})")
            
    except Exception as e:
        pending_task["attempts"] = attempt
        pending_task["last_error"] = str(e)
        log_entry = {
            "task_id": task_id,
            "task_name": task_name,
            "attempt": attempt,
            "code": "",
            "success": False,
            "stdout": "",
            "stderr": "",
            "error": str(e),
        }
        if state.get("execution_log") is None:
            state["execution_log"] = []
        state["execution_log"].append(log_entry)

        if "429" in str(e) or "rate" in str(e).lower():
            import time
            time.sleep(2.0)
        if attempt >= MAX_RETRIES:
            pending_task["status"] = "failed"
            print(f"[EXECUTOR] Task {task_id} failed due to exception: {e}")
        else:
            print(f"[EXECUTOR] Task {task_id} error: {e}, retrying (attempt {attempt})")

    
    return state


def reflector_node(state: AgentState) -> AgentState:
    """Checks if analysis plan is complete and reflects on results."""
    
    analysis_plan = state.get("analysis_plan", [])
    profile = state.get("profile", {})
    analysis_results = state.get("analysis_results", {})
    if analysis_results is None:
        analysis_results = {}
    
    reflection_notes = state.get("reflection_notes", [])
    if reflection_notes is None:
        reflection_notes = []
    
    # Check 1: Any pending tasks?
    pending = [t for t in analysis_plan if t["status"] == "pending"]
    failed = [t for t in analysis_plan if t["status"] == "failed"]
    
    if pending:
        note = f"Tasks still pending: {[t['task_name'] for t in pending]}"
        reflection_notes.append(note)
        state["reflection_notes"] = reflection_notes
        print(f"[REFLECTOR] {note}")
        return state
    
    if failed:
        note = f"Tasks failed (max retries exceeded): {[t['task_name'] for t in failed]}"
        reflection_notes.append(note)
        state["reflection_notes"] = reflection_notes
        print(f"[REFLECTOR] {note}")
        # Continue to insight — partial results are better than nothing
    
    # Check 2: LLM reflection — did we miss anything?
    completed_tasks = [t["task_name"] for t in analysis_plan if t["status"] == "completed"]
    
    if completed_tasks:
        prompt = ChatPromptTemplate.from_messages([
            ("system", REFLECTION_PROMPT),
            ("user", "Review this analysis.")
        ])
        
        try:
            response = llm.invoke(prompt.format_messages(
                profile_summary=json.dumps({
                    "numeric": profile.get("numeric_columns", []),
                    "categorical": profile.get("categorical_columns", []),
                    "missing": profile.get("missing_values", {}),
                    "rows": profile.get("rows", 0)
                }, indent=2),
                completed_tasks=json.dumps(completed_tasks),
                results_summary=json.dumps({
                    k: v.get("stdout", "")[:200] 
                    for k, v in analysis_results.items()
                }, indent=2)
            ))
            
            reflection_output = response.content.strip()
            
            if reflection_output != "COMPLETE":
                # Try to parse additional tasks
                try:
                    if reflection_output.startswith("```"):
                        reflection_output = reflection_output.split("```")[1]
                        if reflection_output.startswith("json"):
                            reflection_output = reflection_output[4:]
                    additional_tasks = json.loads(reflection_output.strip())
                    
                    # Add new tasks to plan
                    next_id = max([t["task_id"] for t in analysis_plan]) + 1
                    for task in additional_tasks:
                        task["task_id"] = next_id
                        task["status"] = "pending"
                        task["code"] = None
                        task["attempts"] = 0
                        task["max_retries"] = MAX_RETRIES
                        analysis_plan.append(task)
                        next_id += 1
                    
                    note = f"Reflection found missing analyses, added {len(additional_tasks)} new tasks"
                    reflection_notes.append(note)
                    state["analysis_plan"] = analysis_plan
                    print(f"[REFLECTOR] {note}")
                    
                except (json.JSONDecodeError, AttributeError):
                    note = f"Reflection response not parseable: {reflection_output[:200]}"
                    reflection_notes.append(note)
                    print(f"[REFLECTOR] {note}")
            else:
                note = "Reflection complete — all necessary analyses performed"
                reflection_notes.append(note)
                print(f"[REFLECTOR] {note}")
                
        except Exception as e:
            note = f"Reflection LLM call failed: {e}"
            reflection_notes.append(note)
            if state.get("error_log") is None:
                state["error_log"] = []
            state["error_log"].append(f"Reflector: {note}")
    
    state["reflection_notes"] = reflection_notes
    if state.get("analysis_results"):
        state["status"] = "completed"
    return state

