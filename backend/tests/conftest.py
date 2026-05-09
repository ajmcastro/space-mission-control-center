"""Shared test fixtures — wire app to an in-memory SQLite database.

This module sets DATABASE_URL before any app module is imported, so the
SQLAlchemy engine is created pointing at :memory: for the whole test session.
"""
import os

os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
