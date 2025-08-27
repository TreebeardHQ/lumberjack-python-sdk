import {
  ColumnFiltersState,
  SortingState,
  VisibilityState,
  flexRender,
  getCoreRowModel,
  getFilteredRowModel,
  getSortedRowModel,
  useReactTable,
} from "@tanstack/react-table";
import { useVirtualizer } from "@tanstack/react-virtual";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import {
  Search,
  Pause,
  Play,
  X,
  Moon,
  Sun,
  ArrowDown,
  Code2,
  ChevronUp,
  Loader2,
  Code,
  Copy,
  Keyboard,
  Check,
} from "lucide-react";
import { useState, useEffect, useRef, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useSettings } from "@/hooks/useSettings";
import { useKeyboardShortcuts } from "@/hooks/useKeyboardShortcuts";
import { createShortcutActions } from "@/lib/shortcutActions";
import { EditorSelectionModal } from "@/components/editor-selection-modal";
import { KeyboardShortcutsHelp } from "@/components/KeyboardShortcutsHelp";
import { createColumns } from "./columns";
import { LoadMoreButton } from "./load-more-button";

import type { LogEntry } from "@/types/logs";

interface VirtualizedDataTableProps {
  data: LogEntry[];
  isConnected?: boolean;
  isTailing?: boolean;
  onTailingChange?: (tailing: boolean) => void;
  onLoadMore?: () => void;
  isLoading?: boolean;
  hasMore?: boolean;
}

// Helper function to detect if a log entry has exception information
const hasExceptionData = (attributes: Record<string, any>): boolean => {
  return !!(
    attributes?.["exception.type"] ||
    attributes?.["exception.message"] ||
    attributes?.["exception.stacktrace"]
  );
};

// Function to open file in editor
const openInEditor = (
  filePath: string,
  lineNumber: number | string,
  editor: "cursor" | "vscode"
) => {
  const line =
    typeof lineNumber === "string" ? parseInt(lineNumber) : lineNumber;
  if (isNaN(line)) return;

  let command = "";
  if (editor === "cursor") {
    command = `cursor://file${filePath}:${line}`;
  } else if (editor === "vscode") {
    command = `vscode://file${filePath}:${line}`;
  }

  if (command) {
    try {
      // Use location.href for custom URL schemes to work properly
      window.location.href = command;
    } catch (error) {
      console.error("Failed to open editor:", error);
      // Fallback: try creating a temporary link and clicking it
      const link = document.createElement("a");
      link.href = command;
      link.style.display = "none";
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
    }
  }
};

