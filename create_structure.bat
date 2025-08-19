@echo off
setlocal

set "ROOT=%cd%"
if /i not "%~n0"=="structure" (
  echo Run inside the project root (HOMESHIELD_AI)
)

rem Directories
mkdir app 2>nul
mkdir app\services 2>nul
mkdir app\api 2>nul

rem Files
type nul > app\__init__.py
type nul > app\config.py
type nul > app\vectorstore.py
type nul > app\schemas.py
type nul > app\services\customers.py
type nul > app\services\ingestion.py
type nul > app\services\rag.py
type nul > app\services\claims.py
type nul > app\api\main.py
type nul > run.py

echo Project structure created.
endlocal
