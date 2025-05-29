import sys
from pathlib import Path
import re

DOCS_DIR = Path('docs')

def check_file(path: Path) -> bool:
    content = path.read_text(encoding='utf-8').strip().splitlines()
    if not content:
        print(f"{path}: empty file")
        return False
    if not content[0].startswith('# '):
        print(f"{path}: missing top-level heading")
        return False
    text = '\n'.join(content)
    if '## Summary' not in text:
        print(f"{path}: missing 'Summary' section")
        return False
    if '## References' not in text:
        print(f"{path}: missing 'References' section")
        return False
    return True


def main() -> int:
    success = True
    if not DOCS_DIR.exists():
        print("docs directory not found")
        return 1
    for md_file in DOCS_DIR.glob('*.md'):
        if not check_file(md_file):
            success = False
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
