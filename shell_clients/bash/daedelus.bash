#!/usr/bin/env bash
# Daedalus Bash Integration
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
# In bash, we use bind to set this
DAEDELUS_KEYBIND="${DAEDELUS_KEYBIND:-\\C-@}"  # Ctrl+Space

# Session ID (generated once per shell session)
DAEDELUS_SESSION_ID="${DAEDELUS_SESSION_ID:-bash-$$-$(date +%s)}"

# ============================================
# Internal State
# ============================================

# Command start time (for duration tracking)
DAEDELUS_CMD_START=""

# Current command being executed
DAEDELUS_CURRENT_CMD=""

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

# JSON escape function
daedelus_json_escape() {
    local str="$1"
    # Escape backslashes and quotes
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

# Pre-execution hook (using DEBUG trap)
daedelus_preexec() {
    # Get the command from BASH_COMMAND
    DAEDELUS_CURRENT_CMD="$BASH_COMMAND"
    DAEDELUS_CMD_START="$(date +%s.%N)"
}

# Post-execution hook (using PROMPT_COMMAND)
daedelus_precmd() {
    local exit_code=$?

    # Only log if we have a command
    if [[ -z "$DAEDELUS_CURRENT_CMD" ]]; then
        return
    fi

    # Skip internal commands
    if [[ "$DAEDELUS_CURRENT_CMD" == daedelus_* ]]; then
        DAEDELUS_CURRENT_CMD=""
        return
    fi

    # Calculate duration
    local cmd_end="$(date +%s.%N)"
    local duration
    if command -v bc >/dev/null 2>&1; then
        duration="$(echo "$cmd_end - $DAEDELUS_CMD_START" | bc)"
    else
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

    # Send to daemon asynchronously
    daedelus_send_message "$message" &>/dev/null &

    # Clear current command
    DAEDELUS_CURRENT_CMD=""
    DAEDELUS_CMD_START=""
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
    local history_json="["
    local first=1
    local count=0

    # Read history in reverse
    while IFS= read -r line; do
        if [[ -n "$line" ]] && [[ $count -lt 10 ]]; then
            if [[ $first -eq 0 ]]; then
                history_json+=","
            fi
            local line_escaped="$(daedelus_json_escape "$line")"
            history_json+="\"$line_escaped\""
            first=0
            ((count++))
        fi
    done < <(history 10 | sed 's/^[[:space:]]*[0-9]*[[:space:]]*//')

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
        # Basic JSON parsing
        echo "$response" | grep -o '"command"[[:space:]]*:[[:space:]]*"[^"]*"' | \
            sed 's/"command"[[:space:]]*:[[:space:]]*"\([^"]*\)"/\1/'
    fi
}

# ============================================
# Interactive Suggestion Function
# ============================================

daedelus_suggest() {
    # Don't suggest if daemon not running
    if ! daedelus_is_daemon_running; then
        echo "⚠️  Daedelus daemon not running" >&2
        return 1
    fi

    # Get current command line
    local buffer="$READLINE_LINE"

    # Skip empty buffers
    if [[ -z "$buffer" ]]; then
        return
    fi

    # Get suggestions
    local response="$(daedelus_get_suggestions "$buffer")"

    if [[ -z "$response" ]]; then
        echo "No suggestions available" >&2
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
        echo "No suggestions found" >&2
        return
    fi

    # Show suggestions
    echo
    echo "Suggestions from Daedelus:"
    local i=1
    for suggestion in "${suggestions[@]}"; do
        echo "  [$i] $suggestion"
        ((i++))
    done

    # If only one suggestion, use it
    if [[ ${#suggestions[@]} -eq 1 ]]; then
        READLINE_LINE="${suggestions[0]}"
        READLINE_POINT=${#READLINE_LINE}
    fi
}

# ============================================
# Keybinding Setup
# ============================================

# Bind Ctrl+Space to suggestion function
bind -x '"'"$DAEDELUS_KEYBIND"'": daedelus_suggest'

# ============================================
# Hook Registration
# ============================================

# Add DEBUG trap for pre-execution
trap 'daedelus_preexec' DEBUG

# Add to PROMPT_COMMAND for post-execution
if [[ -z "$PROMPT_COMMAND" ]]; then
    PROMPT_COMMAND="daedelus_precmd"
elif [[ "$PROMPT_COMMAND" != *daedelus_precmd* ]]; then
    PROMPT_COMMAND="daedelus_precmd;$PROMPT_COMMAND"
fi

# ============================================
# Initialization
# ============================================

daedelus_init() {
    # Check if daemon is running
    if ! daedelus_is_daemon_running; then
        echo "⚠️  Daedelus daemon not running"
        echo "Start it with: daedelus start"
        return 1
    fi

    # Send ping to verify communication
    local ping_response="$(daedelus_send_message '{"type":"ping","data":{}}')"

    if [[ -z "$ping_response" ]]; then
        echo "⚠️  Cannot communicate with Daedelus daemon"
        return 1
    fi

    echo "✅ Daedelus Bash integration loaded (session: ${DAEDELUS_SESSION_ID:0:16}...)"
    echo "   Press Ctrl+Space for suggestions"
}

# Run initialization
daedelus_init

# ============================================
# User Commands (optional convenience)
# ============================================

# Quick alias to check daemon status
alias dstatus='daedelus status'

# Quick alias to search history
alias dsearch='daedelus search'

# ============================================
# End of Daedelus Bash Integration
# ============================================
