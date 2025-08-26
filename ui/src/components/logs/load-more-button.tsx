import { Button } from "@/components/ui/button";
import { ChevronUp } from "lucide-react";

interface LoadMoreButtonProps {
  onLoadMore: () => void;
  isLoading: boolean;
  hasMore: boolean;
}

export function LoadMoreButton({
  onLoadMore,
  isLoading,
  hasMore,
}: LoadMoreButtonProps) {
  if (!hasMore) return null;

  return (
    <div className="absolute top-0 w-full z-20 bg-background border-b border-border/50 py-2 px-4 transition-all duration-300 ease-in-out animate-in fade-in slide-in-from-top-2 items-center justify-center">
      <div className="flex justify-center">
        <Button
          variant="outline"
          size="sm"
          onClick={onLoadMore}
          disabled={isLoading}
          className="transition-all duration-200 hover:bg-muted/50"
        >
          <>
            <ChevronUp className="h-4 w-4 mr-2" />
            Load more historical logs
          </>
        </Button>
      </div>
    </div>
  );
}
