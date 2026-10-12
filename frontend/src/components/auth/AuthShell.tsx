import { forwardRef, useId, type InputHTMLAttributes, type ReactNode } from "react";
import { Container } from "@/components/site/primitives";
import { auth } from "@/lib/auth";
import { cn } from "@/lib/utils";

/** Mise en page des écrans de compte : une carte centrée, titre, sous-titre, formulaire, liens. */
export function AuthShell({
  eyebrow,
  title,
  intro,
  children,
  footer,
}: {
  eyebrow: string;
  title: ReactNode;
  intro?: ReactNode;
  children: ReactNode;
  footer?: ReactNode;
}) {
  return (
    <section className="bg-paper-2">
      <Container width="narrow" className="flex min-h-[calc(100dvh-3.5rem)] items-center justify-center py-12">
        <div className="card-paper w-full max-w-md p-6 sm:p-8">
          <span className="eyebrow">{eyebrow}</span>
          <h1 className="display-md mt-3">{title}</h1>
          {intro ? <p className="mt-3 text-sm leading-relaxed text-ink-muted">{intro}</p> : null}
          <div className="mt-6">{children}</div>
          {footer ? <div className="mt-6 border-t border-hairline pt-5 text-sm text-ink-muted">{footer}</div> : null}
        </div>
      </Container>
    </section>
  );
}

type FieldProps = InputHTMLAttributes<HTMLInputElement> & { label: string; error?: string | null; hint?: ReactNode };

/** Champ de formulaire : libellé, saisie, aide ou erreur reliées par aria-describedby. */
export const Field = forwardRef<HTMLInputElement, FieldProps>(function Field(
  { label, error, hint, className, id, ...props },
  ref,
) {
  const auto = useId();
  const inputId = id ?? auto;
  const describedBy = error ? `${inputId}-error` : hint ? `${inputId}-hint` : undefined;
  return (
    <div className="space-y-1.5">
      <label htmlFor={inputId} className="block text-sm font-medium text-ink">
        {label}
      </label>
      <input
        ref={ref}
        id={inputId}
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy}
        className={cn(
          "block min-h-11 w-full rounded-sm border border-hairline-strong bg-paper px-3 text-sm text-ink outline-none transition-colors",
          "placeholder:text-ink-faint focus:border-brand",
          error && "border-destructive",
          className,
        )}
        {...props}
      />
      {error ? (
        <p id={`${inputId}-error`} className="text-xs text-destructive">
          {error}
        </p>
      ) : hint ? (
        <p id={`${inputId}-hint`} className="meta">
          {hint}
        </p>
      ) : null}
    </div>
  );
});

/** Message d'erreur global d'un formulaire. */
export function FormError({ children }: { children?: ReactNode }) {
  if (!children) return null;
  return (
    <p role="alert" className="rounded-sm border border-destructive/30 bg-destructive/5 px-3 py-2 text-sm text-destructive">
      {children}
    </p>
  );
}

/** « Continuer avec Google » : redirection navigateur gérée par allauth. */
export function GoogleButton({ next = "/app" }: { next?: string }) {
  return (
    <button
      type="button"
      onClick={() => auth.google(next)}
      className="inline-flex min-h-11 w-full cursor-pointer items-center justify-center gap-2.5 rounded-sm border border-hairline-strong bg-paper px-4 text-[0.9375rem] font-medium text-ink transition-colors hover:border-ink"
    >
      <svg aria-hidden viewBox="0 0 24 24" className="size-4">
        <path fill="#4285F4" d="M23.5 12.3c0-.8-.1-1.6-.2-2.3H12v4.4h6.5a5.5 5.5 0 0 1-2.4 3.6v3h3.9c2.2-2.1 3.5-5.1 3.5-8.7z" />
        <path fill="#34A853" d="M12 24c3.2 0 6-1.1 8-2.9l-3.9-3c-1.1.7-2.5 1.2-4.1 1.2-3.1 0-5.8-2.1-6.7-5H1.3v3.1A12 12 0 0 0 12 24z" />
        <path fill="#FBBC05" d="M5.3 14.3a7.2 7.2 0 0 1 0-4.6V6.6H1.3a12 12 0 0 0 0 10.8l4-3.1z" />
        <path fill="#EA4335" d="M12 4.8c1.8 0 3.3.6 4.6 1.8l3.4-3.4A12 12 0 0 0 1.3 6.6l4 3.1c.9-2.9 3.6-4.9 6.7-4.9z" />
      </svg>
      Continuer avec Google
    </button>
  );
}

export function Divider({ children }: { children: ReactNode }) {
  return (
    <div className="my-5 flex items-center gap-3">
      <span className="h-px flex-1 bg-hairline" />
      <span className="meta">{children}</span>
      <span className="h-px flex-1 bg-hairline" />
    </div>
  );
}

/** `next` sûr : un chemin interne seulement (pas de redirection ouverte vers un autre site). */
export function safeNext(value: string | null, fallback = "/app/chat") {
  return value && value.startsWith("/") && !value.startsWith("//") ? value : fallback;
}
