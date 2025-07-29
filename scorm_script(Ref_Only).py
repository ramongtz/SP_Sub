import os
import shutil
import zipfile
import re
import xml.etree.ElementTree as ET
import fnmatch

# --- Logging Functions for Clear Output ---
def log_step(message):
    """Prints a major step in the process."""
    print(f"\n[STEP] {message}")

def log_action(message):
    """Prints a specific action being performed."""
    print(f"  -> {message}")

def log_success(message):
    """Prints a success message."""
    print(f"     ✅ SUCCESS: {message}")

def log_warning(message):
    """Prints a warning message."""
    print(f"     ⚠️ WARNING: {message}")

def log_error(message):
    """Prints an error message and indicates a failure."""
    print(f"     ❌ ERROR: {message}")

def clean_unnecessary_files(directory):
    """
    Removes common unnecessary files and folders from the extracted package.
    Returns a list of warnings for files/folders that were removed.
    """
    warnings = []
    log_step("Cleaning unnecessary files and folders")
    
    # Patterns and names to remove
    # CORRECTED: Changed '*.aicc' to 'aicc.*'
    files_to_remove = ['aicc.*', 'readme.md', '.gitignore']
    dirs_to_remove = ['.idea', '.vscode', '__MACOSX']

    for root, dirs, files in os.walk(directory, topdown=False):
        # Remove specified files
        for pattern in files_to_remove:
            for filename in fnmatch.filter(files, pattern):
                file_path = os.path.join(root, filename)
                try:
                    os.remove(file_path)
                    msg = f"Removed unnecessary file: {file_path}"
                    log_action(msg)
                    warnings.append(msg)
                except OSError as e:
                    msg = f"Error removing file {file_path}: {e}"
                    log_error(msg)
                    warnings.append(msg)

        # Remove specified directories
        for dirname in list(dirs): # Iterate over a copy
            if dirname in dirs_to_remove:
                dir_path = os.path.join(root, dirname)
                try:
                    shutil.rmtree(dir_path)
                    msg = f"Removed unnecessary directory: {dir_path}"
                    log_action(msg)
                    warnings.append(msg)
                    dirs.remove(dirname) # Remove from list to prevent further traversal
                except OSError as e:
                    msg = f"Error removing directory {dir_path}: {e}"
                    log_error(msg)
                    warnings.append(msg)
    
    log_success("Cleanup complete.")
    return warnings

def edit_admin_settings(xml_path, scorm_version):
    """
    Edits the specified fields in adminsettings.xml based on the SCORM version.
    Returns a tuple: (bool: success, list: warnings)
    """
    warnings = []
    log_step(f"Editing 'adminsettings.xml' for SCORM {scorm_version}")
    if not os.path.exists(xml_path):
        msg = f"'adminsettings.xml' not found at the expected path: {xml_path}"
        log_error(msg)
        warnings.append(msg)
        return False, warnings

    try:
        log_action(f"Parsing XML file: {xml_path}")
        ET.register_namespace('', "http://www.w3.org/2001/XMLSchema")
        tree = ET.parse(xml_path)
        root = tree.getroot()
        log_success("XML file parsed.")

        if scorm_version == '1.2':
            changes = {
                "UseScorm": "true", "UseScormVersion12": "true", "UseScormVersion2004": "false",
                "URLOnExit": "", "ReviewMode": "false", "HostedOniLMS": "false"
            }
        else:
            changes = {
                "UseScorm": "true", "UseScormVersion12": "false", "UseScormVersion2004": "true",
                "URLOnExit": "", "ReviewMode": "false", "HostedOniLMS": "false"
            }

        for tag_name, value in changes.items():
            log_action(f"Looking for tag <{tag_name}>...")
            element = root.find(f".//{{*}}{tag_name}") or root.find(tag_name)
            if element is not None:
                element.text = value
                log_success(f"Set <{tag_name}> to '{value}'")
            else:
                msg = f"Tag <{tag_name}> not found in file."
                log_warning(msg); warnings.append(msg)
        
        log_action("Saving changes...")
        tree.write(xml_path, encoding='utf-8', xml_declaration=True)
        log_success("File saved.")
        return True, warnings

    except Exception as e:
        msg = f"Error editing {os.path.basename(xml_path)}: {e}"
        log_error(msg); warnings.append(msg)
        return False, warnings

