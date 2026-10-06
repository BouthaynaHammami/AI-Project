import { api } from './api'

export type Profile = {
  id: number
  name: string
  email: string
  pending_email?: string | null
  profile_photo: string | null
  created_at: string
  email_change_pending?: boolean
  role: 'user' | 'admin'
  monthly_quota: number
  is_active: boolean
}
export type Credentials = { email: string; password: string }
export type SignupPayload = Credentials & { name: string }
export type TokenResponse = { access_token: string; token_type: string }
export type AcceptedResponse = { message: string }

export async function signup(payload: SignupPayload) {
  const { data } = await api.post<AcceptedResponse>('/auth/signup', payload)
  return data
}
export async function login(payload: Credentials) {
  const { data } = await api.post<TokenResponse>('/auth/login', payload, {
    headers: { 'X-Auth-Email': payload.email },
  })
  localStorage.setItem('access_token', data.access_token)
  return data
}
export async function verifyEmail(email: string, code: string) {
  const { data } = await api.post<TokenResponse>('/auth/verify-email', { email, code })
  localStorage.setItem('access_token', data.access_token)
  return data
}
export async function resendCode(email: string) {
  const { data } = await api.post<AcceptedResponse>('/auth/resend-code', { email })
  return data
}
export async function forgotPassword(email: string) {
  const { data } = await api.post<AcceptedResponse>('/auth/forgot-password', { email })
  return data
}
export async function resetPassword(email: string, code: string, newPassword: string) {
  const { data } = await api.post<AcceptedResponse>('/auth/reset-password', {
    email,
    code,
    new_password: newPassword,
  })
  return data
}
export async function logout() {
  try {
    await api.post('/auth/logout')
  } finally {
    localStorage.removeItem('access_token')
  }
}
export async function getProfile() {
  const { data } = await api.get<Profile>('/auth/me')
  return data
}
export async function updateProfile(payload: {
  name?: string
  email?: string
  password?: string
  current_password?: string
  profile_photo?: string | null
}) {
  const { data } = await api.put<Profile>('/auth/me', payload)
  return data
}
