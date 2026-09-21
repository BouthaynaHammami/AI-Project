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
    if (error.response?.status === 409) return 'Cette adresse email est déjà utilisée. Connectez-vous ou choisissez une autre adresse.'
    if (error.response?.status === 401) return 'Vérifiez vos données : adresse email et mot de passe incorrects.'
    if (error.response?.status === 422) return 'Vérifiez vos données : l’adresse email doit être valide et le mot de passe doit contenir au moins 8 caractères.'
    return error.response?.data?.detail ?? 'Une erreur réseau est survenue.'
  }
  return 'Une erreur inattendue est survenue.'
}
