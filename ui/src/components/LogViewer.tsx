import { useState, useEffect, useCallback, useRef } from "react";
import { VirtualizedDataTable } from "./logs/virtualized-data-table";
import type { LogEntry, WebSocketMessage } from "@/types/logs";
import { TooltipProvider } from "@/components/ui/tooltip";

const MAX_LOGS_IN_MEMORY = 50000; // Maximum number of logs to keep in memory
const LOAD_MORE_BATCH_SIZE = 100; // Number of logs to load when paginating

export function LogViewer() {
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const [isTailing, setIsTailing] = useState(true);
  const [isLoading, setIsLoading] = useState(false);
  const [hasMore, setHasMore] = useState(true);
  const seenLogIds = useRef<Set<string>>(new Set());
  const wsRef = useRef<WebSocket | null>(null);
  const oldestTimestamp = useRef<number | null>(null);

  // Function to trim logs array to maintain memory limit
  const trimLogsToLimit = useCallback(
    (currentLogs: LogEntry[]) => {
      if (currentLogs.length <= MAX_LOGS_IN_MEMORY) {
        return currentLogs;
      }

      // Keep the most recent logs (for tailing) or oldest logs (for historical viewing)
      // When tailing, keep the newest logs; when viewing history, keep the oldest
      const trimmedLogs = isTailing
        ? currentLogs.slice(-MAX_LOGS_IN_MEMORY)
        : currentLogs.slice(0, MAX_LOGS_IN_MEMORY);

      // Update oldest timestamp to track what we've loaded
      if (trimmedLogs.length > 0) {
        oldestTimestamp.current = Math.min(
          ...trimmedLogs.map((log) => log.timestamp)
        );
      }

      return trimmedLogs;
    },
    [isTailing]
  );

  // Function to load more historical logs
  const loadMoreLogs = useCallback(async () => {
    if (isLoading || !hasMore) {
      return;
    }

    // If we don't have an oldest timestamp yet, get it from current logs
    if (!oldestTimestamp.current && logs.length > 0) {
      oldestTimestamp.current = Math.min(...logs.map((log) => log.timestamp));
    }

    if (!oldestTimestamp.current) {
      return;
    }

    setIsLoading(true);

    try {
      const params = new URLSearchParams({
        limit: LOAD_MORE_BATCH_SIZE.toString(),
        before_timestamp: oldestTimestamp.current.toString(),
      });

      const response = await fetch(`/api/logs/before?${params}`);

      if (!response.ok) {
        throw new Error(`Failed to load logs: ${response.statusText}`);
      }

      const data = await response.json();
      const newLogs = data.logs as LogEntry[];

      if (newLogs.length === 0) {
        setHasMore(false);
        return;
      }

      setLogs((prevLogs) => {
        // Prepend new logs and trim to memory limit
        const combined = [...newLogs, ...prevLogs];

        // Update seen IDs
        newLogs.forEach((log) => seenLogIds.current.add(log.id));

        // Update oldest timestamp
        if (newLogs.length > 0) {
          oldestTimestamp.current = Math.min(
            ...newLogs.map((log) => log.timestamp)
          );
        }

        return trimLogsToLimit(combined);
      });

      // Check if we have more logs to load
      setHasMore(data.has_more || false);
    } catch (error) {
      console.error("Failed to load more logs:", error);
    } finally {
      setIsLoading(false);
    }
  }, [isLoading, hasMore, trimLogsToLimit, logs.length]);

  const connectWebSocket = useCallback(() => {
    // Don't connect if already connected or connecting
    if (
      wsRef.current?.readyState === WebSocket.OPEN ||
      wsRef.current?.readyState === WebSocket.CONNECTING
    ) {
      console.log("WebSocket already connected/connecting, skipping");
      return;
    }

    if (isConnected) {
      console.log("Already marked as connected, skipping");
      return;
    }

    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl = `${protocol}//${window.location.host}/ws/logs`;

    console.log("Connecting to WebSocket:", wsUrl);
    const newWs = new WebSocket(wsUrl);

    newWs.onopen = () => {
      console.log("WebSocket connected");
      setIsConnected(true);
    };

    newWs.onmessage = (event) => {
      try {
        const message: WebSocketMessage = JSON.parse(event.data);

        if (
          message.type === "new_log" &&
          message.data &&
          !Array.isArray(message.data)
        ) {
          console.log(
            `WebSocket received log: ${(message.data as any).id} - ${(
              message.data as any
            ).message?.slice(0, 50)}...`
          );
        }

        switch (message.type) {
          case "initial_logs":
            if (Array.isArray(message.data)) {
              setLogs((prevLogs) => {
                // Filter out logs we already have to avoid duplicates
                const newLogs = (message.data as LogEntry[]).filter(
                  (log: LogEntry) => !seenLogIds.current.has(log.id)
                );

                if (newLogs.length === 0) {
                  // No new logs to add, return existing logs unchanged
                  return prevLogs;
                }

                // Add new logs to seen set
                newLogs.forEach((log: LogEntry) =>
                  seenLogIds.current.add(log.id)
                );

                // Merge new logs with existing logs and sort by timestamp
                const allLogs = [...prevLogs, ...newLogs].sort(
                  (a, b) => a.timestamp - b.timestamp
                );

                // Apply memory management
                const trimmedLogs = trimLogsToLimit(allLogs);

                // Update oldest timestamp only if we don't have one yet
                if (!oldestTimestamp.current && trimmedLogs.length > 0) {
                  oldestTimestamp.current = Math.min(
                    ...trimmedLogs.map((log) => log.timestamp)
                  );
                }

                return trimmedLogs;
              });
            }
            break;

          case "new_log":
            if (message.data && !Array.isArray(message.data)) {
              setLogs((prevLogs) => {
                const newLog = message.data as LogEntry;
                // Check if log already exists to prevent duplicates
                if (seenLogIds.current.has(newLog.id)) {
                  console.warn(
                    `Duplicate log detected and ignored: ${
                      newLog.id
                    } - ${newLog.message.slice(0, 50)}...`
                  );
                  return prevLogs; // Don't add duplicate
                }
                // Add to seen IDs and add new log at the end (like tail command)
                seenLogIds.current.add(newLog.id);
                const updatedLogs = [...prevLogs, newLog];

                // Apply memory management - trim if needed
                return trimLogsToLimit(updatedLogs);
              });
            }
            break;

          case "stats":
            // Stats message received but not displaying total count
            break;

          case "ping":
            // Just ignore pings
            break;

          default:
            console.log("Unknown WebSocket message type:", message.type);
        }
      } catch (error) {
        console.error("Failed to parse WebSocket message:", error);
      }
    };

    newWs.onclose = (event) => {
      console.log("WebSocket disconnected", event.code, event.reason);
      setIsConnected(false);

      // Attempt to reconnect after a delay unless it was a clean close
      if (event.code !== 1000 && isTailing) {
        setTimeout(() => {
          connectWebSocket();
        }, 3000);
      }
    };

    newWs.onerror = (error) => {
      console.error("WebSocket error:", error);
      setIsConnected(false);
    };

    wsRef.current = newWs;
  }, [isConnected]);

  const handleTailingChange = (tailing: boolean) => {
    setIsTailing(tailing);

    if (tailing && !isConnected) {
      connectWebSocket();
    } else if (!tailing && wsRef.current) {
      wsRef.current.close(1000, "Tailing disabled");
      wsRef.current = null;
      setIsConnected(false);
    }
  };

  // Initial connection
  useEffect(() => {
    if (isTailing) {
      connectWebSocket();
    }

    // Cleanup on unmount
    return () => {
      if (wsRef.current) {
        wsRef.current.close(1000, "Component unmounting");
      }
    };
  }, []); // Only run on mount

  // Reconnect when tailing is re-enabled
  useEffect(() => {
    if (isTailing && !isConnected && !wsRef.current) {
      connectWebSocket();
    }
  }, [isTailing, isConnected, connectWebSocket]);

  return (
    <TooltipProvider delayDuration={0}>
      <div className="h-screen flex flex-col overflow-hidden">
        <div className="flex-shrink-0 px-6 py-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-muted-foreground">
                🌲 Lumberjack Local development log viewer
              </p>
            </div>
          </div>
        </div>

        <div className="flex-1 px-6 pb-6 overflow-hidden">
          <VirtualizedDataTable
            data={logs}
            isConnected={isConnected}
            isTailing={isTailing}
            onTailingChange={handleTailingChange}
            onLoadMore={loadMoreLogs}
            isLoading={isLoading}
            hasMore={hasMore}
          />
        </div>
      </div>
    </TooltipProvider>
  );
}
