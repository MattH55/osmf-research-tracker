#!/usr/bin/env python3
"""Rebuild disease-intelligence HTML from JSON (delegates to publish_site)."""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from disease_pipeline.publish_site import main

if __name__ == "__main__":
    raise SystemExit(main())