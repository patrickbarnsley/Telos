/** One fetch wrapper for the whole app.
 *
 *  Two things it guarantees. Credentials are always included, because the
 *  session is an HttpOnly cookie and not a token in localStorage, which is what
 *  keeps an XSS from walking off with the session. And an error carries the
 *  server's own message, which core/errors.py already wrote for a human, rather
 *  than a status code the UI would have to invent words for.
 */

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
    this.name = 'ApiError'
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(path, {
    credentials: 'include',
    headers: init.body instanceof FormData
      ? undefined
      : { 'Content-Type': 'application/json', ...(init.headers || {}) },
    ...init,
  })

  if (res.status === 204) return undefined as T

  let body: unknown = null
  const text = await res.text()
  if (text) { try { body = JSON.parse(text) } catch { body = text } }

  if (!res.ok) {
    const detail =
      typeof body === 'object' && body !== null && 'detail' in body
        ? String((body as { detail: unknown }).detail)
        : `That did not work (${res.status}).`
    throw new ApiError(res.status, detail)
  }
  return body as T
}

export const api = {
  get: <T>(p: string) => request<T>(p),
  post: <T>(p: string, data?: unknown) =>
    request<T>(p, { method: 'POST', body: data === undefined ? undefined : JSON.stringify(data) }),
  patch: <T>(p: string, data: unknown) =>
    request<T>(p, { method: 'PATCH', body: JSON.stringify(data) }),
  put: <T>(p: string, data?: unknown) =>
    request<T>(p, { method: 'PUT', body: data === undefined ? undefined : JSON.stringify(data) }),
  del: <T>(p: string) => request<T>(p, { method: 'DELETE' }),
  upload: <T>(p: string, form: FormData) => request<T>(p, { method: 'POST', body: form }),
}
