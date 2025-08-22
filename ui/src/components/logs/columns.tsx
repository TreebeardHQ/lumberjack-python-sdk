import { ColumnDef } from "@tanstack/react-table";
import { Button } from "@/components/ui/button";
import { ArrowUpDown } from "lucide-react";
import {
  Tooltip,
  TooltipContent,
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

export const createColumns = (): ColumnDef<LogEntry>[] => [
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
        <Tooltip>
          <TooltipTrigger asChild>
            <div
              className={`font-medium truncate cursor-default ${serviceColors[colorIndex]}`}
            >
              {service}
            </div>
          </TooltipTrigger>
          <TooltipContent className="animate-none">
            <p>{service}</p>
          </TooltipContent>
        </Tooltip>
      );
    },
    size: 80,
  },
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
        <div className="text-muted-foreground">
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
          className={`font-medium ${
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
    accessorKey: "logger",
    header: "Logger",
    cell: ({ row }) => {
      const attributes = row.original.attributes as Record<string, any>;
      const loggerName =
        attributes?.["logger_name"] ||
        attributes?.["tb_rv2_logger_name"] ||
        attributes?.["logger"] ||
        "-";

      return (
        <Tooltip>
          <TooltipTrigger asChild>
            <div className="text-xs truncate cursor-default text-purple-600">
              {loggerName === "-"
                ? "-"
                : loggerName.split(".").pop() || loggerName}
            </div>
          </TooltipTrigger>
          <TooltipContent className="animate-none">
            <p>{loggerName}</p>
          </TooltipContent>
        </Tooltip>
      );
    },
    size: 56,
  },
  {
    accessorKey: "message",
    header: "Message",
    cell: ({ row }) => {
      const rawMessage = row.getValue("message") as string;
      const message = stripAnsiCodes(rawMessage);
      const attributes = row.original.attributes as Record<string, any>;

      // Check for exception information in attributes
      const exceptionType = attributes?.["exception.type"];
      const exceptionMessage = attributes?.["exception.message"];
      const exceptionStacktrace = attributes?.["exception.stacktrace"];
      const hasException =
        exceptionType || exceptionMessage || exceptionStacktrace;

      return (
        <div className="break-all">
          {message}
          {hasException && exceptionMessage && (
            <span className="text-red-600 dark:text-red-400 font-medium ml-2">
              - {exceptionMessage}
            </span>
          )}
        </div>
      );
    },
    // Remove fixed size to allow flexible width
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
          onClick={(e) => {
            e.stopPropagation();
            table.setGlobalFilter(traceId);
          }}
          className="text-blue-600 hover:text-blue-800 hover:underline cursor-pointer"
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
export const columns = createColumns();
