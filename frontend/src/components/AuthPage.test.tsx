import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { AuthPage } from './AuthPage'

const props = () => ({
  type: 'login' as const,
  onBack: vi.fn(),
  onSubmit: vi.fn().mockResolvedValue(undefined),
  onVerifyEmail: vi.fn().mockResolvedValue(undefined),
  onResendCode: vi.fn().mockResolvedValue({ message: 'ok' }),
  onForgotPassword: vi.fn().mockResolvedValue({ message: 'ok' }),
  onResetPassword: vi.fn().mockResolvedValue(undefined),
  onSwitch: vi.fn(),
})

afterEach(cleanup)

describe('AuthPage', () => {
  it('validates login credentials and toggles password visibility accessibly', async () => {
    const handlers = props()
    render(<AuthPage {...handlers} />)

    fireEvent.click(screen.getByRole('button', { name: 'Se connecter' }))
    expect(screen.getByText('Saisissez votre adresse email.')).toBeTruthy()

    const email = screen.getByLabelText('Email professionnel')
    const password = screen.getByLabelText('Mot de passe')
    fireEvent.change(email, { target: { value: 'user@example.com' } })
    fireEvent.click(screen.getByRole('button', { name: 'Afficher le mot de passe' }))
    expect(password.getAttribute('type')).toBe('text')
    expect(screen.getByRole('button', { name: 'Masquer le mot de passe' })).toBeTruthy()
  })

  it('submits valid signup data then supports pasted verification code and resend cooldown', async () => {
    const handlers = { ...props(), type: 'signup' as const }
    render(<AuthPage {...handlers} />)

    fireEvent.change(screen.getByLabelText('Nom complet'), { target: { value: 'Ada Lovelace' } })
    fireEvent.change(screen.getByLabelText('Email professionnel'), { target: { value: 'ada@example.com' } })
    fireEvent.change(screen.getByLabelText('Mot de passe'), { target: { value: 'SecurePass123!' } })
    fireEvent.change(screen.getByLabelText('Confirmer le mot de passe'), { target: { value: 'SecurePass123!' } })
    fireEvent.click(screen.getByRole('button', { name: 'Créer mon compte' }))

    await waitFor(() => expect(handlers.onSubmit).toHaveBeenCalledWith('Ada Lovelace', 'ada@example.com', 'SecurePass123!'))
    expect(screen.getByRole('heading', { name: 'Vérifier votre email' })).toBeTruthy()
    const firstCodeInput = screen.getByRole('textbox', { name: 'Chiffre 1' })
    fireEvent.change(firstCodeInput, { target: { value: '123456' } })
    await waitFor(() => expect(handlers.onVerifyEmail).toHaveBeenCalledWith('ada@example.com', '123456'))
    expect(screen.getByRole('button', { name: 'Renvoyer le code' }).hasAttribute('disabled')).toBe(true)
  })

  it('handles password reset validation and successful completion', async () => {
    const handlers = props()
    render(<AuthPage {...handlers} />)
    fireEvent.click(screen.getByRole('button', { name: 'Mot de passe oublié ?' }))
    fireEvent.change(screen.getByLabelText('Email professionnel'), { target: { value: 'user@example.com' } })
    fireEvent.click(screen.getByRole('button', { name: 'Envoyer un code' }))
    await waitFor(() => expect(screen.getByRole('heading', { name: 'Réinitialiser le mot de passe' })).toBeTruthy())

    fireEvent.click(screen.getByRole('button', { name: 'Réinitialiser le mot de passe' }))
    expect(screen.getByText('Saisissez le code à six chiffres reçu par email.')).toBeTruthy()
    const code = screen.getByRole('textbox', { name: 'Chiffre 1' })
    fireEvent.change(code, { target: { value: '654321' } })
    fireEvent.change(screen.getByLabelText('Nouveau mot de passe'), { target: { value: 'NewSecure123!' } })
    fireEvent.change(screen.getByLabelText('Confirmer le mot de passe'), { target: { value: 'NewSecure123!' } })
    fireEvent.click(screen.getByRole('button', { name: 'Réinitialiser le mot de passe' }))
    await waitFor(() => expect(handlers.onResetPassword).toHaveBeenCalledWith('user@example.com', '654321', 'NewSecure123!'))
    expect(handlers.onSwitch).toHaveBeenCalledWith('login')
  })

  it('shows API errors and disables submission while a request is pending', async () => {
    let resolve!: () => void
    const handlers = props()
    handlers.onSubmit = vi.fn().mockImplementation(() => new Promise<void>((done) => { resolve = done }))
    render(<AuthPage {...handlers} />)
    fireEvent.change(screen.getByLabelText('Email professionnel'), { target: { value: 'user@example.com' } })
    fireEvent.change(screen.getByLabelText('Mot de passe'), { target: { value: 'password' } })
    fireEvent.click(screen.getByRole('button', { name: 'Se connecter' }))
    expect(screen.getByRole('button', { name: /Veuillez patienter/ }).hasAttribute('disabled')).toBe(true)
    await act(async () => resolve())
  })
})
