# app.py
# --- The main web application file (with Authentication) ---

import os
import shutil
import zipfile
import re
import xml.etree.ElementTree as ET
import fnmatch
import logging
import time
import io
import json
from functools import wraps
from urllib.request import urlopen

from flask import Flask, request, send_from_directory, jsonify, Response, after_this_request, send_file
from flask_cors import CORS
from werkzeug.utils import secure_filename
from jose import jwt

# --- Auth0 Configuration ---
# IMPORTANT: Replace these with your Auth0 application's details.
AUTH0_DOMAIN = 'dev-b0houl2m3pgvvqbt.us.auth0.com' # e.g., 'dev-12345.us.auth0.com'
API_AUDIENCE = 'https://scorm-processor-api' # e.g., 'https://scorm-processor-api'
ALGORITHMS = ["RS256"]

# --- Flask App Initialization ---
app = Flask(__name__)
CORS(app)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['PROCESSED_FOLDER'] = 'processed'
# CORRECTED: Added the missing configuration line
app.config['KNOWBE4_FILE_PATH'] = 'special_files/scorm_2004.js'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['PROCESSED_FOLDER'], exist_ok=True)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


# --- Authentication Decorator ---
class AuthError(Exception):
    def __init__(self, error, status_code):
        self.error = error
        self.status_code = status_code

@app.errorhandler(AuthError)
def handle_auth_error(ex):
    response = jsonify(ex.error)
    response.status_code = ex.status_code
    return response

def get_token_auth_header():
    """Obtains the Access Token from the Authorization Header"""
    auth = request.headers.get("Authorization", None)
    if not auth:
        raise AuthError({"code": "authorization_header_missing", "description": "Authorization header is expected"}, 401)
    parts = auth.split()
    if parts[0].lower() != "bearer":
        raise AuthError({"code": "invalid_header", "description": "Authorization header must start with Bearer"}, 401)
    elif len(parts) == 1:
        raise AuthError({"code": "invalid_header", "description": "Token not found"}, 401)
    elif len(parts) > 2:
        raise AuthError({"code": "invalid_header", "description": "Authorization header must be Bearer token"}, 401)
    token = parts[1]
    return token

def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = get_token_auth_header()
        jsonurl = urlopen(f"https://{AUTH0_DOMAIN}/.well-known/jwks.json")
        jwks = json.loads(jsonurl.read())
        unverified_header = jwt.get_unverified_header(token)
        rsa_key = {}
        for key in jwks["keys"]:
            if key["kid"] == unverified_header["kid"]:
                rsa_key = {
                    "kty": key["kty"],
                    "kid": key["kid"],
                    "use": key["use"],
                    "n": key["n"],
                    "e": key["e"]
                }
        if rsa_key:
            try:
                payload = jwt.decode(
                    token,
                    rsa_key,
                    algorithms=ALGORITHMS,
                    audience=API_AUDIENCE,
                    issuer=f"https://{AUTH0_DOMAIN}/"
                )
            except jwt.ExpiredSignatureError:
                raise AuthError({"code": "token_expired", "description": "token is expired"}, 401)
            except jwt.JWTClaimsError:
                raise AuthError({"code": "invalid_claims", "description": "incorrect claims, please check the audience and issuer"}, 401)
            except Exception:
                raise AuthError({"code": "invalid_header", "description": "Unable to parse authentication token."}, 400)
            return f(payload, *args, **kwargs)
        raise AuthError({"code": "invalid_header", "description": "Unable to find appropriate key"}, 400)
    return decorated


# --- Generator-based helper functions (Unchanged) ---
def clean_unnecessary_files(directory):
    yield "[STEP] Cleaning unnecessary files and folders"
    files_to_remove = ['aicc.*', 'readme.md', '.gitignore']
    dirs_to_remove = ['.idea', '.vscode', '__MACOSX']
    found_any = False
    for root, dirs, files in os.walk(directory, topdown=False):
        for pattern in files_to_remove:
            for filename in fnmatch.filter(files, pattern):
                found_any = True; file_path = os.path.join(root, filename)
                try:
                    os.remove(file_path)
                    yield f"  -> Removed file: {os.path.relpath(file_path, directory)}"
                except OSError as e:
                    yield f"  -> [ERROR] removing file {os.path.relpath(file_path, directory)}: {e}"
        for dirname in list(dirs):
            if dirname in dirs_to_remove:
                found_any = True; dir_path = os.path.join(root, dirname)
                try:
                    shutil.rmtree(dir_path)
                    yield f"  -> Removed directory: {os.path.relpath(dir_path, directory)}"
                    dirs.remove(dirname)
                except OSError as e:
                    yield f"  -> [ERROR] removing directory {os.path.relpath(dir_path, directory)}: {e}"
    if not found_any:
        yield "  -> No unnecessary files or folders found to clean."
    yield "     ✅ SUCCESS: Cleanup complete."

