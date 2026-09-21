import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"
import { Slot } from "radix-ui"

import { cn } from "@/lib/utils"

/**
 * Customised from the shadcn default: the palette is token-driven, the radius
 * comes from the single system scale, and sizes are set so every button clears
 * a 44px touch target from `md` upward. Motion is intentionally omitted here —
 * springy hover physics live on the Motion wrappers that use these classes, so
 * a plain <Button> stays cheap.
 */
const buttonVariants = cva(
  "inline-flex shrink-0 items-center justify-center gap-2 whitespace-nowrap rounded-lg font-medium outline-none transition-[background-color,border-color,color,box-shadow] duration-200 disabled:pointer-events-none disabled:opacity-45 [&_svg]:pointer-events-none [&_svg]:shrink-0 [&_svg:not([class*='size-'])]:size-[1.15em]",
  {
    variants: {
      variant: {
        default:
          "bg-brand text-white shadow-lift-1 hover:bg-brand-strong active:bg-brand-strong",
        soft:
          "bg-brand-wash text-brand-ink border border-brand-edge hover:bg-brand-wash hover:border-brand",
        outline:
          "border border-line-strong bg-surface text-ink hover:border-brand hover:text-brand-ink",
        ghost:
          "text-ink-muted hover:bg-sunken hover:text-ink",
        danger:
          "bg-danger text-white hover:brightness-110",
        link:
          "text-brand-ink underline-offset-4 hover:underline",
      },
      size: {
        sm: "h-8 px-3 text-caption",
        md: "h-11 px-5 text-body",
        lg: "h-[3.25rem] px-7 text-lead",
        icon: "size-9",
        "icon-lg": "size-11",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "md",
    },
  }
)

function Button({
  className,
  variant,
  size,
  asChild = false,
  ...props
}: React.ComponentProps<"button"> &
  VariantProps<typeof buttonVariants> & {
    asChild?: boolean
  }) {
  const Comp = asChild ? Slot.Root : "button"

  return (
    <Comp
      data-slot="button"
      className={cn(buttonVariants({ variant, size, className }))}
      {...props}
    />
  )
}

export { Button, buttonVariants }
