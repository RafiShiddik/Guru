import requests, urllib.parse, os

pa_user = 'achmadrafi12'
token = 'd82ad83dee1aab44732ee2eb022cda0b5ab3aec6'
headers = {'Authorization': f'Token {token}'}

guru_dir = r'c:\Users\Rafi\Downloads\Guru'

def upload_file(local_p, remote_p):
    if os.path.exists(local_p):
        upload_api = f"https://www.pythonanywhere.com/api/v0/user/{pa_user}/files/path{urllib.parse.quote(remote_p, safe='/')}"
        with open(local_p, 'rb') as f:
            r = requests.post(upload_api, headers=headers, files={'content': f}, timeout=15)
        print(f"Uploaded {os.path.basename(local_p)} -> {remote_p} [{r.status_code}]")

# Upload static files
upload_file(os.path.join(guru_dir, 'static', 'css', 'style.css'), f"/home/{pa_user}/static/css/style.css")
upload_file(os.path.join(guru_dir, 'static', 'js', 'main.js'), f"/home/{pa_user}/static/js/main.js")

# Upload template files
t_dir = os.path.join(guru_dir, 'templates')
for fn in os.listdir(t_dir):
    if fn.endswith('.html'):
        upload_file(os.path.join(t_dir, fn), f"/home/{pa_user}/templates/{fn}")

# Upload python files
upload_file(os.path.join(guru_dir, 'app.py'), f"/home/{pa_user}/app.py")
upload_file(os.path.join(guru_dir, 'teachers_passwords.json'), f"/home/{pa_user}/teachers_passwords.json")

print("Reloading webapp...")
reload_api = f"https://www.pythonanywhere.com/api/v0/user/{pa_user}/webapps/{pa_user}.pythonanywhere.com/reload/"
r_resp = requests.post(reload_api, headers=headers, timeout=15)
print("Reload status:", r_resp.status_code)
