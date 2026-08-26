import { QueryClient } from "@tanstack/react-query"

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 2 * 60 * 1000,     // stay fresh 2 min → no refetch on navigation
      gcTime:   10 * 60 * 1000,     // keep in memory 10 min after last subscriber
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
})
