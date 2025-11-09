#!/bin/bash
# GitHub Upload Script for Daedalus
# Run this to initialize git and push to GitHub

set -e

echo "=========================================="
echo "Daedalus - GitHub Upload Script"
echo "=========================================="
echo ""

# Check if git is installed
if ! command -v git &> /dev/null; then
    echo "❌ Error: git is not installed"
    exit 1
fi

# Check if already a git repo
if [ -d .git ]; then
    echo "✅ Git repository already initialized"
else
    echo "Initializing git repository..."
    git init
    echo "✅ Git repository initialized"
fi

# Add all files
echo ""
echo "Adding files to git..."
git add .

# Show status
echo ""
echo "Git status:"
git status --short

# Create initial commit
echo ""
read -p "Create initial commit? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    git commit -m "Initial commit - Daedalus v0.1.0

Privacy-first terminal assistant with local AI model.

Features:
- 100% local processing (no cloud, no telemetry)
- FastText embeddings + Annoy vector search
- 3-tier suggestion engine
- SQLite command history with FTS5
- Privacy filtering for sensitive commands
- Shell integration for ZSH, Bash, Fish
- Performance: <50MB RAM, <50ms latency

Phase 1 (current): Embedding-based system
Phase 2 (Q2 2025): LLM enhancement with llama.cpp

License: MIT"
    echo "✅ Initial commit created"
fi

# Prompt for GitHub remote
echo ""
echo "=========================================="
echo "GitHub Repository Setup"
echo "=========================================="
echo ""
echo "Before continuing:"
echo "1. Create a new repository on GitHub: https://github.com/new"
echo "2. Name it: daedelus"
echo "3. Make it PUBLIC"
echo "4. Do NOT initialize with README, .gitignore, or license"
echo ""
read -p "Have you created the GitHub repository? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Create the repository first, then run this script again."
    exit 0
fi

# Get GitHub username
echo ""
read -p "Enter your GitHub username [orpheus497]: " username
username=${username:-orpheus497}

# Add remote
echo ""
echo "Adding GitHub remote..."
git remote add origin "https://github.com/$username/daedelus.git" 2>/dev/null || \
    git remote set-url origin "https://github.com/$username/daedelus.git"
echo "✅ Remote added: https://github.com/$username/daedelus.git"

# Push to GitHub
echo ""
read -p "Push to GitHub? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Pushing to GitHub..."
    git branch -M main
    git push -u origin main
    echo ""
    echo "=========================================="
    echo "✅ SUCCESS!"
    echo "=========================================="
    echo ""
    echo "Your repository is now live at:"
    echo "https://github.com/$username/daedelus"
    echo ""
    echo "Next steps:"
    echo "1. Add repository description and topics on GitHub"
    echo "2. Enable Discussions and Issues"
    echo "3. Create v0.1.0 release"
    echo "4. Share your project!"
fi

echo ""
echo "Done!"
