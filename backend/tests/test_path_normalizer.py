"""Unit tests for cross-platform host path sanitization and mount normalization."""

import pytest
from backend.sandbox.path_normalizer import get_dataset_mount_target, normalize_docker_bind_mount


def test_windows_standard_path():
    """Verify standard Windows drive letter path with backslashes is normalized."""
    input_path = r"C:\Users\x\data.csv"
    normalized = normalize_docker_bind_mount(input_path)
    # Must produce POSIX-compliant Docker bind path with lowercased drive letter
    assert normalized == "/c/Users/x/data.csv"


def test_windows_forward_slash_path():
    """Verify Windows drive letter with forward slashes is normalized."""
    input_path = "D:/datasets/sales/monthly_revenue.parquet"
    normalized = normalize_docker_bind_mount(input_path)
    assert normalized == "/d/datasets/sales/monthly_revenue.parquet"


def test_windows_lowercase_drive_letter():
    """Verify lowercase drive letter is handled properly."""
    input_path = r"e:\projects\analytics\data.csv"
    normalized = normalize_docker_bind_mount(input_path)
    assert normalized == "/e/projects/analytics/data.csv"


def test_redundant_slashes_and_quotes():
    """Verify whitespace, wrapping quotes, and redundant separators are sanitized."""
    input_path = '  "C:\\\\Users\\\\alice\\\\sub\\\\//data.csv"  '
    normalized = normalize_docker_bind_mount(input_path)
    assert normalized == "/c/Users/alice/sub/data.csv"


def test_posix_absolute_path():
    """Verify absolute POSIX path remains valid POSIX path."""
    input_path = "/var/data/warehouse/customers.csv"
    normalized = normalize_docker_bind_mount(input_path)
    assert normalized == "/var/data/warehouse/customers.csv"


def test_empty_path_raises_error():
    """Verify empty or whitespace-only paths raise ValueError."""
    with pytest.raises(ValueError, match="Host path cannot be empty"):
        normalize_docker_bind_mount("")

    with pytest.raises(ValueError, match="Host path cannot be empty"):
        normalize_docker_bind_mount("   ")


def test_dataset_mount_target_extensions():
    """Verify correct dataset container target path based on extension."""
    assert get_dataset_mount_target("sales.csv") == "/data/input.csv"
    assert get_dataset_mount_target("METRICS.PARQUET") == "/data/input.parquet"
    assert get_dataset_mount_target("/path/to/my_data.csv") == "/data/input.csv"
    assert get_dataset_mount_target("C:\\data\\users.parquet") == "/data/input.parquet"
    # Fallback default if no extension
    assert get_dataset_mount_target("unknown_format") == "/data/input.csv"
