@echo off
cd /d "%~dp0frontend"
echo Installing frontend dependencies...
npm install
echo.
echo Starting React dev server on http://localhost:5173
npm run dev
