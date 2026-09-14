with open('index.html', 'r', encoding='utf-8') as f:
    text = f.read()

import re
matches = [m.start() for m in re.finditer(r'function updatePortalVisibility', text)]
for pos in matches:
    start = max(0, pos - 50)
    end = min(len(text), pos + 1000)
    print(text[start:end])
    print('='*50)
