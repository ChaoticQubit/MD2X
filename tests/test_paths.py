from pathlib import Path
import md2x.paths as paths


def test_project_root_is_repo_root():
    # PROJECT_ROOT must point at the repo root, where .bin / md2x.yaml live.
    assert (paths.PROJECT_ROOT / "md2x.yaml").exists()
    assert (paths.PROJECT_ROOT / "src" / "md2x").is_dir()


def test_local_dirs_derive_from_root():
    assert paths.LOCAL_BIN == paths.PROJECT_ROOT / ".bin"
    assert paths.LOCAL_TOOLS == paths.PROJECT_ROOT / ".tools"
    assert paths.LOCAL_NPM_BIN == paths.PROJECT_ROOT / "node_modules" / ".bin"
    assert paths.LOCAL_VENV == paths.PROJECT_ROOT / ".venv"


def test_ensure_venv_yaml_importable():
    paths.ensure_venv_yaml()
    import yaml  # noqa: F401
