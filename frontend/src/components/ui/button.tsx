import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";

import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md text-sm font-medium cursor-pointer transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-50 disabled:cursor-not-allowed [&_svg]:pointer-events-none [&_svg]:size-4 [&_svg]:shrink-0",
  {
    variants: {
      variant: {
        default:
          "bg-brand-ink text-on-ink shadow-xs hover:bg-brand-deep active:translate-y-px transition-[background-color,transform]",
        brand:
          "bg-brand text-on-ink shadow-brand hover:bg-brand-strong active:translate-y-px transition-[background-color,transform]",
        ink: "bg-ink text-on-ink hover:bg-ink-muted active:translate-y-px transition-[background-color,transform]",
        destructive: "bg-destructive text-destructive-foreground shadow-sm hover:bg-destructive/90",
        outline: "border border-input bg-paper shadow-xs hover:bg-paper-2 hover:border-brand",
        onInk:
          "border border-white/25 bg-white/5 text-on-ink hover:bg-white/12 hover:border-white/45",
        secondary: "bg-secondary text-secondary-foreground shadow-xs hover:bg-paper-3",
        ghost: "hover:bg-accent hover:text-accent-foreground",
        link: "text-brand-deep underline-offset-4 hover:underline",
      },
      size: {
        default: "h-10 px-4 py-2",
        sm: "h-8 rounded-md px-3 text-xs",
        lg: "h-12 rounded-md px-6 text-[0.9375rem]",
        icon: "h-9 w-9",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  },
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>, VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button";
    return (
      <Comp className={cn(buttonVariants({ variant, size, className }))} ref={ref} {...props} />
    );
  },
);
Button.displayName = "Button";

export { Button, buttonVariants };
