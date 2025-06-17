import os
import re

CYRILLIC_RE = re.compile('[\u0400-\u04FF]')

def test_no_cyrillic_characters():
    base_dir = os.path.dirname(os.path.dirname(__file__))
    for root, _, files in os.walk(base_dir):
        if root.startswith(os.path.join(base_dir, 'docs', 'legacy')):
            continue
        for name in files:
            if name.endswith('.py') or name.endswith('.md') or name.endswith('.yaml') or name.endswith('.yml') or name.endswith('.txt'):
                path = os.path.join(root, name)
                with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    assert not CYRILLIC_RE.search(content), f'Cyrillic characters found in {path}'
