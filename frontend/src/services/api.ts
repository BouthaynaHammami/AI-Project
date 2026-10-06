import axios from 'axios'

export const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL ?? 'http://localhost:8000',
  headers: { 'Content-Type': 'application/json' },
})

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

api.interceptors.response.use((response) => response, (error) => {
  if (error.response?.status === 401) {
    localStorage.removeItem('access_token')
    window.dispatchEvent(new Event('auth:expired'))
  }
  return Promise.reject(error)
})

export const getApiError = (error: unknown) => {
  if (axios.isAxiosError(error)) {
    const isAuthRequest = error.config?.url?.includes('/auth/') ?? false
    if (error.response?.status === 409) return 'Cette adresse email est déjà utilisée. Connectez-vous ou choisissez une autre adresse.'
    if (error.response?.status === 401 && isAuthRequest) return 'Vérifiez vos données : adresse email et mot de passe incorrects.'
    if (error.response?.status === 403 && error.response?.data?.detail === 'EMAIL_NOT_VERIFIED') return 'EMAIL_NOT_VERIFIED'
    if (error.response?.status === 429) {
      const retryAfter = Number(error.response.headers['retry-after'] ?? 60)
      return `Trop de tentatives, réessayez dans ${Number.isFinite(retryAfter) ? retryAfter : 60} secondes`
    }
    if (error.response?.status === 422 && isAuthRequest) {
      const detail = error.response?.data?.detail
      if (Array.isArray(detail) && detail[0]?.msg) {
        const message = String(detail[0].msg).replace(/^Value error,\s*/i, '')
        if (/valid email|email address/i.test(message)) return 'Saisissez une adresse email valide.'
        if (/field required|missing/i.test(message)) return 'Complétez tous les champs obligatoires.'
        return message
      }
      return 'Vérifiez vos données : adresse email ou mot de passe invalide.'
    }
    const detail = error.response?.data?.detail
    if (typeof detail === 'string') return detail
    if (Array.isArray(detail) && detail[0]?.msg) return String(detail[0].msg)
    return 'Une erreur réseau est survenue.'
  }
  return 'Une erreur inattendue est survenue.'
}
