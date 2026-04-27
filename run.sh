#!/bin/bash
set -a
source "$(dirname "$0")/.env.local"
set +a
python3 dashboard/app.py
