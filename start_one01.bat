@echo off

:: Simple script to start the One01 application using Docker Compose

echo Starting Docker Compose services for One01...
docker-compose up --build

if %errorlevel% neq 0 (
    echo Failed to start Docker Compose. Please ensure Docker is installed and running.
    exit /b %errorlevel%
)

:: Optionally open the frontend in the default browser after a short wait
ping -n 10 127.0.0.1 > nul
start "" http://localhost:3000

exit /b 0
