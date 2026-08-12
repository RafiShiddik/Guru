import os
import re
import json
import shutil
import urllib.parse
try:
    import docx
except ImportError:
    docx = None

try:
    import requests
except ImportError:
    requests = None
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash, send_file

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__, static_folder=os.path.join(BASE_DIR, 'static'), static_url_path='/static')
app.secret_key = 'guru_portal_bm2_secure_key_2026'

# Teacher accounts and passwords
TEACHERS_CREDENTIALS = {
    'Ir. Ely Rosidah': 'Bu Ely Cantik',
    'Achmad Rafi Shiddik': 'Achmad 123'
}

CONFIG_FILE = os.path.join(BASE_DIR, 'sync_config.json')

def load_sync_config():
    default_cfg = {
        'remote_url': 'https://14214.pythonanywhere.com',
        'pa_account_url': 'https://www.pythonanywhere.com/user/14214/',
        'sync_token': ''
    }
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                default_cfg.update(data)
        except Exception:
            pass
    return default_cfg

def save_sync_config(cfg):
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(cfg, f, indent=2)
    except Exception:
        pass

def get_student_soal_base_dir():
    """Detects absolute path to 'soal matematika' in Ulangan Harian workspace."""
    candidates = [
        os.path.join(os.path.dirname(BASE_DIR), 'Ulangan Harian', 'soal matematika'),
        os.path.join(os.path.dirname(BASE_DIR), 'soal matematika'),
        os.path.join(BASE_DIR, 'soal matematika'),
        r'C:\Users\Rafi\Downloads\Ulangan Harian\soal matematika',
        r'C:\Users\Rafi\Downloads\soal matematika',
        '/var/task/soal matematika'
    ]
    for c in candidates:
        if os.path.exists(c) and os.path.isdir(c):
            return c
    default_path = os.path.join(BASE_DIR, 'soal matematika')
    try:
        os.makedirs(default_path, exist_ok=True)
    except Exception:
        pass
    return default_path

def get_student_hasil_dir():
    """Detects path to 'hasil ujian' in Ulangan Harian workspace."""
    candidates = [
        os.path.join(os.path.dirname(BASE_DIR), 'Ulangan Harian', 'hasil ujian'),
        os.path.join(os.path.dirname(BASE_DIR), 'hasil ujian'),
        os.path.join(BASE_DIR, 'hasil ujian'),
        r'C:\Users\Rafi\Downloads\Ulangan Harian\hasil ujian',
        r'C:\Users\Rafi\Downloads\hasil ujian'
    ]
    for c in candidates:
        if os.path.exists(c) and os.path.isdir(c):
            return c
    default_path = os.path.join(BASE_DIR, 'hasil ujian')
    try:
        os.makedirs(default_path, exist_ok=True)
    except Exception:
        pass
    return default_path

def get_student_key_dir():
    """Detects path to 'key' directory in Ulangan Harian workspace."""
    candidates = [
        os.path.join(os.path.dirname(BASE_DIR), 'Ulangan Harian', 'key'),
        os.path.join(os.path.dirname(BASE_DIR), 'key'),
        os.path.join(BASE_DIR, 'key'),
        r'C:\Users\Rafi\Downloads\Ulangan Harian\key',
        r'C:\Users\Rafi\Downloads\key'
    ]
    for c in candidates:
        if os.path.exists(c) and os.path.isdir(c):
            return c
    default_path = os.path.join(BASE_DIR, 'key')
    try:
        os.makedirs(default_path, exist_ok=True)
    except Exception:
        pass
    return default_path

