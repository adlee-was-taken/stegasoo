/**
 * Stegasoo Authentication Pages JavaScript
 * Handles login, setup, account, and admin user management pages
 */

const StegasooAuth = {

    // ========================================================================
    // PASSWORD VISIBILITY TOGGLE
    // ========================================================================

    /**
     * Toggle password field visibility
     * @param {string} inputId - ID of the password input
     * @param {HTMLElement} btn - The toggle button element
     */
    togglePassword(inputId, btn) {
        const input = document.getElementById(inputId);
        const icon = btn.querySelector('i');
        if (!input) return;

        if (input.type === 'password') {
            input.type = 'text';
            icon?.classList.replace('bi-eye', 'bi-eye-slash');
        } else {
            input.type = 'password';
            icon?.classList.replace('bi-eye-slash', 'bi-eye');
        }
    },

    // ========================================================================
    // PASSWORD CONFIRMATION VALIDATION
    // ========================================================================

    /**
     * Initialize password confirmation validation on a form
     * @param {string} formId - ID of the form
     * @param {string} passwordId - ID of the password field
     * @param {string} confirmId - ID of the confirmation field
     */
    initPasswordConfirmation(formId, passwordId, confirmId) {
        const form = document.getElementById(formId);
        if (!form) return;

        form.addEventListener('submit', function(e) {
            const password = document.getElementById(passwordId)?.value;
            const confirm = document.getElementById(confirmId)?.value;

            if (password !== confirm) {
                e.preventDefault();
                alert('Passwords do not match');
            }
        });
    },

    // ========================================================================
    // COPY TO CLIPBOARD
    // ========================================================================

    /**
     * Copy field value to clipboard with visual feedback
     * @param {string} fieldId - ID of the input field to copy
     */
    copyField(fieldId) {
        const field = document.getElementById(fieldId);
        if (!field) return;

        field.select();
        navigator.clipboard.writeText(field.value).then(() => {
            const btn = field.nextElementSibling;
            if (!btn) return;

            const originalHTML = btn.innerHTML;
            btn.innerHTML = '<i class="bi bi-check"></i>';
            setTimeout(() => btn.innerHTML = originalHTML, 1000);
        });
    },

    // ========================================================================
    // PASSWORD GENERATION
    // ========================================================================

    /**
     * Generate a random password
     * @param {number} length - Password length (default 8)
     * @returns {string} Generated password
     */
    generatePassword(length = 8) {
        const chars = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789';
        let password = '';
        for (let i = 0; i < length; i++) {
            password += chars.charAt(Math.floor(Math.random() * chars.length));
        }
        return password;
    },

    /**
     * Regenerate password and update input field
     * @param {string} inputId - ID of the password input
     * @param {number} length - Password length
     */
    regeneratePassword(inputId = 'passwordInput', length = 8) {
        const input = document.getElementById(inputId);
        if (input) {
            input.value = this.generatePassword(length);
        }
    },

    // ========================================================================
    // DELETE CONFIRMATION
    // ========================================================================

    /**
     * Confirm deletion with a prompt
     * @param {string} itemName - Name of item being deleted
     * @param {string} formId - ID of the form to submit if confirmed
     * @returns {boolean} True if confirmed
     */
    confirmDelete(itemName, formId = null) {
        const confirmed = confirm(`Are you sure you want to delete "${itemName}"? This cannot be undone.`);
        if (confirmed && formId) {
            const form = document.getElementById(formId);
            form?.submit();
        }
        return confirmed;
    }
};

// Make togglePassword available globally for onclick handlers
function togglePassword(inputId, btn) {
    StegasooAuth.togglePassword(inputId, btn);
}

// Make copyField available globally for onclick handlers
function copyField(fieldId) {
    StegasooAuth.copyField(fieldId);
}

// Make regeneratePassword available globally for onclick handlers
function regeneratePassword() {
    StegasooAuth.regeneratePassword();
}
