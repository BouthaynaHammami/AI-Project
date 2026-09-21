import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App'
import './style.css'
import './error-styles.css'

createRoot(document.getElementById('app')!).render(<StrictMode><App /></StrictMode>)