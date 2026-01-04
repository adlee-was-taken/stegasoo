/**
 * Stegasoo Generate Page JavaScript
 * Handles credential generation form and display
 */

const StegasooGenerate = {

    // ========================================================================
    // FORM CONTROLS
    // ========================================================================

    /**
     * Initialize the words range slider
     */
    initWordsSlider() {
        const wordsRange = document.getElementById('wordsRange');
        const wordsValue = document.getElementById('wordsValue');

        wordsRange?.addEventListener('input', function() {
            const bits = this.value * 11;
            wordsValue.textContent = `${this.value} words (~${bits} bits)`;
        });
    },

    /**
     * Initialize PIN/RSA option toggles
     */
    initOptionToggles() {
        const usePinCheck = document.getElementById('usePinCheck');
        const useRsaCheck = document.getElementById('useRsaCheck');
        const pinOptions = document.getElementById('pinOptions');
        const rsaOptions = document.getElementById('rsaOptions');
        const rsaQrWarning = document.getElementById('rsaQrWarning');
        const rsaBitsSelect = document.getElementById('rsaBitsSelect');

        usePinCheck?.addEventListener('change', function() {
            pinOptions?.classList.toggle('d-none', !this.checked);
        });

        useRsaCheck?.addEventListener('change', function() {
            rsaOptions?.classList.toggle('d-none', !this.checked);
        });

        // RSA key size QR warning (>3072 bits)
        rsaBitsSelect?.addEventListener('change', function() {
            rsaQrWarning?.classList.toggle('d-none', parseInt(this.value) <= 3072);
        });
    },

    // ========================================================================
    // CREDENTIAL VISIBILITY
    // ========================================================================

    pinHidden: false,
    passphraseHidden: false,

    /**
     * Toggle PIN visibility
     */
    togglePinVisibility() {
        const pinDigits = document.getElementById('pinDigits');
        const icon = document.getElementById('pinToggleIcon');
        const text = document.getElementById('pinToggleText');

        this.pinHidden = !this.pinHidden;
        pinDigits?.classList.toggle('blurred', this.pinHidden);

        if (icon) icon.className = this.pinHidden ? 'bi bi-eye' : 'bi bi-eye-slash';
        if (text) text.textContent = this.pinHidden ? 'Show' : 'Hide';
    },

    /**
     * Toggle passphrase visibility
     */
    togglePassphraseVisibility() {
        const display = document.getElementById('passphraseDisplay');
        const icon = document.getElementById('passphraseToggleIcon');
        const text = document.getElementById('passphraseToggleText');

        this.passphraseHidden = !this.passphraseHidden;
        display?.classList.toggle('blurred', this.passphraseHidden);

        if (icon) icon.className = this.passphraseHidden ? 'bi bi-eye' : 'bi bi-eye-slash';
        if (text) text.textContent = this.passphraseHidden ? 'Show' : 'Hide';
    },

    // ========================================================================
    // MEMORY AID STORY GENERATION
    // ========================================================================

    currentStoryTemplate: 0,

    /**
     * Story templates organized by word count (3-12 words supported)
     */
    storyTemplates: {
        3: [
            w => `The ${w[0]} ${w[1]} ${w[2]}.`,
            w => `${w[0]} loves ${w[1]} and ${w[2]}.`,
            w => `A ${w[0]} found a ${w[1]} near the ${w[2]}.`,
            w => `${w[0]}, ${w[1]}, ${w[2]} — never forget.`,
            w => `The ${w[0]} hid the ${w[1]} under the ${w[2]}.`,
        ],
        4: [
            w => `${w[0]} and ${w[1]} discovered a ${w[2]} made of ${w[3]}.`,
            w => `The ${w[0]} ${w[1]} ate ${w[2]} for ${w[3]}.`,
            w => `In the ${w[0]}, a ${w[1]} met a ${w[2]} carrying ${w[3]}.`,
            w => `${w[0]} said "${w[1]}" while holding a ${w[2]} ${w[3]}.`,
            w => `The secret: ${w[0]}, ${w[1]}, ${w[2]}, ${w[3]}.`,
        ],
        5: [
            w => `${w[0]} traveled to ${w[1]} seeking the ${w[2]} of ${w[3]} and ${w[4]}.`,
            w => `The ${w[0]} ${w[1]} lived in a ${w[2]} house with ${w[3]} ${w[4]}.`,
            w => `"${w[0]}!" shouted ${w[1]} as the ${w[2]} ${w[3]} flew toward ${w[4]}.`,
            w => `Captain ${w[0]} sailed the ${w[1]} ${w[2]} searching for ${w[3]} ${w[4]}.`,
            w => `In ${w[0]} kingdom, ${w[1]} guards protected the ${w[2]} ${w[3]} ${w[4]}.`,
        ],
        6: [
            w => `${w[0]} met ${w[1]} at the ${w[2]}. Together they found ${w[3]}, ${w[4]}, and ${w[5]}.`,
            w => `The ${w[0]} ${w[1]} wore a ${w[2]} hat while eating ${w[3]} ${w[4]} ${w[5]}.`,
            w => `Detective ${w[0]} found ${w[1]} ${w[2]} near the ${w[3]} ${w[4]} ${w[5]}.`,
            w => `In the ${w[0]} ${w[1]}, a ${w[2]} ${w[3]} sang about ${w[4]} ${w[5]}.`,
            w => `Chef ${w[0]} combined ${w[1]}, ${w[2]}, ${w[3]}, ${w[4]}, and ${w[5]}.`,
        ],
        7: [
            w => `${w[0]} and ${w[1]} walked through the ${w[2]} ${w[3]} to find the ${w[4]} ${w[5]} ${w[6]}.`,
            w => `The ${w[0]} professor studied ${w[1]} ${w[2]} while drinking ${w[3]} ${w[4]} with ${w[5]} ${w[6]}.`,
            w => `"${w[0]} ${w[1]}!" yelled ${w[2]} as ${w[3]} ${w[4]} attacked the ${w[5]} ${w[6]}.`,
            w => `In ${w[0]}, King ${w[1]} decreed that ${w[2]} ${w[3]} must honor ${w[4]} ${w[5]} ${w[6]}.`,
        ],
        8: [
            w => `${w[0]} ${w[1]} and ${w[2]} ${w[3]} met at the ${w[4]} ${w[5]} to discuss ${w[6]} ${w[7]}.`,
            w => `The ${w[0]} ${w[1]} ${w[2]} traveled from ${w[3]} to ${w[4]} carrying ${w[5]} ${w[6]} ${w[7]}.`,
            w => `${w[0]} discovered that ${w[1]} ${w[2]} plus ${w[3]} ${w[4]} equals ${w[5]} ${w[6]} ${w[7]}.`,
        ],
        9: [
            w => `${w[0]} ${w[1]} ${w[2]} watched as ${w[3]} ${w[4]} ${w[5]} danced with ${w[6]} ${w[7]} ${w[8]}.`,
            w => `In the ${w[0]} ${w[1]} ${w[2]}, three friends — ${w[3]}, ${w[4]}, ${w[5]} — found ${w[6]} ${w[7]} ${w[8]}.`,
            w => `The recipe: ${w[0]}, ${w[1]}, ${w[2]}, ${w[3]}, ${w[4]}, ${w[5]}, ${w[6]}, ${w[7]}, ${w[8]}.`,
        ],
        10: [
            w => `${w[0]} ${w[1]} told ${w[2]} ${w[3]} about the ${w[4]} ${w[5]} ${w[6]} hidden in ${w[7]} ${w[8]} ${w[9]}.`,
            w => `The ${w[0]} ${w[1]} ${w[2]} ${w[3]} ${w[4]} lived beside ${w[5]} ${w[6]} ${w[7]} ${w[8]} ${w[9]}.`,
        ],
        11: [
            w => `${w[0]} ${w[1]} ${w[2]} and ${w[3]} ${w[4]} ${w[5]} discovered ${w[6]} ${w[7]} ${w[8]} ${w[9]} ${w[10]}.`,
            w => `In ${w[0]} ${w[1]}, the ${w[2]} ${w[3]} ${w[4]} sang of ${w[5]} ${w[6]} ${w[7]} ${w[8]} ${w[9]} ${w[10]}.`,
        ],
        12: [
            w => `${w[0]} ${w[1]} ${w[2]} met ${w[3]} ${w[4]} ${w[5]} at the ${w[6]} ${w[7]} ${w[8]} ${w[9]} ${w[10]} ${w[11]}.`,
            w => `The twelve treasures: ${w[0]}, ${w[1]}, ${w[2]}, ${w[3]}, ${w[4]}, ${w[5]}, ${w[6]}, ${w[7]}, ${w[8]}, ${w[9]}, ${w[10]}, ${w[11]}.`,
        ],
    },

    /**
     * Wrap word in highlight span
     */
    hl(word) {
        return `<span class="passphrase-word">${word}</span>`;
    },

    /**
     * Generate a memory story for given words
     * @param {string[]} words - Array of passphrase words
     * @param {number|null} idx - Template index (null for current)
     * @returns {string} HTML story
     */
    generateStory(words, idx = null) {
        const count = words.length;
        if (count === 0) return '';

        // Clamp to supported range (3-12)
        const templateKey = Math.max(3, Math.min(12, count));
        const templates = this.storyTemplates[templateKey];

        if (!templates || templates.length === 0) {
            // Fallback: just list the words
            return words.map(w => this.hl(w)).join(' &mdash; ');
        }

        const templateIdx = (idx ?? this.currentStoryTemplate) % templates.length;
        // Apply highlighting to words
        const highlighted = words.map(w => this.hl(w));
        return templates[templateIdx](highlighted);
    },

    /**
     * Toggle memory aid visibility
     * @param {string[]} words - Passphrase words array
     */
    toggleMemoryAid(words) {
        const container = document.getElementById('memoryAidContainer');
        const icon = document.getElementById('memoryAidIcon');
        const text = document.getElementById('memoryAidText');

        const isHidden = container?.classList.contains('d-none');
        container?.classList.toggle('d-none', !isHidden);

        if (icon) icon.className = isHidden ? 'bi bi-lightbulb-fill' : 'bi bi-lightbulb';
        if (text) text.textContent = isHidden ? 'Hide Aid' : 'Memory Aid';

        if (isHidden) {
            document.getElementById('memoryStory').innerHTML = this.generateStory(words);
        }
    },

    /**
     * Regenerate story with next template
     * @param {string[]} words - Passphrase words array
     */
    regenerateStory(words) {
        const count = words.length;
        const templateKey = Math.max(3, Math.min(12, count));
        const templates = this.storyTemplates[templateKey] || [];
        this.currentStoryTemplate = (this.currentStoryTemplate + 1) % Math.max(1, templates.length);
        document.getElementById('memoryStory').innerHTML = this.generateStory(words, this.currentStoryTemplate);
    },

    // ========================================================================
    // QR CODE PRINTING
    // ========================================================================

    /**
     * Print QR code in new window
     */
    printQrCode() {
        const qrImg = document.getElementById('qrCodeImage');
        if (!qrImg) return;

        const printWindow = window.open('', '_blank');
        printWindow.document.write(`<!DOCTYPE html>
<html>
<head>
    <title>Stegasoo RSA Key QR Code</title>
    <style>
        body { display: flex; flex-direction: column; align-items: center; justify-content: center; min-height: 100vh; margin: 0; font-family: sans-serif; }
        img { max-width: 400px; }
        .warning { margin-top: 20px; padding: 10px; border: 2px solid #ff9800; background: #fff3e0; max-width: 400px; text-align: center; font-size: 12px; }
    </style>
</head>
<body>
    <h2>Stegasoo RSA Private Key</h2>
    <img src="${qrImg.src}" alt="RSA Key QR Code">
    <div class="warning">
        <strong>Warning:</strong> This QR code contains your unencrypted RSA private key.
        Store securely and destroy after use.
    </div>
    <script>window.onload = function() { window.print(); }<\/script>
</body>
</html>`);
        printWindow.document.close();
    },

    // ========================================================================
    // INITIALIZATION
    // ========================================================================

    /**
     * Initialize generate form page
     */
    initForm() {
        this.initWordsSlider();
        this.initOptionToggles();
    }
};

// Global function wrappers for onclick handlers
function togglePinVisibility() {
    StegasooGenerate.togglePinVisibility();
}

function togglePassphraseVisibility() {
    StegasooGenerate.togglePassphraseVisibility();
}

function printQrCode() {
    StegasooGenerate.printQrCode();
}

// Auto-init form controls
document.addEventListener('DOMContentLoaded', () => {
    if (document.querySelector('[data-page="generate"]')) {
        StegasooGenerate.initForm();
    }
});
