import { useState, useEffect, useCallback, useRef } from "react";
import { DataTable } from "./logs/data-table";
import type { LogEntry, WebSocketMessage } from "@/types/logs";

export function LogViewer() {
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const [isTailing, setIsTailing] = useState(true);
  const seenLogIds = useRef<Set<string>>(new Set());
  const wsRef = useRef<WebSocket | null>(null);

  const connectWebSocket = useCallback(() => {
    // Don't connect if already connected or connecting
    if (wsRef.current?.readyState === WebSocket.OPEN || wsRef.current?.readyState === WebSocket.CONNECTING) {
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
              setLogs(message.data); // Keep original order (oldest first)
              // Update seen IDs set
              seenLogIds.current.clear();
              message.data.forEach((log) => seenLogIds.current.add(log.id));
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
                return [...prevLogs, newLog];
              });
            }
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
    <div className="container mx-auto py-6">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-muted-foreground">
            🌲 Lumberjack Local development log viewer
          </p>
        </div>
      </div>

      <DataTable
        data={logs}
        isConnected={isConnected}
        isTailing={isTailing}
        onTailingChange={handleTailingChange}
      />
    </div>
  );
}
