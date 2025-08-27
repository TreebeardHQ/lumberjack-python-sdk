import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Badge } from "@/components/ui/badge"
import { Keyboard } from "lucide-react"

interface KeyboardShortcutsHelpProps {
  open: boolean
  onClose: () => void
}

interface ShortcutGroup {
  title: string
  shortcuts: {
    keys: string[]
    description: string
  }[]
}

export function KeyboardShortcutsHelp({ open, onClose }: KeyboardShortcutsHelpProps) {
  const isMac = typeof navigator !== 'undefined' && navigator.platform.toUpperCase().indexOf('MAC') >= 0
  const modKey = isMac ? '⌘' : 'Ctrl'

  const shortcutGroups: ShortcutGroup[] = [
    {
      title: "Row Navigation",
      shortcuts: [
        { keys: ["↑", "↓"], description: "Navigate between log rows" },
        { keys: ["j", "k"], description: "Navigate up/down (vim-style)" },
        { keys: ["Enter"], description: "Toggle row details" },
        { keys: ["Home"], description: "Go to first row" },
        { keys: ["End"], description: "Go to last row" },
      ]
    },
    {
      title: "Row Actions",
      shortcuts: [
        { keys: ["o"], description: "Open file in editor" },
        { keys: ["c"], description: "Copy log message" },
      ]
    },
    {
      title: "Search & Filtering",
      shortcuts: [
        { keys: ["/"], description: "Focus search input" },
        { keys: [modKey, "F"], description: "Focus search input" },
        { keys: ["Escape"], description: "Clear search & deselect row" },
      ]
    },
    {
      title: "View Controls",
      shortcuts: [
        { keys: ["Space"], description: "Toggle log tailing" },
        { keys: ["d"], description: "Toggle dark mode" },
      ]
    },
    {
      title: "Navigation",
      shortcuts: [
        { keys: ["Home"], description: "Scroll to top" },
        { keys: ["End"], description: "Scroll to bottom" },
      ]
    },
    {
      title: "Help",
      shortcuts: [
        { keys: ["?"], description: "Show this help" },
      ]
    }
  ]

  const handleOpenChange = (isOpen: boolean) => {
    if (!isOpen) {
      onClose()
    }
  }

  const renderKeys = (keys: string[]) => {
    return keys.map((key, index) => (
      <span key={index} className="flex items-center">
        {index > 0 && <span className="mx-1 text-muted-foreground">or</span>}
        <Badge variant="outline" className="font-mono text-xs px-2 py-1">
          {key}
        </Badge>
      </span>
    ))
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-2xl max-h-[80vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Keyboard className="h-5 w-5" />
            Keyboard Shortcuts
          </DialogTitle>
        </DialogHeader>
        
        <div className="space-y-6">
          {shortcutGroups.map((group) => (
            <div key={group.title} className="space-y-3">
              <h3 className="font-semibold text-sm text-muted-foreground uppercase tracking-wider">
                {group.title}
              </h3>
              <div className="space-y-2">
                {group.shortcuts.map((shortcut, index) => (
                  <div key={index} className="flex items-center justify-between">
                    <span className="text-sm">{shortcut.description}</span>
                    <div className="flex items-center gap-1">
                      {renderKeys(shortcut.keys)}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ))}
          
          <div className="pt-4 border-t border-border">
            <p className="text-xs text-muted-foreground">
              Note: Most shortcuts are disabled when typing in the search input, except for Escape and {modKey}+F.
            </p>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}