import { ArrowLeft, Camera, Check, LockKeyhole, Save, UserRound } from 'lucide-react'
import { useRef, useState } from 'react'
import { useEffect } from 'react'
import { getApiError } from '../services/api'
import { getProfile, updateProfile } from '../services/authService'

type Props = { initialName: string; profilePhoto: string; onBack: () => void; onSaveName: (name: string) => void; onSavePhoto: (photo: string) => void }

const MAX_FILE_SIZE = 2 * 1024 * 1024

export function SettingsPage({ initialName, profilePhoto, onBack, onSaveName, onSavePhoto }: Props) {
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
  return <div className="settings-page"><div className="settings-page-inner"><button className="settings-back" onClick={onBack}><ArrowLeft size={16} /> Retour à l’analyse</button><div className="settings-heading"><div><span className="workspace-kicker">COMPTE UTILISATEUR</span><h1>Paramètres du profil</h1><p>Gérez vos informations personnelles et vos préférences.</p></div><button className="primary-button save-top" onClick={() => void save()} disabled={loading}>{saved ? <><Check size={16} /> Enregistré</> : <><Save size={16} /> {loading ? 'Chargement...' : 'Enregistrer'}</>}</button></div>{error && <div className="error-banner settings-error">{error}</div>}{photoError && <div className="error-banner settings-error">{photoError}</div>}<div className="settings-layout"><section className="settings-card profile-card"><div className="settings-card-heading"><div><span className="section-kicker">VOTRE PROFIL</span><h2>Informations personnelles</h2></div></div><div className="profile-photo-row"><div className={`profile-photo ${photo ? 'profile-photo-filled' : ''}`}>{photo ? <img src={photo} alt="Photo de profil" /> : <UserRound size={30} />}</div><div><strong>Photo de profil</strong><p>JPG ou PNG, 2 Mo maximum.</p><input ref={photoInput} type="file" accept="image/png,image/jpeg" hidden onChange={(event) => { const file = event.target.files?.[0]; choosePhoto(file); if (event.target) event.target.value = '' }} /><button className="photo-button" onClick={() => photoInput.current?.click()}><Camera size={15} /> Changer la photo</button></div></div><label>Nom complet<input value={name} onChange={(event) => { setName(event.target.value); setSaved(false) }} /></label><label>Email professionnel<input type="email" value={email} onChange={(event) => { setEmail(event.target.value); setSaved(false) }} /></label></section><section className="settings-card"><div className="settings-card-heading"><div><span className="section-kicker">SÉCURITÉ</span><h2>Modifier le mot de passe</h2></div><LockKeyhole size={18} /></div><label>Mot de passe actuel<input type="password" placeholder="••••••••" /></label><label>Nouveau mot de passe<input type="password" value={password} onChange={(event) => setPassword(event.target.value)} placeholder="••••••••" /></label><label>Confirmer le nouveau mot de passe<input type="password" value={passwordConfirmation} onChange={(event) => setPasswordConfirmation(event.target.value)} placeholder="••••••••" /></label><p className="password-hint">Utilisez au moins 8 caractères avec un mélange de lettres et de chiffres.</p></section></div></div></div>
}