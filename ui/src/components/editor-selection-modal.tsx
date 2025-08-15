import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Editor } from "@/hooks/useSettings"
import { Code, ExternalLink } from "lucide-react"

interface EditorSelectionModalProps {
  open: boolean
  onSelect: (editor: Editor) => void
}

export function EditorSelectionModal({ open, onSelect }: EditorSelectionModalProps) {
  return (
    <Dialog open={open} onOpenChange={() => {}}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Code className="h-5 w-5" />
            Choose your preferred editor
          </DialogTitle>
        </DialogHeader>
        <div className="space-y-3">
          <p className="text-sm text-muted-foreground">
            Select your preferred code editor to open files directly from log entries.
          </p>
          <div className="grid gap-2">
            <Button
              onClick={() => onSelect('cursor')}
              className="justify-start gap-2"
              variant="outline"
            >
              <ExternalLink className="h-4 w-4" />
              Cursor
            </Button>
            <Button
              onClick={() => onSelect('vscode')}
              className="justify-start gap-2"
              variant="outline"
            >
              <ExternalLink className="h-4 w-4" />
              Visual Studio Code
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}