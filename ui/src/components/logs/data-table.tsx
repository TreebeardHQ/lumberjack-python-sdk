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

import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
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
  TooltipProvider,
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
} from "lucide-react";
import { useState, useEffect } from "react";
import { useSettings } from "@/hooks/useSettings";
import { EditorSelectionModal } from "@/components/editor-selection-modal";
import { createColumns } from "./columns";

import type { LogEntry } from "@/types/logs";

interface DataTableProps {
  data: LogEntry[];
  isConnected?: boolean;
  isTailing?: boolean;
  onTailingChange?: (tailing: boolean) => void;
}

export function DataTable({
  data,
  isConnected = false,
  isTailing = true,
  onTailingChange,
}: DataTableProps) {
  const [sorting, setSorting] = useState<SortingState>([
    { id: "timestamp", desc: false }, // Default to ascending (oldest first)
  ]);
  const [columnFilters, setColumnFilters] = useState<ColumnFiltersState>([
    { id: "level", value: ["INFO", "WARNING", "ERROR", "CRITICAL"] }, // Exclude DEBUG by default
  ]);
  const [columnVisibility, setColumnVisibility] = useState<VisibilityState>({});
  const [globalFilter, setGlobalFilter] = useState("");
  const [showScrollToBottom, setShowScrollToBottom] = useState(false);
  const [showEditorModal, setShowEditorModal] = useState(false);

  const { settings, loading, setFontSize, toggleDarkMode, setEditor } =
    useSettings();

  const fontSizeClasses = {
    small: "text-[12px]",
    medium: "text-sm",
    large: "text-base",
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
    }
    setShowEditorModal(false);
  };

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

  // Create columns with editor support
  const columns = createColumns(settings?.editor || null, () => {
    setShowEditorModal(true);
  });

  const table = useReactTable({
    data,
    columns,
    onSortingChange: setSorting,
    onColumnFiltersChange: setColumnFilters,
    getCoreRowModel: getCoreRowModel(),
    // Remove getPaginationRowModel() for infinite scrolling
    getSortedRowModel: getSortedRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    onColumnVisibilityChange: setColumnVisibility,
    onGlobalFilterChange: setGlobalFilter,
    globalFilterFn: (row, _columnId, value) => {
      // Search through all text fields including nested attributes
      const searchableText = [
        row.original.message,
        row.original.level,
        row.original.service,
        row.original.trace_id,
        row.original.span_id,
        // Include attributes in search
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

  // Auto scroll to bottom when new data arrives and tailing is enabled
  useEffect(() => {
    if (isTailing && data.length > 0) {
      const timer = setTimeout(() => {
        const tableContainer = document.getElementById("logs-table-container");
        if (tableContainer) {
          tableContainer.scrollTop = tableContainer.scrollHeight;
        }
      }, 100);
      return () => clearTimeout(timer);
    }
  }, [data, isTailing]);

  // Check scroll position to show/hide scroll-to-bottom button
  useEffect(() => {
    const tableContainer = document.getElementById("logs-table-container");
    if (!tableContainer) return;

    const handleScroll = () => {
      const { scrollTop, scrollHeight, clientHeight } = tableContainer;
      const isNearBottom = scrollTop + clientHeight >= scrollHeight - 50; // 50px threshold
      setShowScrollToBottom(!isNearBottom && data.length > 0);
    };

    tableContainer.addEventListener("scroll", handleScroll);
    // Initial check
    handleScroll();

    return () => tableContainer.removeEventListener("scroll", handleScroll);
  }, [data.length]);

  const scrollToBottom = () => {
    const tableContainer = document.getElementById("logs-table-container");
    if (tableContainer) {
      tableContainer.scrollTo({
        top: tableContainer.scrollHeight,
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
    <TooltipProvider delayDuration={0}>
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
            <div className="text-sm text-muted-foreground">
              {data.length} logs
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
                            // If no filter exists, create one with all levels except the unchecked one
                            const newFilter = checked
                              ? allLevels
                              : allLevels.filter((l) => l !== level);
                            levelColumn?.setFilterValue(newFilter);
                          } else {
                            // Normal filter logic
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
                            // If no filter exists, create one with all services except the unchecked one
                            const newFilter = checked
                              ? allServices
                              : allServices.filter((s) => s !== service);
                            serviceColumn?.setFilterValue(newFilter);
                          } else {
                            // Normal filter logic
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
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Button variant="outline" size="sm">
                      <Code2 className="h-4 w-4" />
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent className="animate-none">
                    <p>Select code editor</p>
                  </TooltipContent>
                </Tooltip>
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

            {/* Font Size */}
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Button variant="outline" size="sm">
                      Aa
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent className="animate-none">
                    <p>Change font size</p>
                  </TooltipContent>
                </Tooltip>
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

            {/* Column visibility */}
            {/* <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="outline" size="sm">
                <Settings2 className="h-4 w-4" />
                View
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              {table
                .getAllColumns()
                .filter((column) => column.getCanHide())
                .map((column) => {
                  return (
                    <DropdownMenuCheckboxItem
                      key={column.id}
                      className="capitalize"
                      checked={column.getIsVisible()}
                      onCheckedChange={(value) =>
                        column.toggleVisibility(!!value)
                      }
                    >
                      {column.id}
                    </DropdownMenuCheckboxItem>
                  );
                })}
            </DropdownMenuContent>
          </DropdownMenu> */}
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
              <Badge
                variant="secondary"
                className="flex items-center gap-2 pr-1"
              >
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

        {/* Table */}
        <div className="flex-1 rounded-md border relative min-w-0 overflow-hidden">
          <div
            id="logs-table-container"
            className="h-full overflow-y-auto overflow-x-hidden overscroll-contain"
            style={{
              WebkitOverflowScrolling: "touch",
              // Prevent bounce scrolling on macOS
              overscrollBehavior: "contain",
            }}
          >
            <Table className="w-full border-separate border-spacing-0 table-fixed font-mono">
              <TableHeader className={fontSizeClasses[settings.fontSize]}>
                {table.getHeaderGroups().map((headerGroup) => (
                  <TableRow key={headerGroup.id}>
                    {headerGroup.headers.map((header, index) => {
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
                          ? "" // Message column - flex to fill remaining space
                          : index === 5
                          ? columnWidths.trace
                          : "";
                      return (
                        <TableHead
                          key={header.id}
                          className={`sticky  top-0 z-20 bg-background border-b ${widthClass}`}
                        >
                          {header.isPlaceholder
                            ? null
                            : flexRender(
                                header.column.columnDef.header,
                                header.getContext()
                              )}
                        </TableHead>
                      );
                    })}
                  </TableRow>
                ))}
              </TableHeader>
              <TableBody className={fontSizeClasses[settings.fontSize]}>
                {table.getRowModel().rows?.length ? (
                  table.getRowModel().rows.map((row) => (
                    <TableRow
                      key={row.id}
                      data-state={row.getIsSelected() && "selected"}
                      className="hover:bg-muted/50"
                    >
                      {row.getVisibleCells().map((cell, cellIndex) => (
                        <TableCell
                          key={cell.id}
                          className={`px-2 py-1 align-top ${
                            cellIndex === 4 ? "break-all" : ""
                          }`}
                        >
                          {flexRender(
                            cell.column.columnDef.cell,
                            cell.getContext()
                          )}
                        </TableCell>
                      ))}
                    </TableRow>
                  ))
                ) : (
                  <TableRow>
                    <TableCell
                      colSpan={columns.length}
                      className="h-24 text-center"
                    >
                      {isConnected
                        ? "No logs yet. Start your application to see logs here!"
                        : "Connecting to log server..."}
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </div>

          {/* Scroll to Bottom Button */}
          {showScrollToBottom && (
            <button
              onClick={scrollToBottom}
              className="absolute bottom-4 right-4 p-2 bg-primary text-primary-foreground rounded-md shadow-lg hover:bg-primary/90 transition-all duration-200 opacity-80 hover:opacity-100"
              aria-label="Scroll to bottom"
            >
              <ArrowDown className="h-4 w-4" />
            </button>
          )}
        </div>

        {/* Editor Selection Modal */}
        <EditorSelectionModal
          open={showEditorModal}
          onSelect={handleEditorSelect}
          onClose={() => setShowEditorModal(false)}
        />
      </div>
    </TooltipProvider>
  );
}
