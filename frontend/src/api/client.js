const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

async function apiFetch(path, options = {}) {
    const headers = { ...(options.headers || {}) }
    const hasBody = options.body !== undefined && options.body !== null

    if (hasBody && !headers['Content-Type']) {
        headers['Content-Type'] = 'application/json'
    }

    return fetch(`${API_BASE_URL}${path}`, {
        ...options,
        headers,
        credentials: 'include',
    })
}

export { apiFetch, API_BASE_URL }
