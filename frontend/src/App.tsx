import { ArrowRight, BarChart3, Check, CheckCircle2, ChevronRight, Database, FileChartColumn, LockKeyhole, Sparkles } from 'lucide-react'
import { useEffect, useState } from 'react'
import { AuthPage } from './components/AuthPage'
import { AnalysisBar } from './components/AnalysisBar'
import { AnalysisPage } from './components/AnalysisPage'
import { SettingsPage } from './components/SettingsPage'
import { Sidebar } from './components/Sidebar'
import { PublicSharedAnalysis } from './components/PublicSharedAnalysis'
import { useDemoData } from './hooks/useDemoData'
import { getApiError } from './services/api'
import { getProfile, login, logout, requestPasswordReset, resendVerificationCode, resetPassword, signup, verifyEmail } from './services/authService'
import { uploadFiles, type DatasetPreview } from './services/fileService'

function Landing({ onAuth }: { onAuth: (type: 'signup' | 'login') => void }) {
  return <div className="landing"><header className="landing-header"><div className="brand"><span className="brand-mark"><BarChart3 size={18} /></span><span>AI Data <b>Analyst</b></span></div><nav><button className="nav-login" onClick={() => onAuth('login')}>Log In</button><button className="nav-signup" onClick={() => onAuth('signup')}>Sign Up <ArrowRight size={15} /></button></nav></header><main className="hero"><div className="hero-copy"><div className="eyebrow"><span className="eyebrow-line" /> ANALYSEZ AVEC CLARTÉ</div><h1>Vos données.<br /><em>Des réponses</em><br />qui comptent.</h1><p>Importez vos données, posez vos questions, obtenez des analyses instantanées grâce à l’IA.</p><div className="trust-line"><span><Check size={14} /> Sans carte bancaire</span><span><LockKeyhole size={14} /> Données sécurisées</span></div></div><div className="hero-visual"><div className="visual-grid" /><div className="floating-card card-main"><div className="card-label"><span className="live-dot" /> ANALYSE EN COURS</div><div className="visual-title">Performance<br /><b>étudiants</b></div><div className="mini-chart"><span style={{ height: '34%' }} /><span style={{ height: '48%' }} /><span style={{ height: '43%' }} /><span style={{ height: '68%' }} /><span style={{ height: '58%' }} /><span style={{ height: '86%' }} /><span style={{ height: '76%' }} /></div><div className="chart-caption"><span>Jan</span><span>Juil</span><strong>+24.8%</strong></div></div><div className="floating-card card-stat"><span className="stat-icon"><Sparkles size={15} /></span><strong>1,204</strong><small>lignes analysées</small></div><div className="floating-card card-question"><span className="question-mark">?</span><span>Pourquoi ce pic<br />en juin ?</span><ChevronRight size={14} /></div></div></main><section className="landing-bottom"><div><Database size={18} /><span><b>Un espace unique</b> pour comprendre vos données</span></div><div><FileChartColumn size={18} /><span><b>Des réponses visuelles</b> en quelques secondes</span></div><div><BarChart3 size={18} /><span><b>Des décisions éclairées</b> par des faits</span></div></section></div>
}

