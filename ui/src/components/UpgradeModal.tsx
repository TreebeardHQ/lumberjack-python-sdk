import { useState } from 'react'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from './ui/dialog'
import { Button } from './ui/button'
import { AlertCircle, ArrowUpCircle, CheckCircle, XCircle, Terminal, RefreshCw, Sparkles } from 'lucide-react'
import { VersionInfo, UpgradeResult } from '../hooks/useVersionCheck'

interface UpgradeModalProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  versionInfo: VersionInfo
  onUpgrade: () => Promise<UpgradeResult>
}

export function UpgradeModal({
  open,
  onOpenChange,
  versionInfo,
  onUpgrade,
}: UpgradeModalProps) {
  const [isUpgrading, setIsUpgrading] = useState(false)
  const [upgradeResult, setUpgradeResult] = useState<UpgradeResult | null>(null)
  const [showOutput, setShowOutput] = useState(false)

  const handleUpgrade = async () => {
    setIsUpgrading(true)
    setUpgradeResult(null)
    
    try {
      const result = await onUpgrade()
      setUpgradeResult(result)
      
      if (result.success && result.requires_restart) {
        // Show restart message for 3 seconds then close
        setTimeout(() => {
          window.location.reload()
        }, 3000)
      }
    } catch (error) {
      setUpgradeResult({
        success: false,
        message: error instanceof Error ? error.message : 'Upgrade failed',
      })
    } finally {
      setIsUpgrading(false)
    }
  }

  const handleClose = () => {
    if (!isUpgrading) {
      onOpenChange(false)
      setUpgradeResult(null)
      setShowOutput(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="sm:max-w-[600px]">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            {versionInfo.update_available ? (
              <>
                <ArrowUpCircle className="h-5 w-5" />
                Upgrade Lumberjack SDK
              </>
            ) : (
              <>
                <CheckCircle className="h-5 w-5 text-green-600 dark:text-green-400" />
                Lumberjack SDK Version
              </>
            )}
          </DialogTitle>
          <DialogDescription>
            {upgradeResult ? (
              upgradeResult.success ? (
                <div className="mt-4 space-y-4">
                  <div className="flex items-start gap-3">
                    <CheckCircle className="h-5 w-5 text-green-600 dark:text-green-400 mt-0.5" />
                    <div>
                      <p className="font-medium">Upgrade successful!</p>
                      {upgradeResult.requires_restart && (
                        <p className="text-sm mt-1">The server will restart in a few seconds...</p>
                      )}
                    </div>
                  </div>
                </div>
              ) : (
                <div className="mt-4 space-y-4">
                  <div className="flex items-start gap-3">
                    <XCircle className="h-5 w-5 text-red-600 dark:text-red-400 mt-0.5" />
                    <div>
                      <p className="font-medium">Upgrade failed</p>
                      <p className="text-sm mt-1">{upgradeResult.message}</p>
                    </div>
                  </div>
                </div>
              )
            ) : versionInfo.update_available ? (
              <>
                <div className="mt-4 space-y-4">
                  <div className="rounded-lg bg-gray-50 dark:bg-gray-900 p-4 space-y-2">
                    <div className="flex justify-between text-sm">
                      <span className="text-gray-600 dark:text-gray-400">Current Version:</span>
                      <span className="font-mono">{versionInfo.current_version}</span>
                    </div>
                    <div className="flex justify-between text-sm">
                      <span className="text-gray-600 dark:text-gray-400">Latest Version:</span>
                      <span className="font-mono text-green-600 dark:text-green-400">
                        {versionInfo.latest_version}
                      </span>
                    </div>
                    <div className="flex justify-between text-sm">
                      <span className="text-gray-600 dark:text-gray-400">Install Method:</span>
                      <span className="font-mono">{versionInfo.install_info.install_method}</span>
                    </div>
                  </div>

                  {versionInfo.upgrade_command && (
                    <div className="space-y-2">
                      <div className="flex items-center gap-2 text-sm font-medium">
                        <Terminal className="h-4 w-4" />
                        Detected upgrade command:
                      </div>
                      <div className="rounded-lg bg-gray-900 dark:bg-black p-3">
                        <code className="text-xs text-gray-100 break-all">
                          {versionInfo.upgrade_command.command}
                        </code>
                      </div>
                      <p className="text-xs text-gray-500 dark:text-gray-500">
                        Or upgrade by your preferred method manually
                      </p>
                    </div>
                  )}

                  <div className="rounded-lg bg-yellow-50 dark:bg-yellow-950/20 border border-yellow-200 dark:border-yellow-900 p-3">
                    <div className="flex gap-2">
                      <AlertCircle className="h-4 w-4 text-yellow-600 dark:text-yellow-400 shrink-0 mt-0.5" />
                      <div className="text-sm text-yellow-800 dark:text-yellow-200">
                        <p className="font-medium">Important:</p>
                        <ul className="mt-1 space-y-1 list-disc list-inside text-xs">
                          <li>The server will restart after a successful upgrade</li>
                          <li>If in SQLite memory mode, logs will be lost</li>
                          <li>The upgrade may take a few moments to complete</li>
                        </ul>
                      </div>
                    </div>
                  </div>
                </div>
              </>
            ) : (
              <>
                <div className="mt-4 space-y-4">
                  <div className="flex items-start gap-3">
                    <Sparkles className="h-5 w-5 text-green-600 dark:text-green-400 mt-0.5" />
                    <div>
                      <p className="font-medium text-green-800 dark:text-green-200">You're up to date!</p>
                      <p className="text-sm mt-1">You have the latest version installed.</p>
                    </div>
                  </div>
                  
                  <div className="rounded-lg bg-gray-50 dark:bg-gray-900 p-4 space-y-2">
                    <div className="flex justify-between text-sm">
                      <span className="text-gray-600 dark:text-gray-400">Current Version:</span>
                      <span className="font-mono">{versionInfo.current_version}</span>
                    </div>
                    <div className="flex justify-between text-sm">
                      <span className="text-gray-600 dark:text-gray-400">Latest Version:</span>
                      <span className="font-mono">{versionInfo.latest_version || versionInfo.current_version}</span>
                    </div>
                    <div className="flex justify-between text-sm">
                      <span className="text-gray-600 dark:text-gray-400">Install Method:</span>
                      <span className="font-mono">{versionInfo.install_info.install_method}</span>
                    </div>
                    <div className="flex justify-between text-sm">
                      <span className="text-gray-600 dark:text-gray-400">Install Path:</span>
                      <span className="font-mono text-xs break-all">{versionInfo.install_info.install_path}</span>
                    </div>
                  </div>
                </div>
              </>
            )}
          </DialogDescription>
        </DialogHeader>

        {upgradeResult?.output && (
          <div className="mt-4">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setShowOutput(!showOutput)}
              className="mb-2"
            >
              {showOutput ? 'Hide' : 'Show'} Output
            </Button>
            {showOutput && (
              <div className="rounded-lg bg-gray-900 dark:bg-black p-3 max-h-48 overflow-y-auto">
                <pre className="text-xs text-gray-100 whitespace-pre-wrap">
                  {upgradeResult.output}
                </pre>
              </div>
            )}
          </div>
        )}

        <DialogFooter>
          {upgradeResult ? (
            upgradeResult.success ? (
              <div className="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-400">
                <RefreshCw className="h-4 w-4 animate-spin" />
                Restarting...
              </div>
            ) : (
              <Button onClick={handleClose}>Close</Button>
            )
          ) : versionInfo.update_available ? (
            <>
              <Button variant="outline" onClick={handleClose} disabled={isUpgrading}>
                Cancel
              </Button>
              <Button onClick={handleUpgrade} disabled={isUpgrading}>
                {isUpgrading ? (
                  <>
                    <RefreshCw className="animate-spin -ml-1 mr-2 h-4 w-4" />
                    Upgrading...
                  </>
                ) : (
                  <>
                    <ArrowUpCircle className="-ml-1 mr-2 h-4 w-4" />
                    Upgrade Now
                  </>
                )}
              </Button>
            </>
          ) : (
            <Button onClick={handleClose}>Close</Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}