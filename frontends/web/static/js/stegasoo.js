/**
 * Stegasoo Frontend JavaScript
 * Shared functionality across encode, decode, and generate pages
 */

const Stegasoo = {
    
    // ========================================================================
    // PASSWORD/PIN VISIBILITY TOGGLES
    // ========================================================================
    
    initPasswordToggles() {
        document.querySelectorAll('[data-toggle-password]').forEach(btn => {
            btn.addEventListener('click', function() {
                const targetId = this.dataset.togglePassword;
                const input = document.getElementById(targetId);
                const icon = this.querySelector('i');
                
                if (!input) return;
                
                if (input.type === 'password') {
                    input.type = 'text';
                    icon?.classList.replace('bi-eye', 'bi-eye-slash');
                } else {
                    input.type = 'password';
                    icon?.classList.replace('bi-eye-slash', 'bi-eye');
                }
            });
        });
    },
    
    // ========================================================================
    // RSA INPUT METHOD TOGGLE (File vs QR)
    // ========================================================================
    
    initRsaMethodToggle() {
        const fileRadio = document.getElementById('rsaMethodFile');
        const qrRadio = document.getElementById('rsaMethodQr');
        const fileSection = document.getElementById('rsaFileSection');
        const qrSection = document.getElementById('rsaQrSection');
        
        if (!fileRadio || !qrRadio || !fileSection || !qrSection) return;
        
        const update = () => {
            const isFile = fileRadio.checked;
            fileSection.classList.toggle('d-none', !isFile);
            qrSection.classList.toggle('d-none', isFile);
        };
        
        fileRadio.addEventListener('change', update);
        qrRadio.addEventListener('change', update);
    },
    
    // ========================================================================
    // DROP ZONES (Drag & Drop + Preview)
    // ========================================================================
    
    initDropZones(options = {}) {
        document.querySelectorAll('.drop-zone').forEach(zone => {
            const input = zone.querySelector('input[type="file"]');
            const label = zone.querySelector('.drop-zone-label');
            const preview = zone.querySelector('.drop-zone-preview');
            
            if (!input) return;
            
            // Check if this is a special zone type
            const isPayloadZone = zone.id === 'payloadDropZone';
            const isCarrierZone = zone.id === 'carrierDropZone';
            const isQrZone = zone.id === 'qrDropZone';
            
            // Drag events
            ['dragenter', 'dragover'].forEach(evt => {
                zone.addEventListener(evt, e => {
                    e.preventDefault();
                    zone.classList.add('drag-over');
                });
            });
            
            ['dragleave', 'drop'].forEach(evt => {
                zone.addEventListener(evt, e => {
                    e.preventDefault();
                    zone.classList.remove('drag-over');
                });
            });
            
            // Drop handler
            zone.addEventListener('drop', e => {
                if (e.dataTransfer.files.length) {
                    input.files = e.dataTransfer.files;
                    input.dispatchEvent(new Event('change'));
                }
            });
            
            // Change handler for preview (skip payload and QR zones - they have special handling)
            if (!isPayloadZone && !isQrZone) {
                input.addEventListener('change', function() {
                    if (this.files && this.files[0]) {
                        Stegasoo.showImagePreview(this.files[0], preview, label, zone);
                    }
                });
            }

            // Make preview clickable to replace file
            if (preview) {
                preview.style.cursor = 'pointer';
                preview.addEventListener('click', (e) => {
                    e.stopPropagation();
                    input.click();
                });
            }

            // Make entire zone clickable (in case label/preview don't cover it)
            zone.addEventListener('click', (e) => {
                // Only trigger if not clicking directly on the input
                if (e.target !== input) {
                    input.click();
                }
            });
        });
    },
    
    showImagePreview(file, previewEl, labelEl, zone = null) {
        if (!file.type.startsWith('image/')) return;
        
        const isScanContainer = zone && zone.classList.contains('scan-container');
        const isPixelContainer = zone && zone.classList.contains('pixel-container');
        
        const reader = new FileReader();
        reader.onload = e => {
            if (previewEl) {
                previewEl.src = e.target.result;
                previewEl.classList.remove('d-none');
            }
            // For scan/pixel containers, hide the label entirely (filename will appear in data panel)
            if (labelEl) {
                if (isScanContainer || isPixelContainer) {
                    labelEl.classList.add('d-none');
                } else {
                    labelEl.textContent = '';
                    const icon = document.createElement('i');
                    icon.className = 'bi bi-check-circle text-success me-1';
                    labelEl.appendChild(icon);
                    labelEl.appendChild(document.createTextNode(file.name));
                }
            }
            
            // Trigger appropriate animation
            if (isScanContainer) {
                Stegasoo.triggerScanAnimation(zone, file);
            } else if (isPixelContainer) {
                Stegasoo.triggerPixelReveal(zone, file);
            }
        };
        reader.readAsDataURL(file);
    },
    
    // ========================================================================
    // REFERENCE PHOTO SCAN ANIMATION
    // ========================================================================
    
    triggerScanAnimation(container, file, duration = 700) {
        // Reset any previous state
        container.classList.remove('scan-complete');
        container.classList.add('scanning');
        
        const preview = container.querySelector('.drop-zone-preview');
        
        // Create hash blocks for the "hashing" visual effect
        const createHashBlocks = () => {
            // Remove old hash blocks
            const oldBlocks = container.querySelector('.hash-blocks');
            if (oldBlocks) oldBlocks.remove();
            
            const hashContainer = document.createElement('div');
            hashContainer.className = 'hash-blocks';
            
            // Size and position to match preview image exactly
            const imgWidth = preview.offsetWidth;
            const imgHeight = preview.offsetHeight;
            const imgTop = preview.offsetTop;
            const imgLeft = preview.offsetLeft;
            
            hashContainer.style.width = imgWidth + 'px';
            hashContainer.style.height = imgHeight + 'px';
            hashContainer.style.top = imgTop + 'px';
            hashContainer.style.left = imgLeft + 'px';
            
            // Create grid of hash blocks (10x8 for better coverage)
            const cols = 10;
            const rows = 8;
            
            hashContainer.style.gridTemplateColumns = `repeat(${cols}, 1fr)`;
            hashContainer.style.gridTemplateRows = `repeat(${rows}, 1fr)`;
            
            // Create blocks with staggered delays for wave disappearance
            for (let row = 0; row < rows; row++) {
                for (let col = 0; col < cols; col++) {
                    const block = document.createElement('div');
                    block.className = 'hash-block';
                    // Diagonal wave pattern for disappearance
                    const delay = (row + col) * 25 + Math.random() * 30;
                    block.style.animationDelay = delay + 'ms';
                    hashContainer.appendChild(block);
                }
            }
            
            container.appendChild(hashContainer);
        };
        
        // Wait for image to be ready
        if (preview.complete && preview.naturalWidth) {
            createHashBlocks();
        } else {
            preview.onload = createHashBlocks;
        }
        
        // After animation duration, switch to complete state
        setTimeout(() => {
            container.classList.remove('scanning');
            container.classList.add('scan-complete');
            
            // Remove hash blocks container
            const hashBlocks = container.querySelector('.hash-blocks');
            if (hashBlocks) hashBlocks.remove();
            
            // Populate data panel if file provided
            if (file) {
                const nameEl = container.querySelector('#refFileName') || container.querySelector('.scan-data-filename span');
                const sizeEl = container.querySelector('#refFileSize') || container.querySelector('.scan-data-value');
                const hashEl = container.querySelector('#refHashPreview') || container.querySelector('.scan-hash-preview');
                
                if (nameEl) {
                    nameEl.textContent = file.name;
                }
                
                if (sizeEl) {
                    const sizeKB = (file.size / 1024).toFixed(1);
                    const sizeMB = (file.size / (1024 * 1024)).toFixed(2);
                    sizeEl.textContent = file.size > 1024 * 1024 ? `${sizeMB} MB` : `${sizeKB} KB`;
                }
                
                if (hashEl) {
                    // Generate a deterministic fake hash preview from filename + size
                    const fakeHash = Stegasoo.generateFakeHash(file.name + file.size);
                    hashEl.textContent = `SHA256: ${fakeHash.substring(0, 8)}····${fakeHash.substring(56)}`;
                }
            }
        }, duration);
    },
    
    generateFakeHash(input) {
        // Simple deterministic hash-like string for display purposes
        let hash = '';
        const chars = '0123456789abcdef';
        let seed = 0;
        for (let i = 0; i < input.length; i++) {
            seed = ((seed << 5) - seed) + input.charCodeAt(i);
            seed = seed & seed;
        }
        for (let i = 0; i < 64; i++) {
            seed = (seed * 1103515245 + 12345) & 0x7fffffff;
            hash += chars[seed % 16];
        }
        return hash;
    },
    
    // ========================================================================
    // CARRIER/STEGO PIXEL REVEAL ANIMATION
    // ========================================================================
    
    triggerPixelReveal(container, file, duration = 700) {
        // Reset any previous state
        container.classList.remove('load-complete');
        container.classList.add('loading');
        
        const preview = container.querySelector('.drop-zone-preview');
        
        // Create embed traces container sized to image
        const createTraces = () => {
            // Remove old elements
            let tracesContainer = container.querySelector('.embed-traces');
            if (tracesContainer) tracesContainer.remove();
            let oldGrid = container.querySelector('.embed-grid');
            if (oldGrid) oldGrid.remove();
            
            // Add grid overlay (covers whole panel like ref does)
            const grid = document.createElement('div');
            grid.className = 'embed-grid';
            container.appendChild(grid);
            
            // Create traces container
            tracesContainer = document.createElement('div');
            tracesContainer.className = 'embed-traces';
            container.appendChild(tracesContainer);
            
            // Size and position traces to match preview image exactly
            const imgWidth = preview.offsetWidth;
            const imgHeight = preview.offsetHeight;
            const imgTop = preview.offsetTop;
            const imgLeft = preview.offsetLeft;
            
            tracesContainer.style.width = imgWidth + 'px';
            tracesContainer.style.height = imgHeight + 'px';
            tracesContainer.style.top = imgTop + 'px';
            tracesContainer.style.left = imgLeft + 'px';
            
            // Generate Tron-style circuit traces covering the image
            Stegasoo.generateEmbedTraces(tracesContainer, imgWidth, imgHeight);
        };
        
        // Wait for image to be ready
        if (preview.complete && preview.naturalWidth) {
            createTraces();
        } else {
            preview.onload = createTraces;
        }
        
        setTimeout(() => {
            container.classList.remove('loading');
            container.classList.add('load-complete');
            
            // Remove traces and grid
            const traces = container.querySelector('.embed-traces');
            if (traces) traces.remove();
            const grid = container.querySelector('.embed-grid');
            if (grid) grid.remove();
            
            // Populate data panel
            Stegasoo.populatePixelDataPanel(container, file, preview);
        }, duration);
    },
    
    generateEmbedTraces(container, width, height) {
        // Color classes for variety
        const colors = ['color-yellow', 'color-cyan', 'color-purple', 'color-blue'];

        // Grid-based distribution: divide image into cells for even coverage
        const gridCols = 5;
        const gridRows = 4;
        const cellWidth = width / gridCols;
        const cellHeight = height / gridRows;

        let pathIndex = 0;

        // Spawn 1-2 paths from each grid cell for even distribution
        for (let row = 0; row < gridRows; row++) {
            for (let col = 0; col < gridCols; col++) {
                // 1-2 paths per cell
                const pathsInCell = 1 + Math.floor(Math.random() * 2);

                for (let p = 0; p < pathsInCell; p++) {
                    const pathColor = colors[Math.floor(Math.random() * colors.length)];

                    // Start within this grid cell (with padding)
                    let x = (col * cellWidth) + (cellWidth * 0.15) + (Math.random() * cellWidth * 0.7);
                    let y = (row * cellHeight) + (cellHeight * 0.15) + (Math.random() * cellHeight * 0.7);
                    let delay = pathIndex * 15;

                    // Each path has 3-5 short segments
                    const numSegments = 3 + Math.floor(Math.random() * 3);
                    let horizontal = Math.random() > 0.5;

                    for (let s = 0; s < numSegments; s++) {
                        const trace = document.createElement('div');
                        trace.className = 'embed-trace ' + (horizontal ? 'h' : 'v') + ' ' + pathColor;

                        // Shorter segments: 12-30px for denser circuit look
                        const length = 12 + Math.random() * 18;
                        trace.style.left = Math.max(0, Math.min(x, width - length)) + 'px';
                        trace.style.top = Math.max(0, Math.min(y, height - length)) + 'px';
                        trace.style.animationDelay = delay + 'ms';

                        if (horizontal) {
                            trace.style.width = length + 'px';
                        } else {
                            trace.style.height = length + 'px';
                        }

                        container.appendChild(trace);

                        // Move position for next segment
                        if (horizontal) {
                            x += length * (Math.random() > 0.5 ? 1 : -1);
                        } else {
                            y += length * (Math.random() > 0.5 ? 1 : -1);
                        }

                        // Keep within bounds
                        x = Math.max(5, Math.min(x, width - 20));
                        y = Math.max(5, Math.min(y, height - 20));

                        // Alternate direction (90 degree turn)
                        horizontal = !horizontal;
                        delay += 20;
                    }
                    pathIndex++;
                }
            }
        }
    },
    
    populatePixelDataPanel(container, file, preview) {
        const nameEl = container.querySelector('.pixel-data-filename span');
        const sizeEl = container.querySelector('.pixel-data-value');
        const dimsEl = container.querySelector('.pixel-dimensions');
        
        if (nameEl) {
            nameEl.textContent = file.name;
        }
        
        if (sizeEl) {
            const sizeKB = (file.size / 1024).toFixed(1);
            const sizeMB = (file.size / (1024 * 1024)).toFixed(2);
            sizeEl.textContent = file.size > 1024 * 1024 ? `${sizeMB} MB` : `${sizeKB} KB`;
        }
        
        if (dimsEl && preview) {
            dimsEl.textContent = `${preview.naturalWidth} × ${preview.naturalHeight} px`;
        }
    },
    
    initReferenceScanAnimation() {
        // Find all scan containers and wire up their inputs
        document.querySelectorAll('.scan-container').forEach(container => {
            const input = container.querySelector('input[type="file"]');
            const preview = container.querySelector('.drop-zone-preview');
            const label = container.querySelector('.drop-zone-label');
            
            if (!input) return;
            
            input.addEventListener('change', function() {
                if (this.files && this.files[0]) {
                    Stegasoo.showImagePreview(this.files[0], preview, label, container);
                }
            });
        });
    },
    
    // ========================================================================
    // CLIPBOARD PASTE
    // ========================================================================
    
    initClipboardPaste(imageInputSelectors) {
        document.addEventListener('paste', function(e) {
            const items = e.clipboardData?.items;
            if (!items) return;
            
            for (let i = 0; i < items.length; i++) {
                if (items[i].type.indexOf('image') !== -1) {
                    const blob = items[i].getAsFile();
                    
                    // Find first empty input from the list
                    let targetInput = null;
                    for (const selector of imageInputSelectors) {
                        const input = document.querySelector(selector);
                        if (input && (!input.files || !input.files.length)) {
                            targetInput = input;
                            break;
                        }
                    }
                    
                    // Fallback to first input if all have files
                    if (!targetInput) {
                        targetInput = document.querySelector(imageInputSelectors[0]);
                    }
                    
                    if (targetInput) {
                        const container = new DataTransfer();
                        container.items.add(blob);
                        targetInput.files = container.files;
                        targetInput.dispatchEvent(new Event('change'));
                    }
                    break;
                }
            }
        });
    },
    
    // ========================================================================
    // QR CODE CROP ANIMATION WITH SECTION SCANNING
    // ========================================================================
    
    initQrCropAnimation(inputId = 'rsaKeyQrInput') {
        const input = document.getElementById(inputId);
        const container = document.getElementById('qrCropContainer');
        const original = document.getElementById('qrOriginal');
        const cropped = document.getElementById('qrCropped');
        const dropZone = document.getElementById('qrDropZone');
        
        if (!input || !container || !original || !cropped) return;
        
        input.addEventListener('change', function() {
            if (!this.files || !this.files[0]) return;
            
            const file = this.files[0];
            if (!file.type.startsWith('image/')) return;
            
            const label = dropZone?.querySelector('.drop-zone-label');
            
            // Reset animation state
            container.classList.remove('scan-complete', 'scanning');
            container.classList.add('d-none');
            
            // Remove old overlay if exists
            const oldOverlay = container.querySelector('.qr-section-overlay');
            if (oldOverlay) oldOverlay.remove();
            
            // Show loading state immediately
            container.classList.remove('d-none');
            container.classList.add('loading');
            label?.classList.add('d-none');
            
            // Add loading indicator if not present
            let loader = container.querySelector('.qr-loader');
            if (!loader) {
                loader = document.createElement('div');
                loader.className = 'qr-loader';
                loader.innerHTML = `
                    <i class="bi bi-qr-code-scan"></i>
                    <span>Detecting QR code...</span>
                `;
                container.appendChild(loader);
            }
            
            // Fetch cropped version
            const formData = new FormData();
            formData.append('image', file);
            
            fetch('/qr/crop', {
                method: 'POST',
                body: formData
            })
            .then(response => {
                if (!response.ok) throw new Error('No QR detected');
                return response.blob();
            })
            .then(blob => {
                // Hide loader, show cropped image
                container.classList.remove('loading');
                cropped.src = URL.createObjectURL(blob);
                
                return new Promise((resolve) => {
                    cropped.onload = () => {
                        // Start scanning animation
                        container.classList.add('scanning');
                        
                        // Add scanner overlay - will be positioned via CSS to cover the image
                        let overlay = container.querySelector('.qr-scanner-overlay');
                        if (!overlay) {
                            overlay = document.createElement('div');
                            overlay.className = 'qr-scanner-overlay';
                            
                            ['tl', 'tr', 'bl', 'br'].forEach(pos => {
                                const bracket = document.createElement('div');
                                bracket.className = `qr-finder-bracket ${pos}`;
                                overlay.appendChild(bracket);
                            });
                            
                            // Add data panel inside overlay
                            const dataPanel = document.createElement('div');
                            dataPanel.className = 'qr-data-panel';
                            dataPanel.innerHTML = `
                                <div class="qr-data-row">
                                    <span class="qr-status-badge">KEY LOADED</span>
                                    <span class="qr-data-value">--</span>
                                </div>
                            `;
                            overlay.appendChild(dataPanel);
                            
                            container.appendChild(overlay);
                        }
                        
                        // Let CSS handle overlay positioning (inset with padding)
                        resolve();
                    };
                });
            })
            .then(() => {
                // Now verify key extraction
                const keyFormData = new FormData();
                keyFormData.append('qr_image', file);
                
                return fetch('/extract-key-from-qr', {
                    method: 'POST',
                    body: keyFormData
                });
            })
            .then(response => response.json())
            .then(data => {
                // Extraction complete - stop animation
                container.classList.remove('scanning');
                container.classList.add('scan-complete');
                
                // Update data panel (inside overlay)
                const overlay = container.querySelector('.qr-scanner-overlay');
                const sizeEl = overlay?.querySelector('.qr-data-value');
                
                if (data.success && sizeEl) {
                    const sizeKB = (file.size / 1024).toFixed(1);
                    sizeEl.textContent = sizeKB + ' KB';
                }
            })
            .catch(err => {
                console.log('QR crop/extract error:', err);
                container.classList.remove('loading', 'scanning');
                container.classList.add('error');

                // Update loader to show error
                const loader = container.querySelector('.qr-loader');
                if (loader) {
                    loader.innerHTML = `
                        <i class="bi bi-exclamation-triangle-fill"></i>
                        <span>No QR code detected</span>
                    `;
                }

                // Reset after delay so user can try again
                setTimeout(() => {
                    container.classList.remove('error');
                    container.classList.add('d-none');
                    label?.classList.remove('d-none');
                    // Clear the file input so same file can be re-selected
                    input.value = '';
                    // Remove loader
                    if (loader) loader.remove();
                }, 2000);
            });
        });
    },
    
    // ========================================================================
    // COLLAPSE CHEVRON ANIMATION
    // ========================================================================
    
    initCollapseChevrons() {
        document.querySelectorAll('[data-chevron]').forEach(collapse => {
            const chevronId = collapse.dataset.chevron;
            const chevron = document.getElementById(chevronId);
            
            if (!chevron) return;
            
            collapse.addEventListener('show.bs.collapse', () => {
                chevron.classList.add('bi-chevron-up');
                chevron.classList.remove('bi-chevron-down');
            });
            
            collapse.addEventListener('hide.bs.collapse', () => {
                chevron.classList.remove('bi-chevron-up');
                chevron.classList.add('bi-chevron-down');
            });
        });
    },
    
    // ========================================================================
    // FORM LOADING STATE
    // ========================================================================
    
    initFormLoading(formId, buttonId, loadingText = 'Processing...') {
        const form = document.getElementById(formId);
        const btn = document.getElementById(buttonId);
        
        if (!form || !btn) return;
        
        form.addEventListener('submit', () => {
            btn.disabled = true;
            btn.innerHTML = `<span class="spinner-border spinner-border-sm me-2"></span>${loadingText}`;
        });
    },
    
    // ========================================================================
    // COPY TO CLIPBOARD
    // ========================================================================
    
    copyToClipboard(text, iconEl, textEl) {
        navigator.clipboard.writeText(text).then(() => {
            const origIcon = iconEl?.className;
            const origText = textEl?.textContent;
            
            if (iconEl) iconEl.className = 'bi bi-check';
            if (textEl) textEl.textContent = 'Copied!';
            
            setTimeout(() => {
                if (iconEl) iconEl.className = origIcon;
                if (textEl) textEl.textContent = origText;
            }, 2000);
        });
    },
    
    // ========================================================================
    // MODE CARD HIGHLIGHTING
    // ========================================================================
    
    initModeCards(config) {
        // config: { radioName: 'embed_mode', cards: { 'lsb': { id: 'lsbCard', borderClass: 'border-primary' }, ... } }
        const radios = document.querySelectorAll(`input[name="${config.radioName}"]`);
        
        const update = () => {
            radios.forEach(radio => {
                const cardConfig = config.cards[radio.value];
                if (!cardConfig) return;
                
                const card = document.getElementById(cardConfig.id);
                if (!card) return;
                
                card.classList.toggle(cardConfig.borderClass, radio.checked);
                card.classList.toggle('border-2', radio.checked);
            });
        };
        
        radios.forEach(radio => radio.addEventListener('change', update));
        update(); // Initial state
    },
    
    // ========================================================================
    // PASSPHRASE FONT SIZE AUTO-ADJUST
    // ========================================================================
    
    initPassphraseFontResize(inputId = 'passphraseInput') {
        const input = document.getElementById(inputId);
        if (!input) return;
        
        const steps = [
            { maxChars: 30, size: 1.1 },
            { maxChars: 45, size: 1.0 },
            { maxChars: 60, size: 0.95 },
            { maxChars: Infinity, size: 0.9 }
        ];
        
        const adjust = () => {
            const len = input.value.length;
            for (const step of steps) {
                if (len <= step.maxChars) {
                    input.style.fontSize = step.size + 'rem';
                    break;
                }
            }
        };
        
        input.addEventListener('input', adjust);
        adjust();
    },
    
    // ========================================================================
    // CHANNEL KEY HANDLING (v4.0.0)
    // ========================================================================
    
    /**
     * Generate a random channel key in format XXXX-XXXX-XXXX-XXXX-XXXX-XXXX-XXXX-XXXX
     * @returns {string} Generated key
     */
    generateChannelKey() {
        const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789';
        let key = '';
        for (let i = 0; i < 8; i++) {
            if (i > 0) key += '-';
            for (let j = 0; j < 4; j++) {
                key += chars.charAt(Math.floor(Math.random() * chars.length));
            }
        }
        return key;
    },
    
    /**
     * Validate channel key format
     * @param {string} key - Key to validate
     * @returns {boolean} True if valid
     */
    validateChannelKey(key) {
        const pattern = /^[A-Z0-9]{4}(-[A-Z0-9]{4}){7}$/;
        return pattern.test(key);
    },
    
    /**
     * Format channel key input (auto-add dashes, uppercase)
     * @param {HTMLInputElement} input - Input element
     */
    formatChannelKeyInput(input) {
        let value = input.value.toUpperCase();
        const clean = value.replace(/-/g, '');
        
        if (clean.length > 0 && clean.length <= 32) {
            const formatted = clean.match(/.{1,4}/g)?.join('-') || clean;
            if (formatted !== value && formatted.length <= 39) {
                input.value = formatted;
            } else {
                input.value = value;
            }
        }
        
        // Validate and show/hide error state
        const isValid = this.validateChannelKey(input.value);
        input.classList.toggle('is-invalid', input.value.length > 0 && !isValid);
    },
    
    /**
     * Initialize channel key UI for encode/decode pages
     * @param {Object} config - Configuration object
     * @param {string} config.selectId - ID of channel select dropdown
     * @param {string} config.customInputId - ID of custom key input container
     * @param {string} config.keyInputId - ID of key input field
     * @param {string} config.generateBtnId - ID of generate button (optional)
     */
    initChannelKey(config = {}) {
        const selectId = config.selectId || 'channelSelect';
        const customInputId = config.customInputId || 'channelCustomInput';
        const keyInputId = config.keyInputId || 'channelKeyInput';
        const generateBtnId = config.generateBtnId;
        const serverInfoId = config.serverInfoId || 'channelServerInfo';

        const select = document.getElementById(selectId);
        const customInput = document.getElementById(customInputId);
        const keyInput = document.getElementById(keyInputId);
        const generateBtn = generateBtnId ? document.getElementById(generateBtnId) : null;
        const serverInfo = document.getElementById(serverInfoId);

        // Show/hide custom input and server info based on selection
        const updateVisibility = () => {
            const value = select?.value;
            const isCustom = value === 'custom';
            const isPublic = value === 'none';
            const isAuto = value === 'auto';

            // Custom input visibility
            customInput?.classList.toggle('d-none', !isCustom);
            if (isCustom && keyInput) {
                keyInput.focus();
                // Pulse highlight effect
                customInput?.classList.add('channel-highlight');
                setTimeout(() => customInput?.classList.remove('channel-highlight'), 400);
            }

            // Server info: show for auto, hide for custom, show "no key" for public
            if (serverInfo) {
                if (isAuto) {
                    serverInfo.innerHTML = '<i class="bi bi-shield-lock me-1"></i>Server: <code>' + (serverInfo.dataset.fingerprint || '••••-••••-···-••••-••••') + '</code>';
                    serverInfo.className = 'small text-success mt-2';
                    serverInfo.classList.remove('d-none');
                } else if (isPublic) {
                    serverInfo.innerHTML = '<i class="bi bi-globe me-1"></i>No channel key will be used';
                    serverInfo.className = 'small text-muted mt-2';
                    serverInfo.classList.remove('d-none');
                } else {
                    serverInfo.classList.add('d-none');
                }
            }
        };

        select?.addEventListener('change', updateVisibility);

        // Initial state
        updateVisibility();

        // Format and validate key input
        keyInput?.addEventListener('input', () => {
            this.formatChannelKeyInput(keyInput);
        });

        // Generate button (if present)
        generateBtn?.addEventListener('click', () => {
            if (keyInput) {
                keyInput.value = this.generateChannelKey();
                keyInput.classList.remove('is-invalid');
            }
        });
    },

    /**
     * Handle form submission with channel key validation
     * @param {HTMLFormElement} form - Form element
     * @param {string} selectId - ID of channel select dropdown
     * @param {string} keyInputId - ID of key input field
     * @returns {boolean} True if valid, false to prevent submission
     */
    validateChannelKeyOnSubmit(form, selectId, keyInputId) {
        const select = document.getElementById(selectId);
        const keyInput = document.getElementById(keyInputId);

        if (select?.value === 'custom' && keyInput) {
            if (!this.validateChannelKey(keyInput.value)) {
                keyInput.classList.add('is-invalid');
                keyInput.focus();
                return false;
            }
            // Set the select value to the actual key for form submission
            select.value = keyInput.value;
        }

        // Track saved key usage (fire-and-forget)
        const selectedOption = select?.selectedOptions?.[0];
        const keyId = selectedOption?.dataset?.keyId;
        if (keyId) {
            fetch(`/api/channel/keys/${keyId}/use`, { method: 'POST' }).catch(() => {});
        }

        return true;
    },
    
    /**
     * Initialize standalone channel key generator (for generate page)
     * @param {string} inputId - ID of generated key input
     * @param {string} generateBtnId - ID of generate button
     * @param {string} copyBtnId - ID of copy button
     */
    initChannelKeyGenerator(inputId, generateBtnId, copyBtnId) {
        const input = document.getElementById(inputId);
        const generateBtn = document.getElementById(generateBtnId);
        const copyBtn = document.getElementById(copyBtnId);
        
        generateBtn?.addEventListener('click', () => {
            if (input) {
                input.value = this.generateChannelKey();
            }
            if (copyBtn) {
                copyBtn.disabled = false;
            }
        });
        
        copyBtn?.addEventListener('click', () => {
            if (input?.value) {
                navigator.clipboard.writeText(input.value).then(() => {
                    const icon = copyBtn.querySelector('i');
                    if (icon) {
                        icon.className = 'bi bi-check';
                        setTimeout(() => { icon.className = 'bi bi-clipboard'; }, 2000);
                    }
                });
            }
        });
    },
    
    // ========================================================================
    // ASYNC ENCODE WITH PROGRESS (v4.1.2)
    // ========================================================================

    /**
     * Submit encode form asynchronously with progress tracking
     * @param {HTMLFormElement} form - The encode form
     * @param {HTMLElement} btn - The submit button
     */
    async submitEncodeAsync(form, btn) {
        const formData = new FormData(form);
        formData.append('async', 'true');

        // Show progress modal
        this.showProgressModal('Encoding');

        try {
            // Start encode job
            const response = await fetch('/encode', {
                method: 'POST',
                body: formData,
            });

            if (!response.ok) {
                throw new Error('Failed to start encode');
            }

            const result = await response.json();

            if (result.error) {
                throw new Error(result.error);
            }

            const jobId = result.job_id;

            // Poll for progress
            await this.pollEncodeProgress(jobId);

        } catch (error) {
            this.hideProgressModal();
            alert('Encode failed: ' + error.message);
            btn.disabled = false;
            btn.innerHTML = '<i class="bi bi-lock-fill me-2"></i>Encode';
        }
    },

    /**
     * Poll encode progress until complete
     * @param {string} jobId - The job ID
     */
    async pollEncodeProgress(jobId) {
        const progressBar = document.getElementById('progressBar');
        const progressText = document.getElementById('progressText');
        const phaseText = document.getElementById('progressPhase');

        const poll = async () => {
            try {
                // Check status first
                const statusResponse = await fetch(`/encode/status/${jobId}`);
                const statusData = await statusResponse.json();

                if (statusData.status === 'complete') {
                    // Done - redirect to result
                    this.updateProgress(100, 'Complete!');
                    setTimeout(() => {
                        window.location.href = `/encode/result/${statusData.file_id}`;
                    }, 500);
                    return;
                }

                if (statusData.status === 'error') {
                    throw new Error(statusData.error || 'Encode failed');
                }

                // Get progress
                const progressResponse = await fetch(`/encode/progress/${jobId}`);
                const progressData = await progressResponse.json();

                const percent = progressData.percent || 0;
                const phase = progressData.phase || 'processing';

                // Use indeterminate mode for initializing/starting phases
                const isIndeterminate = (phase === 'initializing' || phase === 'starting');
                this.updateProgress(percent, this.formatPhase(phase), isIndeterminate);

                // Continue polling
                setTimeout(poll, 500);

            } catch (error) {
                this.hideProgressModal();
                alert('Encode failed: ' + error.message);
            }
        };

        await poll();
    },

    /**
     * Format phase name for display
     */
    formatPhase(phase) {
        const phases = {
            'starting': 'Starting...',
            'initializing': 'Initializing...',
            'embedding': 'Embedding data...',
            'saving': 'Saving image...',
            'finalizing': 'Finalizing...',
            'complete': 'Complete!',
        };
        return phases[phase] || phase;
    },

    /**
     * Show progress modal
     */
    showProgressModal(operation = 'Processing') {
        // Create modal if doesn't exist
        let modal = document.getElementById('progressModal');
        if (!modal) {
            modal = document.createElement('div');
            modal.id = 'progressModal';
            modal.className = 'modal fade';
            modal.setAttribute('data-bs-backdrop', 'static');
            modal.setAttribute('data-bs-keyboard', 'false');
            modal.innerHTML = `
                <div class="modal-dialog modal-dialog-centered">
                    <div class="modal-content bg-dark text-light">
                        <div class="modal-body p-4">
                            <h5 class="mb-3" id="progressTitle">${operation}...</h5>
                            <div class="progress mb-2" style="height: 24px;">
                                <div id="progressBar" class="progress-bar progress-bar-striped progress-bar-animated bg-success"
                                     role="progressbar" style="width: 0%"></div>
                            </div>
                            <div class="d-flex justify-content-between text-muted small">
                                <span id="progressPhase">Initializing...</span>
                                <span id="progressText">0%</span>
                            </div>
                        </div>
                    </div>
                </div>
            `;
            document.body.appendChild(modal);
        }

        // Reset progress tracking and start with indeterminate state
        this.resetProgressTracking();
        this.updateProgress(0, 'Initializing...', true);

        // Show modal
        const bsModal = new bootstrap.Modal(modal);
        bsModal.show();
    },

    /**
     * Hide progress modal
     */
    hideProgressModal() {
        const modal = document.getElementById('progressModal');
        if (modal) {
            const bsModal = bootstrap.Modal.getInstance(modal);
            bsModal?.hide();
        }
    },

    /**
     * Track max progress to prevent backwards jumps
     */
    _maxProgress: 0,

    /**
     * Reset progress tracking (call when starting new operation)
     */
    resetProgressTracking() {
        this._maxProgress = 0;
    },

    /**
     * Update progress bar and text
     * Supports indeterminate mode for initializing phase (barber pole at full width)
     */
    updateProgress(percent, phase, indeterminate = false) {
        const progressBar = document.getElementById('progressBar');
        const progressText = document.getElementById('progressText');
        const phaseText = document.getElementById('progressPhase');

        if (indeterminate) {
            // Barber pole animation at full width, no percentage
            if (progressBar) {
                progressBar.style.width = '100%';
                progressBar.classList.add('progress-bar-striped', 'progress-bar-animated');
            }
            if (progressText) progressText.textContent = '';
            if (phaseText) phaseText.textContent = phase;
        } else {
            // Determinate progress - never go backwards
            const safePercent = Math.max(percent, this._maxProgress);
            this._maxProgress = safePercent;

            if (progressBar) {
                progressBar.style.width = safePercent + '%';
                // Keep animation but show actual progress
                progressBar.classList.add('progress-bar-striped', 'progress-bar-animated');
            }
            if (progressText) progressText.textContent = Math.round(safePercent) + '%';
            if (phaseText) phaseText.textContent = phase;
        }
    },

    // ========================================================================
    // ASYNC DECODE WITH PROGRESS (v4.1.5)
    // ========================================================================

    /**
     * Submit decode form asynchronously with progress tracking
     * @param {HTMLFormElement} form - The decode form
     * @param {HTMLElement} btn - The submit button
     */
    async submitDecodeAsync(form, btn) {
        const formData = new FormData(form);
        formData.append('async', 'true');

        // Show progress modal
        this.showProgressModal('Decoding');

        try {
            // Start decode job
            const response = await fetch('/decode', {
                method: 'POST',
                body: formData,
            });

            if (!response.ok) {
                throw new Error('Failed to start decode');
            }

            const result = await response.json();

            if (result.error) {
                throw new Error(result.error);
            }

            const jobId = result.job_id;

            // Poll for progress
            await this.pollDecodeProgress(jobId);

        } catch (error) {
            this.hideProgressModal();
            alert('Decode failed: ' + error.message);
            btn.disabled = false;
            btn.innerHTML = '<i class="bi bi-unlock-fill me-2"></i>Decode';
        }
    },

    /**
     * Poll decode progress until complete
     * @param {string} jobId - The job ID
     */
    async pollDecodeProgress(jobId) {
        const poll = async () => {
            try {
                // Check status first
                const statusResponse = await fetch(`/decode/status/${jobId}`);
                const statusData = await statusResponse.json();

                if (statusData.status === 'complete') {
                    // Done - redirect to result page
                    this.updateProgress(100, 'Complete!');
                    setTimeout(() => {
                        window.location.href = `/decode/result/${jobId}`;
                    }, 500);
                    return;
                }

                if (statusData.status === 'error') {
                    // Handle specific error types
                    const errorType = statusData.error_type;
                    let errorMsg = statusData.error || 'Decode failed';

                    if (errorType === 'DecryptionError' || errorMsg.toLowerCase().includes('decrypt')) {
                        errorMsg = 'Wrong credentials. Double-check your reference photo, passphrase, PIN, and channel key.';
                    }

                    throw new Error(errorMsg);
                }

                // Get progress
                const progressResponse = await fetch(`/decode/progress/${jobId}`);
                const progressData = await progressResponse.json();

                const percent = progressData.percent || 0;
                const phase = progressData.phase || 'processing';

                // Use indeterminate mode for initializing/starting/loading phases
                const isIndeterminate = (phase === 'initializing' || phase === 'starting' || phase === 'loading');
                this.updateProgress(percent, this.formatDecodePhase(phase), isIndeterminate);

                // Continue polling
                setTimeout(poll, 500);

            } catch (error) {
                this.hideProgressModal();
                alert(error.message);
            }
        };

        await poll();
    },

    /**
     * Format decode phase name for display
     */
    formatDecodePhase(phase) {
        const phases = {
            'starting': 'Starting...',
            'reading': 'Reading image...',
            'extracting': 'Extracting data...',
            'decrypting': 'Decrypting...',
            'verifying': 'Verifying...',
            'finalizing': 'Finalizing...',
            'complete': 'Complete!',
        };
        return phases[phase] || phase;
    },

    // ========================================================================
    // WEBCAM QR SCANNING (v4.1.5)
    // ========================================================================

    /**
     * Active scanner instance
     */
    _qrScanner: null,
    _qrScannerModal: null,
    _qrScannerCallback: null,

    /**
     * Show webcam QR scanner modal
     * @param {Function} onSuccess - Callback with decoded QR text
     * @param {string} title - Modal title
     */
    showQrScanner(onSuccess, title = 'Scan QR Code') {
        this._qrScannerCallback = onSuccess;

        // Create modal if doesn't exist
        let modal = document.getElementById('qrScannerModal');
        if (!modal) {
            modal = document.createElement('div');
            modal.id = 'qrScannerModal';
            modal.className = 'modal fade';
            modal.innerHTML = `
                <div class="modal-dialog modal-dialog-centered">
                    <div class="modal-content bg-dark text-light">
                        <div class="modal-header border-secondary">
                            <h5 class="modal-title">
                                <i class="bi bi-camera-video me-2"></i>
                                <span id="qrScannerTitle">${title}</span>
                            </h5>
                            <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
                        </div>
                        <div class="modal-body p-0">
                            <div id="qrScannerReader" style="width: 100%;"></div>
                            <div id="qrScannerStatus" class="text-center py-3 text-muted">
                                <i class="bi bi-qr-code-scan me-2"></i>
                                Point camera at QR code
                            </div>
                        </div>
                        <div class="modal-footer border-secondary">
                            <button type="button" class="btn btn-primary" id="qrCaptureBtn">
                                <i class="bi bi-camera me-1"></i>Capture
                            </button>
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                        </div>
                    </div>
                </div>
            `;
            document.body.appendChild(modal);

            // Clean up scanner when modal hides
            modal.addEventListener('hidden.bs.modal', () => {
                this.stopQrScanner();
            });

            // Manual capture button
            modal.querySelector('#qrCaptureBtn')?.addEventListener('click', () => {
                this.captureQrFrame();
            });
        }

        // Update title
        const titleEl = modal.querySelector('#qrScannerTitle');
        if (titleEl) titleEl.textContent = title;

        // Reset status
        const statusEl = modal.querySelector('#qrScannerStatus');
        if (statusEl) {
            statusEl.innerHTML = '<i class="bi bi-qr-code-scan me-2"></i>Point camera at QR code';
            statusEl.className = 'text-center py-3 text-muted';
        }

        // Show modal
        this._qrScannerModal = new bootstrap.Modal(modal);
        this._qrScannerModal.show();

        // Start scanner after modal is shown
        modal.addEventListener('shown.bs.modal', () => {
            this.startQrScanner();
        }, { once: true });
    },

    /**
     * Start the QR scanner
     */
    startQrScanner() {
        const readerEl = document.getElementById('qrScannerReader');
        if (!readerEl) return;

        // Check if Html5Qrcode is available
        if (typeof Html5Qrcode === 'undefined') {
            console.error('Html5Qrcode library not loaded');
            const statusEl = document.getElementById('qrScannerStatus');
            if (statusEl) {
                statusEl.innerHTML = '<i class="bi bi-exclamation-triangle text-warning me-2"></i>QR scanner not available';
            }
            return;
        }

        this._qrScanner = new Html5Qrcode('qrScannerReader');

        const config = {
            fps: 10,
            qrbox: { width: 250, height: 250 },
            aspectRatio: 1.0,
        };

        this._qrScanner.start(
            { facingMode: 'environment' }, // Prefer back camera
            config,
            (decodedText, decodedResult) => {
                // QR code detected
                this.onQrCodeDetected(decodedText);
            },
            (errorMessage) => {
                // Scan error (ignore, keep scanning)
            }
        ).catch((err) => {
            console.error('Failed to start scanner:', err);
            const statusEl = document.getElementById('qrScannerStatus');
            if (statusEl) {
                if (err.toString().includes('Permission')) {
                    statusEl.innerHTML = '<i class="bi bi-camera-video-off text-danger me-2"></i>Camera permission denied';
                } else {
                    statusEl.innerHTML = '<i class="bi bi-exclamation-triangle text-warning me-2"></i>Could not access camera';
                }
                statusEl.className = 'text-center py-3';
            }
        });
    },

    /**
     * Capture a frame with countdown and try to decode
     */
    captureQrFrame() {
        const statusEl = document.getElementById('qrScannerStatus');
        const captureBtn = document.getElementById('qrCaptureBtn');
        if (!statusEl || !this._qrScanner) return;

        // Disable button during countdown
        if (captureBtn) captureBtn.disabled = true;

        let count = 3;
        const countdown = () => {
            if (count > 0) {
                statusEl.innerHTML = `<i class="bi bi-camera me-2"></i><span style="font-size: 1.5rem; font-weight: bold;">${count}</span>`;
                statusEl.className = 'text-center py-3 text-warning';
                count--;
                setTimeout(countdown, 1000);
            } else {
                // Capture!
                statusEl.innerHTML = '<i class="bi bi-hourglass-split me-2"></i>Analyzing...';
                statusEl.className = 'text-center py-3 text-info';

                // Get video element and capture frame
                const video = document.querySelector('#qrScannerReader video');
                if (video) {
                    const canvas = document.createElement('canvas');
                    canvas.width = video.videoWidth;
                    canvas.height = video.videoHeight;
                    const ctx = canvas.getContext('2d');
                    ctx.drawImage(video, 0, 0);

                    // Stop the scanner before file scan (prevents conflicts)
                    const scanner = this._qrScanner;
                    scanner.stop().then(() => {
                        canvas.toBlob((blob) => {
                            const file = new File([blob], 'capture.png', { type: 'image/png' });
                            scanner.scanFile(file, true)
                                .then((decodedText) => {
                                    this.onQrCodeDetected(decodedText);
                                })
                                .catch((err) => {
                                    statusEl.innerHTML = '<i class="bi bi-x-circle text-danger me-2"></i>No QR code found. Try again.';
                                    statusEl.className = 'text-center py-3 text-danger';
                                    if (captureBtn) captureBtn.disabled = false;
                                    // Restart the scanner
                                    this.startQrScanner();
                                });
                        }, 'image/png');
                    }).catch(() => {
                        statusEl.innerHTML = '<i class="bi bi-x-circle text-danger me-2"></i>Scanner error';
                        statusEl.className = 'text-center py-3 text-danger';
                        if (captureBtn) captureBtn.disabled = false;
                    });
                } else {
                    statusEl.innerHTML = '<i class="bi bi-x-circle text-danger me-2"></i>Camera not ready';
                    statusEl.className = 'text-center py-3 text-danger';
                    if (captureBtn) captureBtn.disabled = false;
                }
            }
        };
        countdown();
    },

    /**
     * Stop the QR scanner
     */
    stopQrScanner() {
        if (this._qrScanner) {
            this._qrScanner.stop().then(() => {
                this._qrScanner.clear();
                this._qrScanner = null;
            }).catch((err) => {
                console.log('Scanner stop error:', err);
            });
        }
    },

    /**
     * Handle detected QR code
     * @param {string} text - Decoded QR text
     */
    onQrCodeDetected(text) {
        // Update status
        const statusEl = document.getElementById('qrScannerStatus');
        if (statusEl) {
            statusEl.innerHTML = '<i class="bi bi-check-circle text-success me-2"></i>QR code detected!';
            statusEl.className = 'text-center py-3 text-success';
        }

        // Close modal after brief delay
        setTimeout(() => {
            this._qrScannerModal?.hide();

            // Call callback
            if (this._qrScannerCallback) {
                this._qrScannerCallback(text);
            }
        }, 500);
    },

    /**
     * Add camera scan button to an input field
     * @param {string} inputId - ID of the input field
     * @param {string} title - Modal title
     * @param {Function} validator - Optional validation function for scanned text
     */
    addCameraScanButton(inputId, title = 'Scan QR Code', validator = null) {
        const input = document.getElementById(inputId);
        if (!input) return;

        // Create button
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'btn btn-outline-secondary';
        btn.innerHTML = '<i class="bi bi-camera"></i>';
        btn.title = 'Scan QR code with camera';

        btn.addEventListener('click', () => {
            this.showQrScanner((text) => {
                // Validate if validator provided
                if (validator && !validator(text)) {
                    alert('Invalid QR code format');
                    return;
                }
                // Set input value
                input.value = text;
                // Trigger input event for formatting
                input.dispatchEvent(new Event('input', { bubbles: true }));
            }, title);
        });

        // Wrap input in input-group if not already
        const parent = input.parentElement;
        if (!parent.classList.contains('input-group')) {
            const wrapper = document.createElement('div');
            wrapper.className = 'input-group';
            parent.insertBefore(wrapper, input);
            wrapper.appendChild(input);
            wrapper.appendChild(btn);
        } else {
            parent.appendChild(btn);
        }
    },

    // ========================================================================
    // INITIALIZATION HELPERS
    // ========================================================================

    initEncodePage() {
        this.initPasswordToggles();
        this.initRsaMethodToggle();
        this.initDropZones();
        this.initClipboardPaste(['input[name="carrier"]', 'input[name="reference_photo"]']);
        this.initQrCropAnimation('rsaQrInput');
        this.initCollapseChevrons();
        this.initPassphraseFontResize();
        
        // Channel key (v4.0.0) - uses select dropdown
        this.initChannelKey({
            selectId: 'channelSelect',
            customInputId: 'channelCustomInput',
            keyInputId: 'channelKeyInput',
            generateBtnId: 'channelKeyGenerate'
        });

        // Webcam QR scanning for channel key (v4.1.5)
        document.getElementById('channelKeyScan')?.addEventListener('click', () => {
            this.showQrScanner((text) => {
                const input = document.getElementById('channelKeyInput');
                if (input) {
                    const clean = text.replace(/[^A-Za-z0-9]/g, '').toUpperCase();
                    input.value = clean.length === 32 ? clean.match(/.{4}/g).join('-') : text.toUpperCase();
                    input.dispatchEvent(new Event('input', { bubbles: true }));
                }
            }, 'Scan Channel Key');
        });

        // Webcam QR scanning for RSA key (v4.1.5)
        document.getElementById('rsaQrWebcam')?.addEventListener('click', () => {
            this.showQrScanner((text) => {
                // Check for raw PEM or compressed format (STEGASOO-Z: prefix)
                const isRawPem = text.includes('-----BEGIN') && text.includes('KEY-----');
                const isCompressed = text.startsWith('STEGASOO-Z:');
                if (isRawPem || isCompressed) {
                    // Valid RSA key data scanned
                    document.getElementById('rsaKeyPem').value = text;
                    // Show success in drop zone
                    const dropZone = document.getElementById('qrDropZone');
                    const label = dropZone?.querySelector('.drop-zone-label');
                    if (label) {
                        label.innerHTML = '<i class="bi bi-check-circle text-success fs-4 d-block mb-1"></i><span class="text-success small">RSA Key scanned successfully</span>';
                    }
                } else {
                    alert('QR code does not contain a valid RSA key');
                }
            }, 'Scan RSA Key QR');
        });

        // Form submission with async progress tracking (v4.1.2)
        const form = document.getElementById('encodeForm');
        const btn = document.getElementById('encodeBtn');
        form?.addEventListener('submit', (e) => {
            e.preventDefault();

            if (!this.validateChannelKeyOnSubmit(form, 'channelSelect', 'channelKeyInput')) {
                return false;
            }

            if (btn) {
                btn.disabled = true;
                btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Starting...';
            }

            // Use async submission with progress tracking
            this.submitEncodeAsync(form, btn);
        });
    },
    
    initDecodePage() {
        this.initPasswordToggles();
        this.initRsaMethodToggle();
        this.initDropZones();
        this.initClipboardPaste(['input[name="stego_image"]', 'input[name="reference_photo"]']);
        this.initQrCropAnimation('rsaQrInput');
        this.initCollapseChevrons();
        this.initPassphraseFontResize();
        
        // Channel key (v4.0.0) - uses select dropdown
        this.initChannelKey({
            selectId: 'channelSelectDec',
            customInputId: 'channelCustomInputDec',
            keyInputId: 'channelKeyInputDec',
            serverInfoId: 'channelServerInfoDec'
        });

        // Webcam QR scanning for channel key (v4.1.5)
        document.getElementById('channelKeyScanDec')?.addEventListener('click', () => {
            this.showQrScanner((text) => {
                const input = document.getElementById('channelKeyInputDec');
                if (input) {
                    const clean = text.replace(/[^A-Za-z0-9]/g, '').toUpperCase();
                    input.value = clean.length === 32 ? clean.match(/.{4}/g).join('-') : text.toUpperCase();
                    input.dispatchEvent(new Event('input', { bubbles: true }));
                }
            }, 'Scan Channel Key');
        });

        // Webcam QR scanning for RSA key (v4.1.5)
        document.getElementById('rsaQrWebcam')?.addEventListener('click', () => {
            this.showQrScanner((text) => {
                // Check for raw PEM or compressed format (STEGASOO-Z: prefix)
                const isRawPem = text.includes('-----BEGIN') && text.includes('KEY-----');
                const isCompressed = text.startsWith('STEGASOO-Z:');
                if (isRawPem || isCompressed) {
                    // Valid RSA key data scanned
                    document.getElementById('rsaKeyPem').value = text;
                    // Show success in drop zone
                    const dropZone = document.getElementById('qrDropZone');
                    const label = dropZone?.querySelector('.drop-zone-label');
                    if (label) {
                        label.innerHTML = '<i class="bi bi-check-circle text-success fs-4 d-block mb-1"></i><span class="text-success small">RSA Key scanned successfully</span>';
                    }
                } else {
                    alert('QR code does not contain a valid RSA key');
                }
            }, 'Scan RSA Key QR');
        });

        // Form submission with async progress tracking (v4.1.5)
        const form = document.getElementById('decodeForm');
        const btn = document.getElementById('decodeBtn');
        form?.addEventListener('submit', (e) => {
            e.preventDefault();

            if (!this.validateChannelKeyOnSubmit(form, 'channelSelectDec', 'channelKeyInputDec')) {
                return false;
            }

            if (btn) {
                btn.disabled = true;
                btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Starting...';
            }

            // Use async submission with progress tracking
            this.submitDecodeAsync(form, btn);
        });
    },
    
    initGeneratePage() {
        this.initPasswordToggles();
        // Channel key generator (v4.0.0)
        this.initChannelKeyGenerator('channelKeyGenerated', 'generateChannelKeyBtn', 'copyChannelKeyBtn');
    }
};

// Auto-init based on page
document.addEventListener('DOMContentLoaded', () => {
    // Detect page and initialize
    if (document.getElementById('encodeForm')) {
        Stegasoo.initEncodePage();
    } else if (document.getElementById('decodeForm')) {
        Stegasoo.initDecodePage();
    } else if (document.querySelector('[data-page="generate"]')) {
        Stegasoo.initGeneratePage();
    }
});
