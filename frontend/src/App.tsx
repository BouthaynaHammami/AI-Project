import { ArrowRight, BarChart3, Check, ChevronRight, Database, FileChartColumn, LockKeyhole, Sparkles } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import logoUrl from '../../ai-data-analyst-icon.jpg'
import { AuthPage } from './components/AuthPage'
import { AnalysisBar } from './components/AnalysisBar'
import { AnalysisPage } from './components/AnalysisPage'
import { PublicSharedAnalysis } from './components/PublicSharedAnalysis'
import { AdminPage } from './components/AdminPage'
import { SettingsPage } from './components/SettingsPage'
import { Sidebar } from './components/Sidebar'
import { useDemoData } from './hooks/useDemoData'
import { getApiError } from './services/api'
import {
  forgotPassword,
  getProfile,
  login,
  logout,
  resendCode,
  resetPassword,
  signup,
  verifyEmail,
} from './services/authService'
import { uploadFiles, type DatasetPreview } from './services/fileService'
import { getMyUsage, type UsageSnapshot } from './services/usageService'

function Landing({ onAuth }: { onAuth: (type: 'signup' | 'login') => void }) {
  return <div className="landing"><header className="landing-header"><div className="brand"><img className="landing-logo" src={logoUrl} alt="" /><span>AI Data <b>Analyst</b></span></div><nav><button className="nav-login" onClick={() => onAuth('login')}>Log In</button><button className="nav-signup" onClick={() => onAuth('signup')}>Sign Up <ArrowRight size={15} /></button></nav></header><main className="hero"><div className="hero-copy"><div className="eyebrow"><span className="eyebrow-line" /> ANALYSEZ AVEC CLARTÉ</div><h1>Vos données.<br /><em>Des réponses</em><br />qui comptent.</h1><p>Importez vos données, posez vos questions, obtenez des analyses instantanées grâce à l’IA.</p><div className="trust-line"><span><Check size={14} /> Sans carte bancaire</span><span><LockKeyhole size={14} /> Données sécurisées</span></div></div><div className="hero-visual"><div className="visual-grid" /><div className="floating-card card-main"><div className="card-label"><span className="live-dot" /> ANALYSE EN COURS</div><div className="visual-title">Performance<br /><b>étudiants</b></div><div className="mini-chart"><span style={{ height: '34%' }} /><span style={{ height: '48%' }} /><span style={{ height: '43%' }} /><span style={{ height: '68%' }} /><span style={{ height: '58%' }} /><span style={{ height: '86%' }} /><span style={{ height: '76%' }} /></div><div className="chart-caption"><span>Jan</span><span>Juil</span><strong>+24.8%</strong></div></div><div className="floating-card card-stat"><span className="stat-icon"><Sparkles size={15} /></span><strong>1,204</strong><small>lignes analysées</small></div><div className="floating-card card-question"><span className="question-mark">?</span><span>Pourquoi ce pic<br />en juin ?</span><ChevronRight size={14} /></div></div></main><section className="landing-bottom"><div><Database size={18} /><span><b>Un espace unique</b> pour comprendre vos données</span></div><div><FileChartColumn size={18} /><span><b>Des réponses visuelles</b> en quelques secondes</span></div><div><BarChart3 size={18} /><span><b>Des décisions éclairées</b> par des faits</span></div></section></div>
}