def edit_admin_settings(xml_path, scorm_version):
    yield f"[STEP] Editing 'adminsettings.xml' for SCORM {scorm_version}"
    if not os.path.exists(xml_path):
        raise ValueError("'adminsettings.xml' not found.")
    try:
        ET.register_namespace('', "http://www.w3.org/2001/XMLSchema")
        tree = ET.parse(xml_path)
        root = tree.getroot()
        changes = ({"UseScorm": "true", "UseScormVersion12": "true", "UseScormVersion2004": "false", "URLOnExit": "", "ReviewMode": "false", "HostedOniLMS": "false"}
                   if scorm_version == '1.2' else
                   {"UseScorm": "true", "UseScormVersion12": "false", "UseScormVersion2004": "true", "URLOnExit": "", "ReviewMode": "false", "HostedOniLMS": "false"})
        for tag_name, value in changes.items():
            element = root.find(f".//{{*}}{tag_name}") or root.find(tag_name)
            if element is not None:
                element.text = value
                yield f"  -> Set <{tag_name}> to '{value}'"
        tree.write(xml_path, encoding='utf-8', xml_declaration=True)
        yield "     ✅ SUCCESS: 'adminsettings.xml' saved."
    except Exception as e:
        raise ValueError(f"Error parsing or editing adminsettings.xml: {e}")

def edit_js_files_2004(js_folder_path, is_knowbe4):
    yield "[STEP] Editing JavaScript files for SCORM 2004"
    scorm_2004_js_path = os.path.join(js_folder_path, 'scorm_2004.js')
    if is_knowbe4:
        yield "  -> KnowBe4 option selected. Replacing scorm_2004.js..."
        knowbe4_special_file = app.config['KNOWBE4_FILE_PATH']
        if not os.path.exists(knowbe4_special_file):
            raise ValueError(f"Special KnowBe4 file not found on server at: {knowbe4_special_file}")
        if not os.path.exists(scorm_2004_js_path):
             raise ValueError("Cannot replace scorm_2004.js because it does not exist in the package.")
        try:
            shutil.copyfile(knowbe4_special_file, scorm_2004_js_path)
            yield "     ✅ SUCCESS: Replaced scorm_2004.js with KnowBe4 version."
        except Exception as e:
            raise ValueError(f"Could not replace scorm_2004.js: {e}")
    else:
        yield "  -> Standard processing. Replacing LMSCommit() with SCORM2004_CallCommit()..."
        if os.path.exists(scorm_2004_js_path):
            with open(scorm_2004_js_path, 'r+', encoding='utf-8') as f:
                content = f.read()
                new_content = content.replace('LMSCommit()', 'SCORM2004_CallCommit()')
                if content != new_content:
                    f.seek(0); f.write(new_content); f.truncate()
                    yield "     ✅ SUCCESS: Replacement complete."
                else:
                    yield "     ⚠️ WARNING: 'LMSCommit()' not found. No changes made."
        else:
            yield "     ⚠️ WARNING: 'scorm_2004.js' not found. Skipping."
    yield "     ✅ SUCCESS: JS file edits complete."


