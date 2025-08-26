import { useState, useEffect } from 'react'

export type FontSize = 'small' | 'medium' | 'large'
export type Editor = 'cursor' | 'vscode' | null

interface Settings {
  darkMode: boolean
  fontSize: FontSize
  editor: Editor
}

const DEFAULT_SETTINGS: Settings = {
  darkMode: window.matchMedia('(prefers-color-scheme: dark)').matches,
  fontSize: 'small',
  editor: null
}

const STORAGE_KEY = 'lumberjack-settings'

function loadSettings(): Settings {
  try {
    const stored = localStorage.getItem(STORAGE_KEY)
    if (stored) {
      return { ...DEFAULT_SETTINGS, ...JSON.parse(stored) }
    }
  } catch (error) {
    console.warn('Failed to load settings:', error)
  }
  return DEFAULT_SETTINGS
}

function saveSettings(settings: Settings) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(settings))
  } catch (error) {
    console.warn('Failed to save settings:', error)
  }
}

function applyDarkMode(darkMode: boolean) {
  if (darkMode) {
    document.documentElement.classList.add('dark')
  } else {
    document.documentElement.classList.remove('dark')
  }
}

export function useSettings() {
  const [settings, setSettings] = useState<Settings | null>(null)
  const [loading, setLoading] = useState(true)

  // Load settings on mount
  useEffect(() => {
    const loadedSettings = loadSettings()
    setSettings(loadedSettings)
    applyDarkMode(loadedSettings.darkMode)
    setLoading(false)
  }, [])

  const updateSettings = (updates: Partial<Settings>) => {
    if (!settings) return
    
    const newSettings = { ...settings, ...updates }
    setSettings(newSettings)
    saveSettings(newSettings)
    
    // Apply dark mode immediately if it changed
    if ('darkMode' in updates) {
      applyDarkMode(newSettings.darkMode)
    }
  }

  const setFontSize = (fontSize: FontSize) => {
    updateSettings({ fontSize })
  }

  const toggleDarkMode = () => {
    if (!settings) return
    updateSettings({ darkMode: !settings.darkMode })
  }

  const setEditor = (editor: Editor) => {
    updateSettings({ editor })
  }

  return {
    settings,
    loading,
    setFontSize,
    toggleDarkMode,
    setEditor,
    updateSettings
  }
}