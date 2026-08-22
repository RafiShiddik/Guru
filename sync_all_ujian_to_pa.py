import os
import requests
import urllib.parse

pa_user = 'achmadrafi12'
token = 'd82ad83dee1aab44732ee2eb022cda0b5ab3aec6'
headers = {'Authorization': f'Token {token}'}

ulangan_dir = r'c:\Users\Rafi\Downloads\Ulangan Harian'

def upload_file(local_p, remote_p):
    if os.path.exists(local_p):
        upload_api = f"https://www.pythonanywhere.com/api/v0/user/{pa_user}/files/path{urllib.parse.quote(remote_p, safe='/')}"
        with open(local_p, 'rb') as f:
            r = requests.post(upload_api, headers=headers, files={'content': f}, timeout=15)
        print(f"Uploaded {os.path.basename(local_p)} -> {remote_p} [{r.status_code}]")

print("=== SYNCING ULANGAN HARIAN (SERVER UJIAN SISWA) TO PYTHONANYWHERE ===")

# 1. Upload main app.py
upload_file(os.path.join(ulangan_dir, 'app.py'), f"/home/{pa_user}/app.py")
upload_file(os.path.join(ulangan_dir, 'app.py'), f"/home/{pa_user}/Demo-ulangan/app.py")

# 2. Upload template files
t_dir = os.path.join(ulangan_dir, 'templates')
if os.path.exists(t_dir):
    for fn in os.listdir(t_dir):
        if fn.endswith('.html'):
            upload_file(os.path.join(t_dir, fn), f"/home/{pa_user}/templates/{fn}")
            upload_file(os.path.join(t_dir, fn), f"/home/{pa_user}/Demo-ulangan/templates/{fn}")

# 3. Upload static CSS / JS if available
s_dir = os.path.join(ulangan_dir, 'static')
if os.path.exists(s_dir):
    for root, dirs, files in os.walk(s_dir):
        for f in files:
            full_p = os.path.join(root, f)
            rel_p = os.path.relpath(full_p, s_dir).replace('\\', '/')
            upload_file(full_p, f"/home/{pa_user}/static/{rel_p}")
            upload_file(full_p, f"/home/{pa_user}/Demo-ulangan/static/{rel_p}")

print("\nReloading PythonAnywhere WebApp (achmadrafi12.pythonanywhere.com)...")
reload_api = f"https://www.pythonanywhere.com/api/v0/user/{pa_user}/webapps/{pa_user}.pythonanywhere.com/reload/"
r_resp = requests.post(reload_api, headers=headers, timeout=15)
print(f"Reload Status: [{r_resp.status_code}]")

if r_resp.status_code == 200:
    print("SUCCESS! Application 'Ulangan Harian' is fully updated & active on PythonAnywhere!")
else:
    print("Reload warning:", r_resp.text)
