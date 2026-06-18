@echo off
echo Starting One01 Locally (Without Docker)...

echo.
echo Starting Backend in a new window...
start "One01 Backend" cmd /c "cd /d e:\one01\backend && venv\Scripts\activate && uvicorn main:app --port 8000 --reload"

timeout /t 5 /nobreak >nul

echo.
echo Starting Frontend in a new window...
start "One01 Frontend" cmd /c "cd /d e:\one01\frontend && npm run dev"

echo.
echo Opening Browser...
timeout /t 5 /nobreak >nul
start "" "http://localhost:3000"

echo.
echo Both services have been started in separate windows!
echo If you want to stop them, just close those new windows.
pause
