#!/usr/bin/env bash
# Install global git pre-push adversarial review hook
set -euo pipefail

HOOKS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Installing pre-push adversarial review hook..."

# Ensure structure
mkdir -p "$HOOKS_DIR/lib" "$HOOKS_DIR/prompts" "$HOOKS_DIR/reports"

# Make pre-push executable
chmod +x "$HOOKS_DIR/pre-push"
chmod +x "$HOOKS_DIR/pre-push.py"

# Configure git to use this hooks directory globally
git config --global core.hooksPath "$HOOKS_DIR"
echo "  ✓ git config --global core.hooksPath $HOOKS_DIR"

# Check dependencies
MISSING=()
command -v python3 &>/dev/null || MISSING+=("python3")
command -v codex &>/dev/null || MISSING+=("codex (optional: code review)")
command -v claude &>/dev/null || MISSING+=("claude (optional: red-team fallback)")

if [[ ${#MISSING[@]} -gt 0 ]]; then
    echo ""
    echo "  ⚠ Missing optional dependencies: ${MISSING[*]}"
    echo "    Install them for full functionality."
else
    echo "  ✓ All dependencies found"
fi

echo ""
echo "Done. Every git push will now run adversarial review."
echo "To skip: SKIP_REVIEW=1 git push"
echo "Reports: $HOOKS_DIR/reports/"
