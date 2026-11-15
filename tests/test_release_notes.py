"""REL-02: перевірка тегу релізу та приміток (scripts/release_notes.py)."""
import importlib.util
from pathlib import Path

from sipl import __version__

ROOT = Path(__file__).resolve().parent.parent


def load_script():
    spec = importlib.util.spec_from_file_location("release_notes", ROOT / "scripts" / "release_notes.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


rn = load_script()

CHANGELOG = """# Changelog

## [Unreleased]

## [1.2.3] - 2026-01-01

### Added
- нова можливість

## [1.2.2] - 2025-12-01

### Fixed
- старе виправлення

[1.2.3]: https://example.com/1.2.3
"""


def make_root(tmp_path, version="1.2.3", pkg_version="1.2.3", changelog=CHANGELOG):
    (tmp_path / "src" / "sipl").mkdir(parents=True)
    (tmp_path / "pyproject.toml").write_text(f'[project]\nname = "x"\nversion = "{version}"\n', encoding="utf-8")
    (tmp_path / "src" / "sipl" / "__init__.py").write_text(f'__version__ = "{pkg_version}"\n', encoding="utf-8")
    (tmp_path / "CHANGELOG.md").write_text(changelog, encoding="utf-8")
    return tmp_path


def error_of(tag, root):
    try:
        rn.check_release(tag, root)
    except rn.ReleaseError as exc:
        return str(exc)
    return None


def test_notes_contain_only_the_requested_version(tmp_path):
    notes = rn.check_release("v1.2.3", make_root(tmp_path))
    assert "нова можливість" in notes
    assert "старе виправлення" not in notes
    assert "example.com" not in notes


def test_tag_must_follow_semver(tmp_path):
    root = make_root(tmp_path)
    for bad in ("1.2.3", "v1.2", "v1.2.3-rc1", "release-1"):
        assert "SemVer" in error_of(bad, root)


def test_tag_must_match_pyproject_version(tmp_path):
    assert "pyproject.toml" in error_of("v1.2.4", make_root(tmp_path))


def test_tag_must_match_package_version(tmp_path):
    assert "__init__.py" in error_of("v1.2.3", make_root(tmp_path, pkg_version="1.2.0"))


def test_changelog_section_is_required(tmp_path):
    root = make_root(tmp_path, version="2.0.0", pkg_version="2.0.0")
    assert "CHANGELOG" in error_of("v2.0.0", root)


def test_empty_changelog_section_is_rejected(tmp_path):
    root = make_root(tmp_path, changelog="# Changelog\n\n## [1.2.3] - 2026-01-01\n\n## [1.2.2]\n- x\n")
    assert "CHANGELOG" in error_of("v1.2.3", root)


def test_missing_file_is_reported(tmp_path):
    root = make_root(tmp_path)
    (root / "CHANGELOG.md").unlink()
    assert "Не знайдено файл CHANGELOG.md" in error_of("v1.2.3", root)


def test_main_writes_notes_file_and_returns_exit_codes(tmp_path):
    root = make_root(tmp_path)
    out = tmp_path / "notes.md"
    assert rn.main(["v1.2.3", "--root", str(root), "--out", str(out)]) == 0
    assert "нова можливість" in out.read_text(encoding="utf-8")
    assert rn.main(["v9.9.9", "--root", str(root)]) == 1


def test_real_repository_is_ready_for_release_of_current_version():
    notes = rn.check_release(f"v{__version__}", ROOT)
    assert "CORE-01" in notes and "REL-02" in notes
