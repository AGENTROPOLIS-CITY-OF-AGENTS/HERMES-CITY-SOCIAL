# HERMES-CITY-SOCIAL — canonical verification entry points
#
# `make` is canonical on Linux/WSL/macOS. On hosts without make (e.g. this
# Windows git-bash host) use the documented Python commands:
#
#   uv run --with jsonschema --with pyyaml --with fastapi --with httpx python -m unittest discover -s tests -v
#   python scripts/verify-contracts.py
#
.PHONY: verify
verify:
	python scripts/verify-contracts.py

.PHONY: canary
canary:
	uv run --with jsonschema --with pyyaml --with fastapi --with httpx python scripts/canary-b4.py
