import * as React from "react"

import { cn } from "@/lib/utils"

/**
 * Customised from the shadcn default: 44px tall so it is comfortable on a
 * phone, painted on the sunken surface so fields read as wells rather than
 * floating boxes, and focused with the brand ring from the token set.
 */
function Input({ className, type, ...props }: React.ComponentProps<"input">) {
  return (
    <input
      type={type}
      data-slot="input"
      className={cn(
        "h-11 w-full min-w-0 rounded-lg border border-line bg-sunken px-3.5 text-body text-ink outline-none transition-[border-color,box-shadow] duration-200",
        "placeholder:text-ink-faint",
        "focus-visible:border-brand focus-visible:ring-2 focus-visible:ring-brand/25 focus-visible:outline-none",
        "disabled:cursor-not-allowed disabled:opacity-50",
        "aria-invalid:border-danger aria-invalid:ring-2 aria-invalid:ring-danger/20",
        className
      )}
      {...props}
    />
  )
}

export { Input }
