import { ArrowLeft, Camera, Check, LockKeyhole, Save, Trash2, UserRound } from 'lucide-react'
import { useRef, useState } from 'react'
import { useEffect } from 'react'
import { getApiError } from '../services/api'
import { deleteAccount as deleteAccountRequest, getProfile, updateProfile } from '../services/authService'

type Props = {
  initialName: string
  profilePhoto: string
  onBack: () => void
  onSaveName: (name: string) => void
  onSavePhoto: (photo: string) => void
  onAccountDeleted: (filesCleanupPending: number) => void
}

const MAX_FILE_SIZE = 2 * 1024 * 1024

export function SettingsPage({ initialName, profilePhoto, onBack, onSaveName, onSavePhoto, onAccountDeleted }: Props) {
  const photoInput = useRef<HTMLInputElement>(null)
  const [name, setName] = useState(initialName)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [passwordConfirmation, setPasswordConfirmation] = useState('')
  const [photo, setPhoto] = useState(profilePhoto)
  const [saved, setSaved] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [photoError, setPhotoError] = useState('')
  const [showDeleteConfirmation, setShowDeleteConfirmation] = useState(false)
  const [deletePassword, setDeletePassword] = useState('')
  const [deleteConfirmation, setDeleteConfirmation] = useState('')
  const [deletingAccount, setDeletingAccount] = useState(false)

  useEffect(() => {
    getProfile()
      .then((profile) => {
        setName(profile.name)
        setEmail(profile.email)
        if (profilePhoto) setPhoto(profilePhoto)
      })
      .catch((profileError) => setError(getApiError(profileError)))
      .finally(() => setLoading(false))
  }, [profilePhoto])

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

    try {
      const profile = await updateProfile({
        name: name.trim() || initialName,
        email,
        profile_photo: photo,
        ...(password ? { password } : {}),
      })

      onSaveName(profile.name)
      onSavePhoto(profile.profile_photo ?? '')
      setName(profile.name)
      setPassword('')
      setPasswordConfirmation('')
      setSaved(true)
      setTimeout(() => setSaved(false), 2500)
    } catch (saveError) {
      setError(getApiError(saveError))
    }
  }

  const confirmDeleteAccount = async () => {
    setError('')
    if (deleteConfirmation !== 'SUPPRIMER') {
      setError('Saisissez SUPPRIMER pour confirmer la suppression définitive.')
      return
    }
    if (!deletePassword) {
      setError('Saisissez votre mot de passe actuel pour confirmer.')
      return
    }

    setDeletingAccount(true)
    try {
      const result = await deleteAccountRequest(deletePassword)
      onAccountDeleted(result.files_cleanup_pending)
    } catch (deleteError) {
      setError(getApiError(deleteError))
    } finally {
      setDeletingAccount(false)
    }
  }

  return (
    <div className="settings-page">
      <div className="settings-page-inner">
        <button className="settings-back" onClick={onBack}><ArrowLeft size={16} /> Retour à l’analyse</button>
        <div className="settings-heading">
          <div><span className="workspace-kicker">COMPTE UTILISATEUR</span><h1>Paramètres du profil</h1><p>Gérez vos informations personnelles et vos préférences.</p></div>
          <button className="primary-button save-top" onClick={() => void save()} disabled={loading || deletingAccount}>
            {saved ? <><Check size={16} /> Enregistré</> : <><Save size={16} /> {loading ? 'Chargement...' : 'Enregistrer'}</>}
          </button>
        </div>
        {error && <div className="error-banner settings-error" role="alert">{error}</div>}
        {photoError && <div className="error-banner settings-error" role="alert">{photoError}</div>}
        <div className="settings-layout">
          <section className="settings-card profile-card">
            <div className="settings-card-heading"><div><span className="section-kicker">VOTRE PROFIL</span><h2>Informations personnelles</h2></div></div>
            <div className="profile-photo-row">
              <div className={`profile-photo ${photo ? 'profile-photo-filled' : ''}`}>{photo ? <img src={photo} alt="Photo de profil" /> : <UserRound size={30} />}</div>
              <div>
                <strong>Photo de profil</strong><p>JPG ou PNG, 2 Mo maximum.</p>
                <input ref={photoInput} type="file" accept="image/png,image/jpeg" hidden onChange={(event) => { const file = event.target.files?.[0]; choosePhoto(file); if (event.target) event.target.value = '' }} />
                <button className="photo-button" onClick={() => photoInput.current?.click()}><Camera size={15} /> Changer la photo</button>
              </div>
            </div>
            <label>Nom complet<input value={name} onChange={(event) => { setName(event.target.value); setSaved(false) }} /></label>
            <label>Email professionnel<input type="email" value={email} onChange={(event) => { setEmail(event.target.value); setSaved(false) }} /></label>
          </section>
          <section className="settings-card">
            <div className="settings-card-heading"><div><span className="section-kicker">SÉCURITÉ</span><h2>Modifier le mot de passe</h2></div><LockKeyhole size={18} /></div>
            <label>Mot de passe actuel<input type="password" placeholder="••••••••" /></label>
            <label>Nouveau mot de passe<input type="password" value={password} onChange={(event) => setPassword(event.target.value)} placeholder="••••••••" /></label>
            <label>Confirmer le nouveau mot de passe<input type="password" value={passwordConfirmation} onChange={(event) => setPasswordConfirmation(event.target.value)} placeholder="••••••••" /></label>
            <p className="password-hint">Utilisez au moins 8 caractères avec un mélange de lettres et de chiffres.</p>
          </section>
        </div>
        <section className="settings-card danger-zone">
          <div className="settings-card-heading"><div><span className="section-kicker danger-kicker">ZONE DANGEREUSE</span><h2>Supprimer mon compte</h2></div><Trash2 size={18} /></div>
          <p>La suppression est définitive. Votre profil, vos analyses, votre historique et tous vos fichiers importés seront supprimés.</p>
          {!showDeleteConfirmation ? (
            <button className="danger-button" type="button" onClick={() => { setError(''); setShowDeleteConfirmation(true) }}>
              <Trash2 size={16} /> Supprimer mon compte
            </button>
          ) : (
            <div className="delete-account-confirmation">
              <label>Mot de passe actuel<input type="password" value={deletePassword} onChange={(event) => setDeletePassword(event.target.value)} autoComplete="current-password" /></label>
              <label>Saisissez SUPPRIMER pour confirmer<input value={deleteConfirmation} onChange={(event) => setDeleteConfirmation(event.target.value)} autoComplete="off" /></label>
              <div className="delete-account-actions">
                <button className="settings-back" type="button" onClick={() => { setShowDeleteConfirmation(false); setDeletePassword(''); setDeleteConfirmation(''); setError('') }} disabled={deletingAccount}>Annuler</button>
                <button className="danger-button" type="button" onClick={() => void confirmDeleteAccount()} disabled={deletingAccount || loading}>
                  <Trash2 size={16} /> {deletingAccount ? 'Suppression...' : 'Confirmer la suppression'}
                </button>
              </div>
            </div>
          )}
        </section>
      </div>
    </div>
  )
}