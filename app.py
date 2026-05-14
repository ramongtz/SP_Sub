import os
import sys
import shutil
import zipfile
import re
import xml.etree.ElementTree as ET
import fnmatch
import logging
import time
import io
import json
import threading
import webbrowser
from PIL import Image
from flask import Flask, request, send_from_directory, jsonify, send_file
from flask_cors import CORS
from werkzeug.utils import secure_filename
from logging_config import setup_logging

# --- Local Infrastructure Helpers ---
def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

# --- Configuration ---
app = Flask(__name__)
CORS(app)

setup_logging(app)

app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['PROCESSED_FOLDER'] = 'processed'
# Use resource_path for the bundled KnowBe4 JS file
app.config['KNOWBE4_FILE_PATH'] = resource_path('special_files/scorm_2004.js')

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['PROCESSED_FOLDER'], exist_ok=True)

# Branding Constants
LOGO_WIDTH = 300
LOGO_HEIGHT = 88
LOGO_FILENAME_IENGINE5 = "customer_logo.png"

# --- Watchdog for Auto-Shutdown ---
last_request_time = time.time()

def auto_shutdown_check():
    global last_request_time
    while True:
        time.sleep(10)
        if time.time() - last_request_time > 300:  # 5 minutes idle
            print("Idle timeout reached. Shutting down...")
            os._exit(0)

# --- Processing Logic (Restored from Remote) ---

def _replace_text_in_file(file_path, search_text, replace_text, logs):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        new_content = content.replace(search_text, replace_text)
        if content != new_content:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
            return True
    except Exception as e:
        logs.append(f"  -> [ERROR] Could not edit {os.path.basename(file_path)}: {e}")
    return False

def clean_unnecessary_files(directory, logs):
    logs.append("[STEP] Cleaning unnecessary files and folders")
    exact_files = {'.ds_store', 'readme.md', '.gitignore', '.gitattributes', '.gitmodules', '.code-workspace', '_gitignore', '__notes'}
    dirs_to_remove = {'.idea', '.vscode', '__macosx', 'nbproject', '._', '.git'}
    file_patterns = ['aicc.*', 'thumbs.db']
    
    for root, dirs, files in os.walk(directory, topdown=False):
        for dirname in list(dirs):
            if dirname.lower() in dirs_to_remove:
                shutil.rmtree(os.path.join(root, dirname))
                logs.append(f"  -> Removed directory: {dirname}")
        for filename in files:
            file_lower = filename.lower()
            if file_lower in exact_files or any(fnmatch.fnmatch(file_lower, p) for p in file_patterns):
                os.remove(os.path.join(root, filename))
                logs.append(f"  -> Removed file: {filename}")

def edit_admin_settings(directory, scorm_version, engine_type, is_licensed, is_scorm_enabled, logs, logo_details=None, license_key=None):
    logs.append("[STEP] Editing adminsettings.xml files")
    for root, _, files in os.walk(directory):
        if 'adminsettings.xml' in files:
            xml_path = os.path.join(root, 'adminsettings.xml')
            try:
                ET.register_namespace('', "http://www.w3.org/2001/XMLSchema")
                tree = ET.parse(xml_path)
                xml_root = tree.getroot()
                
                settings = {
                    "UseScorm": "true" if is_scorm_enabled else "false",
                    "UseScormVersion12": "true" if scorm_version == '1.2' else "false",
                    "UseScormVersion2004": "true" if scorm_version == '2004' else "false",
                    "URLOnExit": "",
                    "ReviewMode": "false",
                    "HostedOniLMS": "false"
                }

                for tag, val in settings.items():
                    el = xml_root.find(f".//{{*}}{tag}") or xml_root.find(tag)
                    if el is not None: el.text = val
                
                if logo_details:
                    tags = ['toplogo'] if engine_type == 'iengine5' else ['TopLogo', 'CustomerLogo']
                    for tag in tags:
                        el = xml_root.find(f".//{{*}}{tag}") or xml_root.find(tag)
                        if el is not None: el.text = logo_details['path']

                if engine_type == 'iengine6' and is_licensed:
                    check_el = xml_root.find("EnableCheck")
                    if check_el is None: check_el = ET.SubElement(xml_root, "EnableCheck")
                    check_el.text = "true"
                    if license_key:
                        key_el = xml_root.find("KeyCode")
                        if key_el is None: key_el = ET.SubElement(xml_root, "KeyCode")
                        key_el.text = license_key

                tree.write(xml_path, encoding='utf-8', xml_declaration=True)
                logs.append(f"  -> Updated: {os.path.relpath(xml_path, directory)}")
            except Exception as e:
                logs.append(f"  -> [ERROR] Failed to edit XML: {e}")

def handle_branding(directory, logo_data, engine_type, logo_filename, logs):
    logs.append("[STEP] Processing branding logo")
    img = Image.open(logo_data)
    if img.width != LOGO_WIDTH or img.height != LOGO_HEIGHT:
        img = img.resize((LOGO_WIDTH, LOGO_HEIGHT), Image.Resampling.LANCZOS)
    
    if engine_type == 'iengine5':
        dest = os.path.join(directory, 'skins', 'black-unique', 'skinimages')
        final_path = os.path.join(dest, LOGO_FILENAME_IENGINE5)
        path_for_xml = 'skins/black-unique/skinimages/' + LOGO_FILENAME_IENGINE5
    else:
        dest = os.path.join(directory, 'xmls')
        final_path = os.path.join(dest, logo_filename)
        path_for_xml = '../' + logo_filename

    os.makedirs(dest, exist_ok=True)
    img.save(final_path, 'PNG')
    logs.append(f"  -> Saved logo to {os.path.basename(final_path)}")
    return {'path': path_for_xml}

