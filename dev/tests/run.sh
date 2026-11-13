#!/bin/sh
set -eu

pytest -q dev/tests/test_app.py

if python -c 'import playwright.sync_api' >/dev/null 2>&1; then
  pytest -q dev/tests/test_shell_playwright.py
else
  echo "Playwright is not installed; skipped browser check (CI installs dev/tests/requirements.txt)."
fi
