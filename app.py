# app.py
# --- The main web application file (with Authentication and Branding) ---

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

# --- NEW: Import Pillow for image processing ---
from PIL import Image
from flask import Flask, request, send_from_directory, jsonify, Response, after_this_request, send_file
from flask_cors import CORS
from werkzeug.utils import secure_filename
from jose import jwt

# --- NEW: Import Flask-Limiter for rate limiting ---
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# --- NEW: Import and set up logging ---
from logging_config import setup_logging

# --- REVISED: Auth0 Configuration from Environment Variables ---
AUTH0_DOMAIN = os.environ.get('AUTH0_DOMAIN')
API_AUDIENCE = os.environ.get('API_AUDIENCE')
ALGORITHMS = ["RS256"]

# Validate that the environment variables are set
if not all([AUTH0_DOMAIN, API_AUDIENCE]):
    raise RuntimeError("Missing required Auth0 environment variables (AUTH0_DOMAIN, API_AUDIENCE).")

# --- NEW: Branding Configuration ---
LOGO_WIDTH = 300
LOGO_HEIGHT = 88
LOGO_FILENAME_IENGINE5 = "customer_logo.png"

# --- Flask App Initialization ---
app = Flask(__name__)
CORS(app)

# --- NEW: Initialize the rate limiter ---
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://",
)

# --- NEW: Setup logging from the external file ---
setup_logging(app)

app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['PROCESSED_FOLDER'] = 'processed'
app.config['KNOWBE4_FILE_PATH'] = 'special_files/scorm_2004.js'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['PROCESSED_FOLDER'], exist_ok=True)


# --- Authentication Decorator (Unchanged) ---
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
                rsa_key = { "kty": key["kty"], "kid": key["kid"], "use": key["use"], "n": key["n"], "e": key["e"] }
        if rsa_key:
            try:
                payload = jwt.decode( token, rsa_key, algorithms=ALGORITHMS, audience=API_AUDIENCE, issuer=f"https://{AUTH0_DOMAIN}/" )
            except jwt.ExpiredSignatureError:
                raise AuthError({"code": "token_expired", "description": "token is expired"}, 401)
            except jwt.JWTClaimsError:
                raise AuthError({"code": "invalid_claims", "description": "incorrect claims, please check the audience and issuer"}, 401)
            except Exception:
                raise AuthError({"code": "invalid_header", "description": "Unable to parse authentication token."}, 400)
            return f(payload, *args, **kwargs)
        raise AuthError({"code": "invalid_header", "description": "Unable to find appropriate key"}, 400)
    return decorated


# --- Generator-based helper functions ---
def clean_unnecessary_files(directory):
    yield "[STEP] Cleaning unnecessary files and folders"
    app.logger.info("Starting file cleanup process.")
    files_to_remove = ['aicc.*', 'readme.md', '.gitignore', 'README.md']
    dirs_to_remove = ['.idea', '.vscode', '__MACOSX']
    found_any = False
    for root, dirs, files in os.walk(directory, topdown=False):
        for pattern in files_to_remove:
            for filename in fnmatch.filter(files, pattern):
                found_any = True; file_path = os.path.join(root, filename)
                try:
                    os.remove(file_path)
                    log_msg = f"Removed file: {os.path.relpath(file_path, directory)}"
                    yield f"  -> {log_msg}"
                    app.logger.info(log_msg)
                except OSError as e:
                    log_msg = f"Error removing file {os.path.relpath(file_path, directory)}: {e}"
                    yield f"  -> [ERROR] {log_msg}"
                    app.logger.error(log_msg)
        for dirname in list(dirs):
            if dirname in dirs_to_remove:
                found_any = True; dir_path = os.path.join(root, dirname)
                try:
                    shutil.rmtree(dir_path)
                    log_msg = f"Removed directory: {os.path.relpath(dir_path, directory)}"
                    yield f"  -> {log_msg}"
                    app.logger.info(log_msg)
                    dirs.remove(dirname)
                except OSError as e:
                    log_msg = f"Error removing directory {os.path.relpath(dir_path, directory)}: {e}"
                    yield f"  -> [ERROR] {log_msg}"
                    app.logger.error(log_msg)
    if not found_any:
        yield "  -> No unnecessary files or folders found to clean."
        app.logger.info("No unnecessary files found to clean.")
    yield "     ✅ SUCCESS: Cleanup complete."
    app.logger.info("File cleanup process completed.")


