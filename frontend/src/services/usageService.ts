import { api } from './api'

export type UsageSnapshot = {
  used: number
  quota: number
  unit: 'analyses'
  tokens_in: number
  tokens_out: number
  reset_at: string
}

export type AdminUser = {
  id: number
  name: string
  email: string
  role: string
  is_active: boolean
  monthly_quota: number
  analyses_used: number
  tokens_in: number
  tokens_out: number
  last_activity: string | null
}

export type AdminDailyStats = {
  date: string
  analyses: number
  errors: number
  tokens: number
}

export type AdminStats = {
  analyses_today: number
  error_rate: number
  like_rate: number
  tokens_in: number
  tokens_out: number
  daily: AdminDailyStats[]
}

export async function getMyUsage() {
  const { data } = await api.get<UsageSnapshot>('/usage/me')
  return data
}

export async function getAdminUsers() {
  const { data } = await api.get<AdminUser[]>('/admin/users')
  return data
}

export async function updateAdminUser(userId: number, update: { monthly_quota?: number; is_active?: boolean }) {
  const { data } = await api.patch<AdminUser>(`/admin/users/${userId}`, update)
  return data
}

export async function getAdminStats() {
  const { data } = await api.get<AdminStats>('/admin/stats')
  return data
}
