@echo off
setlocal
cd /d "%~dp0"
set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY (where python >nul 2>nul && set "PY=python")
if not defined PY (
 echo Python 3.12 is required to build. Install from https://www.python.org/downloads/windows/
 pause
 exit /b 1
)
%PY% -m pip install --upgrade pip || goto failed
%PY% -m pip install -r requirements.txt || goto failed
set "PLAYWRIGHT_BROWSERS_PATH=%CD%\browser"
%PY% -m playwright install chromium || goto failed
%PY% -m PyInstaller --noconfirm --clean --windowed --onedir --name "Snapshot Crawl" --collect-all playwright snapshot_crawl.py || goto failed
xcopy /E /I /Y "browser" "dist\Snapshot Crawl\browser" >nul
echo.
echo Portable application created in dist\Snapshot Crawl\
echo To create the setup wizard, install Inno Setup 6 and compile installer.iss.
pause
exit /b 0
:failed
echo Build failed. Review the error above.
pause
exit /b 1
