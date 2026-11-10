@echo off
rem Checks every monitor over DDC/CI and prints what it answers (start yarilo.cmd once first).
setlocal
set "ROOT=%~dp0"
if not exist "%ROOT%.venv\Scripts\python.exe" (
  echo Run yarilo.cmd once first: it makes the Python environment.
  pause
  exit /b 1
)
"%ROOT%.venv\Scripts\python.exe" -m yarilo probe %*
pause
