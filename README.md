# Twi DSL API

## Overview
A FastAPI-based service that translates Twi DSL to Python and executes it safely.

## Endpoints
- `POST /api/translate` → Returns Python code from Twi DSL input.
- `POST /api/execute` → Executes translated code in a sandbox.

## Local Development
```bash
pip install -r requirements.txt
uvicorn app:app --reload