function Analyst({ userName, profilePhoto, onSettings, onLogout }: { userName: string; profilePhoto: string; onSettings: () => void; onLogout: () => void }) {
  const {
    history,
    messages,
    isAnalyzing,
    activeConversationId,
    historyError,
    askQuestion,
    createNewConversation,
    updateConversationDatasets,
    loadHistoryEntry,
    refreshHistory,
    remove,
    rename,
    toggleFavorite,
  } = useDemoData()
  const [analysis, setAnalysis] = useState<{ datasets: DatasetPreview[]; question: string; chartConfig: string | null } | null>(null)
  const initials = userName.split(/\s+/).filter(Boolean).slice(0, 2).map((part) => part[0]).join('').toUpperCase() || 'U'
  const startNewConversation = async () => {
    setAnalysis(null)
    await createNewConversation()
  }
  const openHistory = async (id: number) => {
    try {
      const selected = await loadHistoryEntry(id)
      if (selected) {
        setAnalysis({ datasets: selected.datasets, question: selected.question, chartConfig: selected.chartConfig })
      }
    } catch {
      return
    }
  }
  const askFromAnalysis = async (question: string, datasetIds?: number[]) => {
    const selectedDatasetIds = datasetIds ?? analysis?.datasets.map((dataset) => dataset.dataset_id) ?? []
    let conversationId = activeConversationId
    if (conversationId === null) {
      conversationId = await createNewConversation(selectedDatasetIds)
    } else {
      const currentDatasetIds = analysis?.datasets.map((dataset) => dataset.dataset_id) ?? []
      await updateConversationDatasets(conversationId, [...new Set([...currentDatasetIds, ...selectedDatasetIds])])
    }
    const answer = await askQuestion(question, selectedDatasetIds, conversationId)
    if (answer?.chart_config) setAnalysis((current) => current ? { ...current, chartConfig: answer.chart_config } : current)
  }
  const addFilesToAnalysis = async (files: File[]) => {
    const addedDatasets = await uploadFiles(files)
    const updatedDatasets = [...(analysis?.datasets ?? []), ...addedDatasets]
    if (activeConversationId !== null) {
      await updateConversationDatasets(activeConversationId, updatedDatasets.map((dataset) => dataset.dataset_id))
    }
    setAnalysis((current) => current ? { ...current, datasets: [...current.datasets, ...addedDatasets] } : current)
    await refreshHistory()
  }
  const startAnalysis = async (datasets: DatasetPreview[], question: string) => {
    const datasetIds = datasets.map((dataset) => dataset.dataset_id)
    const conversationId = activeConversationId === null
      ? await createNewConversation(datasetIds)
      : activeConversationId
    if (activeConversationId !== null) await updateConversationDatasets(conversationId, datasetIds)
    setAnalysis({ datasets, question, chartConfig: null })
    if (!question.trim()) return
    const answer = await askQuestion(question, datasetIds, conversationId)
    if (answer?.chart_config) setAnalysis((current) => current ? { ...current, chartConfig: answer.chart_config } : current)
  }
  return (
    <div className="app-shell">
      <Sidebar
        userName={userName}
        profilePhoto={profilePhoto}
        history={history}
        activeId={activeConversationId ?? 0}
        error={historyError}
        onRetry={() => void refreshHistory()}
        onNew={() => void startNewConversation().catch(() => undefined)}
        onHistory={(id) => void openHistory(id)}
        onSettings={onSettings}
        onLogout={onLogout}
        onRename={rename}
        onToggleFavorite={toggleFavorite}
        onRemove={remove}
      />
      <main className="workspace">
        <header className="workspace-header">
          <div><span className="workspace-kicker">ESPACE D’ANALYSE</span><h1>{analysis ? 'Analyse détaillée' : `Bonjour, ${userName}`} <span>{analysis ? '📊' : '👋'}</span></h1></div>
          <button className="user-chip" onClick={onSettings}>
            <span className={`user-chip-avatar ${profilePhoto ? 'user-chip-avatar-image' : ''}`}>{profilePhoto ? <img src={profilePhoto} alt="Photo de profil" /> : initials}</span>
            <div><strong>{userName}</strong></div>
          </button>
        </header>
        <div className="workspace-content">
          {analysis
            ? <AnalysisPage datasets={analysis.datasets} firstQuestion={analysis.question} messages={messages} isAnalyzing={isAnalyzing} chartConfig={analysis.chartConfig} onAsk={(question, datasetIds) => void askFromAnalysis(question, datasetIds)} onAddFiles={addFilesToAnalysis} />
            : <><div className="page-intro"><div><h2>Nouvelle analyse</h2><p>Transformez une question en décision.</p></div><span className="usage-pill">12 / 50 analyses ce mois</span></div><AnalysisBar onAnalyze={(dataset, question) => void startAnalysis(dataset, question)} /></>}
        </div>
      </main>
    </div>
  )
}

