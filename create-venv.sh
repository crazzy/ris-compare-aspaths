#!/usr/bin/env bash
if ! which python >/dev/null 2>/dev/null; then
	echo "ERROR: Python missing!" >&2
fi
python -m venv .
source bin/activate
pip install -r requirements.txt