def edit_admin_settings(directory, scorm_version, engine_type, logo_details=None, license_key=None):
    yield f"[STEP] Finding and editing 'adminsettings.xml' files for SCORM {scorm_version}"
    app.logger.info(f"Starting to edit adminsettings.xml files for SCORM {scorm_version}.")
    found_files = []
    for root, _, files in os.walk(directory):
        if 'adminsettings.xml' in files:
            xml_path = os.path.join(root, 'adminsettings.xml')
            found_files.append(xml_path)
            relative_path = os.path.relpath(xml_path, directory)
            yield f"  -> Found '{relative_path}'. Applying changes..."
            app.logger.info(f"Processing adminsettings.xml at: {relative_path}")
            try:
                ET.register_namespace('', "http://www.w3.org/2001/XMLSchema")
                tree = ET.parse(xml_path)
                xml_root = tree.getroot()
                changes = ({"UseScorm": "true", "UseScormVersion12": "true", "UseScormVersion2004": "false", "URLOnExit": "", "ReviewMode": "false", "HostedOniLMS": "false"}
                           if scorm_version == '1.2' else
                           {"UseScorm": "true", "UseScormVersion12": "false", "UseScormVersion2004": "true", "URLOnExit": "", "ReviewMode": "false", "HostedOniLMS": "false"})
                for tag_name, value in changes.items():
                    element = xml_root.find(f".//{{*}}{tag_name}") or xml_root.find(tag_name)
                    if element is not None:
                        element.text = value
                        app.logger.info(f"Set <{tag_name}> to '{value}' in {relative_path}")
                
                if logo_details:
                    path_to_set = logo_details['path']
                    tags_to_update = ['toplogo'] if engine_type == 'iengine5' else ['TopLogo', 'CustomerLogo']
                    for tag in tags_to_update:
                        logo_element = xml_root.find(f".//{{*}}{tag}") or xml_root.find(tag)
                        if logo_element is not None:
                            logo_element.text = path_to_set
                            yield f"  -> Set <{tag}> to '{path_to_set}'"
                            app.logger.info(f"Set <{tag}> to '{path_to_set}' in {relative_path}")

                if engine_type == 'iengine6' and license_key:
                    key_element = xml_root.find("KeyCode")
                    if key_element is None:
                        key_element = ET.SubElement(xml_root, "KeyCode")
                        yield f"  -> Created missing <KeyCode> tag."
                        app.logger.info(f"Created missing <KeyCode> tag in {relative_path}")
                    key_element.text = license_key
                    yield f"  -> Set <KeyCode> with license key."
                    app.logger.info(f"Set <KeyCode> in {relative_path}")
                    
                    check_element = xml_root.find("EnableCheck")
                    if check_element is None:
                        check_element = ET.SubElement(xml_root, "EnableCheck")
                        yield f"  -> Created missing <EnableCheck> tag."
                        app.logger.info(f"Created missing <EnableCheck> tag in {relative_path}")
                    check_element.text = "true"
                    yield f"  -> Set <EnableCheck> to 'true'."
                    app.logger.info(f"Set <EnableCheck> to 'true' in {relative_path}")

                tree.write(xml_path, encoding='utf-8', xml_declaration=True)
            except Exception as e:
                log_msg = f"Failed to edit {relative_path}: {e}"
                yield f"  -> [ERROR] {log_msg}"
                app.logger.error(log_msg)
    if not found_files:
        yield "     ⚠️ WARNING: No 'adminsettings.xml' files were found in the package."
        app.logger.warning("No adminsettings.xml files found.")
    else:
        yield f"     ✅ SUCCESS: Processed {len(found_files)} 'adminsettings.xml' file(s)."
        app.logger.info(f"Finished processing {len(found_files)} adminsettings.xml file(s).")


