import { ColumnDef } from "@tanstack/react-table";
import { Button } from "@/components/ui/button";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { ArrowUpDown, Code } from "lucide-react";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { format } from "date-fns";
import type { LogEntry } from "@/types/logs";

// Log level colors (now just text colors, no badges)
const levelColors = {
  DEBUG: "text-gray-500",
  INFO: "text-blue-600",
  WARNING: "text-yellow-600",
  ERROR: "text-red-600",
  CRITICAL: "text-red-700 font-semibold",
} as const;

// Hash function for service name colors
function hashServiceName(name: string): number {
  let hash = 0;
  for (let i = 0; i < name.length; i++) {
    const char = name.charCodeAt(i);
    hash = (hash << 5) - hash + char;
    hash = hash & hash; // Convert to 32bit integer
  }
  return Math.abs(hash) % 10;
}

// Service colors array (10 colors)
const serviceColors = [
  "text-red-600",
  "text-blue-600",
  "text-green-600",
  "text-purple-600",
  "text-orange-600",
  "text-pink-600",
  "text-indigo-600",
  "text-teal-600",
  "text-amber-600",
  "text-cyan-600",
] as const;

// Function to strip ANSI color codes from log messages
const stripAnsiCodes = (text: string): string => {
  return text.replace(/\x1b\[[0-9;]*m/g, "");
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
      const link = document.createElement('a');
      link.href = command;
      link.style.display = 'none';
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
    }
  }
};

