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
                    labelEl.innerHTML = '<i class="bi bi-check-circle text-success me-1"></i>' + file.name;
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
        
        // Generate 6-8 snake paths spread across the whole image
        const numPaths = 6 + Math.floor(Math.random() * 3);
        
        for (let p = 0; p < numPaths; p++) {
            // Each path gets a random color
            const pathColor = colors[Math.floor(Math.random() * colors.length)];
            
            // Distribute starting points across the image
            let x = (width * 0.1) + (Math.random() * width * 0.8);
            let y = (height * 0.1) + (Math.random() * height * 0.8);
            let delay = p * 40;
            
            // Each path has 3-5 segments for more coverage
            const numSegments = 3 + Math.floor(Math.random() * 3);
            let horizontal = Math.random() > 0.5;
            
            for (let s = 0; s < numSegments; s++) {
                const trace = document.createElement('div');
                trace.className = 'embed-trace ' + (horizontal ? 'h' : 'v') + ' ' + pathColor;
                
                const length = 30 + Math.random() * 60;
                trace.style.left = x + 'px';
                trace.style.top = y + 'px';
                trace.style.animationDelay = delay + 'ms';
                
                if (horizontal) {
                    trace.style.width = length + 'px';
                } else {
                    trace.style.height = length + 'px';
                }
                
                container.appendChild(trace);
                
                // Move position for next segment
                if (horizontal) {
                    x += length;
                } else {
                    y += length;
                }
                
                // Wrap around if out of bounds to keep traces in view
                if (x > width - 20) x = 10 + Math.random() * 40;
                if (y > height - 20) y = 10 + Math.random() * 40;
                if (x < 10) x = width - 60 + Math.random() * 40;
                if (y < 10) y = height - 60 + Math.random() * 40;
                
                // Alternate direction (90 degree turn)
                horizontal = !horizontal;
                delay += 30;
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
    // INITIALIZATION HELPERS
    // ========================================================================
    
    initEncodePage() {
        this.initPasswordToggles();
        this.initRsaMethodToggle();
        this.initDropZones();
        this.initClipboardPaste(['input[name="carrier"]', 'input[name="reference_photo"]']);
        this.initQrCropAnimation('rsaQrInput');
        this.initCollapseChevrons();
        this.initFormLoading('encodeForm', 'encodeBtn', 'Encoding...');
        this.initPassphraseFontResize();
    },
    
    initDecodePage() {
        this.initPasswordToggles();
        this.initRsaMethodToggle();
        this.initDropZones();
        this.initClipboardPaste(['input[name="stego_image"]', 'input[name="reference_photo"]']);
        this.initQrCropAnimation('rsaKeyQrInput');
        this.initCollapseChevrons();
        this.initFormLoading('decodeForm', 'decodeBtn', 'Decoding...');
        this.initPassphraseFontResize();
    },
    
    initGeneratePage() {
        this.initPasswordToggles();
        // Generate page has mostly unique functionality
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