export function VirtualizedDataTable({
  data,
  isConnected = false,
  isTailing = true,
  onTailingChange,
  onLoadMore,
  isLoading = false,
  hasMore = false,
}: VirtualizedDataTableProps) {
  const [sorting, setSorting] = useState<SortingState>([
    { id: "timestamp", desc: false },
  ]);
  const [columnFilters, setColumnFilters] = useState<ColumnFiltersState>([
    { id: "level", value: ["INFO", "WARNING", "ERROR", "CRITICAL"] },
  ]);
  const [columnVisibility, setColumnVisibility] = useState<VisibilityState>({});
  const [globalFilter, setGlobalFilter] = useState("");
  const [isAtBottom, setIsAtBottom] = useState(true);
  const [isAtTop, setIsAtTop] = useState(true);
  const [scrollWhenTailing, setScrollWhenTailing] = useState(true);
  const [showScrollToTop, setShowScrollToTop] = useState(false);
  const [selectedRow, setSelectedRow] = useState<{
    id: string;
    attributes: Record<string, any>;
  } | null>(null);
  const [showEditorModal, setShowEditorModal] = useState(false);
  const [hoveredRow, setHoveredRow] = useState<string | null>(null);
  const [pendingFileOpen, setPendingFileOpen] = useState<{
    filePath: string;
    lineNumber: string | number;
  } | null>(null);
  const [showHelp, setShowHelp] = useState(false);
  const [copiedButtons, setCopiedButtons] = useState<Set<string>>(new Set());

  const { settings, loading, setFontSize, toggleDarkMode, setEditor } =
    useSettings();

  const parentRef = useRef<HTMLDivElement>(null);
  const searchInputRef = useRef<HTMLInputElement>(null);
  const isProgrammaticScroll = useRef(false);

  const fontSizeClasses = {
    small: "text-[12px]",
    medium: "text-sm",
    large: "text-base",
  };

  const handleCopy = (text: string, buttonId: string) => {
    navigator.clipboard.writeText(text);
    setCopiedButtons((prev) => new Set([...prev, buttonId]));
    setTimeout(() => {
      setCopiedButtons((prev) => {
        const newSet = new Set(prev);
        newSet.delete(buttonId);
        return newSet;
      });
    }, 1500);
  };

  const getColumnWidths = (fontSize: "small" | "medium" | "large") => {
    switch (fontSize) {
      case "small":
        return {
          time: "w-24",
          level: "w-16",
          service: "w-24",
          logger: "w-20",
          trace: "w-16",
        };
      case "medium":
        return {
          time: "w-28",
          level: "w-20",
          service: "w-28",
          logger: "w-24",
          trace: "w-16",
        };
      case "large":
        return {
          time: "w-32",
          level: "w-24",
          service: "w-32",
          logger: "w-28",
          trace: "w-20",
        };
    }
  };

  const handleEditorSelect = (selectedEditor: "cursor" | "vscode" | null) => {
    if (selectedEditor) {
      setEditor(selectedEditor);

      // If we have a pending file to open, open it now
      if (pendingFileOpen) {
        openInEditor(
          pendingFileOpen.filePath,
          pendingFileOpen.lineNumber,
          selectedEditor
        );
        setPendingFileOpen(null);
      }
    }
    setShowEditorModal(false);
  };

  // Create shortcut actions
  const shortcutActions = createShortcutActions(
    parentRef,
    searchInputRef,
    setSelectedRow,
    setGlobalFilter,
    onTailingChange,
    isTailing,
    toggleDarkMode,
    setShowEditorModal,
    setPendingFileOpen,
    setShowHelp
  );

  // Filter helper functions
  const getAllLevels = () => ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"];
  const getAllServices = () =>
    Array.from(new Set(data.map((item) => item.service))).sort();

  const getLevelFilter = () => {
    const levelColumn = table.getColumn("level");
    return levelColumn?.getFilterValue() as string[] | undefined;
  };

  const getServiceFilter = () => {
    const serviceColumn = table.getColumn("service");
    return serviceColumn?.getFilterValue() as string[] | undefined;
  };

  const getActiveLevels = () => {
    const filter = getLevelFilter();
    return filter || getAllLevels();
  };

  const getActiveServices = () => {
    const filter = getServiceFilter();
    return filter || getAllServices();
  };

  const isLevelFilterActive = () => {
    const filter = getLevelFilter();
    return filter && filter.length < getAllLevels().length;
  };

  const isServiceFilterActive = () => {
    const filter = getServiceFilter();
    return filter && filter.length < getAllServices().length;
  };

  const isLevelFilterEmpty = () => {
    const filter = getLevelFilter();
    return filter && filter.length === 0;
  };

  const isServiceFilterEmpty = () => {
    const filter = getServiceFilter();
    return filter && filter.length === 0;
  };

  const removeLevelFilter = (levelToRemove: string) => {
    const levelColumn = table.getColumn("level");
    const currentFilter = getLevelFilter();
    if (currentFilter) {
      const newFilter = currentFilter.filter((l) => l !== levelToRemove);
      levelColumn?.setFilterValue(
        newFilter.length === getAllLevels().length ? undefined : newFilter
      );
    }
  };

  const removeServiceFilter = (serviceToRemove: string) => {
    const serviceColumn = table.getColumn("service");
    const currentFilter = getServiceFilter();
    if (currentFilter) {
      const newFilter = currentFilter.filter((s) => s !== serviceToRemove);
      serviceColumn?.setFilterValue(
        newFilter.length === getAllServices().length ? undefined : newFilter
      );
    }
  };

  const clearAllFilters = () => {
    const levelColumn = table.getColumn("level");
    const serviceColumn = table.getColumn("service");
    levelColumn?.setFilterValue(undefined);
    serviceColumn?.setFilterValue(undefined);
    setGlobalFilter("");
  };

  // Create columns without editor support (we'll handle this in the hover menu)
  const columns = createColumns();

  const table = useReactTable({
    data,
    columns,
    onSortingChange: setSorting,
    onColumnFiltersChange: setColumnFilters,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    onColumnVisibilityChange: setColumnVisibility,
    onGlobalFilterChange: setGlobalFilter,
    globalFilterFn: (row, _columnId, value) => {
      const searchableText = [
        row.original.message,
        row.original.level,
        row.original.service,
        row.original.trace_id,
        row.original.span_id,
        row.original.attributes ? JSON.stringify(row.original.attributes) : "",
      ]
        .join(" ")
        .toLowerCase();

      return searchableText.includes(value.toLowerCase());
    },
    state: {
      sorting,
      columnFilters,
      columnVisibility,
      globalFilter,
    },
  });

  const { rows } = table.getRowModel();

  // Keyboard shortcuts integration
  const { selectedRowIndex, setSelectedRowIndex } = useKeyboardShortcuts({
    totalRows: rows.length,
    onNavigateRow: (index) => {
      const tableRow = index >= 0 && index < rows.length ? rows[index] : null;
      if (!tableRow) return;

      const row = tableRow.original;
      const attributes = row.attributes as Record<string, any>;
      const hasAttributes = attributes && Object.keys(attributes).length > 0;

      // If details are currently open, update them to show the newly selected row
      if (selectedRow && hasAttributes) {
        setSelectedRow({ id: row.id, attributes });
      }

      // Scroll the selected row into view
      if (parentRef.current) {
        const rowHeight = 40; // Approximate row height
        const scrollTop = index * rowHeight;
        const container = parentRef.current;
        const containerHeight = container.clientHeight;
        const currentScrollTop = container.scrollTop;

        // Only scroll if the row is not visible
        if (
          scrollTop < currentScrollTop ||
          scrollTop > currentScrollTop + containerHeight - rowHeight
        ) {
          container.scrollTo({
            top: Math.max(0, scrollTop - containerHeight / 2),
            behavior: "smooth",
          });
        }
      }
    },
    onToggleDetails: () => {
      // Use rows (filtered/sorted) instead of data (raw) to match the visual display
      const tableRow =
        selectedRowIndex >= 0 && selectedRowIndex < rows.length
          ? rows[selectedRowIndex]
          : null;
      if (!tableRow) return;

      const row = tableRow.original;
      const attributes = row.attributes as Record<string, any>;
      const hasAttributes = attributes && Object.keys(attributes).length > 0;

      if (!hasAttributes) return;

      // Toggle details: if already selected, deselect; otherwise select
      if (selectedRow?.id === row.id) {
        setSelectedRow(null);
      } else {
        setSelectedRow({ id: row.id, attributes });
      }
    },
    onOpenInEditor: () => {
      const tableRow =
        selectedRowIndex >= 0 && selectedRowIndex < rows.length
          ? rows[selectedRowIndex]
          : null;
      const row = tableRow?.original || null;
      shortcutActions.openInEditor(row, settings?.editor || null);
    },
    onCopyMessage: () => {
      const tableRow =
        selectedRowIndex >= 0 && selectedRowIndex < rows.length
          ? rows[selectedRowIndex]
          : null;
      const row = tableRow?.original || null;
      shortcutActions.copyMessage(row);
    },
    onFocusSearch: shortcutActions.focusSearch,
    onClearSearch: shortcutActions.clearSearch,
    onToggleTailing: shortcutActions.toggleTailing,
    onScrollToTop: shortcutActions.scrollToTop,
    onScrollToBottom: shortcutActions.scrollToBottom,
    onToggleDarkMode: shortcutActions.toggleDarkMode,
    onShowHelp: shortcutActions.showHelp,
    isSearchFocused: document.activeElement === searchInputRef.current,
  });

  // Virtualization with dynamic sizing
  const rowVirtualizer = useVirtualizer({
    count: rows.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 40, // Just a rough estimate, actual size will be measured
    overscan: 10,
  });

  // Auto scroll to bottom when new data arrives, tailing is enabled, and scrollWhenTailing is true
  useEffect(() => {
    if (
      isTailing &&
      scrollWhenTailing &&
      data.length > 0 &&
      parentRef.current
    ) {
      // Mark this as a programmatic scroll
      isProgrammaticScroll.current = true;

      // Use requestAnimationFrame for better timing with renders
      requestAnimationFrame(() => {
        if (parentRef.current) {
          const element = parentRef.current;
          element.scrollTo({
            top: element.scrollHeight - element.clientHeight,
            behavior: "instant",
          });

          // Reset flag after a short delay to ensure scroll event has fired
          setTimeout(() => {
            isProgrammaticScroll.current = false;
          }, 50);
        }
      });
    }
  }, [data, isTailing, scrollWhenTailing]);

  // Handle scroll for showing scroll buttons and loading more
  const handleScroll = useCallback(
    (e: Event) => {
      const element = e.target as HTMLElement;
      const { scrollTop, scrollHeight, clientHeight } = element;
      const isNearBottom = scrollTop + clientHeight >= scrollHeight - 50;
      const isExactlyAtTop = scrollTop === 0;

      setIsAtBottom(isNearBottom);
      setIsAtTop(isExactlyAtTop);

      // Only update scrollWhenTailing based on user scrolls, not programmatic ones
      if (!isProgrammaticScroll.current) {
        if (isNearBottom) {
          // User scrolled to bottom - enable auto-scroll
          setScrollWhenTailing(true);
        } else {
          // User scrolled up - disable auto-scroll
          setScrollWhenTailing(false);
        }
      }

      setShowScrollToTop(scrollTop > 100);
    },
    [data.length, hasMore, isLoading, onLoadMore]
  );

  useEffect(() => {
    const element = parentRef.current;
    if (element) {
      element.addEventListener("scroll", handleScroll);
      return () => element.removeEventListener("scroll", handleScroll);
    }
  }, [handleScroll]);

  const scrollToBottom = () => {
    if (parentRef.current) {
      const element = parentRef.current;

      // Mark this as a programmatic scroll
      isProgrammaticScroll.current = true;

      // Enable auto-scrolling when user explicitly scrolls to bottom
      setScrollWhenTailing(true);

      // Use instant scroll for immediate response
      element.scrollTo({
        top: element.scrollHeight - element.clientHeight,
        behavior: "instant",
      });

      // Reset flag after scroll completes
      setTimeout(() => {
        isProgrammaticScroll.current = false;
      }, 50);
    }
  };

  const scrollToTop = () => {
    if (parentRef.current) {
      parentRef.current.scrollTo({
        top: 0,
        behavior: "smooth",
      });
    }
  };

  // Don't render if settings are still loading
  if (loading || !settings) {
    return (
      <div className="w-full h-64 flex items-center justify-center">
        Loading...
      </div>
    );
  }

  return (
    <div className="w-full h-full flex flex-col space-y-4">
      {/* Header with controls */}
      <div className="flex-shrink-0 flex items-center justify-between pt-2">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <Badge
              variant={isConnected ? "default" : "destructive"}
              className="text-xs"
            >
              {isConnected ? "Connected" : "Disconnected"}
            </Badge>
            <div className="flex items-center gap-2">
              <Switch checked={isTailing} onCheckedChange={onTailingChange} />
              <span className="text-sm text-muted-foreground flex items-center gap-1">
                {isTailing ? (
                  <Play className="h-3 w-3" />
                ) : (
                  <Pause className="h-3 w-3" />
                )}
                Tailing
              </span>
            </div>
          </div>
          <div className="text-sm text-muted-foreground flex items-center gap-2">
            {data.length} logs
            {isLoading && <Loader2 className="h-3 w-3 animate-spin" />}
          </div>
        </div>

        <div className="flex items-center gap-2">
          {/* Level Filter */}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                variant={isLevelFilterActive() ? "default" : "outline"}
                size="sm"
              >
                {isLevelFilterActive()
                  ? `Level (${getActiveLevels().length}/${
                      getAllLevels().length
                    })`
                  : "Level"}
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="start">
              {["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"].map(
                (level) => {
                  const levelColumn = table.getColumn("level");
                  const currentFilter = levelColumn?.getFilterValue() as
                    | string[]
                    | undefined;
                  const allLevels = [
                    "DEBUG",
                    "INFO",
                    "WARNING",
                    "ERROR",
                    "CRITICAL",
                  ];

                  return (
                    <DropdownMenuCheckboxItem
                      key={level}
                      checked={
                        currentFilter ? currentFilter.includes(level) : true
                      }
                      onCheckedChange={(checked) => {
                        if (!currentFilter) {
                          const newFilter = checked
                            ? allLevels
                            : allLevels.filter((l) => l !== level);
                          levelColumn?.setFilterValue(newFilter);
                        } else {
                          if (checked) {
                            const newFilter = [...currentFilter, level];
                            levelColumn?.setFilterValue(newFilter);
                          } else {
                            const newFilter = currentFilter.filter(
                              (l) => l !== level
                            );
                            levelColumn?.setFilterValue(
                              newFilter.length === allLevels.length
                                ? undefined
                                : newFilter
                            );
                          }
                        }
                      }}
                    >
                      {level}
                    </DropdownMenuCheckboxItem>
                  );
                }
              )}
            </DropdownMenuContent>
          </DropdownMenu>

          {/* Service Filter */}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                variant={isServiceFilterActive() ? "default" : "outline"}
                size="sm"
              >
                {isServiceFilterActive()
                  ? `Service (${getActiveServices().length}/${
                      getAllServices().length
                    })`
                  : "Service"}
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="start">
              {Array.from(new Set(data.map((item) => (item as any).service)))
                .sort()
                .map((service) => {
                  const serviceColumn = table.getColumn("service");
                  const currentFilter = serviceColumn?.getFilterValue() as
                    | string[]
                    | undefined;
                  const allServices = Array.from(
                    new Set(data.map((item) => (item as any).service))
                  ).sort();

                  return (
                    <DropdownMenuCheckboxItem
                      key={service}
                      checked={
                        currentFilter ? currentFilter.includes(service) : true
                      }
                      onCheckedChange={(checked) => {
                        if (!currentFilter) {
                          const newFilter = checked
                            ? allServices
                            : allServices.filter((s) => s !== service);
                          serviceColumn?.setFilterValue(newFilter);
                        } else {
                          if (checked) {
                            const newFilter = [...currentFilter, service];
                            serviceColumn?.setFilterValue(newFilter);
                          } else {
                            const newFilter = currentFilter.filter(
                              (s) => s !== service
                            );
                            serviceColumn?.setFilterValue(
                              newFilter.length === allServices.length
                                ? undefined
                                : newFilter
                            );
                          }
                        }
                      }}
                    >
                      {service}
                    </DropdownMenuCheckboxItem>
                  );
                })}
            </DropdownMenuContent>
          </DropdownMenu>

          {/* Search */}
          <div className="relative">
            <Search className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
            <Input
              ref={searchInputRef}
              placeholder="Search logs..."
              value={globalFilter}
              onChange={(event) => setGlobalFilter(event.target.value)}
              className="pl-10 pr-10 w-80"
            />
            {globalFilter && (
              <button
                onClick={() => setGlobalFilter("")}
                className="absolute right-3 top-3 h-4 w-4 text-muted-foreground hover:text-foreground"
              >
                <X className="h-4 w-4" />
              </button>
            )}
          </div>

          {/* Dark Mode Toggle */}
          <Tooltip>
            <TooltipTrigger asChild>
              <Button variant="outline" size="sm" onClick={toggleDarkMode}>
                {settings.darkMode ? (
                  <Sun className="h-4 w-4" />
                ) : (
                  <Moon className="h-4 w-4" />
                )}
              </Button>
            </TooltipTrigger>
            <TooltipContent className="animate-none">
              <p>
                {settings.darkMode
                  ? "Switch to light mode"
                  : "Switch to dark mode"}
              </p>
            </TooltipContent>
          </Tooltip>

          {/* Editor Selection */}
          <Tooltip>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <TooltipTrigger asChild>
                  <Button variant="outline" size="sm">
                    <Code2 className="h-4 w-4" />
                  </Button>
                </TooltipTrigger>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuCheckboxItem
                  checked={settings.editor === null}
                  onCheckedChange={() => setEditor(null)}
                >
                  None
                </DropdownMenuCheckboxItem>
                <DropdownMenuCheckboxItem
                  checked={settings.editor === "cursor"}
                  onCheckedChange={() => setEditor("cursor")}
                >
                  Cursor
                </DropdownMenuCheckboxItem>
                <DropdownMenuCheckboxItem
                  checked={settings.editor === "vscode"}
                  onCheckedChange={() => setEditor("vscode")}
                >
                  VS Code
                </DropdownMenuCheckboxItem>
              </DropdownMenuContent>
            </DropdownMenu>
            <TooltipContent className="animate-none">
              <p>Select code editor</p>
            </TooltipContent>
          </Tooltip>

          {/* Font Size */}
          <Tooltip>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <TooltipTrigger asChild>
                  <Button variant="outline" size="sm">
                    Aa
                  </Button>
                </TooltipTrigger>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuCheckboxItem
                  checked={settings.fontSize === "small"}
                  onCheckedChange={() => setFontSize("small")}
                >
                  Small
                </DropdownMenuCheckboxItem>
                <DropdownMenuCheckboxItem
                  checked={settings.fontSize === "medium"}
                  onCheckedChange={() => setFontSize("medium")}
                >
                  Medium
                </DropdownMenuCheckboxItem>
                <DropdownMenuCheckboxItem
                  checked={settings.fontSize === "large"}
                  onCheckedChange={() => setFontSize("large")}
                >
                  Large
                </DropdownMenuCheckboxItem>
              </DropdownMenuContent>
            </DropdownMenu>
            <TooltipContent className="animate-none">
              <p>Change font size</p>
            </TooltipContent>
          </Tooltip>

          {/* Keyboard Shortcuts Help */}
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setShowHelp(true)}
              >
                <Keyboard className="h-4 w-4" />
              </Button>
            </TooltipTrigger>
            <TooltipContent className="animate-none">
              <p>Keyboard shortcuts (?)</p>
            </TooltipContent>
          </Tooltip>
        </div>
      </div>

      {/* Active Filter Chips */}
      {(isLevelFilterActive() ||
        isServiceFilterActive() ||
        globalFilter ||
        isLevelFilterEmpty() ||
        isServiceFilterEmpty()) && (
        <div className="flex flex-wrap items-center gap-2 p-2 bg-muted/30 rounded-md">
          <span className="text-sm text-muted-foreground font-medium">
            Active filters:
          </span>

          {/* Level filter chips */}
          {isLevelFilterEmpty() ? (
            <Badge
              variant="destructive"
              className="flex items-center gap-2 pr-1"
            >
              No levels selected
              <button
                onClick={() => {
                  const levelColumn = table.getColumn("level");
                  levelColumn?.setFilterValue(undefined);
                }}
                className="hover:bg-destructive-foreground/20 rounded-full p-1 transition-colors"
              >
                <X className="h-3 w-3" />
              </button>
            </Badge>
          ) : (
            isLevelFilterActive() && (
              <>
                {getActiveLevels().map((level) => (
                  <Badge
                    key={`level-${level}`}
                    variant="secondary"
                    className="flex items-center gap-2 pr-1"
                  >
                    {level}
                    <button
                      onClick={() => removeLevelFilter(level)}
                      className="hover:bg-muted-foreground/20 rounded-full p-1 transition-colors"
                    >
                      <X className="h-3 w-3" />
                    </button>
                  </Badge>
                ))}
              </>
            )
          )}

          {/* Service filter chips */}
          {isServiceFilterEmpty() ? (
            <Badge
              variant="destructive"
              className="flex items-center gap-2 pr-1"
            >
              No services selected
              <button
                onClick={() => {
                  const serviceColumn = table.getColumn("service");
                  serviceColumn?.setFilterValue(undefined);
                }}
                className="hover:bg-destructive-foreground/20 rounded-full p-1 transition-colors"
              >
                <X className="h-3 w-3" />
              </button>
            </Badge>
          ) : (
            isServiceFilterActive() && (
              <>
                {getActiveServices().map((service) => (
                  <Badge
                    key={`service-${service}`}
                    variant="secondary"
                    className="flex items-center gap-2 pr-1"
                  >
                    {service}
                    <button
                      onClick={() => removeServiceFilter(service)}
                      className="hover:bg-muted-foreground/20 rounded-full p-1 transition-colors"
                    >
                      <X className="h-3 w-3" />
                    </button>
                  </Badge>
                ))}
              </>
            )
          )}

          {/* Search filter chip */}
          {globalFilter && (
            <Badge variant="secondary" className="flex items-center gap-2 pr-1">
              Search: "{globalFilter}"
              <button
                onClick={() => setGlobalFilter("")}
                className="hover:bg-muted-foreground/20 rounded-full p-1 transition-colors"
              >
                <X className="h-3 w-3" />
              </button>
            </Badge>
          )}

          {/* Clear all button */}
          <button
            onClick={clearAllFilters}
            className="text-sm text-muted-foreground hover:text-foreground ml-auto"
          >
            Clear all
          </button>
        </div>
      )}

      {/* Virtualized Table */}
      <div className="flex-1 rounded-md border relative min-w-0 overflow-hidden flex">
        <div className="flex-1 overflow-hidden relative">
          <div
            ref={parentRef}
            className="h-full overflow-auto overscroll-contain"
            style={{
              contain: "strict",
            }}
          >
            <div
              style={{
                height: `${rowVirtualizer.getTotalSize()}px`,
              }}
            >
              {/* Table Header */}
              <div className="sticky top-0 z-10 bg-background border-b h-[50px]">
                <div
                  className={`flex ${
                    fontSizeClasses[settings.fontSize]
                  } font-mono`}
                  style={{ minWidth: "100%" }}
                >
                  {table.getHeaderGroups().map((headerGroup) =>
                    headerGroup.headers.map((header, index) => {
                      const columnWidths = getColumnWidths(settings.fontSize);
                      const widthClass =
                        index === 0
                          ? columnWidths.service
                          : index === 1
                          ? columnWidths.time
                          : index === 2
                          ? columnWidths.level
                          : index === 3
                          ? columnWidths.logger
                          : index === 4
                          ? "flex-1 min-w-0"
                          : index === 5
                          ? columnWidths.trace
                          : "";

                      return (
                        <div
                          key={header.id}
                          className={`px-2 py-2 font-medium ${widthClass} flex items-center`}
                        >
                          {header.isPlaceholder
                            ? null
                            : flexRender(
                                header.column.columnDef.header,
                                header.getContext()
                              )}
                        </div>
                      );
                    })
                  )}
                </div>
              </div>
              {/* Load More Button - only show when at top */}
              {hasMore && data.length > 0 && isAtTop && onLoadMore && (
                <LoadMoreButton
                  onLoadMore={onLoadMore}
                  isLoading={isLoading}
                  hasMore={hasMore}
                />
              )}

              {/* Virtualized Rows */}
              {rowVirtualizer.getVirtualItems().map((virtualRow) => {
                const row = rows[virtualRow.index];
                if (!row) return null;

                const attributes = row.original.attributes as Record<
                  string,
                  any
                >;
                const hasAttributes =
                  attributes && Object.keys(attributes).length > 0;
                const isErrorRow = hasExceptionData(attributes);
                const isHovered = hoveredRow === row.id;
                const isKeyboardSelected =
                  selectedRowIndex === virtualRow.index;

                // Check for code file and line information
                const filePath = attributes?.["code.file.path"];
                const lineNumber = attributes?.["code.line.number"];
                const hasCodeInfo =
                  filePath && lineNumber && lineNumber !== false;

                const handleRowClick = () => {
                  if (!hasAttributes) return;

                  // Sync keyboard navigation with mouse click
                  setSelectedRowIndex(virtualRow.index);

                  // Toggle details
                  if (selectedRow?.id === row.id) {
                    setSelectedRow(null);
                  } else {
                    setSelectedRow({ id: row.id, attributes });
                  }
                };

                const handleCodeClick = () => {
                  if (!hasCodeInfo) return;

                  if (!settings?.editor) {
                    // Store the file info for after editor selection
                    setPendingFileOpen({ filePath, lineNumber });
                    setShowEditorModal(true);
                    return;
                  }

                  openInEditor(filePath, lineNumber, settings.editor);
                };

                const handleCopyMessage = () => {
                  const message = row.original.message;
                  navigator.clipboard.writeText(message);
                };

                return (
                  <div
                    key={row.id}
                    style={{
                      position: "absolute",
                      top: 50,
                      left: 0,
                      width: "100%",
                      transform: `translateY(${virtualRow.start}px)`,
                    }}
                    data-index={virtualRow.index}
                    ref={rowVirtualizer.measureElement}
                  >
                    <div
                      className={`relative flex hover:bg-muted/50 border-b border-border/50 items-start py-1 ${
                        fontSizeClasses[settings.fontSize]
                      } font-mono ${hasAttributes ? "cursor-pointer" : ""} ${
                        selectedRow?.id === row.id ? "bg-muted/30" : ""
                      } ${
                        isKeyboardSelected
                          ? "ring-2 ring-primary/50 bg-primary/5"
                          : ""
                      } ${
                        isErrorRow
                          ? "bg-red-50/70 dark:bg-red-950/20 border-red-200/50 dark:border-red-800/30"
                          : ""
                      }`}
                      style={{
                        minWidth: "100%",
                      }}
                      onClick={handleRowClick}
                      onMouseEnter={() => setHoveredRow(row.id)}
                      onMouseLeave={() => setHoveredRow(null)}
                    >
                      {/* Hover Menu */}
                      <AnimatePresence>
                        {(isHovered || isKeyboardSelected) && (
                          <div
                            className={`absolute top-0 bottom-0 flex items-center z-20 ${
                              settings.fontSize === "small"
                                ? "right-20"
                                : settings.fontSize === "medium"
                                ? "right-24"
                                : "right-28"
                            }`}
                          >
                            <div className="flex items-center gap-1">
                              {/* Open in Editor - Now leftmost */}
                              {hasCodeInfo && (
                                <motion.div
                                  initial={{ x: "100%", opacity: 0 }}
                                  animate={{ x: 0, opacity: 1 }}
                                  exit={{ x: "100%", opacity: 0 }}
                                  transition={{
                                    type: "spring",
                                    stiffness: 400,
                                    damping: 40,
                                    mass: 0.8,
                                    delay: 0.1, // Leftmost item gets longer delay to arrive with others
                                  }}
                                  className="bg-background/95 backdrop-blur-sm border border-border/50 rounded-md shadow-lg"
                                >
                                  <Tooltip>
                                    <TooltipTrigger asChild>
                                      <Button
                                        variant="ghost"
                                        size="sm"
                                        onClick={(e) => {
                                          e.stopPropagation();
                                          handleCodeClick();
                                        }}
                                        className="h-7 w-7 p-0 hover:bg-primary/10"
                                      >
                                        <Code className="h-3.5 w-3.5" />
                                      </Button>
                                    </TooltipTrigger>
                                    <TooltipContent
                                      side="top"
                                      className="text-xs px-2 py-1"
                                    >
                                      <p>
                                        {filePath.split("/").pop()}:{lineNumber}{" "}
                                        - Open in editor
                                      </p>
                                    </TooltipContent>
                                  </Tooltip>
                                </motion.div>
                              )}

                              {/* Copy Message - Now rightmost */}
                              <motion.div
                                initial={{ x: "100%", opacity: 0 }}
                                animate={{ x: 0, opacity: 1 }}
                                exit={{ x: "100%", opacity: 0 }}
                                transition={{
                                  type: "spring",
                                  stiffness: 400,
                                  damping: 40,
                                  mass: 0.8,
                                  delay: 0, // Rightmost item starts immediately
                                }}
                                className="bg-background/95 backdrop-blur-sm border border-border/50 rounded-md shadow-lg"
                              >
                                <Tooltip>
                                  <TooltipTrigger asChild>
                                    <Button
                                      variant="ghost"
                                      size="sm"
                                      onClick={(e) => {
                                        e.stopPropagation();
                                        handleCopyMessage();
                                      }}
                                      className="h-7 w-7 p-0 hover:bg-primary/10"
                                    >
                                      <Copy className="h-3.5 w-3.5" />
                                    </Button>
                                  </TooltipTrigger>
                                  <TooltipContent
                                    side="top"
                                    className="text-xs px-2 py-1"
                                  >
                                    <p>Copy message</p>
                                  </TooltipContent>
                                </Tooltip>
                              </motion.div>
                            </div>
                          </div>
                        )}
                      </AnimatePresence>

                      {row.getVisibleCells().map((cell, cellIndex) => {
                        const columnWidths = getColumnWidths(settings.fontSize);
                        const widthClass =
                          cellIndex === 0
                            ? columnWidths.service
                            : cellIndex === 1
                            ? columnWidths.time
                            : cellIndex === 2
                            ? columnWidths.level
                            : cellIndex === 3
                            ? columnWidths.logger
                            : cellIndex === 4
                            ? "flex-1 min-w-0"
                            : cellIndex === 5
                            ? columnWidths.trace
                            : "";

                        return (
                          <div
                            key={cell.id}
                            className={`px-2 py-1 flex items-start ${widthClass} ${
                              cellIndex === 4 ? "break-all" : ""
                            }`}
                          >
                            {flexRender(
                              cell.column.columnDef.cell,
                              cell.getContext()
                            )}
                          </div>
                        );
                      })}
                    </div>
                  </div>
                );
              })}

              {/* No data message */}
              {rows.length === 0 && (
                <div className="flex items-center justify-center h-24 text-center text-muted-foreground">
                  {isConnected
                    ? "No logs yet. Start your application to see logs here! Remember to set LUMBERJACK_LOCAL_SERVER_ENABLED=true in your project environment locally."
                    : "Connecting to log server..."}
                </div>
              )}
            </div>
          </div>

          {/* Scroll Buttons */}
          {showScrollToTop && (
            <button
              onClick={scrollToTop}
              className="absolute top-16 right-4 p-2 bg-primary text-primary-foreground rounded-md shadow-lg hover:bg-primary/90 transition-all duration-200 opacity-80 hover:opacity-100"
              aria-label="Scroll to top"
            >
              <ChevronUp className="h-4 w-4" />
            </button>
          )}

          {!isAtBottom && data.length > 0 && (
            <button
              onClick={scrollToBottom}
              className="absolute bottom-4 right-4 p-2 bg-primary text-primary-foreground rounded-md shadow-lg hover:bg-primary/90 transition-all duration-200 opacity-80 hover:opacity-100"
              aria-label="Scroll to bottom"
            >
              <ArrowDown className="h-4 w-4" />
            </button>
          )}

          {/* Loading indicator for more logs */}
          {isLoading && (
            <div className="absolute top-16 left-1/2 transform -translate-x-1/2 bg-background border rounded-md px-3 py-1 shadow-lg">
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <Loader2 className="h-4 w-4 animate-spin" />
                Loading more logs...
              </div>
            </div>
          )}
        </div>

        {/* Details Panel */}
        {selectedRow && (
          <div className="w-80 border-l bg-background flex-shrink-0">
            <div className="h-full flex flex-col">
              <div className="px-2 py-2 border-b bg-muted/20 h-[50px]">
                <div className="flex items-center justify-between h-full">
                  <h3 className="font-medium text-sm">Log Details</h3>
                  <button
                    onClick={() => setSelectedRow(null)}
                    className="text-muted-foreground hover:text-foreground transition-colors"
                  >
                    <X className="h-4 w-4" />
                  </button>
                </div>
              </div>

              <div className="flex-1 overflow-auto px-4 py-3">
                <div className="space-y-3">
                  {/* Exception Details Section */}
                  {hasExceptionData(selectedRow.attributes) && (
                    <div>
                      <h4 className="font-medium text-sm mb-2 text-red-600 dark:text-red-400">
                        Exception Details
                      </h4>
                      <div className="space-y-2">
                        {selectedRow.attributes["exception.stacktrace"] && (
                          <div>
                            <div className="text-[11px] font-medium text-red-600 dark:text-red-400 mb-1">
                              Stack Trace
                            </div>
                            <div className="relative group">
                              <div className="text-[9px] font-mono bg-red-50 dark:bg-red-950/30 p-2 rounded break-all max-h-48 overflow-y-auto border border-red-200 dark:border-red-800">
                                <pre className="whitespace-pre-wrap">
                                  {
                                    selectedRow.attributes[
                                      "exception.stacktrace"
                                    ]
                                  }
                                </pre>
                              </div>
                              <button
                                onClick={() =>
                                  handleCopy(
                                    selectedRow.attributes[
                                      "exception.stacktrace"
                                    ],
                                    `stacktrace-${selectedRow.id}`
                                  )
                                }
                                className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity bg-background/80 hover:bg-background border rounded p-1"
                              >
                                {copiedButtons.has(
                                  `stacktrace-${selectedRow.id}`
                                ) ? (
                                  <Check className="h-3 w-3 text-green-500" />
                                ) : (
                                  <Copy className="h-3 w-3" />
                                )}
                              </button>
                            </div>
                          </div>
                        )}
                        {selectedRow.attributes["exception.type"] && (
                          <div>
                            <div className="text-[11px] font-medium text-red-600 dark:text-red-400 mb-1">
                              Exception Type
                            </div>
                            <div className="relative group">
                              <div className="text-[11px] font-mono bg-red-50 dark:bg-red-950/30 p-2 rounded break-all border border-red-200 dark:border-red-800">
                                {selectedRow.attributes["exception.type"]}
                              </div>
                              <button
                                onClick={() =>
                                  handleCopy(
                                    selectedRow.attributes["exception.type"],
                                    `exception-type-${selectedRow.id}`
                                  )
                                }
                                className="absolute top-1/2 right-2 -translate-y-1/2 opacity-0 group-hover:opacity-100 transition-opacity bg-background/80 hover:bg-background border rounded p-1"
                              >
                                {copiedButtons.has(
                                  `exception-type-${selectedRow.id}`
                                ) ? (
                                  <Check className="h-3 w-3 text-green-500" />
                                ) : (
                                  <Copy className="h-3 w-3" />
                                )}
                              </button>
                            </div>
                          </div>
                        )}
                        {selectedRow.attributes["exception.message"] && (
                          <div>
                            <div className="text-[11px] font-medium text-red-600 dark:text-red-400 mb-1">
                              Exception Message
                            </div>
                            <div className="relative group">
                              <div className="text-[11px] font-mono bg-red-50 dark:bg-red-950/30 p-2 rounded break-all border border-red-200 dark:border-red-800">
                                {selectedRow.attributes["exception.message"]}
                              </div>
                              <button
                                onClick={() =>
                                  handleCopy(
                                    selectedRow.attributes["exception.message"],
                                    `exception-message-${selectedRow.id}`
                                  )
                                }
                                className="absolute top-1/2 right-2 -translate-y-1/2 opacity-0 group-hover:opacity-100 transition-opacity bg-background/80 hover:bg-background border rounded p-1"
                              >
                                {copiedButtons.has(
                                  `exception-message-${selectedRow.id}`
                                ) ? (
                                  <Check className="h-3 w-3 text-green-500" />
                                ) : (
                                  <Copy className="h-3 w-3" />
                                )}
                              </button>
                            </div>
                          </div>
                        )}
                      </div>
                    </div>
                  )}

                  {/* Regular Attributes Section */}
                  <div>
                    <h4 className="font-medium text-sm mb-2">Attributes</h4>
                    <div className="space-y-2">
                      {Object.entries(selectedRow.attributes)
                        .filter(([key]) => !key.startsWith("exception.")) // Exclude exception attributes
                        .map(([key, value]) => {
                          const valueString =
                            typeof value === "object"
                              ? JSON.stringify(value, null, 2)
                              : String(value);

                          return (
                            <div key={key} className="">
                              <div className="text-[11px] font-medium text-muted-foreground mb-1">
                                {key}
                              </div>
                              <div className="relative group">
                                <div className="text-[11px] font-mono bg-muted p-2 rounded break-all">
                                  {valueString}
                                </div>
                                <button
                                  onClick={() =>
                                    handleCopy(
                                      valueString,
                                      `attr-${key}-${selectedRow.id}`
                                    )
                                  }
                                  className="absolute top-1/2 right-2 -translate-y-1/2 opacity-0 group-hover:opacity-100 transition-opacity bg-background/80 hover:bg-background border rounded p-1"
                                >
                                  {copiedButtons.has(
                                    `attr-${key}-${selectedRow.id}`
                                  ) ? (
                                    <Check className="h-3 w-3 text-green-500" />
                                  ) : (
                                    <Copy className="h-3 w-3" />
                                  )}
                                </button>
                              </div>
                            </div>
                          );
                        })}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Editor Selection Modal */}
      <EditorSelectionModal
        open={showEditorModal}
        onSelect={handleEditorSelect}
        onClose={() => {
          setShowEditorModal(false);
          setPendingFileOpen(null); // Clear pending file if modal is closed without selection
        }}
      />

      {/* Keyboard Shortcuts Help */}
      <KeyboardShortcutsHelp
        open={showHelp}
        onClose={() => setShowHelp(false)}
      />
    </div>
  );
}