function Analyst({ userName, profilePhoto, isAdmin, onSettings, onLogout, onAdmin }: { userName: string; profilePhoto: string; isAdmin: boolean; onSettings: () => void; onLogout: () => void; onAdmin: () => void }) {
  const historyState = useDemoData()
  const { history, messages, isAnalyzing, askQuestion, loadHistoryEntry, refreshHistory, saveFeedback, clearFeedback, newConversation } = historyState
  const [activeId, setActiveId] = useState(1)
  const [usage, setUsage] = useState<UsageSnapshot | null>(null)
  const [usageError, setUsageError] = useState('')
   const [analysis, setAnalysis] = useState<{ datasets: DatasetPreview[]; question: string; chartConfig: string | null } | null>(null)
  const refreshUsage = useCallback(async () => {
    try {
      setUsage(await getMyUsage())
      setUsageError('')
    } catch (error) {
      setUsageError(getApiError(error))
    }
  }, [])
  useEffect(() => {
    void refreshUsage()
  }, [refreshUsage])
  const reset = () => { setActiveId(0); setAnalysis(null); newConversation() }
  const startNewConversation = () => {
    newConversation()
    setAnalysis((current) => current ? { ...current, question: '', chartConfig: null } : current)
  }
  const initials = userName.split(/\s+/).filter(Boolean).slice(0, 2).map((part) => part[0]).join('').toUpperCase() || 'U'
  const openHistory = async (id: number) => {
    setActiveId(id)
    const selected = await loadHistoryEntry(id)
    if (selected) {
      setAnalysis({ datasets: selected.datasets, question: selected.question, chartConfig: selected.chartConfig })
      return
    }

    await refreshHistory()
    const reloaded = await loadHistoryEntry(id)
    if (reloaded) {
      setAnalysis({ datasets: reloaded.datasets, question: reloaded.question, chartConfig: reloaded.chartConfig })
    }
  }
  const askFromAnalysis = async (question: string, datasetIds?: number[]) => { const answer = await askQuestion(question, datasetIds ?? analysis?.datasets.map((d) => d.dataset_id)); if (answer) { setAnalysis((current) => current ? { ...current, chartConfig: answer.chart_config } : current); void refreshUsage() } }
  const addFilesToAnalysis = async (files: File[]) => {
    const addedDatasets = await uploadFiles(files)
    setAnalysis((current) => current ? { ...current, datasets: [...current.datasets, ...addedDatasets] } : current)
    await refreshHistory()
  }
  const startAnalysis = async (datasets: DatasetPreview[], question: string) => { setAnalysis({ datasets, question, chartConfig: null }); await refreshHistory(); if (datasets.length && question) { const answer = await askQuestion(question, datasets.map((d) => d.dataset_id)); if (answer) { setAnalysis((current) => current ? { ...current, chartConfig: answer.chart_config } : current); void refreshUsage() } } }
  const quotaPercent = usage ? Math.min(100, usage.quota > 0 ? usage.used / usage.quota * 100 : 100) : 0
  return <div className="app-shell"><Sidebar userName={userName} profilePhoto={profilePhoto} history={history} activeId={activeId} query={historyState.query} favoriteOnly={historyState.favoriteOnly} loading={historyState.loadingHistory} hasMore={historyState.hasMore} error={historyState.historyError} undoEntry={historyState.undoEntry} cascadePrompt={historyState.cascadePrompt} onNew={reset} onHistory={(id) => void openHistory(id)} onSettings={onSettings} onLogout={onLogout} onSearch={historyState.search} onLoadMore={historyState.loadMore} onRetry={refreshHistory} onRename={historyState.rename} onToggleFavorite={historyState.toggleFavorite} onRemove={historyState.remove} onUndoRemove={() => void historyState.undoRemove()} onConfirmCascade={() => void historyState.confirmCascadeDelete()} onCancelCascade={historyState.cancelCascadeDelete} /><main className="workspace"><header className="workspace-header"><div><span className="workspace-kicker">ESPACE D’ANALYSE</span><h1>{analysis ? 'Analyse détaillée' : `Bonjour, ${userName}`} <span>{analysis ? '' : '👋'}</span></h1></div><div className="workspace-header-actions">{isAdmin && <button className="admin-nav-button" type="button" onClick={onAdmin}>Administration</button>}<button className="user-chip" onClick={onSettings}><span className={`user-chip-avatar ${profilePhoto ? 'user-chip-avatar-image' : ''}`}>{profilePhoto ? <img src={profilePhoto} alt="Photo de profil" /> : initials}</span><div><strong>{userName}</strong></div></button></div></header><div className="workspace-content">{analysis ? <AnalysisPage datasets={analysis.datasets} firstQuestion={analysis.question} messages={messages} isAnalyzing={isAnalyzing} chartConfig={analysis.chartConfig} onAsk={(question, datasetIds) => void askFromAnalysis(question, datasetIds)} onFeedback={saveFeedback} onClearFeedback={clearFeedback} onNewConversation={startNewConversation} onAddFiles={addFilesToAnalysis} /> : <><div className="page-intro"><div><h2>Nouvelle analyse</h2><p>Transformez une question en décision.</p></div><div>{usageError && <p className="usage-error" role="status">{usageError}</p>}{usage && <div className="usage-meter" title={`Réinitialisation le ${new Date(usage.reset_at).toLocaleDateString('fr-FR')}`}><span className="usage-pill">{usage.used} / {usage.quota} analyses ce mois</span><div className="usage-track" role="progressbar" aria-label="Quota mensuel utilisé" aria-valuemin={0} aria-valuemax={Math.max(usage.quota, 1)} aria-valuenow={usage.used}><span style={{ width: `${quotaPercent}%` }} /></div></div>}</div></div><AnalysisBar onAnalyze={(dataset, question) => void startAnalysis(dataset, question)} /></>}</div></main></div>
}

