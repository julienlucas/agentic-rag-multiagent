import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";

import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-xs font-medium transition-colors focus:outline-none",
  {
    variants: {
      variant: {
        default: "border-transparent bg-primary text-primary-foreground",
        brand: "border-transparent bg-brand-surface text-brand-deep",
        sand: "border-transparent bg-paper-3 text-ink-muted",
        secondary: "border-transparent bg-secondary text-secondary-foreground",
        success: "border-transparent bg-success/12 text-success",
        warning: "border-transparent bg-warning/18 text-brand-deep",
        destructive: "border-transparent bg-destructive/12 text-destructive",
        outline: "text-foreground",
        mono: "mono-xs border-border bg-paper text-ink-muted",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  },
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>, VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return <div className={cn(badgeVariants({ variant }), className)} {...props} />;
}

export { Badge, badgeVariants };
