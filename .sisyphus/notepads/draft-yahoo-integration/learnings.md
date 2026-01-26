
## 2026-01-26: Yahoo Integration Implementation
- **YFPY Auth**: Must use `browser_callback=False` and handle OAuth flow manually with `yahoo_access_token_json`.
- **Frontend State**: `useCallback` is essential for `fetch*` functions used in `useEffect` to avoid linter errors and infinite loops.
- **CORS**: Backend redirects work fine with `window.location.href`, but `fetch` follows redirects automatically which can be tricky if you want the browser to redirect.
