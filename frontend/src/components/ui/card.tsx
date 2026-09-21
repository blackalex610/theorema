import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"

import { cn } from "@/lib/utils"

/**
 * Customised from the shadcn default. Three surfaces only:
 *  - plate:  the standard raised sheet (most content)
 *  - sunken: recessed panel for secondary/meta information
 *  - bare:   structure without a visible container, for dense grids
 * Padding is tighter than stock so data-heavy screens do not balloon.
 */
const cardVariants = cva(
  "flex flex-col rounded-xl text-ink transition-[border-color,box-shadow] duration-200",
  {
    variants: {
      variant: {
        plate: "border border-line bg-surface shadow-lift-1",
        sunken: "border border-line bg-sunken",
        bare: "bg-transparent",
      },
      pad: {
        none: "",
        sm: "p-4 gap-3",
        md: "p-5 gap-4 sm:p-6",
        lg: "p-6 gap-5 sm:p-8",
      },
    },
    defaultVariants: { variant: "plate", pad: "md" },
  }
)

function Card({
  className,
  variant,
  pad,
  ...props
}: React.ComponentProps<"div"> & VariantProps<typeof cardVariants>) {
  return (
    <div
      data-slot="card"
      className={cn(cardVariants({ variant, pad, className }))}
      {...props}
    />
  )
}

function CardHeader({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="card-header"
      className={cn("flex items-start justify-between gap-3", className)}
      {...props}
    />
  )
}

function CardTitle({ className, ...props }: React.ComponentProps<"h3">) {
  return (
    <h3
      data-slot="card-title"
      className={cn("font-display text-title font-semibold", className)}
      {...props}
    />
  )
}

function CardDescription({ className, ...props }: React.ComponentProps<"p">) {
  return (
    <p
      data-slot="card-description"
      className={cn("text-caption text-ink-muted", className)}
      {...props}
    />
  )
}

function CardContent({ className, ...props }: React.ComponentProps<"div">) {
  return <div data-slot="card-content" className={cn(className)} {...props} />
}

function CardFooter({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="card-footer"
      className={cn("flex items-center gap-3", className)}
      {...props}
    />
  )
}

export {
  Card,
  CardHeader,
  CardFooter,
  CardTitle,
  CardDescription,
  CardContent,
  cardVariants,
}
