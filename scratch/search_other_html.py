import os

files = ['admin.html', 'officer.html']
for fn in files:
    if os.path.exists(fn):
        with open(fn, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        for i, line in enumerate(lines):
            l_lower = line.lower()
            if 'citizen view' in l_lower or 'demo' in l_lower:
                safe = line.strip().encode('ascii', 'replace').decode('ascii')[:140]
                print(f"{fn} Line {i+1}: {safe}")
