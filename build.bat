@echo off
setlocal

:: 1. Define paths relative to this batch file
set "PYTHON_EXE=%~dp0.venv\Scripts\python.exe"
set "PYINSTALLER_EXE=%~dp0.venv\Scripts\pyinstaller.exe"

echo ---------------------------------------------------
echo CHECKING FOR REQUIRED FILES...
echo ---------------------------------------------------

if not exist "%PYINSTALLER_EXE%" (
    echo [ERROR] PyInstaller not found in .venv. 
    echo Please run: python -m pip install pyinstaller
    pause
    exit /b
)

:: 2. Cleanup old build artifacts
echo Cleaning old builds...
if exist dist rmdir /s /q dist
if exist build rmdir /s /q build

:: 3. Run the build using the venv's pyinstaller
echo Starting PyInstaller build...
"%PYINSTALLER_EXE%" --onefile --noconsole ^
    --add-data "templates;templates" ^
    --add-data "special_files;special_files" ^
    --name "SCORM_Courses_Tool" ^
    app.py

echo ---------------------------------------------------
echo BUILD FINISHED
echo ---------------------------------------------------
pause