def handle_branding(directory, logo_file_storage, engine_type, logo_filename):
    yield "[STEP] Processing branding logo"
    app.logger.info("Starting branding process.")
    try:
        img = Image.open(logo_file_storage)
        if img.width != LOGO_WIDTH or img.height != LOGO_HEIGHT:
            yield f"  -> Resizing logo from {img.width}x{img.height} to {LOGO_WIDTH}x{LOGO_HEIGHT}px."
            app.logger.info(f"Resizing logo to {LOGO_WIDTH}x{LOGO_HEIGHT}px.")
            img = img.resize((LOGO_WIDTH, LOGO_HEIGHT), Image.Resampling.LANCZOS)
        
        logo_details = {}
        if engine_type == 'iengine5':
            logo_dest_folder = os.path.join(directory, 'skins', 'black-unique', 'skinimages')
            logo_final_path = os.path.join(logo_dest_folder, LOGO_FILENAME_IENGINE5)
            logo_path_for_xml = 'skins/black-unique/skinimages/' + LOGO_FILENAME_IENGINE5
        else: # iengine6
            logo_dest_folder = os.path.join(directory, 'xmls')
            logo_final_path = os.path.join(logo_dest_folder, logo_filename)
            logo_path_for_xml = '../' + logo_filename

        os.makedirs(logo_dest_folder, exist_ok=True)
        img.save(logo_final_path, 'PNG')
        log_msg = f"Saved logo to: {os.path.relpath(logo_final_path, directory)}"
        yield f"  -> {log_msg}"
        app.logger.info(log_msg)
        
        logo_details['path'] = logo_path_for_xml
        yield "     ✅ SUCCESS: Branding processed."
        app.logger.info("Branding process completed successfully.")
        return logo_details
    except Exception as e:
        app.logger.error(f"Branding failed: {e}", exc_info=True)
        raise ValueError(f"Could not process logo: {e}")


def handle_license_key(directory, license_key):
    yield "[STEP] Applying license key for iengine5"
    app.logger.info("Applying license key for iengine5.")
    data_xml_path = os.path.join(directory, 'js', 'data.xml')
    if not os.path.exists(data_xml_path):
        app.logger.error("data.xml not found for iengine5.")
        raise ValueError("'data.xml' not found in js folder for iengine5 course.")
    
    try:
        with open(data_xml_path, 'w', encoding='utf-8') as f:
            f.write(license_key)
        yield "  -> Overwrote 'js/data.xml' with the new license key."
        yield "     ✅ SUCCESS: License key applied."
        app.logger.info("Successfully wrote license key to js/data.xml.")
    except Exception as e:
        app.logger.error(f"Failed to write license key: {e}", exc_info=True)
        raise ValueError(f"Could not write license key to data.xml: {e}")


def edit_js_files_2004(js_folder_path, is_knowbe4):
    yield "[STEP] Editing JavaScript files for SCORM 2004"
    app.logger.info("Starting JS file edits for SCORM 2004.")
    scorm_2004_js_path = os.path.join(js_folder_path, 'scorm_2004.js')
    if is_knowbe4:
        yield "  -> KnowBe4 option selected. Replacing scorm_2004.js..."
        app.logger.info("KnowBe4 option selected. Replacing scorm_2004.js.")
        knowbe4_special_file = app.config['KNOWBE4_FILE_PATH']
        if not os.path.exists(knowbe4_special_file):
            raise ValueError(f"Special KnowBe4 file not found on server at: {knowbe4_special_file}")
        if not os.path.exists(scorm_2004_js_path):
             raise ValueError("Cannot replace scorm_2004.js because it does not exist in the package.")
        try:
            shutil.copyfile(knowbe4_special_file, scorm_2004_js_path)
            yield "     ✅ SUCCESS: Replaced scorm_2004.js with KnowBe4 version."
            app.logger.info("Successfully replaced scorm_2004.js with KnowBe4 version.")
        except Exception as e:
            app.logger.error(f"Failed to replace scorm_2004.js: {e}", exc_info=True)
            raise ValueError(f"Could not replace scorm_2004.js: {e}")
    else:
        yield "  -> Standard processing. Replacing LMSCommit() with SCORM2004_CallCommit()..."
        app.logger.info("Standard SCORM 2004 processing.")
        if os.path.exists(scorm_2004_js_path):
            with open(scorm_2004_js_path, 'r+', encoding='utf-8') as f:
                content = f.read()
                new_content = content.replace('LMSCommit()', 'SCORM2004_CallCommit()')
                if content != new_content:
                    f.seek(0); f.write(new_content); f.truncate()
                    yield "     ✅ SUCCESS: Replacement complete."
                    app.logger.info("Successfully replaced LMSCommit() in scorm_2004.js.")
                else:
                    yield "     ⚠️ WARNING: 'LMSCommit()' not found. No changes made."
                    app.logger.warning("'LMSCommit()' not found in scorm_2004.js.")
        else:
            yield "     ⚠️ WARNING: 'scorm_2004.js' not found. Skipping."
            app.logger.warning("scorm_2004.js not found, skipping edit.")
    yield "     ✅ SUCCESS: JS file edits complete."
    app.logger.info("JS file edits for SCORM 2004 completed.")


