@echo off
setlocal
set "AURA_DATA=D:/AURA/data"
set "OLLAMA_MODELS=D:\AURA\ollama-models"
cd /d "%~dp0.."

for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":8765" ^| findstr "LISTENING"') do (
  taskkill /F /PID %%p >nul 2>&1
)

py -3.13 "%~dp0launch-aura.py"
endlocal
