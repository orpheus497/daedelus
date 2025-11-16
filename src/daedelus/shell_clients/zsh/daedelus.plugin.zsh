#!/usr/bin/env zsh
# Daedalus ZSH Plugin
# Version: 0.1.0
# Created by: orpheus497
#
# Provides real-time command logging and intelligent suggestions
# for the Daedalus self-learning terminal assistant.

# ============================================
# Configuration
# ============================================

# Socket path for daemon communication
DAEDELUS_SOCKET="${DAEDELUS_SOCKET:-${HOME}/.local/share/daedelus/runtime/daemon.sock}"

# Keybinding for manual suggestions (default: Ctrl+Space)
DAEDELUS_KEYBIND="${DAEDELUS_KEYBIND:-^ }"

# Enable/disable auto-suggestions (default: 1 = enabled)
DAEDELUS_AUTO_SUGGEST="${DAEDELUS_AUTO_SUGGEST:-1}"

# Suggestion delay in milliseconds (default: 300ms)
DAEDELUS_SUGGEST_DELAY="${DAEDELUS_SUGGEST_DELAY:-300}"

# Session ID (generated once per shell session)
DAEDELUS_SESSION_ID="${DAEDELUS_SESSION_ID:-$(uuidgen 2>/dev/null || echo "zsh-$$-$(date +%s)")}"

# ============================================
# Color Configuration
# ============================================

# Suggestion text color (gray)
DAEDELUS_SUGGESTION_COLOR="${DAEDELUS_SUGGESTION_COLOR:-8}"

# Error color (red)
DAEDELUS_ERROR_COLOR="${DAEDELUS_ERROR_COLOR:-1}"

# ============================================
# Internal State
# ============================================

# Command start time (for duration tracking)
typeset -g DAEDELUS_CMD_START

# Current command being executed
typeset -g DAEDELUS_CURRENT_CMD

# Last suggestion shown
typeset -g DAEDELUS_LAST_SUGGESTION

# ============================================
# Utility Functions
# ============================================

# Check if daemon is running
daedelus_is_daemon_running() {
    [[ -S "$DAEDELUS_SOCKET" ]]
}

# Send JSON message to daemon via Unix socket
daedelus_send_message() {
    local message="$1"

    if ! daedelus_is_daemon_running; then
        return 1
    fi

    # Use nc (netcat) to send message to Unix socket
    # Timeout after 1 second to avoid hanging
    echo "$message" | timeout 1s nc -U "$DAEDELUS_SOCKET" 2>/dev/null
}

# URL-encode a string for JSON
daedelus_json_escape() {
    local str="$1"
    # Escape quotes and backslashes
    str="${str//\\/\\\\}"
    str="${str//\"/\\\"}"
    # Escape newlines and tabs
    str="${str//$'\n'/\\n}"
    str="${str//$'\t'/\\t}"
    echo "$str"
}

# ============================================
# Core Hooks
# ============================================

# Pre-execution hook (before command runs)
daedelus_preexec() {
    local cmd="$1"

    # Store command and start time
    DAEDELUS_CURRENT_CMD="$cmd"
    DAEDELUS_CMD_START="$(date +%s.%N)"
}

# Post-execution hook (after command completes)
daedelus_precmd() {
    local exit_code=$?

    # Only log if we have a command
    if [[ -z "$DAEDELUS_CURRENT_CMD" ]]; then
        return
    fi

    # Calculate duration
    local cmd_end="$(date +%s.%N)"
    local duration
    if command -v bc >/dev/null 2>&1; then
        duration="$(echo "$cmd_end - $DAEDELUS_CMD_START" | bc)"
    else
        # Fallback if bc not available
        duration="0.0"
    fi

    # Build JSON message
    local cwd_escaped="$(daedelus_json_escape "$PWD")"
    local cmd_escaped="$(daedelus_json_escape "$DAEDELUS_CURRENT_CMD")"
    local session_escaped="$(daedelus_json_escape "$DAEDELUS_SESSION_ID")"

    local message=$(cat <<EOF
{
    "type": "log_command",
    "data": {
        "command": "$cmd_escaped",
        "exit_code": $exit_code,
        "duration": $duration,
        "cwd": "$cwd_escaped",
        "session_id": "$session_escaped"
    }
}
EOF
)

    # Send to daemon asynchronously (don't block prompt)
    daedelus_send_message "$message" &>/dev/null &

    # Clear current command
    unset DAEDELUS_CURRENT_CMD
    unset DAEDELUS_CMD_START
}

