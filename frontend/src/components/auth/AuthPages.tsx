import { useEffect, useState, type FormEvent } from "react";
import { Link, Navigate, useNavigate, useSearchParams } from "react-router-dom";
import { ArrowRight } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { auth, type AuthResult } from "@/lib/auth";
import { integer, usePricing, useSession } from "@/lib/session";
import { AuthShell, Divider, Field, FormError, GoogleButton, safeNext } from "./AuthShell";

const MIN_PASSWORD = 8;

function useAfterAuth() {
  const { refresh } = useSession();
  const navigate = useNavigate();
  return async (next: string) => {
    await refresh();
    navigate(next, { replace: true });
  };
}

/** Déjà connecté : les écrans de compte renvoient vers l'app. */
function useRedirectIfSignedIn(next: string) {
  const { status } = useSession();
  return status === "authenticated" ? <Navigate to={next} replace /> : null;
}

/* ---------- Connexion ---------- */

export function LoginPage() {
  const [params] = useSearchParams();
  const next = safeNext(params.get("next"));
  const navigate = useNavigate();
  const afterAuth = useAfterAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const redirect = useRedirectIfSignedIn(next);
  if (redirect) return redirect;

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const r = await auth.login(email.trim(), password);
      if (r.kind === "authenticated") await afterAuth(next);
      else if (r.kind === "verify_email")
        navigate(`/verifier-email?${new URLSearchParams({ email: email.trim(), next })}`);
      else setError(r.kind === "error" ? r.message : "Connexion impossible.");
    } catch {
      setError("Serveur injoignable, réessayez.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthShell
      eyebrow="Connexion"
      title="Bon retour parmi nous"
      footer={
        <>
          Pas encore de compte ?{" "}
          <Link to={`/inscription${next !== "/app/chat" ? `?next=${encodeURIComponent(next)}` : ""}`} className="font-medium text-brand-deep hover:underline">
            Créer un compte gratuit
          </Link>
        </>
      }
    >
      <GoogleButton next={next} />
      <Divider>ou avec votre e-mail</Divider>
      <form onSubmit={submit} className="space-y-4" noValidate>
        <FormError>{error}</FormError>
        <Field label="E-mail" type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
        <Field
          label="Mot de passe"
          type="password"
          autoComplete="current-password"
          required
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          hint={
            <Link to="/mot-de-passe-oublie" className="text-brand-deep hover:underline">
              Mot de passe oublié ?
            </Link>
          }
        />
        <Button type="submit" variant="brand" className="w-full" disabled={busy || !email || !password}>
          {busy ? "Connexion…" : "Se connecter"} <ArrowRight />
        </Button>
      </form>
    </AuthShell>
  );
}

/* ---------- Inscription ---------- */

export function SignupPage() {
  const [params] = useSearchParams();
  const next = safeNext(params.get("next"), "/app/documents");
  const navigate = useNavigate();
  const afterAuth = useAfterAuth();
  const pricing = usePricing();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<AuthResult | null>(null);
  const [busy, setBusy] = useState(false);
  const redirect = useRedirectIfSignedIn(next);
  if (redirect) return redirect;

  const tooShort = password.length > 0 && password.length < MIN_PASSWORD;

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (password.length < MIN_PASSWORD) return;
    setBusy(true);
    setError(null);
    try {
      const r = await auth.signup(email.trim(), password);
      if (r.kind === "authenticated") await afterAuth(next);
      else if (r.kind === "verify_email")
        navigate(`/verifier-email?${new URLSearchParams({ email: email.trim(), next })}`);
      else setError(r);
    } catch {
      setError({ kind: "error", message: "Serveur injoignable, réessayez." });
    } finally {
      setBusy(false);
    }
  }

  const fieldError = (name: string) => (error?.kind === "error" && error.field === name ? error.message : null);
  const globalError = error?.kind === "error" && !["email", "password"].includes(error.field ?? "") ? error.message : null;

  return (
    <AuthShell
      eyebrow="Inscription"
      title="Créez votre espace"
      intro={`${pricing.free.documents} documents et ${integer(pricing.free.welcome_credits)} crédits offerts, sans carte bancaire.`}
      footer={
        <>
          Déjà un compte ?{" "}
          <Link to="/connexion" className="font-medium text-brand-deep hover:underline">
            Se connecter
          </Link>
        </>
      }
    >
      <GoogleButton next={next} />
      <Divider>ou avec votre e-mail</Divider>
      <form onSubmit={submit} className="space-y-4" noValidate>
        <FormError>{globalError}</FormError>
        <Field
          label="E-mail"
          type="email"
          autoComplete="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          error={fieldError("email")}
        />
        <Field
          label="Mot de passe"
          type="password"
          autoComplete="new-password"
          required
          minLength={MIN_PASSWORD}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          error={fieldError("password") ?? (tooShort ? `${MIN_PASSWORD} caractères minimum.` : null)}
          hint={`${MIN_PASSWORD} caractères minimum.`}
        />
        <Button type="submit" variant="brand" className="w-full" disabled={busy || !email || password.length < MIN_PASSWORD}>
          {busy ? "Création…" : "Créer mon compte"} <ArrowRight />
        </Button>
        <p className="meta text-center">Un code de confirmation vous sera envoyé par e-mail.</p>
      </form>
    </AuthShell>
  );
}

/* ---------- Vérification de l'e-mail (code) ---------- */

