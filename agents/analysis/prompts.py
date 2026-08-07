# analysis_prompts.py

PLANNER_SYSTEM_PROMPT = """You are an expert data analyst AI. Given a dataset profile, your job is to create a logical, ordered analysis plan.

The profile will contain:
- numeric_columns: list of column names
- categorical_columns: list of column names
- datetime_columns: list of column names (if any)
- rows, columns: dataset dimensions
- missing_values: dict of column -> count of missing values
- duplicates: number of duplicate rows

Create a plan with these possible tasks (choose only what's appropriate):
1. descriptive_statistics - for all numeric columns (mean, median, std, min, max)
2. missing_value_analysis - calculate missing percentages for columns with missing data
3. correlation_analysis - correlation matrix for numeric columns (if 2+ numeric columns)
4. outlier_detection - IQR method for numeric columns
5. distribution_plots - histogram with KDE for key numeric columns (max 4 plots)
6. category_frequency - value counts for categorical columns (if any)

Output format — return ONLY a JSON array, no other text:
[
  {{"task_id": 1, "task_name": "descriptive_statistics", "description": "Compute mean, median, std, min, max for all numeric columns"}},
  {{"task_id": 2, "task_name": "correlation_analysis", "description": "Generate correlation matrix for numeric columns"}}
]

Rules:
- Only include tasks that make sense given the profile
- Max 6 tasks total
- Order from most fundamental to most advanced
- If a column type is missing (e.g., no categorical columns), skip those tasks
"""

CODE_GENERATION_PROMPT = """You are a Python data analyst. Generate executable Python code for the following task.

Dataset: The CSV is ALREADY loaded as a pandas DataFrame called `df`. Do NOT call pd.read_csv() or open any file.
The variable `df` is already available in the execution scope — just use it directly.

Task: {task_description}

Profile Info:
- Numeric columns: {numeric_columns}
- Categorical columns: {categorical_columns}

Requirements:
1. Use pandas (imported as `pd`), numpy (imported as `np`), matplotlib (imported as `plt`), seaborn (imported as `sns`)
2. Print results using `print()` so stdout can be captured
3. If generating a plot, save to: `output/analysis/{{plot_filename}}.png` using `plt.savefig()`, then `plt.close()`
4. ONLY use the columns listed above — double-check column names match exactly
5. Handle potential errors (e.g., empty columns, division by zero) gracefully
6. Return ONLY the Python code, no explanation, no markdown backticks
7. CRITICAL: Never call pd.read_csv() or open any file. The DataFrame `df` is pre-loaded.

Example for descriptive_statistics:
stats = df[{numeric_columns}].describe()
print(stats)

Now generate code for: {task_description}
"""


ERROR_FIX_PROMPT = """The following Python code failed during execution.

ORIGINAL CODE:
{original_code}

ERROR MESSAGE:
{error_message}

STDOUT SO FAR:
{stdout}

Please fix the code. Common issues:
- Column name mismatch (check exact column names from profile)
- Missing imports
- Incorrect method names
- Division by zero or empty data

CRITICAL: The DataFrame `df` is pre-loaded. NEVER use pd.read_csv() or load any file.
If the original code calls pd.read_csv(), remove it — the DataFrame is already available as `df`.


Profile Info:
- Numeric columns: {numeric_columns}
- Categorical columns: {categorical_columns}

Return ONLY the corrected Python code, no explanation, no markdown backticks.
"""

REFLECTION_PROMPT = """You are a quality assurance analyst. Review the completed analysis and determine if anything was missed.

Dataset Profile:
{profile_summary}

Completed Tasks:
{completed_tasks}

Analysis Results Summary:
{results_summary}

Questions to consider:
- Are there numeric columns that had NO analysis performed?
- Are there categorical columns that had NO analysis performed?
- Were missing values properly analyzed if they existed?
- Should any additional analysis be added?

If everything is complete, respond with EXACTLY: "COMPLETE"
If something is missing, respond with a JSON array of additional tasks to add:
[
  {{"task_name": "descriptive_statistics", "description": "Add descriptive stats for column X"}}
]

Response:"""
