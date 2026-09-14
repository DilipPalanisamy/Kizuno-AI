with open('index.html', 'r', encoding='utf-8') as f:
    text = f.read()

import re
matches = [m.start() for m in re.finditer(r'DOMContentLoaded|window\.onload|initApp', text)]
for pos in matches:
    start = max(0, pos - 100)
    end = min(len(text), pos + 1000)
    print(text[start:end])
    print('='*50)
