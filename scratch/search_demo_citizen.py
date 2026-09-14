import sys

with open('index.html', 'r', encoding='utf-8') as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    l_lower = line.lower()
    if 'citizen view' in l_lower or 'demo' in l_lower or 'quick demo' in l_lower or 'offline demo' in l_lower or 'role-tab' in l_lower or 'login-role' in l_lower:
        safe_line = line.strip().encode('ascii', 'replace').decode('ascii')[:140]
        print(f"Line {i+1}: {safe_line}")