def scan_all_materials():
    """Scans student exam soal directory and returns list of material dicts."""
    base_dir = get_student_soal_base_dir()
    results = []
    if not os.path.exists(base_dir):
        return results

    for class_folder in sorted(os.listdir(base_dir)):
        class_path = os.path.join(base_dir, class_folder)
        if os.path.isdir(class_path):
            norm_class = class_folder.replace('Kelas ', '').replace('kelas ', '').strip()
            
            subfolders = [f for f in os.listdir(class_path) if os.path.isdir(os.path.join(class_path, f))]
            if subfolders:
                for mat_name in sorted(subfolders):
                    mat_path = os.path.join(class_path, mat_name)
                    files = os.listdir(mat_path)
                    
                    meta = {}
                    meta_path = os.path.join(mat_path, 'metadata.json')
                    if os.path.exists(meta_path):
                        try:
                            with open(meta_path, 'r', encoding='utf-8') as mf:
                                meta = json.load(mf)
                        except Exception:
                            pass

                    results.append({
                        'kelas_raw': class_folder,
                        'kelas': norm_class,
                        'materi': mat_name,
                        'jurusan': meta.get('jurusan', 'Semua Jurusan'),
                        'uploaded_by': meta.get('uploaded_by', 'Guru'),
                        'timestamp': meta.get('timestamp', ''),
                        'has_pg': any(f.endswith('.docx') and 'kunci' not in f.lower() and 'essay' not in f.lower() for f in files),
                        'has_key': any(f.endswith('.docx') and 'kunci' in f.lower() and 'essay' not in f.lower() for f in files),
                        'has_essay': any(f.endswith('.docx') and 'essay' in f.lower() for f in files),
                        'files': files
                    })
            else:
                files = os.listdir(class_path)
                docx_files = [f for f in files if f.endswith('.docx')]
                if docx_files:
                    results.append({
                        'kelas_raw': class_folder,
                        'kelas': norm_class,
                        'materi': 'Matematika Umum',
                        'jurusan': 'Semua Jurusan',
                        'uploaded_by': 'Guru',
                        'timestamp': '',
                        'has_pg': True,
                        'has_key': False,
                        'files': docx_files
                    })
                    
    local_keys = {(m['kelas'], m['materi']) for m in results}
    remote_mats = fetch_remote_materials()
    for rm in remote_mats:
        if (rm['kelas'], rm['materi']) not in local_keys:
            results.append(rm)

    return results

