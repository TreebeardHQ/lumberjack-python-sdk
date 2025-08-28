import { VersionInfo } from '../hooks/useVersionCheck'

interface UpgradeNotificationProps {
  versionInfo: VersionInfo
  onUpgradeClick: () => void
}

export function UpgradeNotification({
  versionInfo,
  onUpgradeClick,
}: UpgradeNotificationProps) {
  if (!versionInfo.update_available) {
    return null
  }

  return (
    <button
      onClick={onUpgradeClick}
      className="text-xs flex items-center gap-2 px-3 py-1.5 rounded border border-yellow-600 dark:border-yellow-500 bg-yellow-50 dark:bg-yellow-950/30 text-yellow-700 dark:text-yellow-400 hover:bg-yellow-100 dark:hover:bg-yellow-950/50 transition-colors"
      title={`Click to upgrade from v${versionInfo.current_version} to v${versionInfo.latest_version}`}
    >
      <span>v{versionInfo.current_version}</span>
      <span className="text-yellow-600 dark:text-yellow-500">→</span>
      <span className="font-medium">v{versionInfo.latest_version} available</span>
    </button>
  )
}