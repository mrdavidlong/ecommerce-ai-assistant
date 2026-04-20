#!/bin/bash

# run-checks.sh — Run all linting and tests for the ecommerce AI assistant
# Usage: ./run-checks.sh [--lint] [--test] [--all]
# Defaults to --all if no args provided

set -e  # exit on first error

# Check for required tools
for cmd in uv npm python3; do
  if ! command -v "$cmd" &> /dev/null; then
    echo "❌ Error: Required command '$cmd' not found in PATH"
    echo "   Please install $cmd and try again"
    exit 1
  fi
done

LINT=false
TEST=false

# If no args, default to all
if [ $# -eq 0 ]; then
  LINT=true
  TEST=true
fi

# Parse arguments
for arg in "$@"; do
  case $arg in
    --lint)
      LINT=true
      ;;
    --test)
      TEST=true
      ;;
    --all)
      LINT=true
      TEST=true
      ;;
    *)
      echo "Unknown argument: $arg"
      echo "Usage: $0 [--lint] [--test] [--all]"
      exit 1
      ;;
  esac
done

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ "$LINT" = true ]; then
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo "🔍 Backend Linting (Python)"
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  cd "$PROJECT_ROOT/backend"
  uv run ruff check . --fix
  uv run ruff format .
  echo "✅ Backend linting done"
  echo ""

  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo "🔍 Frontend Linting (TypeScript + JavaScript)"
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  cd "$PROJECT_ROOT/frontend"
  npm run check
  echo "✅ Frontend linting done"
  echo ""
fi

if [ "$TEST" = true ]; then
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo "🧪 Backend Tests (Python)"
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  cd "$PROJECT_ROOT/backend"
  uv run pytest tests/ -v
  echo "✅ All tests passed"
  echo ""
fi

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🎉 All checks passed!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
