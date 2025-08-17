@echo off
cd HOMESHIELD_AI
mkdir app app\api tests
type nul > app\__init__.py
type nul > app\config.py
type nul > app\schemas.py
type nul > app\embeddings.py
type nul > app\vectorstore.py
type nul > app\ingestion.py
type nul > app\retrieval.py
type nul > app\prompts.py
type nul > app\chains.py
type nul > app\rules.py
type nul > app\service.py
type nul > app\api\__init__.py
type nul > app\api\main.py
type nul > tests\test_smoke.py
type nul > .env
type nul > requirements.txt
type nul > README.md
dir /s /b
pause