import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"
import { Slot } from "radix-ui"

import { cn } from "@/lib/utils"

/**
 * Customised from the shadcn default: tonal wash + matching edge + text token,
 * so a badge never becomes a solid colour block competing with the primary CTA.
 * The `numeric` variant switches to the mono face with tabular figures, which
 * is how every count, score and percentage is set across the product.
 */
const badgeVariants = cva(
  "inline-flex w-fit shrink-0 items-center justify-center gap-1.5 whitespace-nowrap rounded-md border px-2 py-0.5 text-micro font-semibold uppercase tracking-[0.06em] [&>svg]:pointer-events-none [&>svg]:size-3.5",
  {
    variants: {
      variant: {
        brand: "border-brand-edge bg-brand-wash text-brand-ink",
        neutral: "border-line bg-sunken text-ink-muted",
        warn: "border-warn-edge bg-warn-wash text-warn",
        danger: "border-danger-edge bg-danger-wash text-danger",
        solid: "border-transparent bg-brand text-white",
        outline: "border-line-strong bg-transparent text-ink-muted",
      },
      numeric: {
        true: "font-mono tabular-nums tracking-normal normal-case",
        false: "",
      },
    },
    defaultVariants: { variant: "neutral", numeric: false },
  }
)

function Badge({
  className,
  variant,
  numeric,
  asChild = false,
  ...props
}: React.ComponentProps<"span"> &
  VariantProps<typeof badgeVariants> & { asChild?: boolean }) {
  const Comp = asChild ? Slot.Root : "span"

  return (
    <Comp
      data-slot="badge"
      className={cn(badgeVariants({ variant, numeric }), className)}
      {...props}
    />
  )
}

export { Badge, badgeVariants }
