# Stegasoo v4.2 Wishlist

Blue sky ideas for future development. No timeline - just capturing thoughts.

---

## Performance

### GPU-Accelerated DCT Encoding/Decoding
- **Idea**: Leverage GPU for JPEG DCT coefficient manipulation
- **Potential Approaches**:
  - OpenCL/CUDA for parallel DCT operations
  - Raspberry Pi VideoCore IV/VI GPU compute
  - WebGPU for browser-based acceleration
- **Challenges**:
  - jpegio library is CPU-bound (C extension)
  - Would need custom DCT implementation
  - Memory transfer overhead may negate gains for small images
- **Research**:
  - libjpeg-turbo uses SIMD but not GPU
  - nvJPEG (NVIDIA) does GPU-accelerated JPEG
  - Could potentially use GPU for the embedding math, not JPEG decode

---

## Features

(Add ideas here)

---

## Infrastructure

(Add ideas here)

---

## Notes

- This is a living document - add ideas anytime
- Not all ideas will be implemented
- Feasibility research needed before committing to roadmap
