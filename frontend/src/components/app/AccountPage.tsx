import { useState, type FormEvent, type ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import { LogOut } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { appApi } from "@/api";
import { Field, FormError } from "@/components/auth/AuthShell";
import { auth } from "@/lib/auth";
import { errorMessage } from "@/lib/http";
import { integer, useSession } from "@/lib/session";
import { PageHeader } from "./AppLayout";

const MIN_PASSWORD = 8;
const CONFIRM_WORD = "SUPPRIMER";

function Card({ title, children, danger }: { title: string; children: ReactNode; danger?: boolean }) {
  return (
    <section className={danger ? "card-paper border-destructive/40 p-6" : "card-paper p-6"} aria-label={title}>
      <h2 className="display-sm">{title}</h2>
      <div className="mt-4">{children}</div>
    </section>
  );
}

export function AccountPage() {
  const { me, logout } = useSession();
  const navigate = useNavigate();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [pwError, setPwError] = useState<string | null>(null);
  const [pwBusy, setPwBusy] = useState(false);
  const [confirm, setConfirm] = useState("");
  const [deleting, setDeleting] = useState(false);

  async function changePassword(e: FormEvent) {
    e.preventDefault();
    if (next.length < MIN_PASSWORD) return;
    setPwBusy(true);
    setPwError(null);
    try {
      const r = await auth.changePassword(current, next);
      if (r.kind === "error") setPwError(r.message);
      else {
        toast.success("Mot de passe modifié.");
        setCurrent("");
        setNext("");
      }
    } catch {
      setPwError("Serveur injoignable, réessayez.");
    } finally {
      setPwBusy(false);
    }
  }

  async function deleteAccount() {
    setDeleting(true);
    try {
      await appApi.deleteAccount();
      await logout();
      toast.success("Votre compte et vos documents ont été supprimés.");
      navigate("/", { replace: true });
    } catch (err) {
      setDeleting(false);
      toast.error("Suppression impossible", { description: errorMessage(err) });
    }
  }

  return (
    <div className="h-full overflow-y-auto" data-lenis-prevent>
      <div className="mx-auto max-w-3xl space-y-6 px-4 py-8 sm:px-8">
        <PageHeader eyebrow="Espace" title="Compte" />

        <Card title="Profil">
          <dl className="divide-y divide-hairline text-sm">
            {[
              ["E-mail", me?.user.email ?? "—"],
              ["Offre", me?.workspace.plan === "paid" ? "À la carte" : "Gratuite"],
              ["Documents", me ? `${integer(me.workspace.documents_count)} / ${integer(me.workspace.max_documents)}` : "—"],
              ["Pages indexées", me ? `${integer(me.workspace.pages_count)} / ${integer(me.workspace.max_pages)}` : "—"],
            ].map(([k, v]) => (
              <div key={k} className="flex justify-between gap-4 py-2.5">
                <dt className="text-ink-muted">{k}</dt>
                <dd className="truncate text-ink">{v}</dd>
              </div>
            ))}
          </dl>
          <Button
            variant="outline"
            size="sm"
            className="mt-5"
            onClick={async () => {
              await logout();
              navigate("/");
            }}
          >
            <LogOut /> Se déconnecter
          </Button>
        </Card>

        <Card title="Mot de passe">
          <form onSubmit={changePassword} className="max-w-sm space-y-4" noValidate>
            <FormError>{pwError}</FormError>
            <Field
              label="Mot de passe actuel"
              type="password"
              autoComplete="current-password"
              value={current}
              onChange={(e) => setCurrent(e.target.value)}
              hint="Laissez vide si vous vous connectez avec Google."
            />
            <Field
              label="Nouveau mot de passe"
              type="password"
              autoComplete="new-password"
              minLength={MIN_PASSWORD}
              value={next}
              onChange={(e) => setNext(e.target.value)}
              hint={`${MIN_PASSWORD} caractères minimum.`}
            />
            <Button type="submit" variant="ink" size="sm" disabled={pwBusy || next.length < MIN_PASSWORD}>
              {pwBusy ? "Enregistrement…" : "Changer le mot de passe"}
            </Button>
          </form>
        </Card>

        <Card title="Supprimer le compte" danger>
          <p className="text-sm leading-relaxed text-ink-muted">
            Supprime définitivement votre compte, vos documents (originaux et index), vos conversations et vos crédits
            restants. Cette action est irréversible.
          </p>
          <div className="mt-4 max-w-sm space-y-3">
            <Field
              label={`Tapez ${CONFIRM_WORD} pour confirmer`}
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              autoComplete="off"
            />
            <Button variant="destructive" size="sm" disabled={confirm !== CONFIRM_WORD || deleting} onClick={deleteAccount}>
              {deleting ? "Suppression…" : "Supprimer définitivement"}
            </Button>
          </div>
        </Card>
      </div>
    </div>
  );
}