function AppShell() {
  const [isLoggedIn, setIsLoggedIn] = useState(Boolean(localStorage.getItem('access_token')))
  const [userName, setUserName] = useState('Utilisateur')
  const [profilePhoto, setProfilePhoto] = useState(localStorage.getItem('user_photo') || '')
  const [authPage, setAuthPage] = useState<'signup' | 'login' | null>(null)
  const [settingsPage, setSettingsPage] = useState(false)
  const [accountDeletionNotice, setAccountDeletionNotice] = useState<number | null>(null)

  useEffect(() => {
    const onExpired = () => {
      setIsLoggedIn(false)
      setSettingsPage(false)
      setProfilePhoto('')
    }

    window.addEventListener('auth:expired', onExpired)
    if (localStorage.getItem('access_token')) {
      getProfile()
        .then((profile) => {
          setUserName(profile.name)
          setProfilePhoto(profile.profile_photo || '')
        })
        .catch(onExpired)
    }
    return () => window.removeEventListener('auth:expired', onExpired)
  }, [])

  useEffect(() => {
    if (profilePhoto) localStorage.setItem('user_photo', profilePhoto)
    else localStorage.removeItem('user_photo')
  }, [profilePhoto])

  const submitAuth = async (name: string, email: string, password: string) => {
    try {
      if (authPage === 'signup') {
        return await signup({ name: name.trim(), email, password })
      }
      await login({ email, password })
      const profile = await getProfile()
      setUserName(profile.name)
      setProfilePhoto(profile.profile_photo || '')
      setIsLoggedIn(true)
      setAuthPage(null)
    } catch (error) {
      throw new Error(getApiError(error))
    }
  }

  const signOut = async () => {
    await logout()
    setIsLoggedIn(false)
    setSettingsPage(false)
    setProfilePhoto('')
  }

  if (isLoggedIn && settingsPage) {
    return (
      <SettingsPage
        initialName={userName}
        profilePhoto={profilePhoto}
        onBack={() => setSettingsPage(false)}
        onSaveName={(name) => {
          setUserName(name)
          setSettingsPage(false)
        }}
        onSavePhoto={setProfilePhoto}
        onAccountDeleted={(filesCleanupPending) => {
          setIsLoggedIn(false)
          setSettingsPage(false)
          setUserName('Utilisateur')
          setProfilePhoto('')
          setAccountDeletionNotice(filesCleanupPending)
        }}
      />
    )
  }

  if (isLoggedIn) {
    return <Analyst userName={userName} profilePhoto={profilePhoto} onSettings={() => setSettingsPage(true)} onLogout={signOut} />
  }
  if (authPage) {
    return <AuthPage
      type={authPage}
      onBack={() => setAuthPage(null)}
      onSubmit={submitAuth}
      onVerifyEmail={async (email, code) => {
        await verifyEmail({ email, code })
        const profile = await getProfile()
        setUserName(profile.name)
        setProfilePhoto(profile.profile_photo || '')
        setIsLoggedIn(true)
        setAuthPage(null)
      }}
      onResendCode={resendVerificationCode}
      onForgotPassword={requestPasswordReset}
      onResetPassword={async (email, code, password) => { await resetPassword({ email, code, new_password: password }) }}
      onSwitch={setAuthPage}
    />
  }
  return (
    <>
      <Landing onAuth={setAuthPage} />
      {accountDeletionNotice !== null && (
        <div className="success-modal-backdrop">
          <section className="success-modal" role="dialog" aria-modal="true" aria-labelledby="account-deleted-title">
            <span className="success-modal-icon"><CheckCircle2 size={26} /></span>
            <h2 id="account-deleted-title">Compte supprimé</h2>
            <p>
              Votre compte et ses données ont été supprimés. Vous avez été déconnecté.
              {accountDeletionNotice > 0 && ` ${accountDeletionNotice} fichier(s) importé(s) n’ont pas pu être supprimés du disque.`}
            </p>
            <button className="primary-button" onClick={() => setAccountDeletionNotice(null)}>Retour à l’accueil</button>
          </section>
        </div>
      )}
    </>
  )
}

export default function App() {
  const shareToken = window.location.pathname.match(/^\/share\/([^/]+)$/)?.[1]
  if (shareToken) return <PublicSharedAnalysis token={decodeURIComponent(shareToken)} />
  return <AppShell />
}