def edit_js_files_2004(js_folder_path, knowbe4_file_path):
    """
    Edits the required JS files for SCORM 2004 packages.
    Returns a tuple: (bool: success, list: warnings)
    """
    warnings = []
    log_step("Editing JavaScript files for SCORM 2004")
    if not os.path.exists(js_folder_path):
        msg = f"JS folder not found at: {js_folder_path}"
        log_error(msg); warnings.append(msg)
        return False, warnings

    scorm_js_path = os.path.join(js_folder_path, 'scorm.js')
    scorm_2004_js_path = os.path.join(js_folder_path, 'scorm_2004.js')
    course_engine_js_path = os.path.join(js_folder_path, 'course-engine.js')

    if not os.path.exists(scorm_js_path) or not os.path.exists(scorm_2004_js_path):
        msg = "One or both JS files ('scorm.js', 'scorm_2004.js') are missing. Check if this is an iengine6 course."
        log_warning(msg); warnings.append(msg)
    else:
        log_success("'scorm.js' and 'scorm_2004.js' found.")

    if os.path.exists(scorm_2004_js_path):
        if knowbe4_file_path:
            log_action("Overwriting 'scorm_2004.js' with KnowBe4 version...")
            try:
                shutil.copyfile(knowbe4_file_path, scorm_2004_js_path)
                log_success("'scorm_2004.js' replaced.")
            except Exception as e:
                msg = f"Failed to overwrite file: {e}"; log_error(msg); warnings.append(msg)
        else:
            log_action("Editing 'scorm_2004.js': Replacing LMSCommit() with SCORM2004_CallCommit()...")
            try:
                with open(scorm_2004_js_path, 'r+', encoding='utf-8') as f:
                    content = f.read()
                    new_content = content.replace('LMSCommit()', 'SCORM2004_CallCommit()')
                    if content != new_content:
                        f.seek(0); f.write(new_content); f.truncate()
                        log_success("Replacement complete.")
                    else:
                        msg = "'LMSCommit()' not found. No changes made."; log_warning(msg); warnings.append(msg)
            except Exception as e:
                msg = f"Could not edit 'scorm_2004.js': {e}"; log_error(msg); warnings.append(msg)
            
    if os.path.exists(course_engine_js_path):
        log_action("Editing 'course-engine.js': Setting 'dialogisvisible' to true...")
        try:
            with open(course_engine_js_path, 'r+', encoding='utf-8') as f:
                content = f.read()
                new_content, count = re.subn(r'dialogisvisible(\s*[:=]\s*)false', r'dialogisvisible\1true', content)
                if count > 0:
                    f.seek(0); f.write(new_content); f.truncate()
                    log_success("'dialogisvisible' set to true.")
                else:
                    msg = "'dialogisvisible: false' not found. No changes made."; log_warning(msg); warnings.append(msg)
        except Exception as e:
            msg = f"Could not edit 'course-engine.js': {e}"; log_error(msg); warnings.append(msg)
    else:
        msg = "'course-engine.js' not found. Skipping."; log_warning(msg); warnings.append(msg)

    if os.path.exists(scorm_js_path):
        log_action("Editing 'scorm.js': Replacing 'self.close();' with 'top.close();'...")
        try:
            with open(scorm_js_path, 'r+', encoding='utf-8') as f:
                content = f.read()
                new_content = content.replace("'self.close();'", "'top.close();'").replace('"self.close();"', '"top.close();"')
                if content != new_content:
                    f.seek(0); f.write(new_content); f.truncate()
                    log_success("Replacement complete.")
                else:
                    msg = "'self.close();' not found. No changes made."; log_warning(msg); warnings.append(msg)
        except Exception as e:
            msg = f"Could not edit 'scorm.js': {e}"; log_error(msg); warnings.append(msg)
        
    return True, warnings