export const createColumns = (
  editor: "cursor" | "vscode" | null,
  onEditorNeeded?: () => void
): ColumnDef<LogEntry>[] => [
  {
    accessorKey: "timestamp",
    header: ({ column }) => {
      return (
        <Button
          variant="ghost"
          onClick={() => column.toggleSorting(column.getIsSorted() === "asc")}
          className="h-8 px-2"
        >
          Time
          <ArrowUpDown className="ml-2 h-4 w-4" />
        </Button>
      );
    },
    cell: ({ row }) => {
      const timestamp = row.getValue("timestamp") as number;
      const date = new Date(timestamp / 1000000); // Convert from nanoseconds
      return (
        <div className="font-mono text-muted-foreground w-16">
          {format(date, "HH:mm:ss.SSS")}
        </div>
      );
    },
    size: 70,
  },
  {
    accessorKey: "level",
    header: "Level",
    filterFn: (row, id, value) => {
      return !value || value.includes(row.getValue(id));
    },
    cell: ({ row }) => {
      const level = row.getValue("level") as string;
      const normalizedLevel = level.toUpperCase() as keyof typeof levelColors;
      return (
        <div
          className={`font-medium w-12 ${
            levelColors[normalizedLevel] || levelColors.INFO
          }`}
        >
          {level}
        </div>
      );
    },
    size: 60,
  },
  {
    accessorKey: "service",
    header: "Service",
    filterFn: (row, id, value) => {
      return !value || value.includes(row.getValue(id));
    },
    cell: ({ row }) => {
      const service = row.getValue("service") as string;
      const colorIndex = hashServiceName(service);
      return (
        <TooltipProvider delayDuration={0}>
          <Tooltip>
            <TooltipTrigger asChild>
              <div
                className={`font-medium w-16 truncate cursor-default ${serviceColors[colorIndex]}`}
              >
                {service}
              </div>
            </TooltipTrigger>
            <TooltipContent className="animate-none">
              <p>{service}</p>
            </TooltipContent>
          </Tooltip>
        </TooltipProvider>
      );
    },
    size: 80,
  },
  {
    accessorKey: "logger",
    header: "Logger",
    cell: ({ row }) => {
      const attributes = row.original.attributes as Record<string, any>;
      const loggerName = attributes?.["logger_name"] || attributes?.["tb_rv2_logger_name"] || attributes?.["logger"] || "-";
      
      return (
        <TooltipProvider delayDuration={0}>
          <Tooltip>
            <TooltipTrigger asChild>
              <div className="font-mono text-xs w-20 truncate cursor-default text-purple-600">
                {loggerName === "-" ? "-" : loggerName.split('.').pop() || loggerName}
              </div>
            </TooltipTrigger>
            <TooltipContent className="animate-none">
              <p>{loggerName}</p>
            </TooltipContent>
          </Tooltip>
        </TooltipProvider>
      );
    },
    size: 80,
  },
  {
    accessorKey: "message",
    header: "Message",
    cell: ({ row }) => {
      const rawMessage = row.getValue("message") as string;
      const message = stripAnsiCodes(rawMessage);
      const attributes = row.original.attributes as Record<string, any>;
      const hasAttributes = attributes && Object.keys(attributes).length > 0;

      // Check for exception information in attributes
      const exceptionType = attributes?.["exception.type"];
      const exceptionMessage = attributes?.["exception.message"];
      const exceptionStacktrace = attributes?.["exception.stacktrace"];
      const hasException =
        exceptionType || exceptionMessage || exceptionStacktrace;

      // Check for code file and line information
      const filePath = attributes?.["code.file.path"];
      const lineNumber = attributes?.["code.line.number"];
      const hasCodeInfo = filePath && lineNumber && lineNumber !== false;

      const handleCodeClick = () => {
        if (!hasCodeInfo) return;

        if (!editor) {
          onEditorNeeded?.();
          return;
        }

        openInEditor(filePath, lineNumber, editor);
      };

      return (
        <div className="flex flex-col gap-1">
          <div className="flex items-center gap-2">
            <Popover>
              <PopoverTrigger asChild>
                <div
                  className={`break-words cursor-pointer flex-1 ${
                    hasAttributes ? "hover:bg-muted/50 rounded px-1 py-0.5" : ""
                  }`}
                >
                  {message}
                </div>
              </PopoverTrigger>
              {hasAttributes && (
                <PopoverContent className="w-80">
                  <div className="space-y-2">
                    <h4 className="font-medium text-sm">Attributes</h4>
                    <div className="space-y-1 max-h-64 overflow-auto">
                      {Object.entries(attributes).map(([key, value]) => (
                        <div key={key} className="flex flex-col gap-1">
                          <div className="text-[10px] font-medium text-muted-foreground">
                            {key}
                          </div>
                          <div className="text-[10px] font-mono break-all bg-muted p-1 rounded">
                            {typeof value === "object"
                              ? JSON.stringify(value, null, 2)
                              : String(value)}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                </PopoverContent>
              )}
            </Popover>

            {hasCodeInfo && (
              <TooltipProvider delayDuration={0}>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={handleCodeClick}
                      className="h-6 w-6 p-0"
                    >
                      <Code className="h-3 w-3" />
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent className="text-xs px-2 py-1">
                    <p>{filePath.split('/').pop()}:{lineNumber} - Open in editor</p>
                  </TooltipContent>
                </Tooltip>
              </TooltipProvider>
            )}
          </div>

          {hasException && (
            <div className="mt-2 p-2 bg-red-50 dark:bg-red-950/30 border-l-2 border-red-200 dark:border-red-800 rounded-r">
              {exceptionType && (
                <div className="font-medium text-red-700 dark:text-red-300 mb-1">
                  {exceptionType}
                </div>
              )}
              {exceptionMessage && (
                <div className="text-red-600 dark:text-red-400 mb-2">
                  {exceptionMessage}
                </div>
              )}
              {exceptionStacktrace && (
                <details className="mt-1">
                  <summary className="cursor-pointer text-red-600 dark:text-red-400 hover:text-red-800 dark:hover:text-red-300 font-medium">
                    Stack Trace
                  </summary>
                  <pre className="mt-1 text-[9px] font-mono text-red-700 dark:text-red-300 bg-red-50 dark:bg-red-950/50 p-1 rounded overflow-x-auto whitespace-pre-wrap">
                    {exceptionStacktrace}
                  </pre>
                </details>
              )}
            </div>
          )}
        </div>
      );
    },
    size: 600,
  },
  {
    accessorKey: "trace_id",
    header: "Trace",
    cell: ({ row, table }) => {
      const traceId = row.getValue("trace_id") as string;
      if (!traceId) return null;

      const shortTrace = traceId.slice(0, 6);

      return (
        <button
          onClick={() => {
            table.setGlobalFilter(traceId);
          }}
          className="font-mono text-blue-600 hover:text-blue-800 hover:underline cursor-pointer"
          title={`Click to search for trace: ${traceId}`}
        >
          {shortTrace}
        </button>
      );
    },
    size: 60,
  },
];

// Default export for backwards compatibility
export const columns = createColumns(null);
