import { cn } from "@/lib/utils"

/**
 * Customised from the shadcn default: a slow shimmer on the sunken token
 * instead of a pulsing accent block, so loading states stay quiet.
 */
function Skeleton({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="skeleton"
      aria-hidden="true"
      className={cn(
        "animate-pulse rounded-lg bg-sunken [animation-duration:1.8s]",
        className
      )}
      {...props}
    />
  )
}

export { Skeleton }