export default function App() {
  const shareTokenMatch = window.location.pathname.match(/^\/share\/([A-Za-z0-9_-]+)\/?$/)
  const [isLoggedIn, setIsLoggedIn] = useState(Boolean(localStorage.getItem('access_token')))
  const [userName, setUserName] = useState('Utilisateur')
  const [profilePhoto, setProfilePhoto] = useState(localStorage.getItem('user_photo') || '')
  const [userRole, setUserRole] = useState<'user' | 'admin'>('user')
  const [profileLoaded, setProfileLoaded] = useState(false)
  const [authPage, setAuthPage] = useState<'signup' | 'login' | null>(null)
  const [settingsPage, setSettingsPage] = useState(false)
  const [adminPage, setAdminPage] = useState(window.location.pathname === '/admin')

  useEffect(() => {
    const onExpired = () => {
      setIsLoggedIn(false)
      setSettingsPage(false)
      setProfilePhoto('')
      setUserRole('user')
      setProfileLoaded(true)
    }
    window.addEventListener('auth:expired', onExpired)
    if (!shareTokenMatch && localStorage.getItem('access_token')) {
      getProfile()
        .then((profile) => {
          setUserName(profile.name)
          setProfilePhoto(profile.profile_photo || '')
          setUserRole(profile.role)
        })
        .catch(onExpired)
        .finally(() => setProfileLoaded(true))
    } else {
      setProfileLoaded(true)
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
        await signup({ name: name.trim(), email, password })
        return
      }
      await login({ email, password })
      const profile = await getProfile()
      setUserName(profile.name)
      setProfilePhoto(profile.profile_photo || '')
      setUserRole(profile.role)
      setIsLoggedIn(true)
      setAuthPage(null)
    } catch (error) {
      throw new Error(getApiError(error))
    }
  }

  const verifyAuthEmail = async (email: string, code: string) => {
    try {
      await verifyEmail(email, code)
      const profile = await getProfile()
      setUserName(profile.name)
      setProfilePhoto(profile.profile_photo || '')
      setUserRole(profile.role)
      setIsLoggedIn(true)
      setAuthPage(null)
    } catch (error) {
      throw new Error(getApiError(error))
    }
  }

  const authAction = async (action: () => Promise<unknown>) => {
    try {
      await action()
    } catch (error) {
      throw new Error(getApiError(error))
    }
  }

  const signOut = async () => {
    await logout()
    setIsLoggedIn(false)
    setSettingsPage(false)
    setProfilePhoto('')
    setUserRole('user')
    setAdminPage(false)
    window.history.pushState({}, '', '/')
  }

  if (shareTokenMatch) {
    return <PublicSharedAnalysis token={shareTokenMatch[1]} />
  }

  if (isLoggedIn && settingsPage) {
    return (
      <SettingsPage
        initialName={userName}
        profilePhoto={profilePhoto}
        onBack={() => setSettingsPage(false)}
        onSaveName={(name) => {
          setUserName(name)
        }}
        onSavePhoto={setProfilePhoto}
        onPasswordChanged={() => {
          localStorage.removeItem('access_token')
          setIsLoggedIn(false)
          setSettingsPage(false)
          setAuthPage('login')
        }}
      />
    )
  }
  if (isLoggedIn && adminPage) {
    if (!profileLoaded) return <main className="admin-page"><p className="admin-loading">Vérification des droits d’accès…</p></main>
    if (userRole !== 'admin') return <main className="admin-page"><p className="admin-error" role="alert">Accès réservé aux administrateurs.</p></main>
    return <AdminPage onBack={() => { setAdminPage(false); window.history.pushState({}, '', '/') }} />
  }
  if (isLoggedIn) {
    return <Analyst userName={userName} profilePhoto={profilePhoto} isAdmin={userRole === 'admin'} onSettings={() => setSettingsPage(true)} onLogout={signOut} onAdmin={() => { setAdminPage(true); window.history.pushState({}, '', '/admin') }} />
  }
  if (authPage) {
    return (
      <AuthPage
        type={authPage}
        onBack={() => setAuthPage(null)}
        onSubmit={submitAuth}
        onVerifyEmail={verifyAuthEmail}
        onResendCode={(email) => authAction(() => resendCode(email))}
        onForgotPassword={(email) => authAction(() => forgotPassword(email))}
        onResetPassword={(email, code, password) => authAction(() => resetPassword(email, code, password))}
        onSwitch={setAuthPage}
      />
    )
  }
  return <Landing onAuth={setAuthPage} />
}