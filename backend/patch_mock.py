import sys
content = open('i:/Proj/TigaMinds/backend/main.py', 'r', encoding='utf-8').read()
old_code = '''cred = credentials.Certificate(firebase_creds)
firebase_admin.initialize_app(cred)

db = firestore.client()'''
new_code = '''cred = credentials.Certificate(firebase_creds)
firebase_admin.initialize_app(cred)

import firestore_mock
db = firestore_mock.client()
print("🔥 Using firestore_mock globally to bypass Firebase quota limits!")'''
if old_code in content:
    content = content.replace(old_code, new_code)
    open('i:/Proj/TigaMinds/backend/main.py', 'w', encoding='utf-8').write(content)
    print('Patched successfully!')
else:
    print('Target code not found')
