@echo off
rem Yarilo - double-click to start (or restart) the tray.
rem The first start makes the Python environment in .venv and installs the libraries;
rem later starts only install again when requirements.txt has changed.
setlocal
set "ROOT=%~dp0"
cd /d "%ROOT%"
if not exist "%ROOT%.venv\Scripts\python.exe" (
  echo Making the Python environment in .venv ...
  call :make_venv py
  if errorlevel 2 call :make_venv python
  if errorlevel 2 call :no_python
  if errorlevel 1 goto :failed
)
fc /b "%ROOT%requirements.txt" "%ROOT%.venv\installed.txt" >nul 2>nul
if errorlevel 1 (
  echo Installing the libraries ...
  "%ROOT%.venv\Scripts\python.exe" -m pip install --disable-pip-version-check -q -r "%ROOT%requirements.txt"
  if errorlevel 1 goto :failed
  copy /y "%ROOT%requirements.txt" "%ROOT%.venv\installed.txt" >nul
)
start "" "%ROOT%.venv\Scripts\pythonw.exe" "%ROOT%yarilo.pyw"
exit /b 0

:failed
pause
exit /b 1

rem Any Python can run make_venv.py: it lists the Pythons, says which one will do and why
rem the others will not. 0 - made, 1 - it said why not, 2 - no such command.
:make_venv
%1 -c "pass" >nul 2>nul || exit /b 2
%1 "%ROOT%scripts\make_venv.py" "%ROOT%.venv"
if errorlevel 1 exit /b 1
exit /b 0

:no_python
echo No Python found: Yarilo needs a 64-bit Python 3.10 or newer.
echo   1. Open https://www.python.org/downloads/windows/ and download
echo      "Windows installer (64-bit)".
echo   2. Install it.
echo   3. Run yarilo.cmd again.
exit /b 1
