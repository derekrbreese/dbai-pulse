const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

const DEFAULT_TIMEOUT_MS = 30000

async function apiFetch(path, options = {}) {
    const { timeout = DEFAULT_TIMEOUT_MS, signal: externalSignal, ...fetchOptions } = options
    const headers = { ...(fetchOptions.headers || {}) }
    const hasBody = fetchOptions.body !== undefined && fetchOptions.body !== null

    if (hasBody && !headers['Content-Type']) {
        headers['Content-Type'] = 'application/json'
    }

    const controller = new AbortController()
    const timeoutId = setTimeout(() => controller.abort(), timeout)

    // If caller provided an external signal, abort our controller when it fires
    if (externalSignal) {
        if (externalSignal.aborted) {
            controller.abort()
        } else {
            externalSignal.addEventListener('abort', () => controller.abort(), { once: true })
        }
    }

    try {
        const response = await fetch(`${API_BASE_URL}${path}`, {
            ...fetchOptions,
            headers,
            credentials: 'include',
            signal: controller.signal,
        })
        return response
    } catch (err) {
        if (err.name === 'AbortError') {
            throw new Error(externalSignal?.aborted ? 'Request cancelled' : 'Request timed out')
        }
        throw err
    } finally {
        clearTimeout(timeoutId)
    }
}

export { apiFetch, API_BASE_URL }
