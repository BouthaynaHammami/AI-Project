import { afterEach, describe, expect, it, vi } from 'vitest'

const api = vi.hoisted(() => ({
  post: vi.fn(),
  get: vi.fn(),
  put: vi.fn(),
  delete: vi.fn(),
}))
vi.mock('./api', () => ({ api }))

import { deleteAccount, login, logout, resetPassword, signup } from './authService'
import { getDatasetPreview, updatePiiPreferences, uploadFiles } from './fileService'

afterEach(() => {
  vi.clearAllMocks()
  localStorage.clear()
})

describe('service HTTP contracts', () => {
  it('persists login tokens and clears them on logout', async () => {
    api.post.mockResolvedValueOnce({ data: { access_token: 'token', token_type: 'bearer' } })
    await login({ email: 'a@example.com', password: 'secret' })
    expect(api.post).toHaveBeenCalledWith('/auth/login', { email: 'a@example.com', password: 'secret' })
    expect(localStorage.getItem('access_token')).toBe('token')
    api.post.mockResolvedValueOnce({ data: {} })
    await logout()
    expect(api.post).toHaveBeenCalledWith('/auth/logout')
    expect(localStorage.getItem('access_token')).toBeNull()
  })

  it('sends auth payloads and account deletion body to the expected endpoints', async () => {
    api.post.mockResolvedValue({ data: { message: 'ok' } })
    await signup({ name: 'Ada', email: 'a@example.com', password: 'secret' })
    await resetPassword({ email: 'a@example.com', code: '123456', new_password: 'new-secret' })
    api.delete.mockResolvedValue({ data: { message: 'deleted', files_cleanup_pending: 0 } })
    await deleteAccount('current-secret')
    expect(api.post).toHaveBeenNthCalledWith(1, '/auth/signup', { name: 'Ada', email: 'a@example.com', password: 'secret' })
    expect(api.post).toHaveBeenNthCalledWith(2, '/auth/reset-password', { email: 'a@example.com', code: '123456', new_password: 'new-secret' })
    expect(api.delete).toHaveBeenCalledWith('/auth/me', { data: { current_password: 'current-secret' } })
  })

  it('builds multipart uploads and maps preview ids while preserving PII preferences', async () => {
    api.post.mockResolvedValue({ data: [{ id: 9, filename: 'data.csv' }] })
    const first = new File(['a,b'], 'data.csv', { type: 'text/csv' })
    const second = new File(['a,b'], 'other.csv', { type: 'text/csv' })
    await uploadFiles([first, second])
    const form = api.post.mock.calls[0][1] as FormData
    expect(api.post.mock.calls[0][0]).toBe('/files/upload')
    expect(form.getAll('files')).toEqual([first, second])
    expect(api.post.mock.calls[0][2]).toEqual({ headers: { 'Content-Type': 'multipart/form-data' } })

    api.get.mockResolvedValue({ data: { id: 9, filename: 'data.csv' } })
    const preview = await getDatasetPreview(9)
    expect(api.get).toHaveBeenCalledWith('/files/9/preview')
    expect(preview.dataset_id).toBe(9)
    api.put.mockResolvedValue({ data: { email: 'exclude' } })
    await updatePiiPreferences(9, { email: 'exclude' })
    expect(api.put).toHaveBeenCalledWith('/files/9/pii-preferences', { preferences: { email: 'exclude' } })
  })
})
