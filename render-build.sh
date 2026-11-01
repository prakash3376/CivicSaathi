#!/usr/bin/env bash
# Build script for Render native Python runtime
set -euo pipefail

echo "==> Building React frontend..."
cd frontend
npm ci
npm run build
cd ..

echo "==> Installing Python dependencies..."
cd backend
python -m pip install --upgrade pip
python -m pip install -r requirements.txt -c constraints.txt
cd ..

echo "==> Build complete!"
