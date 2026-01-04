#!/bin/bash
# Stegasoo First Boot Wizard Trigger
# This file goes in /etc/profile.d/ and runs the wizard on first login

if [ -f /etc/stegasoo-first-boot ]; then
    # Find the wizard script (check /opt first, then home dirs)
    WIZARD=""
    if [ -f /opt/stegasoo/rpi/first-boot-wizard.sh ]; then
        WIZARD="/opt/stegasoo/rpi/first-boot-wizard.sh"
    else
        WIZARD=$(ls /home/*/stegasoo/rpi/first-boot-wizard.sh 2>/dev/null | head -1)
    fi

    if [ -n "$WIZARD" ]; then
        bash "$WIZARD"
    fi
fi
