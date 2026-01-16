import * as React from "react";

import { cn } from "@/lib/utils";

const Card = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => (
  <div
    ref={ref}
    className={cn(
      "rounded-lg border bg-card text-card-foreground shadow-sm",
      className
    )}
    {...props}
  />
));
Card.displayName = "Card";

const CardHeader = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => (
  <div
    ref={ref}
    className={cn("flex flex-col space-y-1.5 p-6", className)}
    {...props}
  />
));
CardHeader.displayName = "CardHeader";

const CardTitle = React.forwardRef<
  HTMLParagraphElement,
  React.HTMLAttributes<HTMLHeadingElement> & {
    variant?: "h1" | "h2" | "h3" | "h3-card" | "h4";
  }
>(({ className, variant = "h3", ...props }, ref) => {
  if (variant === "h1") {
    return (
      <h1
        ref={ref}
        className={cn(
          "text-3xl uppercase font-bold tracking-tight text-black pt-8 mb-[0rem] leading-10",
          className
        )}
        {...props}
      />
    );
  }

  if (variant === "h2") {
    return (
      <h2
        ref={ref}
        className={cn(
          "text-4xl font-bold tracking-tight text-black pt-4 mb-[0rem] leading-10",
          className
        )}
        {...props}
      />
    );
  }

  if (variant === "h4") {
    return (
      <h4
        ref={ref}
        className={cn(
          "text-2xl font-semibold tracking-tight text-black pt-4 mb-[.5rem] leading-10",
          className
        )}
        {...props}
      />
    );
  }

  if (variant === "h3-card") {
    return (
      <h3
        ref={ref}
        className={cn(
          "text-sm uppercase font-semibold tracking-tight bg-black text-white w-fit px-4 py-[.02rem] mt-10 mb-[1rem] leading-8",
          className
        )}
        style={{ fontFamily: "'IBM Plex Mono', monospace" }}
        {...props}
      />
    );
  }

  return (
    <h3
      ref={ref}
      className={cn(
        "text-3xl font-semibold tracking-tight text-black pt-4 mb-[1rem] leading-9",
        className
      )}
      {...props}
    />
  );
});
CardTitle.displayName = "CardTitle";

const CardDescription = React.forwardRef<
  HTMLParagraphElement,
  React.HTMLAttributes<HTMLParagraphElement>
>(({ className, ...props }, ref) => (
  <p ref={ref} className={cn("text-lg text-zinc-600", className)} {...props} />
));
CardDescription.displayName = "CardDescription";

const CardContent = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => (
  <div
    ref={ref}
    className={cn("p-6 pt-0 text-zinc-700", className)}
    {...props}
  />
));
CardContent.displayName = "CardContent";

export { Card, CardHeader, CardTitle, CardDescription, CardContent };
