with open('index.html', 'r', encoding='utf-8') as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if 'app-view' in line or 'id="view-' in line:
        print(f"Line {i+1}: {line.strip()[:120]}")
