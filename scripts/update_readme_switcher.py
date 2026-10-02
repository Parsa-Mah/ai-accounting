"""Regenerate the language switcher block in every README*.md at the repo root.

The block is a <details> table linking every README that exists (README.md is
English, README.{code}.md are translations). Labels are the native language
names from the LANGS registry in static/js/i18n.js; the current file's own
language is bolded instead of linked. The block lives between
<!-- readme-switcher:start --> and <!-- readme-switcher:end --> markers so it
can be regenerated in place.

Usage: python scripts/update_readme_switcher.py
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
I18N_JS = ROOT / "static" / "js" / "i18n.js"

START = "<!-- readme-switcher:start -->"
END = "<!-- readme-switcher:end -->"
COLUMNS = 4


def langs_registry() -> list[tuple[str, str]]:
    """(code, native name) pairs in LANGS order, from static/js/i18n.js."""
    text = I18N_JS.read_text(encoding="utf-8")
    m = re.search(r"export const LANGS\s*=\s*\[(.*?)\];", text, re.S)
    if not m:
        raise SystemExit("LANGS registry not found in static/js/i18n.js")
    return re.findall(r'\{\s*code:\s*"([a-z-]+)",\s*name:\s*"([^"]+)"', m.group(1))


def readme_files() -> list[Path]:
    files = [ROOT / "README.md"] + sorted(ROOT.glob("README.*.md"))
    return [f for f in files if f.is_file()]


def code_of(path: Path) -> str:
    if path.name == "README.md":
        return "en"
    m = re.fullmatch(r"README\.([a-z-]+)\.md", path.name)
    if not m:
        raise SystemExit(f"unexpected README file: {path.name}")
    return m.group(1)


def ordered_codes(files: list[Path]) -> list[str]:
    """Language codes of the given README files, sorted in LANGS order."""
    order = {code: i for i, (code, _) in enumerate(langs_registry())}
    codes = [code_of(p) for p in files]
    codes.sort(key=lambda c: order.get(c, len(order)))
    return codes


def build_block(existing: list[str], current: str) -> str:
    """Build the switcher block. `existing` is a list of README codes (LANGS
    order); `current` is the code of the file the block is being written into."""
    names = dict(langs_registry())
    cells = []
    for code in existing:
        if code not in names:
            raise SystemExit(f"{code} is not in the LANGS registry")
        label = names[code]
        if code == current:
            cells.append(f"**{label}**")
        else:
            href = "README.md" if code == "en" else f"README.{code}.md"
            cells.append(f"[{label}]({href})")
    rows = []
    for i in range(0, len(cells), COLUMNS):
        row = cells[i : i + COLUMNS]
        row += [""] * (COLUMNS - len(row))
        rows.append("| " + " | ".join(row) + " |")
    return (
        f"{START}\n"
        "<details>\n"
        "<summary>Read this README in another language</summary>\n"
        "\n"
        f"{'| ' * COLUMNS}|\n"
        f"| {' | '.join(['---'] * COLUMNS)} |\n"
        + "\n".join(rows)
        + f"\n</details>\n{END}"
    )


def update_file(path: Path, existing: list[str]) -> bool:
    text = path.read_text(encoding="utf-8")
    block = build_block(existing, code_of(path))
    if START in text and END in text:
        new = re.sub(
            re.escape(START) + r".*?" + re.escape(END),
            lambda _m: block,
            text,
            count=1,
            flags=re.S,
        )
    else:
        lines = text.splitlines(keepends=True)
        h1 = next((i for i, line in enumerate(lines) if line.startswith("# ")), None)
        if h1 is None:
            raise SystemExit(f"{path.name}: no H1 title found; insert the block manually")
        insert_at = h1 + 1
        if insert_at < len(lines) and lines[insert_at].strip() == "":
            insert_at += 1
        new = "".join(lines[:insert_at]) + block + "\n\n" + "".join(lines[insert_at:])
    if new != text:
        path.write_text(new, encoding="utf-8")
        return True
    return False


def main() -> None:
    files = readme_files()
    if not files:
        raise SystemExit("README.md not found at the repo root")
    codes = ordered_codes(files)
    changed = [p.name for p in files if update_file(p, codes)]
    print(f"switcher updated in: {', '.join(changed) if changed else '(no changes)'}")


if __name__ == "__main__":
    main()
