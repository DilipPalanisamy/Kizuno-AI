with open('index.html', 'r', encoding='utf-8') as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if 'requestGmailVerificationCode' in line or 'verifyCitizenGmailCode' in line or 'send-verification' in line:
        print(f"index.html Line {i+1}: {line.strip()[:100]}")

with open('server.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if 'send_verification_code' in line or 'send_real_email_verification' in line or '/auth/send-verification' in line or 'smtp' in line.lower():
        print(f"server.py Line {i+1}: {line.strip()[:100]}")
