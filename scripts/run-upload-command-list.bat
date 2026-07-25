@echo off
setlocal EnableExtensions

set "SCRIPT_DIR=%~dp0"
set "ROOT_DIR=%SCRIPT_DIR%.."

cd /d "%ROOT_DIR%"

powershell -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%run-upload-command-list.ps1" %*
exit /b %ERRORLEVEL%
