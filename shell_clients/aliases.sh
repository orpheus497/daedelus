#!/usr/bin/env bash
# Daedelus Quick-Summon Aliases
# Source this file in your shell RC for convenient aliases
#
# Usage: source ~/.daedelus/aliases.sh
# Or add to your .bashrc/.zshrc:
#   source $(python -c "import daedelus; print(daedelus.__file__.replace('__init__.py', '../shell_clients/aliases.sh'))")

# Core aliases for quick access
alias d='daedelus'           # Main shortcut
alias dd='daedelus'          # Alternative
alias dstart='daedelus start'
alias dstop='daedelus stop'
alias drestart='daedelus restart'
alias dstatus='daedelus status'

# Interactive mode - most useful
alias di='daedelus i'        # Interactive REPL
alias drepl='daedelus repl'  # Full name

# Search and exploration
alias ds='daedelus search'   # Fuzzy search
alias dh='daedelus history'  # View history
alias da='daedelus analytics' # Analytics

# LLM features
alias dex='daedelus explain'  # Explain command
alias dgen='daedelus generate' # Generate command
alias dask='daedelus ask'     # Ask question
alias dref='daedelus refine'  # Refine command

# Model management
alias dmodel='daedelus model'
alias dmdownload='daedelus model download'
alias dminit='daedelus model init'
alias dmstatus='daedelus model status'

# Help and tips
alias dtips='daedelus tips'
alias dhelp='daedelus --help'

# Configuration
alias dconfig='daedelus config'

# Function for quick explanation of last command
dlast() {
    local last_cmd=$(fc -ln -1)
    daedelus explain "$last_cmd"
}

# Function for fuzzy search with immediate results
dsearch() {
    if [ -z "$1" ]; then
        echo "Usage: dsearch <query>"
        return 1
    fi
    daedelus search "$@"
}

# Function to start interactive mode if daemon not running
dauto() {
    if ! daedelus status >/dev/null 2>&1; then
        daedelus start
    fi
    daedelus i
}

# Quick stats
dstats() {
    daedelus analytics "$@"
}

# Echo alias setup confirmation
echo "✨ Daedelus aliases loaded!"
echo "Try: d i    (interactive mode)"
echo "     ds     (search history)"
echo "     dex    (explain command)"
echo "     dtips  (show all tips)"