# ============================================
# Suggestion Functions
# ============================================

# Get suggestions from daemon
daedelus_get_suggestions() {
    local partial="$1"
    local cwd_escaped="$(daedelus_json_escape "$PWD")"
    local partial_escaped="$(daedelus_json_escape "$partial")"

    # Get recent history (last 10 commands)
    local history_lines="$(fc -ln -10 | sed 's/^[[:space:]]*//' | grep -v '^$')"

    # Build history array for JSON
    local history_json="["
    local first=1
    while IFS= read -r line; do
        if [[ -n "$line" ]]; then
            if [[ $first -eq 0 ]]; then
                history_json+=","
            fi
            local line_escaped="$(daedelus_json_escape "$line")"
            history_json+="\"$line_escaped\""
            first=0
        fi
    done <<< "$history_lines"
    history_json+="]"

    # Build request message
    local message=$(cat <<EOF
{
    "type": "suggest",
    "data": {
        "partial": "$partial_escaped",
        "cwd": "$cwd_escaped",
        "history": $history_json
    }
}
EOF
)

    # Send request and get response
    daedelus_send_message "$message"
}

# Parse suggestions from JSON response
daedelus_parse_suggestions() {
    local response="$1"

    # Use jq if available, otherwise basic parsing
    if command -v jq >/dev/null 2>&1; then
        echo "$response" | jq -r '.suggestions[]? | .command' 2>/dev/null
    else
        # Basic JSON parsing (fragile but works for simple cases)
        echo "$response" | grep -o '"command"[[:space:]]*:[[:space:]]*"[^"]*"' | \
            sed 's/"command"[[:space:]]*:[[:space:]]*"\([^"]*\)"/\1/'
    fi
}

# ============================================
# Widget: Manual Suggestion
# ============================================

