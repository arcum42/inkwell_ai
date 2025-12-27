#!/usr/bin/env python3
"""Check QSettings for batch mode configuration."""

import sys
from PySide6.QtCore import QSettings, QCoreApplication

# QSettings requires a QCoreApplication
app = QCoreApplication(sys.argv)

settings = QSettings("InkwellAI", "InkwellAI")

print("Current Settings:")
print("=" * 60)

# Check batch mode flag
batch_mode = settings.value("use_batch_diff_dialog", True, type=bool)
print(f"use_batch_diff_dialog: {batch_mode} (type: {type(batch_mode).__name__})")

# Check structured output settings
structured = settings.value("structured_enabled", False, type=bool)
print(f"structured_enabled: {structured}")

schema = settings.value("structured_schema_id", "None")
print(f"structured_schema_id: {schema}")

# Check project path
last_project = settings.value("last_project", "")
print(f"last_project: {last_project}")

print("=" * 60)

if batch_mode:
    print("✅ Batch mode is ENABLED (default)")
else:
    print("⚠️  Batch mode is DISABLED")
    print("   To enable: settings.setValue('use_batch_diff_dialog', True)")

if structured and schema == "diff_patch":
    print("✅ Structured output with diff_patch schema is ENABLED")
    print("   Edits will be processed through structured JSON path")
else:
    print("ℹ️  Structured output disabled or using different schema")
    print("   Edits will be processed through text parsing path")
