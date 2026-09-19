import { api } from './api'

export type Profile = { id: number; name: string; email: string; created_at: string }
export type Credentials = { email: string; password: string }
export type SignupPayload = Credentials & { name: string }
export type TokenResponse = { access_token: string; token_type: string }

export async function signup(payload: SignupPayload) { const { data } = await api.post<TokenResponse>('/auth/signup', payload); return data }
export async function login(payload: Credentials) { const { data } = await api.post<TokenResponse>('/auth/login', payload); localStorage.setItem('access_token', data.access_token); return data }
export async function logout() { try { await api.post('/auth/logout') } finally { localStorage.removeItem('access_token') } }
export async function getProfile() { const { data } = await api.get<Profile>('/auth/me'); return data }
export async function updateProfile(payload: { name?: string; email?: string; password?: string }) { const { data } = await api.put<Profile>('/auth/me', payload); return data }