# --- Main processing stream ---
def process_package_stream(zip_path, output_dir, scorm_type, is_knowbe4):
    base_name = os.path.basename(zip_path)
    temp_extract_dir = os.path.join(output_dir, f"_temp_{base_name}")
    if os.path.exists(temp_extract_dir): shutil.rmtree(temp_extract_dir)
    os.makedirs(temp_extract_dir)
    def format_sse(data, event=None):
        msg = f'data: {data}\n'
        if event is not None:
            msg = f'event: {event}\n{msg}'
        return f'{msg}\n'
    try:
        def main_processing_flow():
            yield f"[STEP] Unzipping '{base_name}'"
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(temp_extract_dir)
            yield "     ✅ SUCCESS: Package unzipped."
            yield from clean_unnecessary_files(temp_extract_dir)
            yield "[STEP] Validating manifest files"
            manifest_path = os.path.join(temp_extract_dir, 'imsmanifest.xml')
            manifest_2004_path = os.path.join(temp_extract_dir, 'imsmanifest_SCORM2004.xml')
            if not (os.path.exists(manifest_path) and os.path.exists(manifest_2004_path)):
                raise ValueError("Package does not contain both 'imsmanifest.xml' and 'imsmanifest_SCORM2004.xml'.")
            yield "     ✅ SUCCESS: Both manifest files found."
            if scorm_type == '2004':
                yield "[STEP] Updating manifest for SCORM 2004"
                os.remove(manifest_path)
                os.rename(manifest_2004_path, manifest_path)
            elif scorm_type == '1.2':
                yield "[STEP] Updating manifest for SCORM 1.2"
                os.remove(manifest_2004_path)
            yield "     ✅ SUCCESS: Manifest updated."
            admin_settings_path = os.path.join(temp_extract_dir, 'xmls', 'en', 'adminsettings.xml')
            yield from edit_admin_settings(admin_settings_path, scorm_type)
            if scorm_type == '2004':
                js_folder = os.path.join(temp_extract_dir, 'js')
                yield from edit_js_files_2004(js_folder, is_knowbe4)
            yield "[STEP] Re-zipping the package"
            new_zip_name = base_name.replace('.zip', f'_processed_{scorm_type}.zip')
            new_zip_path = os.path.join(output_dir, new_zip_name)
            shutil.make_archive(new_zip_path.replace('.zip', ''), 'zip', temp_extract_dir)
            yield f"     ✅ SUCCESS: Created {new_zip_name}"
            return new_zip_name
        flow = main_processing_flow()
        final_filename = None
        while True:
            try:
                log_line = next(flow)
                app.logger.info(log_line)
                yield format_sse(log_line)
                time.sleep(0.1)
            except StopIteration as e:
                final_filename = e.value
                break
        if final_filename:
            download_url = f"/download/{final_filename}"
            yield format_sse(f'{{"url": "{download_url}", "filename": "{final_filename}"}}', 'done')
    except Exception as e:
        app.logger.error(f"Processing failed: {e}", exc_info=True)
        yield format_sse(f'{{"message": "FATAL ERROR: {str(e)}"}}', 'error')
    finally:
        if os.path.exists(temp_extract_dir):
            shutil.rmtree(temp_extract_dir)


# --- API Endpoints ---
@app.route('/api/process', methods=['POST'])
@requires_auth
def process_scorm_file(jwt_payload):
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
    file = request.files['file']
    scorm_type = request.form.get('scorm_type', '2004')
    is_knowbe4 = request.form.get('is_knowbe4') == 'true'
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
    if scorm_type not in ['1.2', '2004']:
        return jsonify({"error": "Invalid scorm_type"}), 400
    filename = secure_filename(file.filename)
    upload_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(upload_path)
    return Response(process_package_stream(upload_path, app.config['PROCESSED_FOLDER'], scorm_type, is_knowbe4), mimetype='text/event-stream')

@app.route('/download/<path:filename>')
# Note: In a true production system, this endpoint should also be protected by @requires_auth
def download_file(filename):
    return send_from_directory(app.config['PROCESSED_FOLDER'], filename, as_attachment=True)

@app.route('/api/batch_download', methods=['POST'])
@requires_auth
def batch_download(jwt_payload):
    filenames = request.json.get('filenames')
    if not filenames:
        return jsonify({"error": "No filenames provided"}), 400
    memory_file = io.BytesIO()
    with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
        for f in filenames:
            file_path = os.path.join(app.config['PROCESSED_FOLDER'], f)
            if os.path.exists(file_path):
                zf.write(file_path, arcname=f)
    memory_file.seek(0)
    for f in filenames:
        file_path = os.path.join(app.config['PROCESSED_FOLDER'], f)
        if os.path.exists(file_path):
            os.remove(file_path)
    return send_file(memory_file, download_name='scorm_batch.zip', as_attachment=True)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
