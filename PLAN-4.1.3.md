# Stegasoo 4.1.3 Plan

## Release Theme
Performance and admin features.

---

## 1. DCT Performance Optimizations

**Status:** Planned

**Problem:** DCT encode/decode can be slow on Pi, especially for large images.

**Ideas:**
- Vectorize block processing with NumPy
- Reduce Python loop overhead
- Parallel block processing (multiprocessing?)
- Profile and identify bottlenecks
- Consider Cython for hot paths

---

## 2. User Management UI

**Status:** Planned

**Problem:** No way for admin to manage users via UI. Currently need direct DB access.

**Features:**
- List all users
- Create new user (admin only)
- Delete user (admin only)
- Reset user password
- User activity/last login

---

## Notes

- These are heavier lifts than 4.1.2
- Profile before optimizing
- Consider security implications of user management
