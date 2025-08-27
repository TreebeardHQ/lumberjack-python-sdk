import { useEffect, useCallback, useState } from 'react';

interface UseKeyboardShortcutsProps {
  totalRows: number;
  onNavigateRow: (index: number) => void;
  onToggleDetails: () => void;
  onOpenInEditor: () => void;
  onCopyMessage: () => void;
  onFocusSearch: () => void;
  onClearSearch: () => void;
  onToggleTailing: () => void;
  onScrollToTop: () => void;
  onScrollToBottom: () => void;
  onToggleDarkMode: () => void;
  onShowHelp: () => void;
  isSearchFocused: boolean;
}

export function useKeyboardShortcuts({
  totalRows,
  onNavigateRow,
  onToggleDetails,
  onOpenInEditor,
  onCopyMessage,
  onFocusSearch,
  onClearSearch,
  onToggleTailing,
  onScrollToTop,
  onScrollToBottom,
  onToggleDarkMode,
  onShowHelp,
  isSearchFocused,
}: UseKeyboardShortcutsProps) {
  const [selectedRowIndex, setSelectedRowIndex] = useState<number>(-1);

  // Platform detection for modifier keys
  const isMac = typeof navigator !== 'undefined' && navigator.platform.toUpperCase().indexOf('MAC') >= 0;
  const modifierKey = isMac ? 'metaKey' : 'ctrlKey';

  const handleKeyDown = useCallback((event: KeyboardEvent) => {
    // Don't interfere with input fields (except for specific shortcuts)
    const target = event.target as HTMLElement;
    const isInputFocused = target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.contentEditable === 'true';

    // Handle escape key even when input is focused
    if (event.key === 'Escape') {
      event.preventDefault();
      onClearSearch();
      setSelectedRowIndex(-1);
      return;
    }

    // Handle search focus shortcut
    if ((event.key === '/' || (event[modifierKey as keyof KeyboardEvent] && event.key === 'f')) && !isInputFocused) {
      event.preventDefault();
      onFocusSearch();
      return;
    }

    // Skip other shortcuts when input is focused
    if (isInputFocused && !isSearchFocused) return;

    switch (event.key) {
      case 'ArrowUp':
        if (totalRows > 0) {
          event.preventDefault();
          const newIndex = selectedRowIndex <= 0 ? 0 : selectedRowIndex - 1;
          setSelectedRowIndex(newIndex);
          onNavigateRow(newIndex);
        }
        break;

      case 'ArrowDown':
        if (totalRows > 0) {
          event.preventDefault();
          const newIndex = selectedRowIndex >= totalRows - 1 ? totalRows - 1 : selectedRowIndex + 1;
          setSelectedRowIndex(newIndex);
          onNavigateRow(newIndex);
        }
        break;

      case 'Enter':
        if (selectedRowIndex >= 0) {
          event.preventDefault();
          onToggleDetails();
        }
        break;

      case 'o':
      case 'O':
        if (selectedRowIndex >= 0 && !isInputFocused) {
          event.preventDefault();
          onOpenInEditor();
        }
        break;

      case 'c':
      case 'C':
        if (selectedRowIndex >= 0 && !isInputFocused) {
          event.preventDefault();
          onCopyMessage();
        }
        break;

      case ' ':
        if (!isInputFocused) {
          event.preventDefault();
          onToggleTailing();
        }
        break;

      case 'Home':
        event.preventDefault();
        onScrollToTop();
        if (totalRows > 0) {
          setSelectedRowIndex(0);
          onNavigateRow(0);
        }
        break;

      case 'End':
        event.preventDefault();
        onScrollToBottom();
        if (totalRows > 0) {
          const lastIndex = totalRows - 1;
          setSelectedRowIndex(lastIndex);
          onNavigateRow(lastIndex);
        }
        break;

      case 'j':
        if (!isInputFocused) {
          event.preventDefault();
          // Vim-style: scroll down
          if (totalRows > 0) {
            const newIndex = selectedRowIndex >= totalRows - 1 ? totalRows - 1 : selectedRowIndex + 1;
            setSelectedRowIndex(newIndex);
            onNavigateRow(newIndex);
          }
        }
        break;

      case 'k':
        if (!isInputFocused) {
          event.preventDefault();
          // Vim-style: scroll up
          if (totalRows > 0) {
            const newIndex = selectedRowIndex <= 0 ? 0 : selectedRowIndex - 1;
            setSelectedRowIndex(newIndex);
            onNavigateRow(newIndex);
          }
        }
        break;

      case 'd':
      case 'D':
        if (!isInputFocused) {
          event.preventDefault();
          onToggleDarkMode();
        }
        break;

      case '?':
        if (!isInputFocused) {
          event.preventDefault();
          onShowHelp();
        }
        break;
    }
  }, [
    totalRows,
    selectedRowIndex,
    isSearchFocused,
    modifierKey,
    onNavigateRow,
    onToggleDetails,
    onOpenInEditor,
    onCopyMessage,
    onFocusSearch,
    onClearSearch,
    onToggleTailing,
    onScrollToTop,
    onScrollToBottom,
    onToggleDarkMode,
    onShowHelp,
  ]);

  useEffect(() => {
    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [handleKeyDown]);

  return {
    selectedRowIndex,
    setSelectedRowIndex,
  };
}