# --- Main processing stream ---
def process_package_stream(zip_path, output_dir, scorm_type, is_knowbe4, logo_data=None, logo_filename=None, license_key=None):
    base_name = os.path.basename(zip_path)
    app.logger.info(f"--- Starting new processing job for: {base_name} ---")
    app.logger.info(f"Parameters: SCORM Type='{scorm_type}', KnowBe4='{is_knowbe4}', Logo Provided='{logo_data is not None}', License Key Provided='{license_key is not None}'")
    
    temp_extract_dir = os.path.join(output_dir, f"_temp_{base_name}")
    if os.path.exists(temp_extract_dir): shutil.rmtree(temp_extract_dir)
    os.makedirs(temp_extract_dir)
    def format_sse(data, event=None):
        msg = f'data: {data}\n'
        if event is not None: msg = f'event: {event}\n{msg}'
        return f'{msg}\n'
    try:
        def main_processing_flow():
            yield f"[STEP] Unzipping '{base_name}'"
            app.logger.info(f"Unzipping {base_name} to {temp_extract_dir}")
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(temp_extract_dir)
            yield "     ✅ SUCCESS: Package unzipped."
            app.logger.info("Unzipping complete.")
            
            # --- NEW: Validate that the package is a valid SCORM file ---
            yield "[STEP] Validating SCORM package..."
            app.logger.info("Validating for imsmanifest.xml")
            manifest_path_check = os.path.join(temp_extract_dir, 'imsmanifest.xml')
            if not os.path.exists(manifest_path_check):
                app.logger.error("Manifest validation failed: imsmanifest.xml not found.")
                raise ValueError("The uploaded file is not a valid SCORM package (missing 'imsmanifest.xml').")
            yield "     ✅ SUCCESS: 'imsmanifest.xml' found."
            app.logger.info("Manifest found.")
            
            is_iengine5 = os.path.exists(os.path.join(temp_extract_dir, 'scorm'))
            engine_type = 'iengine5' if is_iengine5 else 'iengine6'
            yield f"  -> Engine Type detected: {engine_type}"
            app.logger.info(f"Detected engine type: {engine_type}")

            yield from clean_unnecessary_files(temp_extract_dir)
            
            logo_details = None
            if logo_data:
                branding_flow = handle_branding(temp_extract_dir, logo_data, engine_type, logo_filename)
                while True:
                    try:
                        log_line = next(branding_flow)
                        yield log_line
                    except StopIteration as e:
                        logo_details = e.value
                        break
            
            if license_key:
                if engine_type == 'iengine5':
                    yield from handle_license_key(temp_extract_dir, license_key)
            
            app.logger.info("Validating manifest files.")
            yield "[STEP] Validating manifest files"
            manifest_path = os.path.join(temp_extract_dir, 'imsmanifest.xml')
            manifest_2004_path = os.path.join(temp_extract_dir, 'imsmanifest_SCORM2004.xml')
            if not (os.path.exists(manifest_path) and os.path.exists(manifest_2004_path)):
                app.logger.error("Manifest validation failed.")
                raise ValueError("Package does not contain both 'imsmanifest.xml' and 'imsmanifest_SCORM2004.xml'.")
            yield "     ✅ SUCCESS: Both manifest files found."
            app.logger.info("Manifests validated.")

            if scorm_type == '2004':
                yield "[STEP] Updating manifest for SCORM 2004"
                app.logger.info("Updating manifest for SCORM 2004.")
                os.remove(manifest_path); os.rename(manifest_2004_path, manifest_path)
            elif scorm_type == '1.2':
                yield "[STEP] Updating manifest for SCORM 1.2"
                app.logger.info("Updating manifest for SCORM 1.2.")
                os.remove(manifest_2004_path)
            yield "     ✅ SUCCESS: Manifest updated."
            app.logger.info("Manifest update complete.")
            
            yield from edit_admin_settings(temp_extract_dir, scorm_type, engine_type, logo_details, license_key)

            if scorm_type == '2004':
                js_folder = os.path.join(temp_extract_dir, 'js')
                yield from edit_js_files_2004(js_folder, is_knowbe4)

            yield "[STEP] Re-zipping the package"
            app.logger.info("Re-zipping the package.")
            new_zip_name = base_name.replace('.zip', f'_processed_{scorm_type}.zip')
            new_zip_path = os.path.join(output_dir, new_zip_name)
            shutil.make_archive(new_zip_path.replace('.zip', ''), 'zip', temp_extract_dir)
            yield f"     ✅ SUCCESS: Created {new_zip_name}"
            app.logger.info(f"Successfully created processed file: {new_zip_name}")
            return new_zip_name
        
        flow = main_processing_flow()
        final_filename = None
        while True:
            try:
                log_line = next(flow)
                yield format_sse(log_line)
            except StopIteration as e:
                final_filename = e.value
                break
        if final_filename:
            download_url = f"/download/{final_filename}"
            yield format_sse(f'{{"url": "{download_url}", "filename": "{final_filename}"}}', 'done')
            app.logger.info(f"--- Successfully finished processing job for: {base_name} ---")
    except Exception as e:
        app.logger.error(f"--- Processing job for {base_name} failed: {e} ---", exc_info=True)
        yield format_sse(f'{{"message": "FATAL ERROR: {str(e)}"}}', 'error')
    finally:
        # --- MODIFIED: Clean up temp directory AND original uploaded file ---
        if os.path.exists(temp_extract_dir):
            shutil.rmtree(temp_extract_dir)
        if os.path.exists(zip_path):
            try:
                os.remove(zip_path)
                app.logger.info(f"Successfully purged original upload: {os.path.basename(zip_path)}")
            except OSError as e:
                app.logger.error(f"Error purging original upload {os.path.basename(zip_path)}: {e}")


