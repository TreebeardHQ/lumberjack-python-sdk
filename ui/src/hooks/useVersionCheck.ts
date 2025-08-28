import { useEffect, useState, useCallback } from 'react'

export interface VersionInfo {
  current_version: string
  latest_version: string | null
  update_available: boolean
  message: string
  install_info: {
    install_method: string
    install_path: string | null
    is_editable: boolean
    python_executable: string
  }
  upgrade_command: {
    command: string
    description: string
    requires_restart: boolean
  } | null
}

export interface UpgradeResult {
  success: boolean
  message: string
  output?: string
  requires_restart?: boolean
}

export function useVersionCheck(checkInterval: number = 3600000) { // Default: check every hour
  const [versionInfo, setVersionInfo] = useState<VersionInfo | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [isUpgrading, setIsUpgrading] = useState(false)
  const [lastChecked, setLastChecked] = useState<Date | null>(null)

  const checkVersion = useCallback(async () => {
    setIsLoading(true)
    setError(null)
    
    try {
      const response = await fetch('/api/version')
      
      if (!response.ok) {
        throw new Error(`Failed to check version: ${response.statusText}`)
      }
      
      const data: VersionInfo = await response.json()
      setVersionInfo(data)
      setLastChecked(new Date())
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to check version')
      console.error('Version check failed:', err)
    } finally {
      setIsLoading(false)
    }
  }, [])

  const performUpgrade = useCallback(async (): Promise<UpgradeResult> => {
    setIsUpgrading(true)
    setError(null)
    
    try {
      const response = await fetch('/api/upgrade', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
      })
      
      if (!response.ok) {
        throw new Error(`Upgrade failed: ${response.statusText}`)
      }
      
      const result: UpgradeResult = await response.json()
      
      if (result.success) {
        // Re-check version after successful upgrade
        setTimeout(() => checkVersion(), 2000)
      }
      
      return result
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Upgrade failed'
      setError(errorMessage)
      return {
        success: false,
        message: errorMessage,
      }
    } finally {
      setIsUpgrading(false)
    }
  }, [checkVersion])

  // Initial check on mount
  useEffect(() => {
    checkVersion()
  }, [checkVersion])

  // Periodic version checks
  useEffect(() => {
    if (checkInterval > 0) {
      const intervalId = setInterval(() => {
        checkVersion()
      }, checkInterval)
      
      return () => clearInterval(intervalId)
    }
  }, [checkInterval, checkVersion])

  // Check version when window regains focus
  useEffect(() => {
    const handleFocus = () => {
      // Only check if it's been more than 5 minutes since last check
      if (!lastChecked || new Date().getTime() - lastChecked.getTime() > 300000) {
        checkVersion()
      }
    }
    
    window.addEventListener('focus', handleFocus)
    return () => window.removeEventListener('focus', handleFocus)
  }, [checkVersion, lastChecked])

  return {
    versionInfo,
    isLoading,
    error,
    isUpgrading,
    lastChecked,
    checkVersion,
    performUpgrade,
  }
}