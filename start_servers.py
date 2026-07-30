import subprocess, os, sys

py = sys.executable
work = os.path.dirname(os.path.abspath(__file__))

# app.py launcher (避免 __name__ 问题)
app_code = '''import sys
sys.path.insert(0, r'WORKDIR')
from app import app as a
import config
a.run(host=config.SERVER_HOST, port=config.SERVER_PORT, debug=False)
'''

admin_code = '''import sys
sys.path.insert(0, r'WORKDIR')
from admin_app import app as a
a.run(host='0.0.0.0', port=5001, debug=False)
'''

subprocess.Popen([py, '-c', app_code.replace('WORKDIR', work)], cwd=work, creationflags=subprocess.DETACHED_PROCESS)
subprocess.Popen([py, '-c', admin_code.replace('WORKDIR', work)], cwd=work, creationflags=subprocess.DETACHED_PROCESS)
print(f'称重端: http://localhost:5000')
print(f'管理端: http://localhost:5001')
