import { ArrowLeft, ArrowRight, BarChart3, Check, LockKeyhole } from 'lucide-react'
import { useEffect, useRef, useState, type FormEvent } from 'react'

type Props = {
  type: 'signup' | 'login'
  onBack: () => void
  onSubmit: (name: string, email: string, password: string) => Promise<void>
  onVerifyEmail: (email: string, code: string) => Promise<void>
  onResendCode: (email: string) => Promise<void>
  onForgotPassword: (email: string) => Promise<void>
  onResetPassword: (email: string, code: string, password: string) => Promise<void>
  onSwitch: (type: 'signup' | 'login') => void
}

type AuthStep = 'credentials' | 'verify-email' | 'forgot-password' | 'reset-password'
const TRIVIAL_PASSWORDS = new Set(['password123', 'password1234', 'qwerty12345', 'azerty12345', '1234567890', 'iloveyou123'])

function passwordStrength(password: string) {
  const score = [
    password.length >= 10,
    /\p{L}/u.test(password),
    /\d/.test(password),
    /[^A-Za-z0-9]/.test(password),
  ].filter(Boolean).length
  return { score, label: score < 2 ? 'Faible' : score < 4 ? 'Moyen' : 'Fort' }
}

export function AuthPage({
  type,
  onBack,
  onSubmit,
  onVerifyEmail,
  onResendCode,
  onForgotPassword,
  onResetPassword,
  onSwitch,
}: Props) {
  const isSignup = type === 'signup'
  const [step, setStep] = useState<AuthStep>('credentials')
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [passwordConfirmation, setPasswordConfirmation] = useState('')
  const [otp, setOtp] = useState(['', '', '', '', '', ''])
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [loading, setLoading] = useState(false)
  const [resendSeconds, setResendSeconds] = useState(0)
  const otpRefs = useRef<Array<HTMLInputElement | null>>([])
  const strength = passwordStrength(password)

  useEffect(() => {
    if (!resendSeconds) return
    const timer = window.setTimeout(() => setResendSeconds((seconds) => seconds - 1), 1000)
    return () => window.clearTimeout(timer)
  }, [resendSeconds])

  const startVerification = async (resend: boolean) => {
    setStep('verify-email')
    setOtp(['', '', '', '', '', ''])
    setResendSeconds(60)
    setError('')
    setNotice(resend ? '' : 'Un code de vérification a été envoyé à votre adresse email.')
    if (resend) {
      try {
        await onResendCode(email.trim())
      } catch (sendError) {
        setError(sendError instanceof Error ? sendError.message : 'Impossible de renvoyer le code.')
      }
    }
  }

  const submitCredentials = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setError('')
    setNotice('')
    if (!email.trim()) {
      setError('Saisissez votre adresse email.')
      return
    }
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim())) {
      setError('Saisissez une adresse email valide.')
      return
    }
    if (!password) {
      setError('Saisissez votre mot de passe.')
      return
    }
    if (isSignup) {
      if (!name.trim()) {
        setError('Le nom complet est obligatoire.')
        return
      }
      if (password.length < 10 || !/\p{L}/u.test(password) || !/\d/.test(password)) {
        setError('Le mot de passe doit contenir au moins 10 caractères, une lettre et un chiffre.')
        return
      }
      if (new TextEncoder().encode(password).length > 72) {
        setError('Le mot de passe ne doit pas dépasser 72 octets.')
        return
      }
      if (TRIVIAL_PASSWORDS.has(password.toLowerCase())) {
        setError('Ce mot de passe est trop facile à deviner.')
        return
      }
      if (!passwordConfirmation) {
        setError('Confirmez votre mot de passe.')
        return
      }
      if (password !== passwordConfirmation) {
        setError('Les mots de passe ne correspondent pas.')
        return
      }
    }

    setLoading(true)
    try {
      await onSubmit(name.trim(), email.trim(), password)
      if (isSignup) await startVerification(false)
    } catch (submitError) {
      const message = submitError instanceof Error ? submitError.message : 'Une erreur est survenue.'
      if (!isSignup && message === 'EMAIL_NOT_VERIFIED') {
        await startVerification(true)
      } else {
        setError(message)
      }
    } finally {
      setLoading(false)
    }
  }

  const verifyCode = async (code: string) => {
    if (code.length !== 6 || loading) return
    setLoading(true)
    setError('')
    try {
      await onVerifyEmail(email.trim(), code)
    } catch (verifyError) {
      setError(verifyError instanceof Error ? verifyError.message : 'Le code est invalide ou expiré.')
      setOtp(['', '', '', '', '', ''])
      otpRefs.current[0]?.focus()
    } finally {
      setLoading(false)
    }
  }

  const changeOtp = (index: number, rawValue: string) => {
    const digits = rawValue.replace(/\D/g, '')
    if (digits.length > 1) {
      const pasted = digits.slice(0, 6).split('')
      const next = ['', '', '', '', '', '']
      pasted.forEach((digit, position) => { next[position] = digit })
      setOtp(next)
      const target = Math.min(pasted.length, 5)
      otpRefs.current[target]?.focus()
      if (pasted.length === 6) void verifyCode(pasted.join(''))
      return
    }

    const next = [...otp]
    next[index] = digits
    setOtp(next)
    if (digits && index < 5) otpRefs.current[index + 1]?.focus()
    if (next.every(Boolean) && step === 'verify-email') void verifyCode(next.join(''))
  }

  const resend = async () => {
    if (resendSeconds || loading) return
    setError('')
    setNotice('')
    setLoading(true)
    try {
      if (step === 'reset-password') await onForgotPassword(email.trim())
      else await onResendCode(email.trim())
      setResendSeconds(60)
      setNotice('Si cette adresse est associée à un compte, un nouveau code a été envoyé.')
    } catch (sendError) {
      setError(sendError instanceof Error ? sendError.message : 'Impossible de renvoyer le code.')
    } finally {
      setLoading(false)
    }
  }

  const requestPasswordReset = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setError('')
    setNotice('')
    setLoading(true)
    try {
      await onForgotPassword(email.trim())
      setStep('reset-password')
      setOtp(['', '', '', '', '', ''])
      setPassword('')
      setPasswordConfirmation('')
      setResendSeconds(60)
      setNotice('Si cette adresse est associée à un compte, un code de réinitialisation a été envoyé.')
    } catch (resetError) {
      setError(resetError instanceof Error ? resetError.message : 'Impossible de traiter la demande.')
    } finally {
      setLoading(false)
    }
  }

  const completePasswordReset = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setError('')
    if (otp.some((digit) => !digit)) {
      setError('Saisissez le code à six chiffres reçu par email.')
      return
    }
    if (password.length < 10 || !/\p{L}/u.test(password) || !/\d/.test(password)) {
      setError('Le mot de passe doit contenir au moins 10 caractères, une lettre et un chiffre.')
      return
    }
    if (new TextEncoder().encode(password).length > 72 || TRIVIAL_PASSWORDS.has(password.toLowerCase())) {
      setError('Choisissez un mot de passe moins facile à deviner et limité à 72 octets.')
      return
    }
    if (password !== passwordConfirmation) {
      setError('Les mots de passe ne correspondent pas.')
      return
    }
    setLoading(true)
    try {
      const code = otp.join('')
      await onResetPassword(email.trim(), code, password)
      setPassword('')
      setPasswordConfirmation('')
      setStep('credentials')
      setNotice('Votre mot de passe a été réinitialisé. Vous pouvez vous connecter.')
      onSwitch('login')
    } catch (resetError) {
      setError(resetError instanceof Error ? resetError.message : 'Impossible de réinitialiser le mot de passe.')
    } finally {
      setLoading(false)
    }
  }

  const title = step === 'verify-email'
    ? 'Vérifier votre email'
    : step === 'forgot-password'
      ? 'Mot de passe oublié ?'
      : step === 'reset-password'
        ? 'Réinitialiser le mot de passe'
        : isSignup ? 'Créer votre espace' : 'Se connecter'
  const intro = step === 'verify-email'
    ? `Saisissez le code à six chiffres envoyé à ${email}.`
    : step === 'forgot-password'
      ? 'Indiquez votre adresse email pour recevoir un code de réinitialisation.'
      : step === 'reset-password'
        ? 'Saisissez le code reçu et choisissez un nouveau mot de passe.'
        : isSignup ? 'Commencez votre analyse en quelques secondes.' : 'Accédez à votre espace d’analyse.'

  return (
    <div className="auth-page">
      <header className="auth-header">
        <button className="brand auth-brand" onClick={onBack}>
          <span className="brand-mark"><BarChart3 size={18} /></span><span>AI Data <b>Analyst</b></span>
        </button>
        <button className="back-link" onClick={onBack}><ArrowLeft size={15} /> Retour à l’accueil</button>
      </header>
      <main className="auth-layout">
        <section className="auth-aside">
          <span className="eyebrow"><span className="eyebrow-line" /> VOTRE ESPACE DATA</span>
          <h1>{isSignup ? 'Donnez une nouvelle dimension à vos données.' : 'Ravi de vous revoir parmi nous.'}</h1>
          <p>{isSignup ? 'Créez votre espace et commencez à transformer vos fichiers en décisions éclairées.' : 'Retrouvez vos analyses, vos questions et vos insights au même endroit.'}</p>
          <div className="auth-trust"><span><Check size={14} /> Analyses instantanées</span><span><LockKeyhole size={14} /> Données sécurisées</span></div>
        </section>
        <section className="auth-card">
          <span className="section-kicker">AI DATA ANALYST</span>
          <h2>{title}</h2>
          <p className="auth-intro">{intro}</p>

          {step === 'credentials' && (
            <form onSubmit={(event) => void submitCredentials(event)}>
              {isSignup && <label>Nom complet<input value={name} onChange={(event) => setName(event.target.value)} placeholder="Votre nom" autoComplete="name" /></label>}
              <label>Email professionnel<input type="email" value={email} onChange={(event) => setEmail(event.target.value)} placeholder="vous@entreprise.com" autoComplete="email" /></label>
              <label>Mot de passe<input type="password" value={password} onChange={(event) => setPassword(event.target.value)} placeholder="••••••••••" autoComplete={isSignup ? 'new-password' : 'current-password'} /></label>
              {isSignup && password && (
                <div className={`password-strength strength-${strength.score}`}>
                  <span className="password-strength-track"><span /></span>
                  <small>Force du mot de passe : {strength.label}</small>
                </div>
              )}
              {isSignup && <label>Confirmer le mot de passe<input type="password" value={passwordConfirmation} onChange={(event) => setPasswordConfirmation(event.target.value)} placeholder="••••••••••" autoComplete="new-password" /></label>}
              {error && <div className="error-banner auth-error">{error}</div>}
              {notice && <p className="auth-notice">{notice}</p>}
              {!isSignup && <button className="auth-text-link forgot-link" type="button" onClick={() => { setError(''); setNotice(''); setStep('forgot-password') }}>Mot de passe oublié ?</button>}
              <button className="primary-button auth-submit" type="submit" disabled={loading}>
                {loading ? 'Veuillez patienter...' : isSignup ? 'Créer mon compte' : 'Se connecter'} <ArrowRight size={16} />
              </button>
              <p className="auth-switch">{isSignup ? 'Vous avez déjà un compte ?' : 'Pas encore de compte ?'} <button type="button" onClick={() => { setError(''); setNotice(''); onSwitch(isSignup ? 'login' : 'signup') }}>{isSignup ? 'Se connecter' : 'Créer un compte'}</button></p>
            </form>
          )}

          {step === 'verify-email' && (
            <div className="auth-flow">
              <div className="otp-inputs" aria-label="Code de vérification à six chiffres">
                {otp.map((digit, index) => (
                  <input
                    key={index}
                    ref={(element) => { otpRefs.current[index] = element }}
                    aria-label={`Chiffre ${index + 1}`}
                    value={digit}
                    inputMode="numeric"
                    autoComplete={index === 0 ? 'one-time-code' : 'off'}
                    maxLength={6}
                    onChange={(event) => changeOtp(index, event.target.value)}
                    onKeyDown={(event) => {
                      if (event.key === 'Backspace' && !digit && index > 0) otpRefs.current[index - 1]?.focus()
                    }}
                  />
                ))}
              </div>
              {error && <div className="error-banner auth-error">{error}</div>}
              {notice && <p className="auth-notice">{notice}</p>}
              <p className="resend-code-row">{resendSeconds > 0 ? `Vous pourrez renvoyer le code dans ${resendSeconds} s` : 'Vous n’avez pas reçu le code ?'} <button className="auth-text-link" disabled={resendSeconds > 0 || loading} onClick={() => void resend()}>Renvoyer le code</button></p>
              <button className="primary-button auth-submit" disabled={loading || otp.some((digit) => !digit)} onClick={() => void verifyCode(otp.join(''))}>{loading ? 'Vérification...' : 'Vérifier mon email'} <ArrowRight size={16} /></button>
              <p className="auth-switch"><button type="button" onClick={() => { setError(''); setNotice(''); setStep('credentials') }}>Retour à la connexion</button></p>
            </div>
          )}

          {step === 'forgot-password' && (
            <form onSubmit={(event) => void requestPasswordReset(event)}>
              <label>Email professionnel<input type="email" value={email} onChange={(event) => setEmail(event.target.value)} placeholder="vous@entreprise.com" autoComplete="email" /></label>
              {error && <div className="error-banner auth-error">{error}</div>}
              <button className="primary-button auth-submit" type="submit" disabled={loading}>{loading ? 'Envoi...' : 'Envoyer un code'} <ArrowRight size={16} /></button>
              <p className="auth-switch"><button type="button" onClick={() => { setError(''); setStep('credentials') }}>Retour à la connexion</button></p>
            </form>
          )}

          {step === 'reset-password' && (
            <form onSubmit={(event) => void completePasswordReset(event)}>
              <div className="otp-inputs" aria-label="Code de réinitialisation à six chiffres">
                {otp.map((digit, index) => (
                  <input
                    key={index}
                    ref={(element) => { otpRefs.current[index] = element }}
                    aria-label={`Chiffre ${index + 1}`}
                    value={digit}
                    inputMode="numeric"
                    autoComplete={index === 0 ? 'one-time-code' : 'off'}
                    maxLength={6}
                    onChange={(event) => changeOtp(index, event.target.value)}
                    onKeyDown={(event) => {
                      if (event.key === 'Backspace' && !digit && index > 0) otpRefs.current[index - 1]?.focus()
                    }}
                  />
                ))}
              </div>
              <label>Nouveau mot de passe<input type="password" value={password} onChange={(event) => setPassword(event.target.value)} autoComplete="new-password" /></label>
              {password && <p className="password-hint">Force du mot de passe : {strength.label}</p>}
              <label>Confirmer le mot de passe<input type="password" value={passwordConfirmation} onChange={(event) => setPasswordConfirmation(event.target.value)} autoComplete="new-password" /></label>
              {error && <div className="error-banner auth-error">{error}</div>}
              {notice && <p className="auth-notice">{notice}</p>}
              <p className="resend-code-row">{resendSeconds > 0 ? `Vous pourrez renvoyer le code dans ${resendSeconds} s` : 'Vous n’avez pas reçu le code ?'} <button className="auth-text-link" type="button" disabled={resendSeconds > 0 || loading} onClick={() => void resend()}>Renvoyer le code</button></p>
              <button className="primary-button auth-submit" type="submit" disabled={loading}>{loading ? 'Réinitialisation...' : 'Réinitialiser le mot de passe'} <ArrowRight size={16} /></button>
            </form>
          )}
        </section>
      </main>
    </div>
  )
}
