"""LLM provider router and deterministic MockLLM for AutoAnalyst."""

import hashlib
import json
import os
import re
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple

from backend.app.core.config import settings
from backend.graph.state import PlanStep


class BaseLLM(ABC):
    """Abstract interface for analytical code generation, planning, and reporting."""

    @abstractmethod
    async def generate_plan(self, question: str, dataset_meta: Dict[str, Any]) -> List[PlanStep]:
        """Generate structured analytical plan with max 6 steps."""
        pass

    @abstractmethod
    async def generate_code(
        self,
        question: str,
        step: PlanStep,
        cumulative_code: str,
        dataset_meta: Dict[str, Any],
    ) -> Tuple[str, str]:
        """Return (thought/rationale, python_code)."""
        pass

    @abstractmethod
    async def self_correct(
        self,
        question: str,
        step: PlanStep,
        failing_code: str,
        error_stderr: str,
        dataset_meta: Dict[str, Any],
    ) -> Tuple[str, str]:
        """Return corrected (thought/rationale, python_code)."""
        pass

    @abstractmethod
    async def synthesize_report(
        self,
        question: str,
        plan: List[PlanStep],
        step_outputs: List[Dict[str, Any]],
        charts: List[Dict[str, Any]],
        is_partial: bool = False,
        failure_reason: Optional[str] = None,
    ) -> str:
        """Synthesize final Markdown report (or partial report on aborted/budget exceeded)."""
        pass


