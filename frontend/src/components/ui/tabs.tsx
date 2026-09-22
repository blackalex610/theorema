import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"
import { Tabs as TabsPrimitive } from "radix-ui"

import { cn } from "@/lib/utils"

/**
 * Customised from the shadcn default: the underline variant is the default and
 * the pill variant is the opt-in. An underline keeps the page's horizontal
 * rules consistent, where stacked pill groups start to read as chrome.
 */

function Tabs({ className, ...props }: React.ComponentProps<typeof TabsPrimitive.Root>) {
  return (
    <TabsPrimitive.Root
      data-slot="tabs"
      className={cn("group/tabs flex flex-col gap-5", className)}
      {...props}
    />
  )
}

// `group/tabs-list` lets each trigger read its list's variant. The previous
// triggers stacked two arbitrary variants (`[[data-variant=line]_&][data-state=active]:`),
// which Tailwind v4 drops without a word — no active-state CSS was generated
// at all, so the selected tab looked exactly like the others.
const tabsListVariants = cva("group/tabs-list inline-flex items-center", {
  variants: {
    variant: {
      line: "w-full gap-6 border-b border-line",
      pill: "w-fit gap-1 rounded-lg border border-line bg-sunken p-1",
    },
  },
  defaultVariants: { variant: "line" },
})

function TabsList({
  className,
  variant = "line",
  ...props
}: React.ComponentProps<typeof TabsPrimitive.List> &
  VariantProps<typeof tabsListVariants>) {
  return (
    <TabsPrimitive.List
      data-slot="tabs-list"
      data-variant={variant}
      className={cn(tabsListVariants({ variant }), className)}
      {...props}
    />
  )
}

function TabsTrigger({
  className,
  ...props
}: React.ComponentProps<typeof TabsPrimitive.Trigger>) {
  return (
    <TabsPrimitive.Trigger
      data-slot="tabs-trigger"
      className={cn(
        "relative inline-flex items-center justify-center gap-2 whitespace-nowrap text-caption font-semibold text-ink-muted transition-colors duration-200 hover:text-ink disabled:pointer-events-none disabled:opacity-50",
        "[&_svg]:pointer-events-none [&_svg]:shrink-0 [&_svg:not([class*='size-'])]:size-4",
        // underline variant
        "group-data-[variant=line]/tabs-list:-mb-px group-data-[variant=line]/tabs-list:border-b-2 group-data-[variant=line]/tabs-list:border-transparent group-data-[variant=line]/tabs-list:pb-3",
        "group-data-[variant=line]/tabs-list:data-[state=active]:border-brand group-data-[variant=line]/tabs-list:data-[state=active]:text-ink",
        // pill variant
        "group-data-[variant=pill]/tabs-list:rounded-md group-data-[variant=pill]/tabs-list:px-3.5 group-data-[variant=pill]/tabs-list:py-1.5",
        "group-data-[variant=pill]/tabs-list:data-[state=active]:bg-surface group-data-[variant=pill]/tabs-list:data-[state=active]:text-ink group-data-[variant=pill]/tabs-list:data-[state=active]:shadow-lift-1",
        className
      )}
      {...props}
    />
  )
}

function TabsContent({
  className,
  ...props
}: React.ComponentProps<typeof TabsPrimitive.Content>) {
  return (
    <TabsPrimitive.Content
      data-slot="tabs-content"
      className={cn("flex-1 outline-none", className)}
      {...props}
    />
  )
}

export { Tabs, TabsList, TabsTrigger, TabsContent, tabsListVariants }
