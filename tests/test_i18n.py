"""i18n dictionary tests.

Guards the translation system:
- every static/i18n/*.json parses and has a "ui" section of str -> str;
- every language has exactly the same ui keys as en.json;
- {placeholder} sets match en.json per key;
- every static t("key") call in static/js exists in en.json;
- dynamic key families (nav routes, statusBadge values, account types,
  export label keys) all exist in en.json;
- the LANGS registry in i18n.js matches the dictionary files on disk.
"""

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
I18N_DIR = ROOT / "static" / "i18n"
JS_DIR = ROOT / "static" / "js"

PLACEHOLDER = re.compile(r"\{([a-z_]+)\}")


def _js_files():
    return sorted(JS_DIR.rglob("*.js"))


def _load_dict(code: str) -> dict:
    return json.loads((I18N_DIR / f"{code}.json").read_text(encoding="utf-8"))


def _dict_codes() -> list[str]:
    return sorted(p.stem for p in I18N_DIR.glob("*.json"))


def test_all_dictionaries_parse_and_have_ui_section():
    codes = _dict_codes()
    assert "en" in codes, "en.json is the baseline dictionary and must exist"
    for code in codes:
        data = _load_dict(code)
        assert isinstance(data, dict), f"{code}.json must be a JSON object"
        assert "ui" in data, f"{code}.json must have a 'ui' section"
        ui = data["ui"]
        assert isinstance(ui, dict) and ui, f"{code}.json 'ui' section must be non-empty"
        for key, value in ui.items():
            assert isinstance(key, str) and re.fullmatch(r"[a-z0-9_.]+", key), (
                f"{code}.json: bad key {key!r}"
            )
            assert isinstance(value, str), f"{code}.json: {key!r} must be a string"


def test_key_parity_across_languages():
    en_keys = set(_load_dict("en")["ui"])
    for code in _dict_codes():
        if code == "en":
            continue
        keys = set(_load_dict(code)["ui"])
        missing = en_keys - keys
        extra = keys - en_keys
        assert not missing, f"{code}.json missing keys: {sorted(missing)}"
        assert not extra, f"{code}.json has extra keys: {sorted(extra)}"


def test_placeholder_parity():
    en_ui = _load_dict("en")["ui"]
    for code in _dict_codes():
        if code == "en":
            continue
        ui = _load_dict(code)["ui"]
        for key, en_value in en_ui.items():
            value = ui.get(key)
            if value is None:
                continue  # reported by key parity
            en_vars = set(PLACEHOLDER.findall(en_value))
            vars_ = set(PLACEHOLDER.findall(value))
            assert vars_ == en_vars, (
                f"{code}.json {key!r}: placeholders {sorted(vars_)} != en {sorted(en_vars)}"
            )


def test_static_t_calls_exist_in_english():
    en_keys = set(_load_dict("en")["ui"])
    used = set()
    for path in _js_files():
        content = path.read_text(encoding="utf-8")
        used.update(re.findall(r'\bt\(\s*"([A-Za-z0-9_.]+)"', content))
    missing = used - en_keys
    assert not missing, f"t() calls with keys missing from en.json: {sorted(missing)}"


def test_dynamic_key_families_exist_in_english():
    en_keys = set(_load_dict("en")["ui"])

    # nav.<route> for every route in the router's NAV sidebar array.
    router = (JS_DIR / "router.js").read_text(encoding="utf-8")
    nav = re.search(r"const NAV\s*=\s*\[([^\]]*)\]", router)
    assert nav, "router.js NAV array not found"
    for route in re.findall(r'"([a-z_]+)"', nav.group(1)):
        assert f"nav.{route}" in en_keys, f"nav.{route} missing from en.json"

    # status.<key> for every statusBadge("...") literal call.
    for path in _js_files():
        content = path.read_text(encoding="utf-8")
        for status in re.findall(r'statusBadge\(\s*"([^"]+)"', content):
            key = "status." + status.strip().replace(" ", "_")
            assert key in en_keys, f"{key} missing from en.json"

    # accounts.type_<t> for every entry in the TYPES array.
    accounts = (JS_DIR / "pages" / "accounts.js").read_text(encoding="utf-8")
    types = re.search(r"const TYPES\s*=\s*\[([^\]]*)\]", accounts)
    assert types, "accounts.js TYPES array not found"
    for type_ in re.findall(r'"([a-z]+)"', types.group(1)):
        assert f"accounts.type_{type_}" in en_keys, f"accounts.type_{type_} missing"

    # export label keys referenced by the export page.
    export = (JS_DIR / "pages" / "export.js").read_text(encoding="utf-8")
    for label_key in re.findall(r'labelKey:\s*"([^"]+)"', export):
        assert label_key in en_keys, f"{label_key} missing from en.json"


def test_langs_registry_matches_files():
    i18n_js = (JS_DIR / "i18n.js").read_text(encoding="utf-8")
    langs = re.search(r"export const LANGS\s*=\s*\[(.*?)\];", i18n_js, re.S)
    assert langs, "i18n.js LANGS registry not found"
    registry = re.findall(r'code:\s*"([a-z-]+)"', langs.group(1))
    files = _dict_codes()
    assert registry == files, (
        f"LANGS registry {registry} does not match dictionary files {files}"
    )