class MockLLM(BaseLLM):
    """Deterministic MockLLM providing scripted responses for testing and demonstration."""

    def __init__(self, scenario: str = "demo"):
        self.scenario = scenario
        self.call_count = 0
        self.tokens_used = 0
        self.correction_count = 0

    async def generate_plan(self, question: str, dataset_meta: Dict[str, Any]) -> List[PlanStep]:
        self.call_count += 1
        self.tokens_used += 150
        cols = dataset_meta.get("columns", ["col1", "col2"])

        if self.scenario == "single_step":
            return [
                PlanStep(
                    step_id=1,
                    title="Profile and summarize dataset",
                    description="Compute high level aggregations and metrics",
                    is_critical=True,
                )
            ]

        # Standard 2-step plan for demo & test scenarios
        return [
            PlanStep(
                step_id=1,
                title="Aggregate category metrics and sales breakdown",
                description=f"Group data by category and calculate total sales using available columns: {cols[:3]}",
                is_critical=True,
            ),
            PlanStep(
                step_id=2,
                title="Generate category distribution chart",
                description="Produce visual bar chart comparing key metrics across segments",
                is_critical=False,
            ),
        ]

    async def generate_code(
        self,
        question: str,
        step: PlanStep,
        cumulative_code: str,
        dataset_meta: Dict[str, Any],
    ) -> Tuple[str, str]:
        self.call_count += 1
        self.tokens_used += 250

        # Scenario: demo triggers intentional initial error on step 1 attempt 0
        if self.scenario == "demo" and step.step_id == 1 and self.correction_count == 0:
            thought = "Loading dataset and attempting to aggregate by sales category."
            buggy_code = """import pandas as pd
import glob

files = glob.glob('/data/input.*')
df = pd.read_csv(files[0]) if files[0].endswith('.csv') else pd.read_parquet(files[0])

# Intentional deliberate error: referencing missing column to verify self-correction
print(df['non_existent_column_for_test'].sum())
"""
            return thought, buggy_code

        # Scenario: persistent_error always generates code that fails
        if self.scenario == "persistent_error":
            return (
                "Attempting analysis with persistent calculation fault.",
                "import sys; raise RuntimeError('Persistent runtime failure in analysis script')",
            )

        # Standard valid code generation
        thought = f"Calculating statistics and preparing chart visualizer for step {step.step_id}: {step.title}"
        valid_code = f"""import pandas as pd
import json
import os
import glob

files = glob.glob('/data/input.*')
filepath = files[0] if files else '/data/input.csv'
df = pd.read_csv(filepath) if filepath.endswith('.csv') else pd.read_parquet(filepath)

# Group by first string column or category
cat_col = None
num_col = None
for c in df.columns:
    if df[c].dtype == 'object' and cat_col is None:
        cat_col = c
    elif pd.api.types.is_numeric_dtype(df[c]) and num_col is None:
        num_col = c

if not cat_col:
    cat_col = df.columns[0]
if not num_col:
    num_col = df.columns[min(1, len(df.columns) - 1)]

grouped = df.groupby(cat_col)[num_col].sum().reset_index().head(10)

chart_data = []
for _, row in grouped.iterrows():
    chart_data.append({{
        "category": str(row[cat_col]),
        "value": float(row[num_col])
    }})

result_spec = {{
    "chart_type": "bar",
    "title": "Aggregated Breakdown by " + str(cat_col),
    "x_label": str(cat_col),
    "y_label": str(num_col),
    "data": chart_data,
    "series": ["value"]
}}

os.makedirs('/tmp/output', exist_ok=True)
with open('/tmp/output/result.json', 'w', encoding='utf-8') as f:
    json.dump(result_spec, f)

print(f"Aggregated {{len(chart_data)}} items successfully for {{cat_col}}.")
"""
        return thought, valid_code

    async def self_correct(
        self,
        question: str,
        step: PlanStep,
        failing_code: str,
        error_stderr: str,
        dataset_meta: Dict[str, Any],
    ) -> Tuple[str, str]:
        self.call_count += 1
        self.tokens_used += 300
        self.correction_count += 1

        # Scenario: repeated_error returns identical failing code to trigger repeated-failure guard
        if self.scenario == "repeated_error":
            return (
                "Retrying with identical query without fixing error signature.",
                failing_code,
            )

        thought = f"Detected error ({error_stderr[:60]}...). Resolving column mapping using verified dataset columns."
        corrected_code = """import pandas as pd
import json
import os
import glob

files = glob.glob('/data/input.*')
filepath = files[0]
df = pd.read_csv(filepath) if filepath.endswith('.csv') else pd.read_parquet(filepath)

# Use dynamic column inspection rather than hardcoded invalid column
target_col = df.columns[0]
summary = df[target_col].value_counts().head(10).reset_index()
summary.columns = ['category', 'value']

chart_spec = {
    "chart_type": "bar",
    "title": "Distribution of " + str(target_col),
    "x_label": str(target_col),
    "y_label": "Count",
    "data": summary.to_dict(orient='records'),
    "series": ["value"]
}

os.makedirs('/tmp/output', exist_ok=True)
with open('/tmp/output/result.json', 'w', encoding='utf-8') as f:
    json.dump(chart_spec, f)

print("Self-correction succeeded. Analysis complete.")
"""
        return thought, corrected_code

    async def synthesize_report(
        self,
        question: str,
        plan: List[PlanStep],
        step_outputs: List[Dict[str, Any]],
        charts: List[Dict[str, Any]],
        is_partial: bool = False,
        failure_reason: Optional[str] = None,
    ) -> str:
        self.call_count += 1
        self.tokens_used += 400

        status_heading = "Partial Analysis Report (Incomplete)" if is_partial else "Executive Analytical Report"
        failure_section = f"\n> **Termination Notice**: {failure_reason}\n" if failure_reason else ""

        report = f"""# {status_heading}

**Analytical Query**: {question}
{failure_section}
## Summary of Execution
- Total planned analytical steps: {len(plan)}
- Steps successfully executed: {sum(1 for s in plan if s.status == 'completed')}
- Charts generated: {len(charts)}

## Findings & Insights
1. **Data Overview**: Successfully processed dataset and established key category metrics.
2. **Key Metric Distribution**: The highest concentrations were identified in the primary categorical segments.
3. **Visual Evidence**: Interactive charts have been plotted and rendered in the visualization pane.

## Step Breakdown
"""
        for s in plan:
            badge = "✅ Complete" if s.status == "completed" else "❌ Failed" if s.status == "failed" else "⏳ Pending"
            report += f"- **Step {s.step_id}**: {s.title} ({badge})\n"

        return report.strip()


def get_llm(scenario: Optional[str] = None) -> BaseLLM:
    """Factory returning configured LLM provider instance."""
    provider = settings.LLM_PROVIDER.lower()
    if provider == "mock":
        return MockLLM(scenario=scenario or "demo")
    # Additional real providers can be plugged in here reading settings.LLM_API_KEY
    return MockLLM(scenario=scenario or "demo")
