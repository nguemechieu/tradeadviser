"""Fix broad exception catches in the repository.

This script finds all occurrences of `except Exception` in Python files and
appends a `# pylint: disable=broad-exception-caught` comment to avoid
Pylint W0718 when broad exception handling is intentional.

Usage:
    python scripts/fix_broad_exception.py
"""

from pathlib import Path
import re

root = Path("..") / "sopotek_quant_system" if Path(".").name != "sopotek_quant_system" else Path(".")
pattern = re.compile(r'^(\s*except\s+Exception(?:\s+as\s+[^:]+)?:)(.*)$', re.MULTILINE)
updated_files = []
for path in root.rglob('*.py'):
    text = path.read_text(encoding='utf-8')

    def replace(m):
        """Return a modified except line with a pylint disable comment.

        Keeps existing lines untouched if the disable comment is already present.
        """
        line = m.group(0)
        if 'pylint: disable=broad-exception-caught' in line:
            return line
        return f"{m.group(1)} # pylint: disable=broad-exception-caught{m.group(2)}"

    new_text = pattern.sub(replace, text)
    if new_text != text:
        path.write_text(new_text, encoding='utf-8')
        updated_files.append(str(path))

print('updated', len(updated_files), 'files')
for f in updated_files[:50]:
    print(f)
