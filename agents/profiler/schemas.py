from pydantic import BaseModel, Field
from typing import List, Dict, Optional


class DescriptiveStats(BaseModel):
    """Basic descriptive statistics for a single numeric column."""

    mean: float
    median: float
    std: float
    min: float
    max: float


class ProfileOutput(BaseModel):
    """
    Structured dataset profile produced by the LLM after analyzing a CSV.
    This is the exact contract that Member 2 & 3 consume.
    """

    dataset_name: str = Field(description="Name of the CSV file (without path)")
    rows: int = Field(description="Total number of rows in the dataset")
    columns: int = Field(description="Total number of columns in the dataset")

    numeric_columns: List[str] = Field(
        description=(
            "Columns with dtype int64/float64 that are NOT identifiers. "
            "Exclude any column that is clearly an ID (e.g. OrderID, CustomerID)."
        )
    )
    categorical_columns: List[str] = Field(
        description=(
            "Object or category columns with ≤50 distinct values, "
            "or clearly categorical columns like Region, Status."
        )
    )
    datetime_columns: List[str] = Field(
        description="Columns that can be parsed as dates (datetime64 or date-like strings)."
    )
    id_columns: List[str] = Field(
        description=(
            "Columns that appear to be unique identifiers — high cardinality, "
            "name contains 'id', 'key', 'code', etc. "
            "Numeric IDs go here, NOT in numeric_columns."
        )
    )

    missing_values: Dict[str, int] = Field(
        description="Count of missing (null) values per column. Only include columns with >0 missing."
    )
    duplicates: int = Field(description="Number of duplicate rows (keep='first').")
    constant_columns: List[str] = Field(
        description="Columns where all values are identical (nunique == 1)."
    )
    high_cardinality_columns: List[str] = Field(
        description="Categorical columns with >50 unique values that are NOT ID columns."
    )

    memory_usage_mb: float = Field(
        description="Approximate memory usage of the DataFrame in megabytes."
    )
    sample_rows: int = Field(
        default=5,
        description="Number of sample rows shown to the LLM (always 5).",
    )

    descriptive_stats: Dict[str, DescriptiveStats] = Field(
        description=(
            "Basic statistics for each numeric column. "
            "Key = column name. Compute from pandas describe()."
        )
    )
