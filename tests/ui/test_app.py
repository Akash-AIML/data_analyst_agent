import os
import sys

# Ensure project root is in path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from ui.components.diagnostics import render_diagnostics  # noqa: E402
from ui.components.eda_profile import render_eda_profile  # noqa: E402
from ui.components.insights_gallery import render_insights_gallery  # noqa: E402
from ui.services.pipeline_service import (  # noqa: E402
    get_available_samples,
    read_html_report,
    sanitize_filename,
)


def test_sanitize_filename_prevents_path_traversal():
    assert sanitize_filename("../../../etc/passwd") == "passwd"
    assert sanitize_filename("my_data (1).csv") == "my_data1.csv"
    assert sanitize_filename("normal_file.csv") == "normal_file.csv"



def test_get_available_samples_returns_dict():
    samples = get_available_samples()
    assert isinstance(samples, dict)
    assert len(samples) > 0


def test_read_html_report_handles_missing_file():
    assert read_html_report("non_existent_file.html") is None


def test_components_import_and_render_without_error():
    # Smoke test rendering UI functions with empty dict state
    render_eda_profile({})
    render_insights_gallery({})
    render_diagnostics({})
