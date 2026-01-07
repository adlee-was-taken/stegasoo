#!/bin/bash
# Stegasoo Banner/Header Template
# Source this file to use the banner functions
#
# Usage:
#   source "$(dirname "${BASH_SOURCE[0]}")/banner.sh"
#   print_banner "Raspberry Pi Setup"
#   print_gradient_line

# Colors
STEGASOO_GOLD='\033[38;5;220m'
STEGASOO_GRAY='\033[0;90m'
STEGASOO_WHITE='\033[1;37m'
STEGASOO_GREEN='\033[0;32m'
STEGASOO_NC='\033[0m'

# Gradient line (purple -> blue)
print_gradient_line() {
    echo -e "\033[38;5;93m══════════════\033[38;5;99m══════════════\033[38;5;105m══════════════\033[38;5;117m══════════════\033[0m"
}

# Starfield decoration line
print_starfield() {
    echo -e "${STEGASOO_GRAY} · .  · .  *  · .  *  · .  *  · .  *  · .  *  · .  ·${STEGASOO_NC}"
}

# ASCII logo (gold)
print_logo() {
    echo -e "${STEGASOO_GOLD}    ___  _____  ___    ___    _    ___    ___    ___${STEGASOO_NC}"
    echo -e "${STEGASOO_GOLD}   / __||_   _|| __|  / __|  /_\\  / __|  / _ \\  / _ \\\\${STEGASOO_NC}"
    echo -e "${STEGASOO_GOLD}   \\__ \\  | |  | _|  | (_ | / _ \\ \\__ \\ | (_) || (_) |${STEGASOO_NC}"
    echo -e "${STEGASOO_GOLD}   |___/  |_|  |___|  \\___//_/ \\_\\|___/  \\___/  \\___/${STEGASOO_NC}"
}

# Full banner with optional subtitle
# Usage: print_banner "Subtitle Text"
print_banner() {
    local subtitle="$1"
    echo ""
    print_gradient_line
    print_starfield
    print_logo
    print_starfield
    print_gradient_line
    if [ -n "$subtitle" ]; then
        echo -e "${STEGASOO_WHITE}                    ${subtitle}${STEGASOO_NC}"
        print_gradient_line
    fi
}

# Completion banner (green title)
# Usage: print_complete_banner "Setup Complete!"
print_complete_banner() {
    local title="$1"
    echo ""
    print_gradient_line
    print_starfield
    print_logo
    print_starfield
    print_gradient_line
    echo -e "\033[1;32m                      ${title}\033[0m"
    print_gradient_line
}