# --- API Endpoints ---
def _purge_directory(directory):
    """Helper function to delete all files in a directory."""
    for filename in os.listdir(directory):
        file_path = os.path.join(directory, filename)
        try:
            if os.path.isfile(file_path) or os.path.islink(file_path):
                os.unlink(file_path)
            elif os.path.isdir(file_path):
                shutil.rmtree(file_path)
        except Exception as e:
            app.logger.error(f'Failed to delete {file_path}. Reason: {e}')

@app.route('/api/purge', methods=['POST'])
@requires_auth
def purge_workspace(jwt_payload):
    """Endpoint to clean the workspace before a new batch upload."""
    app.logger.info("Received request to purge workspace.")
    try:
        upload_folder = app.config['UPLOAD_FOLDER']
        processed_folder = app.config['PROCESSED_FOLDER']
        
        app.logger.info(f"Purging directory: {upload_folder}")
        _purge_directory(upload_folder)
        
        app.logger.info(f"Purging directory: {processed_folder}")
        _purge_directory(processed_folder)
        
        app.logger.info("Workspace purged successfully.")
        return jsonify({"status": "success", "message": "Workspace purged successfully."}), 200
    except Exception as e:
        app.logger.error(f"An error occurred during workspace purge: {e}", exc_info=True)
        return jsonify({"status": "error", "message": "An error occurred during cleanup."}), 500

@app.route('/api/process', methods=['POST'])
@limiter.limit("20 per minute")
@requires_auth
def process_scorm_file(jwt_payload):
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
    file = request.files['file']
    logo_file = request.files.get('logo', None)
    scorm_type = request.form.get('scorm_type', '2004')
    is_knowbe4 = request.form.get('is_knowbe4') == 'true'
    license_key = request.form.get('license_key', None)

    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
    if scorm_type not in ['1.2', '2004']:
        return jsonify({"error": "Invalid scorm_type"}), 400
    filename = secure_filename(file.filename)
    upload_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(upload_path)

    logo_data = None
    logo_filename = None
    if logo_file:
        logo_filename = secure_filename(logo_file.filename)
        logo_data = io.BytesIO(logo_file.read())

    return Response(process_package_stream(upload_path, app.config['PROCESSED_FOLDER'], scorm_type, is_knowbe4, logo_data, logo_filename, license_key), mimetype='text/event-stream')

@app.route('/download/<path:filename>')
@requires_auth
def download_file(jwt_payload, filename):
    return send_from_directory(app.config['PROCESSED_FOLDER'], filename, as_attachment=True)

@app.route('/api/batch_download', methods=['POST'])
@requires_auth
def batch_download(jwt_payload):
    filenames = request.json.get('filenames')
    if not filenames:
        return jsonify({"error": "No filenames provided"}), 400
    
    safe_filenames = [secure_filename(f) for f in filenames]
    memory_file = io.BytesIO()
    with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
        for f in safe_filenames:
            file_path = os.path.join(app.config['PROCESSED_FOLDER'], f)
            if os.path.exists(file_path):
                zf.write(file_path, arcname=f)
    memory_file.seek(0)
    
    for f in safe_filenames:
        file_path = os.path.join(app.config['PROCESSED_FOLDER'], f)
        if os.path.exists(file_path):
            os.remove(file_path)
            
    return send_file(memory_file, download_name='scorm_batch.zip', as_attachment=True)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)