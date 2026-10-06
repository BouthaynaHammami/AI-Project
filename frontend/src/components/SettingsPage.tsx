import { ArrowLeft, Camera, Check, LockKeyhole, Save, UserRound } from 'lucide-react'
import { useRef, useState } from 'react'
import { useEffect } from 'react'
import { getApiError } from '../services/api'
import { getProfile, resendCode, updateProfile, verifyEmail } from '../services/authService'

type Props = {
  initialName: string
  profilePhoto: string
  onBack: () => void
  onSaveName: (name: string) => void
  onSavePhoto: (photo: string) => void
  onPasswordChanged: () => void
}

const MAX_FILE_SIZE = 2 * 1024 * 1024

export function SettingsPage({ initialName, profilePhoto, onBack, onSaveName, onSavePhoto, onPasswordChanged }: Props) {
  const photoInput = useRef<HTMLInputElement>(null)
  const [name, setName] = useState(initialName)
  const [email, setEmail] = useState('')
  const [currentEmail, setCurrentEmail] = useState('')
  const [password, setPassword] = useState('')
  const [passwordConfirmation, setPasswordConfirmation] = useState('')
  const [currentPassword, setCurrentPassword] = useState('')
  const [verificationCode, setVerificationCode] = useState('')
  const [emailVerificationPending, setEmailVerificationPending] = useState(false)
  const [resendSeconds, setResendSeconds] = useState(0)
  const [photo, setPhoto] = useState(profilePhoto)
  const [saved, setSaved] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [photoError, setPhotoError] = useState('')

  useEffect(() => {
    getProfile()
      .then((profile) => {
        setName(profile.name)
        setEmail(profile.pending_email || profile.email)
        setCurrentEmail(profile.pending_email || profile.email)
        setEmailVerificationPending(Boolean(profile.pending_email))
        if (profile.pending_email) setResendSeconds(60)
        if (profilePhoto) setPhoto(profilePhoto)
      })
      .catch((profileError) => setError(getApiError(profileError)))
      .finally(() => setLoading(false))
  }, [profilePhoto])

  useEffect(() => {
    if (!resendSeconds) return
    const timer = window.setTimeout(() => setResendSeconds((seconds) => seconds - 1), 1000)
    return () => window.clearTimeout(timer)
  }, [resendSeconds])

  const choosePhoto = (file?: File) => {
    setPhotoError('')
    if (!file) return

    const allowedTypes = ['image/jpeg', 'image/png']
    if (!allowedTypes.includes(file.type)) {
      setPhotoError('Le fichier doit être une image au format JPG ou PNG.')
      return
    }

    if (file.size > MAX_FILE_SIZE) {
      setPhotoError('La photo doit faire 2 Mo maximum.')
      return
    }

    const reader = new FileReader()
    reader.onload = () => {
      const result = typeof reader.result === 'string' ? reader.result : ''
      setPhoto(result)
      setSaved(false)
    }
    reader.readAsDataURL(file)
  }

  const save = async () => {
    setError('')
    setPhotoError('')

    if (password && password !== passwordConfirmation) {
      setError('Les mots de passe ne correspondent pas.')
      return
    }
    const emailChanged = email.trim().toLowerCase() !== currentEmail.toLowerCase()
    if ((password || emailChanged) && !currentPassword) {
      setError('Saisissez votre mot de passe actuel pour modifier ces informations.')
      return
    }
    if (password && emailChanged) {
      setError('Modifiez votre adresse email et votre mot de passe en deux opérations séparées.')
      return
    }
    if (password && (
      password.length < 10
      || !/\p{L}/u.test(password)
      || !/\d/.test(password)
      || new TextEncoder().encode(password).length > 72
    )) {
      setError('Le mot de passe doit contenir au moins 10 caractères, une lettre et un chiffre (72 octets maximum).')
      return
    }

    try {
      const profile = await updateProfile({
        name: name.trim() || initialName,
        profile_photo: photo,
        ...(emailChanged ? { email: email.trim() } : {}),
        ...(password ? { password } : {}),
        ...((password || emailChanged) ? { current_password: currentPassword } : {}),
      })

      onSaveName(profile.name)
      onSavePhoto(profile.profile_photo ?? '')
      setName(profile.name)
      setEmail(profile.pending_email || profile.email)
      setCurrentEmail(profile.pending_email || profile.email)
      setPassword('')
      setPasswordConfirmation('')
      setCurrentPassword('')
      setEmailVerificationPending(Boolean(profile.pending_email))
      if (profile.pending_email) setResendSeconds(60)
      setSaved(true)
      setTimeout(() => setSaved(false), 2500)
      if (password) onPasswordChanged()
    } catch (saveError) {
      setError(getApiError(saveError))
    }
  }
  const resendEmailCode = async () => {
    setError('')
    try {
      await resendCode(email.trim())
      setResendSeconds(60)
    } catch (resendError) {
      setError(getApiError(resendError))
    }
  }
  const confirmEmailChange = async () => {
    setError('')
    if (!/^\d{6}$/.test(verificationCode)) {
      setError('Saisissez le code de vérification à six chiffres.')
      return
    }
    try {
      await verifyEmail(email.trim(), verificationCode)
      const profile = await getProfile()
      setEmail(profile.email)
      setCurrentEmail(profile.email)
      setEmailVerificationPending(false)
      setVerificationCode('')
      onSaveName(profile.name)
      setSaved(true)
    } catch (verifyError) {
      setError(getApiError(verifyError))
    }
  }
  return <div className="settings-page"><div className="settings-page-inner"><button className="settings-back" onClick={onBack}><ArrowLeft size={16} /> Retour à l’analyse</button><div className="settings-heading"><div><span className="workspace-kicker">COMPTE UTILISATEUR</span><h1>Paramètres du profil</h1><p>Gérez vos informations personnelles et vos préférences.</p></div><button className="primary-button save-top" onClick={() => void save()} disabled={loading}>{saved ? <><Check size={16} /> Enregistré</> : <><Save size={16} /> {loading ? 'Chargement...' : 'Enregistrer'}</>}</button></div>{error && <div className="error-banner settings-error">{error}</div>}{photoError && <div className="error-banner settings-error">{photoError}</div>}{emailVerificationPending && <div className="settings-card email-verification"><p>Un code a été envoyé à <strong>{email}</strong>. Votre ancienne adresse reste active jusqu’à la vérification.</p><label>Code de vérification<input inputMode="numeric" maxLength={6} value={verificationCode} onChange={(event) => setVerificationCode(event.target.value.replace(/\D/g, '').slice(0, 6))} /></label><button className="primary-button" onClick={() => void confirmEmailChange()}>Confirmer la nouvelle adresse</button><p className="resend-code-row">{resendSeconds > 0 ? `Vous pourrez renvoyer le code dans ${resendSeconds} s` : 'Vous n’avez pas reçu le code ?'} <button className="auth-text-link" disabled={resendSeconds > 0} onClick={() => void resendEmailCode()}>Renvoyer le code</button></p></div>}<div className="settings-layout"><section className="settings-card profile-card"><div className="settings-card-heading"><div><span className="section-kicker">VOTRE PROFIL</span><h2>Informations personnelles</h2></div></div><div className="profile-photo-row"><div className={`profile-photo ${photo ? 'profile-photo-filled' : ''}`}>{photo ? <img src={photo} alt="Photo de profil" /> : <UserRound size={30} />}</div><div><strong>Photo de profil</strong><p>JPG ou PNG, 2 Mo maximum.</p><input ref={photoInput} type="file" accept="image/png,image/jpeg" hidden onChange={(event) => { const file = event.target.files?.[0]; choosePhoto(file); if (event.target) event.target.value = '' }} /><button className="photo-button" onClick={() => photoInput.current?.click()}><Camera size={15} /> Changer la photo</button></div></div><label>Nom complet<input value={name} onChange={(event) => { setName(event.target.value); setSaved(false) }} /></label><label>Email professionnel<input type="email" value={email} onChange={(event) => { setEmail(event.target.value); setSaved(false) }} /></label></section><section className="settings-card"><div className="settings-card-heading"><div><span className="section-kicker">SÉCURITÉ</span><h2>Modifier le mot de passe</h2></div><LockKeyhole size={18} /></div><label>Mot de passe actuel<input type="password" value={currentPassword} onChange={(event) => setCurrentPassword(event.target.value)} placeholder="••••••••" autoComplete="current-password" /></label><label>Nouveau mot de passe<input type="password" value={password} onChange={(event) => setPassword(event.target.value)} placeholder="••••••••••" autoComplete="new-password" /></label><label>Confirmer le nouveau mot de passe<input type="password" value={passwordConfirmation} onChange={(event) => setPasswordConfirmation(event.target.value)} placeholder="••••••••••" autoComplete="new-password" /></label><p className="password-hint">Utilisez au moins 10 caractères, avec une lettre et un chiffre.</p></section></div></div></div>
}