def fetch_remote_materials():
    """Fetches list of exam materials from remote student app (14214.pythonanywhere.com)."""
    if requests is None:
        return []
    cfg = load_sync_config()
    sync_token = cfg.get('sync_token', '').strip()
    remote_results = []

    if sync_token:
        try:
            pa_user = '14214'
            pa_url = cfg.get('pa_account_url', '')
            if 'user/' in pa_url:
                parts = pa_url.split('user/')[1].split('/')
                if parts and parts[0]:
                    pa_user = parts[0].strip()
                    
            headers = {'Authorization': f'Token {sync_token}'}
            api_path_url = f"https://www.pythonanywhere.com/api/v0/user/{pa_user}/files/path/home/{pa_user}/soal%20matematika/"
            
            resp = requests.get(api_path_url, headers=headers, timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                contents = data.get('contents', [])
                for item in contents:
                    if isinstance(item, dict) and item.get('type') == 'directory':
                        class_folder = os.path.basename(item.get('path', ''))
                        norm_class = class_folder.replace('Kelas ', '').replace('kelas ', '').strip()
                        
                        sub_path = item.get('path', '')
                        encoded_sub_path = urllib.parse.quote(sub_path, safe='/')
                        sub_url = f"https://www.pythonanywhere.com/api/v0/user/{pa_user}/files/path{encoded_sub_path}/"
                        s_resp = requests.get(sub_url, headers=headers, timeout=5)
                        if s_resp.status_code == 200:
                            s_contents = s_resp.json().get('contents', [])
                            for s_item in s_contents:
                                if isinstance(s_item, dict) and s_item.get('type') == 'directory':
                                    mat_name = os.path.basename(s_item.get('path', ''))
                                    remote_results.append({
                                        'kelas_raw': class_folder,
                                        'kelas': norm_class,
                                        'materi': mat_name,
                                        'jurusan': 'Semua Jurusan',
                                        'uploaded_by': 'Server Siswa Remote',
                                        'timestamp': '',
                                        'has_pg': True,
                                        'has_key': False,
                                        'has_essay': False,
                                        'files': []
                                    })
        except Exception as e:
            print(f"[Remote Materials Fetch Error] {e}")
            
    return remote_results

def parse_hasil_txt(txt_path):
    info = {
        'nama': '',
        'kelas': '',
        'materi': '',
        'jurusan': '',
        'tanggal': '',
        'skor_pg': '',
        'benar_pg': ''
    }
    try:
        with open(txt_path, 'r', encoding='utf-8') as f:
            for line in f:
                line_str = line.strip()
                if line_str.startswith('Nama') and ':' in line_str:
                    info['nama'] = line_str.split(':', 1)[1].strip()
                elif line_str.startswith('Kelas') and ':' in line_str:
                    info['kelas'] = line_str.split(':', 1)[1].strip()
                elif line_str.startswith('Materi') and ':' in line_str:
                    info['materi'] = line_str.split(':', 1)[1].strip()
                elif line_str.startswith('Jurusan') and ':' in line_str:
                    info['jurusan'] = line_str.split(':', 1)[1].strip()
                elif line_str.startswith('Tanggal') and ':' in line_str:
                    info['tanggal'] = line_str.split(':', 1)[1].strip()
                elif line_str.startswith('Skor PG') and ':' in line_str:
                    info['skor_pg'] = line_str.split(':', 1)[1].strip()
                elif line_str.startswith('Benar PG') and ':' in line_str:
                    info['benar_pg'] = line_str.split(':', 1)[1].strip()
    except Exception:
        pass
    return info

def scan_student_results():
    """Scans student exam results in 'hasil ujian' directory with kelas and jurusan metadata."""
    hasil_dir = get_student_hasil_dir()
    results = []
    if not os.path.exists(hasil_dir):
        return results

    visited_dirs = set()

    for root, dirs, files in os.walk(hasil_dir):
        target_files = [f for f in files if f in ['hasil.txt', 'hasil_ujian.html'] or f.endswith('.txt') or f.endswith('.html')]
        if not target_files or root in visited_dirs:
            continue
            
        visited_dirs.add(root)
        txt_file = next((f for f in files if f == 'hasil.txt'), None) or next((f for f in files if f.endswith('.txt')), None)
        html_file = next((f for f in files if f == 'hasil_ujian.html'), None) or next((f for f in files if f.endswith('.html')), None)
        
        main_file = txt_file or html_file
        if not main_file:
            continue

        file_path = os.path.join(root, main_file)
        rel_path = os.path.relpath(file_path, hasil_dir)
        file_size = os.path.getsize(file_path)
        mod_time = datetime.fromtimestamp(os.path.getmtime(file_path)).strftime('%Y-%m-%d %H:%M:%S')

        norm_rel = rel_path.replace('\\', '/')
        parts = norm_rel.split('/')
        
        parsed_info = {}
        if txt_file:
            parsed_info = parse_hasil_txt(os.path.join(root, txt_file))

        folder_kelas = parts[0] if len(parts) >= 1 else 'Umum'
        folder_materi = parts[1] if len(parts) >= 4 else (parts[1] if len(parts) == 3 else 'Umum')
        folder_jurusan = parts[2] if len(parts) >= 4 else (parts[1] if len(parts) == 3 else 'Semua Jurusan')
        folder_student = parts[3] if len(parts) >= 4 else (parts[2] if len(parts) == 3 else parts[-2] if len(parts) >= 2 else 'Siswa')

        raw_kelas = parsed_info.get('kelas') or folder_kelas
        norm_kelas = raw_kelas if raw_kelas.startswith('Kelas') else f"Kelas {raw_kelas}"
        materi = parsed_info.get('materi') or folder_materi
        jurusan = parsed_info.get('jurusan') or folder_jurusan
        student_name = parsed_info.get('nama') or folder_student.replace('_', ' ').title()
        date_str = parsed_info.get('tanggal') or mod_time
        skor_pg = parsed_info.get('skor_pg') or '-'
        benar_pg = parsed_info.get('benar_pg') or '-'

        view_rel_path = norm_rel
        if html_file:
            view_rel_path = os.path.relpath(os.path.join(root, html_file), hasil_dir).replace('\\', '/')

        results.append({
            'filename': main_file,
            'rel_path': norm_rel,
            'view_rel_path': view_rel_path,
            'student_name': student_name,
            'kelas': norm_kelas,
            'materi': materi,
            'jurusan': jurusan,
            'skor_pg': skor_pg,
            'benar_pg': benar_pg,
            'size_bytes': file_size,
            'date': date_str,
            'full_path': file_path
        })

    results.sort(key=lambda x: x['date'], reverse=True)
    return results

def fetch_remote_student_results():
    """Fetches student exam results and registered classes from remote student app or PythonAnywhere Official REST API."""
    if requests is None:
        return [], []
    cfg = load_sync_config()
    remote_url = cfg.get('remote_url', '').strip().rstrip('/')
    sync_token = cfg.get('sync_token', '').strip()
    
    classes = []
    results = []

    # 1. Try PythonAnywhere Official REST API if API token is configured
    if sync_token:
        try:
            pa_user = '14214'
            pa_url = cfg.get('pa_account_url', '')
            if 'user/' in pa_url:
                pa_user = pa_url.split('user/')[1].split('/')[0].strip() or '14214'
                
            headers = {'Authorization': f'Token {sync_token}'}
            api_path_url = f"https://www.pythonanywhere.com/api/v0/user/{pa_user}/files/path/home/{pa_user}/hasil%20ujian/"
            
            resp = requests.get(api_path_url, headers=headers, timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                contents = data.get('contents', [])
                for item in contents:
                    if isinstance(item, dict) and item.get('type') == 'directory':
                        folder_name = os.path.basename(item.get('path', ''))
                        norm_k = folder_name if folder_name.startswith('Kelas') else f"Kelas {folder_name}"
                        if norm_k not in classes:
                            classes.append(norm_k)
        except Exception as e:
            print(f"[PythonAnywhere REST API Error] {e}")

    # 2. Try App API Endpoint (/api/get_student_results)
    if remote_url:
        try:
            resp = requests.get(f"{remote_url}/api/get_student_results", timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                res_list = data.get('results', [])
                cls_list = data.get('classes', [])
                for c in cls_list:
                    if c not in classes:
                        classes.append(c)
                results.extend(res_list)
        except Exception as e:
            print(f"[Remote Results Fetch Error] {e}")

    return results, sorted(classes)

def sync_to_remote_server(norm_k, materi, jurusan, pg_path, kunci_pg_path=None, essay_path=None, kunci_essay_path=None):
    """Pushes uploaded DOCX files directly to the remote PythonAnywhere Student Exam app via HTTP POST and/or PA REST API."""
    if requests is None:
        return False, "Package 'requests' belum terinstall."
    cfg = load_sync_config()
    sync_token = cfg.get('sync_token', '').strip()
    remote_url = cfg.get('remote_url', 'https://14214.pythonanywhere.com').strip().rstrip('/')
    if not remote_url:
        remote_url = 'https://14214.pythonanywhere.com'

    upload_success = False
    status_msg = ""

    # 1. Try posting to student app /api/upload_soal (creates folders and saves files automatically)
    target_endpoint = f"{remote_url}/api/upload_soal"
    files = {}
    try:
        if pg_path and os.path.exists(pg_path):
            files['file_pg'] = (os.path.basename(pg_path), open(pg_path, 'rb'), 'application/vnd.openxmlformats-officedocument.wordprocessingml.document')
        if kunci_pg_path and os.path.exists(kunci_pg_path):
            files['file_kunci_pg'] = (os.path.basename(kunci_pg_path), open(kunci_pg_path, 'rb'), 'application/vnd.openxmlformats-officedocument.wordprocessingml.document')
        if essay_path and os.path.exists(essay_path):
            files['file_essay'] = (os.path.basename(essay_path), open(essay_path, 'rb'), 'application/vnd.openxmlformats-officedocument.wordprocessingml.document')
        if kunci_essay_path and os.path.exists(kunci_essay_path):
            files['file_kunci_essay'] = (os.path.basename(kunci_essay_path), open(kunci_essay_path, 'rb'), 'application/vnd.openxmlformats-officedocument.wordprocessingml.document')

        data = {
            'kelas': norm_k,
            'materi': materi,
            'jurusan': jurusan,
            'sync_token': sync_token
        }

        resp = requests.post(target_endpoint, data=data, files=files, timeout=10)
        if resp.status_code == 200:
            upload_success = True
            status_msg = "Berhasil terkirim ke server Ujian Siswa via /api/upload_soal."
        else:
            status_msg = f"HTTP POST merespons status {resp.status_code}."
    except Exception as e:
        status_msg = f"HTTP POST error: {str(e)}"
    finally:
        for fkey, ftuple in files.items():
            try:
                ftuple[1].close()
            except Exception:
                pass

    # 2. Try PythonAnywhere Official REST API as direct sync
    if sync_token:
        try:
            pa_user = '14214'
            pa_url = cfg.get('pa_account_url', '')
            if 'user/' in pa_url:
                pa_user = pa_url.split('user/')[1].split('/')[0].strip() or '14214'
            
            headers = {'Authorization': f'Token {sync_token}'}
            file_paths = [pg_path, kunci_pg_path, essay_path, kunci_essay_path]
            uploaded_count = 0
            
            for fp in file_paths:
                if fp and os.path.exists(fp):
                    fname = os.path.basename(fp)
                    file_rel_path = f"/home/{pa_user}/soal matematika/{norm_k}/{materi}/{fname}"
                    target_api = f"https://www.pythonanywhere.com/api/v0/user/{pa_user}/files/path{urllib.parse.quote(file_rel_path, safe='/')}"
                    with open(fp, 'rb') as f_in:
                        r = requests.post(target_api, headers=headers, files={'content': f_in}, timeout=10)
                        if r.status_code in (200, 201):
                            uploaded_count += 1
            
            # Upload metadata.json
            meta_data = {
                'materi': materi,
                'kelas': norm_k,
                'jurusan': jurusan,
                'uploaded_by': session.get('guru_nama', 'Guru'),
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            meta_rel_path = f"/home/{pa_user}/soal matematika/{norm_k}/{materi}/metadata.json"
            meta_api = f"https://www.pythonanywhere.com/api/v0/user/{pa_user}/files/path{urllib.parse.quote(meta_rel_path, safe='/')}"
            requests.post(meta_api, headers=headers, files={'content': json.dumps(meta_data, indent=2)}, timeout=10)
            
            if uploaded_count > 0:
                upload_success = True
                status_msg = f"Berhasil diunggah ke PythonAnywhere API 14214 ({uploaded_count} file)."

            # Trigger Reload on student server via PythonAnywhere REST API so Flask immediately sees new files
            try:
                reload_api = f"https://www.pythonanywhere.com/api/v0/user/{pa_user}/webapps/{pa_user}.pythonanywhere.com/reload/"
                requests.post(reload_api, headers=headers, timeout=10)
                status_msg += " Server siswa direload otomatis!"
            except Exception:
                pass
        except Exception as e:
            print(f"[PA API Upload Error] {e}")

    if upload_success:
        return True, status_msg
    return False, status_msg or "Gagal melakukan sinkronisasi ke server remote."

@app.before_request
def check_auth():
    allowed_routes = ['login', 'static']
    if request.endpoint not in allowed_routes and not session.get('guru_nama'):
        return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        nama = request.form.get('nama', '').strip()
        password = request.form.get('password', '').strip()
        
        matched_teacher = None
        for teacher_name in TEACHERS_CREDENTIALS:
            if teacher_name.lower().replace(' ', '') == nama.lower().replace(' ', ''):
                matched_teacher = teacher_name
                break

        if not matched_teacher:
            return render_template('login.html', error='Nama guru tidak terdaftar!')

        expected_pwd = TEACHERS_CREDENTIALS[matched_teacher]
        if password != expected_pwd:
            return render_template('login.html', error='Password yang Anda masukkan salah!')

        session['guru_nama'] = matched_teacher
        flash(f'Selamat datang, {matched_teacher}!', 'success')
        return redirect(url_for('index'))

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Anda telah keluar dari Portal Guru.', 'info')
    return redirect(url_for('login'))

@app.route('/')
def index():
    materi_list = scan_all_materials()
    total_materi = len(materi_list)
    classes_set = {m['kelas'] for m in materi_list}
    total_kelas = len(classes_set)
    student_results = scan_student_results()
    return render_template('dashboard.html', 
                           materi_list=materi_list, 
                           total_materi=total_materi, 
                           total_kelas=total_kelas,
                           total_hasil_siswa=len(student_results))

@app.route('/input-soal', methods=['GET', 'POST'])
def input_soal():
    if request.method == 'POST':
        materi = request.form.get('materi', '').strip()
        kelas = request.form.get('kelas', '').strip()
        jurusan = request.form.get('jurusan', 'Semua Jurusan').strip()

        file_pg = request.files.get('file_pg')
        file_kunci_pg = request.files.get('file_kunci_pg')
        file_essay = request.files.get('file_essay')
        file_kunci_essay = request.files.get('file_kunci_essay')

        if not materi or not kelas or not file_pg or not file_pg.filename:
            flash('Materi, Kelas, dan File Soal Pilihan Ganda wajib diisi!', 'danger')
            return redirect(url_for('input_soal'))

        base_soal_dir = get_student_soal_base_dir()
        norm_k = kelas if kelas.startswith('Kelas') else f"Kelas {kelas}"
        target_dir = os.path.join(base_soal_dir, norm_k, materi)
        
        try:
            os.makedirs(target_dir, exist_ok=True)
        except Exception as e:
            flash(f'Gagal membuat direktori soal: {str(e)}', 'danger')
            return redirect(url_for('input_soal'))

        try:
            # 1. Soal PG
            pg_path = os.path.join(target_dir, f"Soal Ulangan Pilihan Ganda {norm_k}.docx")
            file_pg.save(pg_path)

            # 2. Kunci PG (Optional)
            kunci_pg_path = None
            if file_kunci_pg and file_kunci_pg.filename:
                kunci_pg_path = os.path.join(target_dir, f"Kunci Jawaban {norm_k}.docx")
                file_kunci_pg.save(kunci_pg_path)

            # 3. Soal Essay (Optional)
            essay_path = None
            if file_essay and file_essay.filename:
                essay_path = os.path.join(target_dir, f"Soal Essay {norm_k.lower()}.docx")
                file_essay.save(essay_path)

            # 4. Kunci Essay (Optional)
            kunci_essay_path = None
            if file_kunci_essay and file_kunci_essay.filename:
                kunci_essay_path = os.path.join(target_dir, "Kunci Jawaban essay.docx")
                file_kunci_essay.save(kunci_essay_path)

            # 5. Metadata JSON
            meta = {
                'materi': materi,
                'kelas': norm_k,
                'jurusan': jurusan,
                'uploaded_by': session.get('guru_nama', 'Guru'),
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            with open(os.path.join(target_dir, 'metadata.json'), 'w', encoding='utf-8') as mf:
                json.dump(meta, mf, indent=2)

            # Trigger Remote HTTP Sync if configured
            sync_ok, sync_msg = sync_to_remote_server(norm_k, materi, jurusan, pg_path, kunci_pg_path, essay_path, kunci_essay_path)
            
            flash(f'Berhasil! Soal "{materi}" ({norm_k}) tersimpan secara lokal. Sync Status: {sync_msg}', 'success')
            return redirect(url_for('index'))

        except Exception as e:
            flash(f'Terjadi kesalahan saat menyimpan file: {str(e)}', 'danger')
            return redirect(url_for('input_soal'))

    return render_template('input_soal.html')

@app.route('/kelola-soal')
def kelola_soal():
    materi_list = scan_all_materials()
    return render_template('kelola_soal.html', materi_list=materi_list)

@app.route('/delete-soal', methods=['POST'])
def delete_soal():
    kelas_raw = request.form.get('kelas', '').strip()
    materi = request.form.get('materi', '').strip()

    if not kelas_raw or not materi:
        flash('Data tidak valid.', 'danger')
        return redirect(url_for('kelola_soal'))

    base_dir = get_student_soal_base_dir()
    target_dir = os.path.join(base_dir, kelas_raw, materi)

    if os.path.exists(target_dir) and os.path.isdir(target_dir):
        try:
            shutil.rmtree(target_dir)
            flash(f'Materi "{materi}" dari {kelas_raw} berhasil dihapus.', 'success')
        except Exception as e:
            flash(f'Gagal menghapus folder: {str(e)}', 'danger')
    else:
        flash('Folder materi tidak ditemukan.', 'danger')

    return redirect(url_for('kelola_soal'))

@app.route('/hasil-ujian')
def hasil_ujian():
    student_results = scan_student_results()
    hasil_dir = get_student_hasil_dir()
    
    class_jurusan_map = {}
    
    # 1. Register existing class directories in local hasil ujian folder
    if os.path.exists(hasil_dir):
        for item in os.listdir(hasil_dir):
            item_path = os.path.join(hasil_dir, item)
            if os.path.isdir(item_path):
                norm_k = item if item.startswith('Kelas') else f"Kelas {item}"
                class_jurusan_map[norm_k] = set()

    # 2. Add classes and jurusans from local scanned result files
    for r in student_results:
        k = r.get('kelas', 'Kelas Umum')
        j = r.get('jurusan', 'Semua Jurusan')
        if k not in class_jurusan_map:
            class_jurusan_map[k] = set()
        if j:
            class_jurusan_map[k].add(j)

    # 3. Fetch from remote student server (14214.pythonanywhere.com) if configured
    remote_results, remote_classes = fetch_remote_student_results()
    if remote_classes:
        for c in remote_classes:
            if c not in class_jurusan_map:
                class_jurusan_map[c] = set()

    if remote_results:
        local_rel_paths = {r['rel_path'] for r in student_results}
        for rr in remote_results:
            if rr['rel_path'] not in local_rel_paths:
                student_results.append(rr)
                k = rr.get('kelas', 'Kelas Umum')
                j = rr.get('jurusan', 'Semua Jurusan')
                if k not in class_jurusan_map:
                    class_jurusan_map[k] = set()
                if j:
                    class_jurusan_map[k].add(j)
            
    class_jurusan_json = {k: sorted(list(v)) for k, v in class_jurusan_map.items()}
    sorted_classes = sorted(list(class_jurusan_map.keys()))

    return render_template('hasil_ujian.html', 
                           results=student_results,
                           classes=sorted_classes,
                           class_jurusan_json=json.dumps(class_jurusan_json))

@app.route('/view-hasil/<path:filepath>')
def view_hasil(filepath):
    hasil_dir = get_student_hasil_dir()
    full_path = os.path.abspath(os.path.join(hasil_dir, filepath))
    if os.path.exists(full_path) and full_path.startswith(os.path.abspath(hasil_dir)):
        return send_file(full_path)

    cfg = load_sync_config()
    remote_url = cfg.get('remote_url', '').strip().rstrip('/')
    sync_token = cfg.get('sync_token', '').strip()
    
    # 1. Try PythonAnywhere REST API if API token is configured
    if sync_token:
        try:
            pa_user = '14214'
            pa_url = cfg.get('pa_account_url', '')
            if 'user/' in pa_url:
                parts = pa_url.split('user/')[1].split('/')
                if parts and parts[0]:
                    pa_user = parts[0].strip()
                    
            headers = {'Authorization': f'Token {sync_token}'}
            clean_fp = filepath.replace('\\', '/')
            rel_fp = f"/home/{pa_user}/hasil ujian/{clean_fp}"
            api_file_url = f"https://www.pythonanywhere.com/api/v0/user/{pa_user}/files/path{urllib.parse.quote(rel_fp, safe='/')}"
            
            r_resp = requests.get(api_file_url, headers=headers, timeout=10)
            if r_resp.status_code == 200:
                from flask import Response
                mtype = 'text/html' if clean_fp.endswith('.html') else 'text/plain'
                return Response(r_resp.content, mimetype=mtype)
        except Exception as e:
            print(f"[PA File Fetch Error] {e}")

    # 2. Fallback to remote student app URL
    if remote_url and requests:
        try:
            r_resp = requests.get(f"{remote_url}/view-hasil/{filepath}", timeout=10)
            if r_resp.status_code == 200:
                from flask import Response
                return Response(r_resp.content, mimetype=r_resp.headers.get('Content-Type', 'text/html'))
        except Exception:
            pass

    flash('File hasil ujian tidak ditemukan.', 'danger')
    return redirect(url_for('hasil_ujian'))

@app.route('/sync-settings', methods=['GET', 'POST'])
def sync_settings():
    cfg = load_sync_config()
    key_dir = get_student_key_dir()
    key_files = os.listdir(key_dir) if os.path.exists(key_dir) else []

    if request.method == 'POST':
        cfg['remote_url'] = request.form.get('remote_url', '').strip()
        cfg['pa_account_url'] = request.form.get('pa_account_url', '').strip()
        cfg['sync_token'] = request.form.get('sync_token', '').strip()
        save_sync_config(cfg)

        file_key = request.files.get('file_key')
        if file_key and file_key.filename.endswith('.json'):
            try:
                target_key_path = os.path.join(key_dir, file_key.filename)
                file_key.save(target_key_path)
                flash('File Google Service Account Key berhasil diperbarui!', 'success')
            except Exception as e:
                flash(f'Gagal menyimpan file key: {str(e)}', 'danger')

        flash('Pengaturan sinkronisasi remote berhasil disimpan!', 'success')
        return redirect(url_for('sync_settings'))

    return render_template('sync_settings.html', 
                           current_remote_url=cfg.get('remote_url', 'https://14214.pythonanywhere.com'),
                           pa_account_url=cfg.get('pa_account_url', 'https://www.pythonanywhere.com/user/14214/'),
                           current_sync_token=cfg.get('sync_token', ''),
                           key_files=key_files)

@app.route('/api/preview-docx', methods=['POST'])
def api_preview_docx():
    if docx is None:
        return jsonify({'error': 'python-docx belum terinstall'}), 500
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
    file = request.files['file']
    if not file or not file.filename.endswith('.docx'):
        return jsonify({'error': 'File must be a .docx document'}), 400

    try:
        doc = docx.Document(file)
        paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
        return jsonify({
            'total_paragraphs': len(paragraphs),
            'sample_paragraphs': paragraphs[:10]
        })
    except Exception as e:
        return jsonify({'error': f'Failed to parse docx: {str(e)}'}), 500

if __name__ == '__main__':
    print("=" * 60)
    print("  SERVER GURU (TEACHER PORTAL) RUNNING ON PORT 5050")
    print("  Student Exam Target Directory:", get_student_soal_base_dir())
    print("  Student Exam Results Directory:", get_student_hasil_dir())
    print("  Google Service Key Directory:", get_student_key_dir())
    print("=" * 60)
    app.run(host='0.0.0.0', port=5050, debug=True)
