# ============================================================================
# Stegasoo Pi - Bash Configuration
# ============================================================================

# If not running interactively, don't do anything
case $- in
    *i*) ;;
      *) return;;
esac

# ============================================================================
# History
# ============================================================================

HISTCONTROL=ignoreboth
HISTSIZE=5000
HISTFILESIZE=10000
shopt -s histappend

# ============================================================================
# Shell Options
# ============================================================================

shopt -s checkwinsize
shopt -s globstar 2>/dev/null
shopt -s cdspell 2>/dev/null

# ============================================================================
# Colors
# ============================================================================

# Color definitions
C_RESET='\[\e[0m\]'
C_GREY='\[\e[38;5;241m\]'
C_GREEN='\[\e[38;5;118m\]'
C_YELLOW='\[\e[38;5;179m\]'
C_BLUE='\[\e[38;5;69m\]'
C_RED='\[\e[38;5;196m\]'
C_BOLD='\[\e[1m\]'

# Enable color support
if [ -x /usr/bin/dircolors ]; then
    test -r ~/.dircolors && eval "$(dircolors -b ~/.dircolors)" || eval "$(dircolors -b)"
    alias ls='ls --color=auto'
    alias grep='grep --color=auto'
    alias fgrep='fgrep --color=auto'
    alias egrep='egrep --color=auto'
fi

# ============================================================================
# Prompt
# ============================================================================

# Git branch in prompt (if git installed)
_git_branch() {
    git branch 2>/dev/null | sed -e '/^[^*]/d' -e 's/* \(.*\)/ \xe2\x8e\x87 \1/'
}

# Two-line prompt similar to zsh theme
# ┌｢user@host｣ ｢path｣ ｢git｣
# └$
_build_prompt() {
    local git_info="$(_git_branch)"
    if [ -n "$git_info" ]; then
        git_info="${C_GREEN}${git_info}${C_GREY}"
    fi

    PS1="${C_GREY}┌｢${C_GREEN}\u@\h${C_GREY}｣ ｢${C_YELLOW}\w${C_GREY}${git_info}｣\n${C_GREY}└${C_BOLD}${C_BLUE}\$ ${C_RESET}"
}

PROMPT_COMMAND='_build_prompt'

# ============================================================================
# Navigation
# ============================================================================

alias ..='cd ..'
alias ...='cd ../..'
alias ....='cd ../../..'
alias ~='cd ~'

# ============================================================================
# Listing
# ============================================================================

alias ll='ls -lah'
alias la='ls -A'
alias l='ls -CF'
alias lt='ls -lahtr'

# ============================================================================
# Safety
# ============================================================================

alias rm='rm -i'
alias cp='cp -i'
alias mv='mv -i'

# ============================================================================
# Shortcuts
# ============================================================================

alias h='history'
alias c='clear'
alias q='exit'
alias reload='source ~/.bashrc'

# ============================================================================
# System
# ============================================================================

alias myip='curl -s ifconfig.me'
alias ports='netstat -tulanp 2>/dev/null || ss -tulanp'
alias df='df -h'
alias du='du -h'
alias free='free -h'
alias temp='vcgencmd measure_temp 2>/dev/null || sensors 2>/dev/null | grep -i temp || echo "No temp sensor"'

# ============================================================================
# Stegasoo
# ============================================================================

alias steg='stegasoo'
alias steglog='journalctl -u stegasoo -f'
alias stegstatus='systemctl status stegasoo'
alias stegrestart='sudo systemctl restart stegasoo'
alias stegstop='sudo systemctl stop stegasoo'
alias stegstart='sudo systemctl start stegasoo'

# Quick access to stegasoo directories
alias cdsteg='cd /opt/stegasoo'
alias cdweb='cd /opt/stegasoo/frontends/web'

# ============================================================================
# Git (if available)
# ============================================================================

alias g='git'
alias gs='git status'
alias ga='git add'
alias gc='git commit'
alias gp='git push'
alias gl='git pull'
alias gd='git diff'
alias gco='git checkout'
alias glog='git log --oneline --graph --decorate -10'

# ============================================================================
# Functions
# ============================================================================

# Create directory and cd into it
mkcd() { mkdir -p "$1" && cd "$1"; }

# Find files by name
ff() { find . -type f -iname "*$1*" 2>/dev/null; }

# Find directories by name
fdir() { find . -type d -iname "*$1*" 2>/dev/null; }

# Quick backup
backup() { cp "$1" "$1.backup-$(date +%Y%m%d-%H%M%S)"; }

# Extract archives
extract() {
    if [ ! -f "$1" ]; then
        echo "'$1' is not a valid file"
        return 1
    fi
    case "$1" in
        *.tar.bz2) tar xjf "$1" ;;
        *.tar.gz)  tar xzf "$1" ;;
        *.tar.xz)  tar xJf "$1" ;;
        *.bz2)     bunzip2 "$1" ;;
        *.gz)      gunzip "$1" ;;
        *.tar)     tar xf "$1" ;;
        *.tbz2)    tar xjf "$1" ;;
        *.tgz)     tar xzf "$1" ;;
        *.zip)     unzip "$1" ;;
        *.Z)       uncompress "$1" ;;
        *.7z)      7z x "$1" ;;
        *.zst)     zstd -d "$1" ;;
        *)         echo "'$1' cannot be extracted" ;;
    esac
}

# Show system info
sysinfo() {
    echo -e "\e[1;32mHostname:\e[0m $(hostname)"
    echo -e "\e[1;32mUptime:\e[0m $(uptime -p)"
    echo -e "\e[1;32mMemory:\e[0m $(free -h | awk '/^Mem:/ {print $3 "/" $2}')"
    echo -e "\e[1;32mDisk:\e[0m $(df -h / | awk 'NR==2 {print $3 "/" $2 " (" $5 ")"}')"
    echo -e "\e[1;32mTemp:\e[0m $(vcgencmd measure_temp 2>/dev/null | cut -d= -f2 || echo 'N/A')"
    echo -e "\e[1;32mIP:\e[0m $(hostname -I | awk '{print $1}')"
}

# ============================================================================
# Completion
# ============================================================================

if ! shopt -oq posix; then
    if [ -f /usr/share/bash-completion/bash_completion ]; then
        . /usr/share/bash-completion/bash_completion
    elif [ -f /etc/bash_completion ]; then
        . /etc/bash_completion
    fi
fi

# ============================================================================
# Path
# ============================================================================

export PATH="$HOME/.local/bin:$PATH"

