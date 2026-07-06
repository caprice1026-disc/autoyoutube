@echo off
setlocal EnableExtensions

set "SCRIPT_DIR=%~dp0"
set "ROOT_DIR=%SCRIPT_DIR%.."
set "COMMAND_FILE=%ROOT_DIR%\commands\upload_commands.txt"

powershell -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%run-upload-command-list.ps1" -CommandFile "%COMMAND_FILE%" %*
exit /b %ERRORLEVEL%
