import re

with open('index.html', 'r', encoding='utf-8') as f:
    content = f.read()

terms = ['citizen view', 'offline demo', 'quick demo', 'demo / offline', 'demo mode', 'role-tab-btn', 'login-role-tabs']
for term in terms:
    print(f"=== Matches for: {term} ===")
    for m in re.finditer(re.escape(term), content, re.IGNORECASE):
        start = max(0, m.start() - 100)
        end = min(len(content), m.end() + 100)
        snippet = content[start:end].replace('\n', ' ').encode('ascii', 'replace').decode('ascii')
        print(f"[{m.start()}]: {snippet}")