export function VerifyEmailPage() {
  const [params] = useSearchParams();
  const next = safeNext(params.get("next"), "/app/documents");
  const email = params.get("email");
  const afterAuth = useAfterAuth();
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [cooldown, setCooldown] = useState(0);

  useEffect(() => {
    if (cooldown <= 0) return;
    const id = setTimeout(() => setCooldown((c) => c - 1), 1000);
    return () => clearTimeout(id);
  }, [cooldown]);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const r = await auth.verifyEmail(code);
      if (r.kind === "authenticated") {
        toast.success("E-mail confirmé, bienvenue !");
        await afterAuth(next);
      } else setError(r.kind === "error" ? r.message : "Code incorrect ou expiré.");
    } catch {
      setError("Serveur injoignable, réessayez.");
    } finally {
      setBusy(false);
    }
  }

  async function resend() {
    const r = await auth.resendVerification().catch(() => null);
    if (r?.kind === "error") toast.error(r.message);
    else toast.success("Un nouveau code vient d'être envoyé.");
    setCooldown(30);
  }

  return (
    <AuthShell
      eyebrow="Vérification"
      title="Confirmez votre e-mail"
      intro={
        <>
          Nous avons envoyé un code à {email ? <strong className="text-ink">{email}</strong> : "votre adresse"}. Saisissez-le
          pour activer votre espace.
        </>
      }
      footer={
        <button
          type="button"
          onClick={resend}
          disabled={cooldown > 0}
          className="cursor-pointer font-medium text-brand-deep hover:underline disabled:cursor-not-allowed disabled:text-ink-faint disabled:no-underline"
        >
          {cooldown > 0 ? `Renvoyer le code (${cooldown} s)` : "Renvoyer le code"}
        </button>
      }
    >
      <form onSubmit={submit} className="space-y-4" noValidate>
        <FormError>{error}</FormError>
        <Field
          label="Code de confirmation"
          inputMode="text"
          autoComplete="one-time-code"
          autoFocus
          required
          value={code}
          onChange={(e) => setCode(e.target.value.toUpperCase())}
          placeholder="XXXX-XXXX"
          hint="8 caractères, avec ou sans tiret."
          className="mono-xs text-center text-lg tracking-[0.3em]"
          maxLength={9}
        />
        <Button type="submit" variant="brand" className="w-full" disabled={busy || code.replace(/[^A-Z0-9]/gi, "").length < 8}>
          {busy ? "Vérification…" : "Confirmer"} <ArrowRight />
        </Button>
      </form>
    </AuthShell>
  );
}

/* ---------- Mot de passe oublié : e-mail → code + nouveau mot de passe ---------- */

export function ForgotPasswordPage() {
  const afterAuth = useAfterAuth();
  const navigate = useNavigate();
  const [step, setStep] = useState<"email" | "code">("email");
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function requestCode(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const r = await auth.requestPasswordReset(email.trim());
      // allauth ne dit pas si l'adresse existe : on passe à l'étape du code dans tous les cas.
      if (r.kind === "error") setError(r.message);
      else setStep("code");
    } catch {
      setError("Serveur injoignable, réessayez.");
    } finally {
      setBusy(false);
    }
  }

  async function reset(e: FormEvent) {
    e.preventDefault();
    if (password.length < MIN_PASSWORD) return;
    setBusy(true);
    setError(null);
    try {
      const r = await auth.resetPassword(code, password);
      if (r.kind === "authenticated") {
        toast.success("Mot de passe modifié.");
        await afterAuth("/app/chat");
      } else if (r.kind === "error") setError(r.message);
      else {
        toast.success("Mot de passe modifié, connectez-vous.");
        navigate("/connexion");
      }
    } catch {
      setError("Serveur injoignable, réessayez.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthShell
      eyebrow="Mot de passe oublié"
      title={step === "email" ? "Réinitialiser le mot de passe" : "Choisissez un nouveau mot de passe"}
      intro={
        step === "email"
          ? "Indiquez l'e-mail de votre compte : nous vous enverrons un code."
          : `Si un compte existe pour ${email}, un code vient de lui être envoyé.`
      }
      footer={
        <Link to="/connexion" className="font-medium text-brand-deep hover:underline">
          Retour à la connexion
        </Link>
      }
    >
      {step === "email" ? (
        <form onSubmit={requestCode} className="space-y-4" noValidate>
          <FormError>{error}</FormError>
          <Field label="E-mail" type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
          <Button type="submit" variant="brand" className="w-full" disabled={busy || !email}>
            {busy ? "Envoi…" : "Recevoir un code"} <ArrowRight />
          </Button>
        </form>
      ) : (
        <form onSubmit={reset} className="space-y-4" noValidate>
          <FormError>{error}</FormError>
          <Field
            label="Code reçu par e-mail"
            autoComplete="one-time-code"
            autoFocus
            required
            value={code}
            onChange={(e) => setCode(e.target.value.toUpperCase())}
            placeholder="XXXX-XXXX"
            hint="8 caractères, avec ou sans tiret."
            maxLength={9}
            className="mono-xs tracking-[0.3em]"
          />
          <Field
            label="Nouveau mot de passe"
            type="password"
            autoComplete="new-password"
            required
            minLength={MIN_PASSWORD}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            hint={`${MIN_PASSWORD} caractères minimum.`}
          />
          <Button
            type="submit"
            variant="brand"
            className="w-full"
            disabled={busy || !code || password.length < MIN_PASSWORD}
          >
            {busy ? "Enregistrement…" : "Enregistrer le mot de passe"} <ArrowRight />
          </Button>
        </form>
      )}
    </AuthShell>
  );
}
