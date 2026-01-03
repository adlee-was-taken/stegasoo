#!/bin/bash
# Stegasoo First Boot Wizard Trigger
# This file goes in /etc/profile.d/ and runs the wizard on first login

if [ -f /etc/stegasoo-first-boot ] && [ -f /home/*/stegasoo/rpi/first-boot-wizard.sh ]; then
    # Find the wizard script
    WIZARD=$(ls /home/*/stegasoo/rpi/first-boot-wizard.sh 2>/dev/null | head -1)
    if [ -n "$WIZARD" ]; then
        bash "$WIZARD"
    fi
fi