def handle_iengine5_licensing(directory, is_licensed, logs):
    logs.append("[STEP] Applying iengine5 licensing (DialogIsVisible)")
    js_folder = os.path.join(directory, 'js')
    files = ['course-engine-txt.js', 'course-engine-video.js']
    target = 'var DialogIsVisible'
    
    for f in files:
        f_path = os.path.join(js_folder, f)
        if os.path.exists(f_path):
            s_true, s_false = f'{target} = true;', f'{target} = false;'
            if is_licensed:
                _replace_text_in_file(f_path, s_false, s_true, logs)
            else:
                _replace_text_in_file(f_path, s_true, s_false, logs)

def edit_js_files_2004(directory, is_knowbe4, logs):
    logs.append("[STEP] Editing SCORM 2004 JS files")
    js_path = os.path.join(directory, 'js', 'scorm_2004.js')
    if not os.path.exists(js_path):
        logs.append("  -> ⚠️ scorm_2004.js not found, skipping.")
        return

    if is_knowbe4:
        shutil.copyfile(app.config['KNOWBE4_FILE_PATH'], js_path)
        logs.append("  -> Replaced with KnowBe4 specialized JS.")
    else:
        with open(js_path, 'r+', encoding='utf-8') as f:
            content = f.read()
            new_content = content.replace('LMSCommit()', 'SCORM2004_CallCommit()')
            if content != new_content:
                f.seek(0); f.write(new_content); f.truncate()
                logs.append("  -> Replaced LMSCommit with SCORM2004_CallCommit.")

# --- API Endpoints ---

@app.route('/')
def serve_frontend():
    """Serves the main index.html UI."""
    return send_file(resource_path(os.path.join('templates', 'index.html')))

@app.route('/api/process', methods=['POST'])
def process_file():
    global last_request_time
    last_request_time = time.time()
    
    logs = []
    try:
        file = request.files['file']
        logo_file = request.files.get('logo')
        scorm_type = request.form.get('scorm_type', '2004')
        is_knowbe4 = request.form.get('is_knowbe4') == 'true'
        is_licensed = request.form.get('is_licensed') == 'true'
        is_scorm_enabled = request.form.get('is_scorm_enabled') == 'true'
        license_key = request.form.get('license_key')

        filename = secure_filename(file.filename)
        upload_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(upload_path)
        
        temp_dir = os.path.join(app.config['PROCESSED_FOLDER'], f"temp_{int(time.time())}")
        os.makedirs(temp_dir, exist_ok=True)

        logs.append(f"Processing: {filename}")
        with zipfile.ZipFile(upload_path, 'r') as zip_ref:
            zip_ref.extractall(temp_dir)

        # Engine detection
        engine_type = 'iengine5' if os.path.exists(os.path.join(temp_dir, 'scorm')) else 'iengine6'
        logs.append(f"  -> Detected Engine: {engine_type}")

        clean_unnecessary_files(temp_dir, logs)

        logo_details = None
        if logo_file:
            logo_data = io.BytesIO(logo_file.read())
            logo_details = handle_branding(temp_dir, logo_data, engine_type, secure_filename(logo_file.filename), logs)

        if is_licensed and engine_type == 'iengine5':
            handle_iengine5_licensing(temp_dir, True, logs)
            if license_key:
                with open(os.path.join(temp_dir, 'js', 'data.xml'), 'w') as f:
                    f.write(license_key)
                logs.append("  -> Applied iEngine5 License Key to data.xml")

        # Manifest Handling
        if is_scorm_enabled:
            m12 = os.path.join(temp_dir, 'imsmanifest.xml')
            m2004 = os.path.join(temp_dir, 'imsmanifest_SCORM2004.xml')
            if os.path.exists(m12) and os.path.exists(m2004):
                if scorm_type == '2004':
                    os.remove(m12); os.rename(m2004, m12)
                else:
                    os.remove(m2004)
                logs.append(f"  -> Manifest set to SCORM {scorm_type}")

        edit_admin_settings(temp_dir, scorm_type, engine_type, is_licensed, is_scorm_enabled, logs, logo_details, license_key)

        if is_scorm_enabled and scorm_type == '2004':
            edit_js_files_2004(temp_dir, is_knowbe4, logs)

        # Finalize
        out_name = filename.replace('.zip', f'_processed_{scorm_type}')
        out_path = os.path.join(app.config['PROCESSED_FOLDER'], out_name)
        shutil.make_archive(out_path, 'zip', temp_dir)
        
        # Cleanup temp
        shutil.rmtree(temp_dir)
        os.remove(upload_path)

        return jsonify({
            "status": "success",
            "filename": f"{out_name}.zip",
            "logs": logs,
            "download_url": f"/download/{out_name}.zip"
        })

    except Exception as e:
        return jsonify({"status": "error", "message": str(e), "logs": logs}), 500

@app.route('/download/<path:filename>')
def download(filename):
    return send_from_directory(app.config['PROCESSED_FOLDER'], filename, as_attachment=True)

if __name__ == '__main__':
    # Start watchdog
    threading.Thread(target=auto_shutdown_check, daemon=True).start()
    
    # Open browser automatically
    webbrowser.open("http://127.0.0.1:8080")
    
    app.run(host='127.0.0.1', port=8080)