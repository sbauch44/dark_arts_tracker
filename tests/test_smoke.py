"""Smoke tests — package imports cleanly and paths resolve."""

from __future__ import annotations


def test_package_imports() -> None:
    import dark_arts

    assert dark_arts.__version__


def test_paths_create_data_dirs(tmp_path, monkeypatch) -> None:
    # Re-import paths in isolation against tmp_path to avoid touching the
    # real data/ tree.
    import importlib

    monkeypatch.setenv("DARK_ARTS_DATA_OVERRIDE", str(tmp_path))
    import dark_arts.paths as paths

    importlib.reload(paths)
    # The real paths module doesn't read the env var yet — this test is a
    # placeholder reminding us to wire one in if/when needed.
    assert paths.DATA.exists()