daedelus_suggest_widget() {
    # Don't suggest if daemon not running
    if ! daedelus_is_daemon_running; then
        zle -M "Daedelus daemon not running"
        return
    fi

    # Get current buffer
    local buffer="$BUFFER"
    local cursor="$CURSOR"

    # Skip empty buffers
    if [[ -z "$buffer" ]]; then
        return
    fi

    # Get suggestions
    local response="$(daedelus_get_suggestions "$buffer")"

    if [[ -z "$response" ]]; then
        zle -M "No suggestions available"
        return
    fi

    # Parse suggestions
    local suggestions=()
    while IFS= read -r suggestion; do
        if [[ -n "$suggestion" ]]; then
            suggestions+=("$suggestion")
        fi
    done < <(daedelus_parse_suggestions "$response")

    if [[ ${#suggestions[@]} -eq 0 ]]; then
        zle -M "No suggestions found"
        return
    fi

    # Show suggestions in a menu
    echo
    echo "Suggestions from Daedelus:"
    local i=1
    for suggestion in "${suggestions[@]}"; do
        echo "  [$i] $suggestion"
        ((i++))
    done

    # Use first suggestion by default or let user choose
    if [[ ${#suggestions[@]} -eq 1 ]]; then
        BUFFER="${suggestions[1]}"
        CURSOR=${#BUFFER}
    else
        # For multiple suggestions, just show them
        # User can manually type or we could implement selection
        zle -M "Tip: Type the number or continue typing"
    fi

    zle reset-prompt
}

# ============================================
# Widget: Auto-Suggestion (Inline)
# ============================================

daedelus_auto_suggest_widget() {
    # Skip if auto-suggest disabled
    if [[ "$DAEDELUS_AUTO_SUGGEST" -ne 1 ]]; then
        return
    fi

    # Skip if daemon not running
    if ! daedelus_is_daemon_running; then
        return
    fi

    # Get current buffer
    local buffer="$BUFFER"

    # Skip short buffers (< 3 chars)
    if [[ ${#buffer} -lt 3 ]]; then
        return
    fi

    # Get first suggestion
    local response="$(daedelus_get_suggestions "$buffer")"

    if [[ -z "$response" ]]; then
        return
    fi

    # Parse first suggestion
    local suggestion="$(daedelus_parse_suggestions "$response" | head -1)"

    if [[ -z "$suggestion" ]] || [[ "$suggestion" == "$buffer" ]]; then
        return
    fi

    # Store suggestion for accept widget
    DAEDELUS_LAST_SUGGESTION="$suggestion"

    # Show suggestion as gray text (similar to fish shell)
    # This is a simplified version - a full implementation would use
    # ZLE's region_highlight for inline display
    zle -M "$(echo -e "\033[${DAEDELUS_SUGGESTION_COLOR}m→ $suggestion\033[0m")"
}

# ============================================
# Widget: Accept Suggestion
# ============================================

daedelus_accept_suggestion() {
    if [[ -n "$DAEDELUS_LAST_SUGGESTION" ]]; then
        BUFFER="$DAEDELUS_LAST_SUGGESTION"
        CURSOR=${#BUFFER}
        unset DAEDELUS_LAST_SUGGESTION
        zle reset-prompt
    fi
}

# ============================================
# Widget Registration
# ============================================

# Register custom widgets
zle -N daedelus-suggest daedelus_suggest_widget
zle -N daedelus-auto-suggest daedelus_auto_suggest_widget
zle -N daedelus-accept-suggestion daedelus_accept_suggestion

# Bind to keybindings
bindkey "$DAEDELUS_KEYBIND" daedelus-suggest        # Ctrl+Space for manual suggestions
bindkey '^[^M' daedelus-accept-suggestion           # Alt+Enter to accept suggestion

# ============================================
# Hook Registration
# ============================================

# Add pre-execution hook
autoload -U add-zsh-hook
add-zsh-hook preexec daedelus_preexec
add-zsh-hook precmd daedelus_precmd

# ============================================
# Initialization
# ============================================

daedelus_init() {
    # Check if daemon is running
    if ! daedelus_is_daemon_running; then
        echo "⚠️  Daedelus daemon not running"
        echo "Start it with: daedelus start (or: deus start)"
        return 1
    fi

    # Send ping to verify communication
    local ping_response="$(daedelus_send_message '{"type":"ping","data":{}}')"

    if [[ -z "$ping_response" ]]; then
        echo "⚠️  Cannot communicate with Daedelus daemon"
        return 1
    fi

    echo "✅ Daedelus ZSH plugin loaded (session: ${DAEDELUS_SESSION_ID:0:8}...)"
    echo "   Keybindings:"
    echo "     Ctrl+Space  - Get suggestions"
    echo "     Alt+Enter   - Accept suggestion"
}

# Run initialization
daedelus_init

# ============================================
# Cleanup on Shell Exit
# ============================================

daedelus_cleanup() {
    # Could send session end notification here if needed
    true
}

# Register cleanup hook
add-zsh-hook zshexit daedelus_cleanup

# ============================================
# User Commands (optional convenience)
# ============================================

# Quick alias to check daemon status
alias dstatus='daedelus status'

# Quick alias to search history
alias dsearch='daedelus search'

# Quick alias for REPL
alias di='daedelus repl'

# ============================================
# End of Daedelus ZSH Plugin
# ============================================
