import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { ShareControls } from './ShareControls'

const shareApi = vi.hoisted(() => ({
  createShareLink: vi.fn(),
  getShareLinks: vi.fn(),
  revokeShareLink: vi.fn(),
}))

vi.mock('../services/analysisService', () => shareApi)

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('ShareControls', () => {
  it('creates a one-time link, copies it, and revokes active links', async () => {
    shareApi.getShareLinks.mockResolvedValue([
      { id: 11, created_at: '2026-10-23T11:00:00Z', expires_at: '2026-10-30T11:00:00Z', view_count: 2 },
    ])
    shareApi.createShareLink.mockResolvedValue({
      id: 12,
      token: 'random-share-token',
      expires_at: '2026-10-30T11:00:00Z',
    })
    shareApi.revokeShareLink.mockResolvedValue(undefined)
    const clipboardWrite = vi.fn().mockResolvedValue(undefined)
    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value: { writeText: clipboardWrite },
    })

    render(<ShareControls analysisId={5} />)
    fireEvent.click(screen.getByRole('button', { name: 'Partager' }))
    await waitFor(() => expect(screen.getByText(/2 consultations/)).toBeTruthy())
    fireEvent.change(screen.getByLabelText('Expiration'), { target: { value: '30' } })
    fireEvent.click(screen.getByRole('button', { name: 'Créer un lien' }))

    await waitFor(() => expect(screen.getByLabelText('Votre lien (affiché uniquement maintenant)')).toBeTruthy())
    expect(shareApi.createShareLink).toHaveBeenCalledWith(5, 30)
    const urlInput = screen.getByLabelText('Votre lien (affiché uniquement maintenant)') as HTMLInputElement
    expect(urlInput.value).toContain('/share/random-share-token')
    fireEvent.click(screen.getByRole('button', { name: 'Copier le lien' }))
    await waitFor(() => expect(clipboardWrite).toHaveBeenCalledWith(urlInput.value))

    fireEvent.click(screen.getByRole('button', { name: /Révoquer le lien/ }))
    await waitFor(() => expect(shareApi.revokeShareLink).toHaveBeenCalledWith(5, 11))
  })
})
