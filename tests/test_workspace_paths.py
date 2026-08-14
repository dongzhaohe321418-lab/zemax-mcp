from pathlib import Path

import pytest

from config import Settings


def settings(tmp_path: Path) -> Settings:
    return Settings(workspace=tmp_path)


def test_valid_zos_path(tmp_path):
    target = settings(tmp_path).resolve_workspace_path("designs/run-1.ZOS", suffix=".ZOS")
    assert target == (tmp_path / "designs/run-1.ZOS").resolve()


@pytest.mark.parametrize("value", ["../escape.ZOS", "design.txt"])
def test_rejects_traversal_or_extension(tmp_path, value):
    with pytest.raises(ValueError):
        settings(tmp_path).resolve_workspace_path(value, suffix=".ZOS")


def test_rejects_absolute_path(tmp_path):
    with pytest.raises(ValueError):
        settings(tmp_path).resolve_workspace_path(str((tmp_path / "x.ZOS").resolve()), suffix=".ZOS")
