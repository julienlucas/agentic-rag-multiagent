import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

export function Container({
  children,
  className,
  width = "default",
}: {
  children: ReactNode;
  className?: string;
  width?: "default" | "narrow" | "wide";
}) {
  return (
    <div
      className={cn(
        "mx-auto w-full px-5 sm:px-8",
        width === "narrow" && "max-w-3xl",
        width === "default" && "max-w-6xl",
        width === "wide" && "max-w-7xl",
        className,
      )}
    >
      {children}
    </div>
  );
}

export function Eyebrow({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <span
      className={cn(
        "eyebrow inline-flex items-center gap-2 rounded-full border border-sand/70 bg-brand-surface px-3 py-1",
        className,
      )}
    >
      {children}
    </span>
  );
}

/** Section numérotée, mise en page éditoriale : grand index, eyebrow, titre display. */
export function Section({
  index,
  eyebrow,
  title,
  intro,
  children,
  className,
  tone = "paper",
  id,
}: {
  index?: string;
  eyebrow?: string;
  title?: ReactNode;
  intro?: ReactNode;
  children?: ReactNode;
  className?: string;
  tone?: "paper" | "muted" | "ink";
  id?: string;
}) {
  return (
    <section
      id={id}
      className={cn(
        "scroll-mt-16 border-t border-border py-20 sm:py-28",
        tone === "muted" && "bg-paper-2",
        tone === "ink" && "grain bg-ink text-on-ink border-white/10",
        className,
      )}
    >
      <Container>
        <div className="grid gap-10 lg:grid-cols-[5rem_1fr]">
          <div className="hidden lg:block">
            {index ? (
              <div
                className={cn(
                  "font-display text-5xl font-light leading-none",
                  tone === "ink" ? "text-on-ink-muted" : "text-sand-deep",
                )}
              >
                {index}
                <div className={cn("mt-3 h-px w-10", tone === "ink" ? "bg-brand-light" : "bg-brand")} />
              </div>
            ) : null}
          </div>
          <div className="min-w-0">
            {eyebrow ? (
              <Eyebrow className={tone === "ink" ? "border-white/15 bg-white/5 text-brand-light" : undefined}>
                {eyebrow}
              </Eyebrow>
            ) : null}
            {title ? (
              <h2 className={cn("display-lg mt-5 max-w-3xl", tone === "ink" && "text-on-ink")}>
                {title}
              </h2>
            ) : null}
            {intro ? (
              <div
                className={cn("copy mt-5 text-[1.0625rem]", tone === "ink" && "text-on-ink-muted")}
              >
                {intro}
              </div>
            ) : null}
            {children ? <div className="mt-12">{children}</div> : null}
          </div>
        </div>
      </Container>
    </section>
  );
}

