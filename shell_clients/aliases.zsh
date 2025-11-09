#!/usr/bin/env zsh
# Daedelus Quick-Summon Aliases for ZSH
# Source this file in your .zshrc for convenient aliases
#
# Usage: source ~/.daedelus/aliases.zsh
# Or add to your .zshrc:
#   source $(python -c "import daedelus; print(daedelus.__file__.replace('__init__.py', '../shell_clients/aliases.zsh'))")

# Core aliases for quick access
alias d='daedelus'
alias dd='daedelus'
alias dstart='daedelus start'
alias dstop='daedelus stop'
alias drestart='daedelus restart'
alias dstatus='daedelus status'

# Interactive mode - most useful
alias di='daedelus i'
alias drepl='daedelus repl'

# Search and exploration
alias ds='daedelus search'
alias dh='daedelus history'
alias da='daedelus analytics'

# LLM features
alias dex='daedelus explain'
alias dgen='daedelus generate'
alias dask='daedelus ask'
alias dref='daedelus refine'

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

# ZSH-specific function for last command explanation
dlast() {
    local last_cmd=$(fc -ln -1 -1)
    daedelus explain "$last_cmd"
}

# Function for fuzzy search with immediate results
dsearch() {
    if [[ -z "$1" ]]; then
        echo "Usage: dsearch <query>"
        return 1
    fi
    daedelus search "$@"
}

# Function to auto-start daemon and enter interactive mode
dauto() {
    if ! daedelus status &>/dev/null; then
        daedelus start
    fi
    daedelus i
}

# Quick stats
dstats() {
    daedelus analytics "$@"
}

# ZSH completion function (basic)
_daedelus_completion() {
    local -a commands
    commands=(
        'start:Start the daemon'
        'stop:Stop the daemon'
        'restart:Restart the daemon'
        'status:Check daemon status'
        'i:Interactive REPL mode'
        'repl:Interactive REPL mode'
        'search:Fuzzy search history'
        'history:View command history'
        'explain:Explain a command'
        'generate:Generate command from description'
        'ask:Ask a question'
        'analytics:Show usage analytics'
        'tips:Show tips and tricks'
        'model:Manage LLM models'
        'config:Manage configuration'
    )

    _describe 'daedelus commands' commands
}

compdef _daedelus_completion daedelus d dd

# Echo alias setup confirmation
print -P "%F{cyan}✨ Daedelus ZSH aliases loaded!%f"
print -P "Try: %F{green}d i%f    (interactive mode)"
print -P "     %F{green}ds%f     (search history)"
print -P "     %F{green}dex%f    (explain command)"
print -P "     %F{green}dtips%f  (show all tips)"
