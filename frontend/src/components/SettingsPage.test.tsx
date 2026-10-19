import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { SettingsPage } from './SettingsPage'

const { getProfile, updateProfile, deleteAccount } = vi.hoisted(() => ({
  getProfile: vi.fn(),
  updateProfile: vi.fn(),
  deleteAccount: vi.fn(),
}))

vi.mock('../services/authService', () => ({
  getProfile,
  updateProfile,
  deleteAccount,
}))

const profile = {
  id: 1,
  name: 'Ada Lovelace',
  email: 'ada@example.com',
  profile_photo: null,
  created_at: '2026-01-01T00:00:00Z',
}

const props = () => ({
  initialName: profile.name,
  profilePhoto: '',
  onBack: vi.fn(),
  onSaveName: vi.fn(),
  onSavePhoto: vi.fn(),
  onAccountDeleted: vi.fn(),
})

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('SettingsPage', () => {
  it('saves profile details without treating the unchanged email as a sensitive change', async () => {
    getProfile.mockResolvedValue(profile)
    updateProfile.mockResolvedValue(profile)
    render(<SettingsPage {...props()} />)

    await waitFor(() => expect((screen.getByLabelText('Email professionnel') as HTMLInputElement).value).toBe(profile.email))
    fireEvent.change(screen.getByLabelText('Nom complet'), { target: { value: 'Ada Byron' } })
    fireEvent.click(screen.getByRole('button', { name: 'Enregistrer' }))

    await waitFor(() => expect(updateProfile).toHaveBeenCalledWith({
      name: 'Ada Byron',
      profile_photo: '',
    }))
  })

  it('requires and submits the current password for a password change', async () => {
    getProfile.mockResolvedValue(profile)
    updateProfile.mockResolvedValue(profile)
    render(<SettingsPage {...props()} />)
    await waitFor(() => expect((screen.getByLabelText('Email professionnel') as HTMLInputElement).value).toBe(profile.email))

    fireEvent.change(screen.getByLabelText('Nouveau mot de passe'), { target: { value: 'NewSecure123!' } })
    fireEvent.change(screen.getByLabelText('Confirmer le nouveau mot de passe'), { target: { value: 'NewSecure123!' } })
    fireEvent.click(screen.getByRole('button', { name: 'Enregistrer' }))
    expect(screen.getByRole('alert').textContent).toContain('mot de passe actuel')
    expect(updateProfile).not.toHaveBeenCalled()

    fireEvent.change(screen.getByLabelText('Mot de passe actuel'), { target: { value: 'CurrentSecure123!' } })
    fireEvent.click(screen.getByRole('button', { name: 'Enregistrer' }))
    await waitFor(() => expect(updateProfile).toHaveBeenCalledWith({
      name: profile.name,
      profile_photo: '',
      password: 'NewSecure123!',
      current_password: 'CurrentSecure123!',
    }))
  })

  it('requires the current password when changing the email', async () => {
    getProfile.mockResolvedValue(profile)
    updateProfile.mockResolvedValue({ ...profile, email: 'new@example.com' })
    render(<SettingsPage {...props()} />)
    await waitFor(() => expect((screen.getByLabelText('Email professionnel') as HTMLInputElement).value).toBe(profile.email))

    fireEvent.change(screen.getByLabelText('Email professionnel'), { target: { value: 'new@example.com' } })
    fireEvent.click(screen.getByRole('button', { name: 'Enregistrer' }))
    expect(screen.getByRole('alert').textContent).toContain('mot de passe actuel')
    expect(updateProfile).not.toHaveBeenCalled()

    fireEvent.change(screen.getByLabelText('Mot de passe actuel'), { target: { value: 'CurrentSecure123!' } })
    fireEvent.click(screen.getByRole('button', { name: 'Enregistrer' }))
    await waitFor(() => expect(updateProfile).toHaveBeenCalledWith({
      name: profile.name,
      profile_photo: '',
      email: 'new@example.com',
      current_password: 'CurrentSecure123!',
    }))
  })
})
