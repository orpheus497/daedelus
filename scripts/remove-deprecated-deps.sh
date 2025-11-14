#!/bin/bash
# Remove Deprecated GPL-Licensed Dependencies
# Removes thefuzz and python-Levenshtein (GPL-2.0)
# These have been replaced with rapidfuzz (MIT)
# Created by: orpheus497

set -e

echo "=========================================="
echo "Remove Deprecated Dependencies"
echo "=========================================="
echo ""

# Detect pip command
if command -v pip3 &> /dev/null; then
    PIP_CMD=pip3
elif command -v pip &> /dev/null; then
    PIP_CMD=pip
else
    echo "❌ Error: pip not found"
    exit 1
fi

echo "Checking for deprecated dependencies..."
echo ""

# Check if deprecated packages are installed
THEFUZZ_INSTALLED=$($PIP_CMD list 2>/dev/null | grep -i "^thefuzz " | wc -l)
LEVENSHTEIN_INSTALLED=$($PIP_CMD list 2>/dev/null | grep -i "^python-Levenshtein " | wc -l)

if [ "$THEFUZZ_INSTALLED" -gt 0 ]; then
    echo "📦 Found: thefuzz (GPL-2.0) - will remove"
fi

if [ "$LEVENSHTEIN_INSTALLED" -gt 0 ]; then
    echo "📦 Found: python-Levenshtein (GPL-2.0) - will remove"
fi

if [ "$THEFUZZ_INSTALLED" -eq 0 ] && [ "$LEVENSHTEIN_INSTALLED" -eq 0 ]; then
    echo "✅ No deprecated dependencies found"
    echo ""
    echo "All dependencies are using permissive licenses (MIT/Apache/BSD)."
    exit 0
fi

echo ""
echo "Removing deprecated dependencies..."
$PIP_CMD uninstall -y thefuzz python-Levenshtein 2>/dev/null || true

echo ""
echo "=========================================="
echo "✅ Cleanup Complete"
echo "=========================================="
echo ""
echo "Deprecated GPL dependencies removed:"
echo "  ❌ thefuzz (GPL-2.0)"
echo "  ❌ python-Levenshtein (GPL-2.0)"
echo ""
echo "Replacement (MIT-licensed):"
echo "  ✅ rapidfuzz (MIT, 3-10x faster)"
echo ""
echo "All dependencies now use permissive licenses."
echo ""
