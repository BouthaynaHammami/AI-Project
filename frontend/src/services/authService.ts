import { api } from './api'

export type Profile = { id: number; name: string; email: string; profile_photo: string | null; created_at: string }
export type Credentials = { email: string; password: string }
export type SignupPayload = Credentials & { name: string }
export type TokenResponse = { access_token: string; token_type: string }
export type SignupAccepted = { message: string; delivery_mode?: 'email' | 'console' | 'unavailable' | null }

export async function signup(payload: SignupPayload) { const { data } = await api.post<SignupAccepted>('/auth/signup', payload); return data }
export async function login(payload: Credentials) { const { data } = await api.post<TokenResponse>('/auth/login', payload); localStorage.setItem('access_token', data.access_token); return data }
export async function logout() { try { await api.post('/auth/logout') } finally { localStorage.removeItem('access_token') } }
export async function getProfile() { const { data } = await api.get<Profile>('/auth/me'); return data }
export async function updateProfile(payload: { name?: string; email?: string; password?: string; profile_photo?: string | null }) { const { data } = await api.put<Profile>('/auth/me', payload); return data }
export async function deleteAccount(currentPassword: string) {
  const { data } = await api.delete<{ message: string; files_cleanup_pending: number }>('/auth/me', {
    data: { current_password: currentPassword },
  })
  localStorage.removeItem('access_token')
  return data
}
export async function verifyEmail(payload: { email: string; code: string }) {
  const { data } = await api.post<TokenResponse>('/auth/verify-email', payload)
  localStorage.setItem('access_token', data.access_token)
  return data
}
export async function resendVerificationCode(email: string) {
  const { data } = await api.post<SignupAccepted>('/auth/resend-code', { email })
  return data
}
export async function requestPasswordReset(email: string) {
  const { data } = await api.post<SignupAccepted>('/auth/forgot-password', { email })
  return data
}
export async function resetPassword(payload: { email: string; code: string; new_password: string }) {
  const { data } = await api.post<SignupAccepted>('/auth/reset-password', payload)
  return data
}