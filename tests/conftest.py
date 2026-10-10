"""Test bootstrap: configure credentials before importing the application."""

import os

os.environ["JWT_SECRET"] = "test-only-secret-for-hina-security-tests"
