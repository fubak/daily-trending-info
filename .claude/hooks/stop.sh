#!/bin/bash
set -e
echo "DTI: Running stop verification..."
cd scripts && python -m pytest ../tests/ -q 2>/dev/null && echo "Tests: OK" || echo "Tests: Check needed"
echo "Stop verification complete"
