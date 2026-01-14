#!/usr/bin/env python3
"""
Test button logging and fragment reruns
Simulates delete button click to verify logging works
"""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import os

# Setup logging exactly as in app.py
LOG_DIR = Path("/root/annotation_tool/logs")
LOG_DIR.mkdir(parents=True, exist_ok=True)

button_logger = logging.getLogger('buttons')
button_logger.setLevel(logging.INFO)
button_log_handler = RotatingFileHandler(
    LOG_DIR / 'buttons.log',
    maxBytes=1024*1024,
    backupCount=3
)
button_log_handler.setFormatter(logging.Formatter(
    '%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
))
button_logger.addHandler(button_log_handler)

# Test the logger
print("Testing button logger...")

# Simulate delete Quran reference
para_id = "test_para_1"
idx = 0
quran_refs = [{'surah': 2, 'ayah_start': 255}]

button_logger.info(f"[DELETE_REF] type=quran para={para_id} idx={idx} before_count={len(quran_refs)}")

# Simulate successful delete
ref_deleted = quran_refs[idx]
quran_refs.pop(idx)

button_logger.info(f"[DELETE_REF] success type=quran para={para_id} after_count={len(quran_refs)} rerun=fragment ref={ref_deleted.get('surah')}:{ref_deleted.get('ayah_start')}")

# Simulate save
button_logger.info(f"[SAVE] starting book=test_book")
button_logger.info(f"[SAVE] success file=test_progress.json size=1.5KB")

print("✅ Logging test complete")
print(f"Check logs at: {LOG_DIR / 'buttons.log'}")
print("\nLog contents:")
print("-" * 70)
with open(LOG_DIR / 'buttons.log', 'r') as f:
    print(f.read())
