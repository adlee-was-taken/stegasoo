# Stegasoo v4.1.6 Planning

## UI Tweaks

### 1. Revamp Tron Lines Animation (Carrier/Stego Image)
**Current state:**
- 6-8 snake paths, each with 3-5 segments (~24-40 total lines)
- 2px thick lines
- 30-60px length per segment
- Starting points spread across 80% of image area
- Colors: yellow, cyan, purple, blue with glow

**Target improvements:**
- [x] Thinner lines (1px instead of 2px)
- [x] More numerous (20-40 paths via 5x4 grid, ~60-200 segments total)
- [x] Better distribution across entire image (grid-based seeding)
- [x] Shorter segments (12-30px) for denser "circuit board" look

**Files:**
- `frontends/web/static/style.css` (~881-979) - `.embed-trace` styling
- `frontends/web/static/js/stegasoo.js` (~333-390) - `generateEmbedTraces()`

---

## Tools Page Expansion

### Analysis Tools
- [x] **JPEG Compression Tester** - Preview image at different quality levels (10-100%), show file size delta. Useful for understanding stego survivability.
- [ ] **LSB Plane Viewer** - Visualize least significant bit plane(s) of RGB channels. Classic stego analysis tool.
- [ ] **Histogram Viewer** - Color distribution graph per channel. Anomalies can indicate hidden data.
- [ ] **Image Diff** - Compare two images side-by-side with pixel difference highlighting. Great for original vs stego comparison.
- [ ] **Noise Analysis** - Chi-square or similar statistical analysis for detecting LSB embedding.

### Transform Tools
- [x] **Rotate/Flip** - 90°/180°/270° rotation, horizontal/vertical flip
- [ ] **Resize** - Scale with aspect ratio lock, common presets (50%, 25%, etc.)
- [ ] **Crop** - Basic rectangular crop with preview
- [x] **Format Convert** - PNG ↔ JPEG ↔ WebP with quality slider

### Existing Tools (already done)
- [x] Capacity Calculator
- [x] EXIF Viewer
- [x] EXIF Strip
- [x] Image Peek (header analysis)

### Tools UI/UX Overhaul

**Final Layout: Office-style Ribbon + Two-Panel**
```
┌─────────────────────────────────────────────────────────────┐
│  📏  📋  👁️  📊  ┃  ✂️  🔄  📐  🔀      Image Tools         │ ← Icon toolbar
├────────────────────────────────────────┬────────────────────┤
│  [Format: PNG ▼] [Quality: 85]         │                    │
├────────────────────────────────────────┤  Capacity          │
│                                        │  Calculator        │
│    ┌────────────────────────────┐     │  ──────────────    │
│    │                            │     │                    │
│    │      Drop image here       │     │  Dimensions:       │
│    │         or click           │     │  1920 × 1080       │
│    │                            │     │                    │
│    └────────────────────────────┘     │  LSB Capacity:     │
│                                        │  245 KB            │
│           [image.jpg]                  │                    │
│                                        │  ──────────────    │
│                                        │  [Clear] [Export]  │
└────────────────────────────────────────┴────────────────────┘
      Options + dropzone/preview             Results sidebar
```

- Top ribbon: Icon buttons grouped by category (Analyze | Transform)
- Left panel: Tool options + dropzone/preview (INPUT)
- Right panel: Tool name + results/metadata + actions (OUTPUT)
- Flow: Left → Right (input → output)

**Implementation Tasks:**
- [x] Move inline CSS to style.css
- [x] Build icon toolbar ribbon
- [x] Build two-panel layout structure
- [x] Migrate existing tools (Capacity, EXIF, Strip)
- [x] Add new tools (Rotate, Compress, Convert)
- [ ] Loading spinner on all async operations
- [ ] Toast notifications instead of alerts
- [ ] Consistent color coding (green=analysis, amber=transform)
- [ ] Mobile: stack panels vertically

---

## CLI Improvements

### (Add items here)

---

## Other UI Tweaks

### (Add items here)

