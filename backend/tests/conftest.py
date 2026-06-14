"""
Pytest Configuration File
-------------------------
Sets environment variables for testing before any tests are collected or run.
"""

import os

# Enforce test environment variables
os.environ["APP_ENV"] = "test"
os.environ["SECURITY_ENABLED"] = "false"
os.environ["SECRET_KEY"] = "dev-local-secret-fallback-key-for-testing-only"
