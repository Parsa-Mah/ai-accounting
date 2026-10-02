"""README translation tests.

Guards the multilingual README system (README.md + README.{code}.md at the
repo root, one file per language, same codes as static/i18n/*.json):
- README.md (English baseline) exists;
- every README.{code}.md on disk has a code in the LANGS registry;
- every README contains the language-switcher block exactly as
  scripts/update_readme_switcher.py generates it (no drift);
- every translated README keeps the English structure: same heading-level
  sequence, identical fenced code blocks, identical external URLs.
"""

import importlib.util
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "update_readme_switcher.py"


def _load_script():
    spec = importlib.util.spec_from_file_location("update_readme_switcher", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _readme_files() -> list[Path]:
    return _load_script().readme_files()


def _headings(text: str) -> list[int]:
    return [len(m.group(1)) for m in re.finditer(r"^(#{1,6})\s", text, re.M)]


def _code_blocks(text: str) -> list[str]:
    return re.findall(r"```[a-zA-Z0-9_-]*\n(.*?)```", text, re.S)


def _urls(text: str) -> set[str]:
    return set(re.findall(r"https?://[^\s\)\]>,]+", text))


def test_english_baseline_exists():
    assert (ROOT / "README.md").is_file(), "README.md (English baseline) must exist"


def test_readme_codes_are_in_langs():
    module = _load_script()
    registry = {code for code, _ in module.langs_registry()}
    for path in _readme_files():
        if path.name == "README.md":
            continue
        code = module.code_of(path)
        assert code in registry, f"{path.name}: code {code!r} not in the LANGS registry"


def test_switcher_block_in_sync():
    module = _load_script()
    files = _readme_files()
    codes = module.ordered_codes(files)
    for path in files:
        content = path.read_text(encoding="utf-8")
        expected = module.build_block(codes, module.code_of(path))
        assert expected in content, (
            f"{path.name}: switcher block is missing or out of sync — "
            "run scripts/update_readme_switcher.py"
        )


def test_translated_readmes_match_english_structure():
    en = (ROOT / "README.md").read_text(encoding="utf-8")
    en_headings = _headings(en)
    en_blocks = _code_blocks(en)
    en_urls = _urls(en)
    for path in _readme_files():
        if path.name == "README.md":
            continue
        text = path.read_text(encoding="utf-8")
        assert _headings(text) == en_headings, (
            f"{path.name}: heading structure differs from README.md "
            f"({len(_headings(text))} vs {len(en_headings)} headings)"
        )
        assert _code_blocks(text) == en_blocks, (
            f"{path.name}: fenced code blocks differ from README.md (keep them verbatim)"
        )
        assert _urls(text) == en_urls, (
            f"{path.name}: external URLs differ from README.md "
            f"(missing: {sorted(en_urls - _urls(text))}, extra: {sorted(_urls(text) - en_urls)})"
        )