def process_package(zip_path, output_dir, scorm_type, knowbe4_file):
    base_name = os.path.basename(zip_path)
    print(f"\n{'='*15} Processing: {base_name} for SCORM {scorm_type} {'='*15}")
    all_warnings = []
    result = {'name': base_name, 'status': 'failure', 'warnings': all_warnings}
    temp_extract_dir = os.path.join(output_dir, f"_temp_{base_name}")
    if os.path.exists(temp_extract_dir): shutil.rmtree(temp_extract_dir)
    os.makedirs(temp_extract_dir)

    try:
        log_step(f"Unzipping '{base_name}'")
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(temp_extract_dir)
        log_success("Package unzipped.")

        # NEW STEP: Clean unnecessary files
        cleanup_warnings = clean_unnecessary_files(temp_extract_dir)
        all_warnings.extend(cleanup_warnings)

        log_step("Validating manifest files")
        manifest_path = os.path.join(temp_extract_dir, 'imsmanifest.xml')
        manifest_2004_path = os.path.join(temp_extract_dir, 'imsmanifest_SCORM2004.xml')
        if not os.path.exists(manifest_path) or not os.path.exists(manifest_2004_path):
            log_error("Package does not contain both 'imsmanifest.xml' and 'imsmanifest_SCORM2004.xml'. Skipping.")
            return result
        log_success("Both manifest files found.")

        if scorm_type == '2004':
            log_step("Updating manifest for SCORM 2004")
            os.remove(manifest_path)
            log_action("Deleted 'imsmanifest.xml'.")
            os.rename(manifest_2004_path, manifest_path)
            log_action("Renamed 'imsmanifest_SCORM2004.xml' to 'imsmanifest.xml'.")
        elif scorm_type == '1.2':
            log_step("Updating manifest for SCORM 1.2")
            os.remove(manifest_2004_path)
            log_action("Deleted 'imsmanifest_SCORM2004.xml'.")

        admin_settings_path = os.path.join(temp_extract_dir, 'xmls', 'en', 'adminsettings.xml')
        success, warnings = edit_admin_settings(admin_settings_path, scorm_type)
        all_warnings.extend(warnings)
        if not success:
            log_error("Skipping due to issues with adminsettings.xml.")
            return result

        if scorm_type == '2004':
            js_folder = os.path.join(temp_extract_dir, 'js')
            success, warnings = edit_js_files_2004(js_folder, knowbe4_file)
            all_warnings.extend(warnings)
            if not success:
                log_error("Skipping due to issues with JS files.")
                return result

        log_step("Re-zipping the package")
        new_zip_name = base_name.replace('.zip', f'_processed_{scorm_type}.zip')
        new_zip_path_base = os.path.join(output_dir, new_zip_name.replace('.zip', ''))
        shutil.make_archive(new_zip_path_base, 'zip', temp_extract_dir)
        log_success(f"Successfully created: {new_zip_name}")
        result['status'] = 'success'
        return result

    except Exception as e:
        log_error(f"A critical unhandled error occurred: {e}")
        all_warnings.append(f"Critical unhandled error: {e}")
        return result
    finally:
        shutil.rmtree(temp_extract_dir)
        print(f"{'='*15} Finished: {base_name} {'='*15}")

def main():
    print("--- SCORM Bulk Processor ---")
    while True:
        work_dir = input("1. Enter the path to the folder with your SCORM .zip files: ")
        if os.path.isdir(work_dir): break
        print("   ❌ ERROR: Invalid directory.")
    while True:
        scorm_type = input("2. Which SCORM format to process? ('1.2' or '2004'): ").strip()
        if scorm_type in ['1.2', '2004']: break
        print("   ❌ ERROR: Invalid input.")
    knowbe4_file = None
    if scorm_type == '2004':
        while True:
            is_knowbe4 = input("3. Are these packages for KnowBe4? (yes/no): ").lower()
            if is_knowbe4 in ['yes', 'y']:
                while True:
                    knowbe4_file_input = input("   -> Enter path to special 'scorm_2004.js' file: ")
                    knowbe4_file = os.path.join(work_dir, knowbe4_file_input) if not os.path.isabs(knowbe4_file_input) else knowbe4_file_input
                    if os.path.isfile(knowbe4_file): break
                    print(f"   ❌ ERROR: File not found at '{knowbe4_file}'.")
                break
            elif is_knowbe4 in ['no', 'n']: break
            else: print("   Invalid input.")
    output_directory = os.path.join(work_dir, "_PROCESSED_SCORMS")
    os.makedirs(output_directory, exist_ok=True)
    print(f"\n✅ Processed files will be saved in: {output_directory}")
    zip_files_found = [f for f in os.listdir(work_dir) if f.lower().endswith('.zip')]
    if not zip_files_found:
        log_warning("No .zip files found."); return
    print(f"Found {len(zip_files_found)} zip file(s) to process.")
    summary_results = [process_package(os.path.join(work_dir, zf), output_directory, scorm_type, knowbe4_file) for zf in zip_files_found]
    print("\n\n" + "="*20 + " 🚀 Final Summary 🚀 " + "="*20)
    successful = [r['name'] for r in summary_results if r['status'] == 'success']
    failed = [r['name'] for r in summary_results if r['status'] == 'failure']
    with_warnings = {r['name']: r['warnings'] for r in summary_results if r['warnings']}
    print(f"\n✅ Successfully processed: {len(successful)} package(s)")
    if successful:
        for name in successful: print(f"  - {name}")
    print(f"\n❌ Failed or skipped: {len(failed)} package(s)")
    if failed:
        for name in failed: print(f"  - {name}")
    print(f"\n⚠️ Warnings generated: {len(with_warnings)} package(s) had warnings")
    if with_warnings:
        for name, warnings in with_warnings.items():
            print(f"\n  --- Warnings for {name}: ---")
            for i, warning in enumerate(warnings, 1): print(f"    {i}. {warning}")
    print("\n" + "="*55 + "\nAll tasks complete!")

if __name__ == '__main__':
    main()
