import { useState } from "react";
import { Button } from "@/components/ui/button";

type SubmitStatus = "success" | "error" | null;

export default function ContactForm() {
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitStatus, setSubmitStatus] = useState<SubmitStatus>(null);

  const handleSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (isSubmitting) {
      return;
    }
    setIsSubmitting(true);
    setSubmitStatus(null);
    const form = event.currentTarget;

    window.setTimeout(() => {
      setIsSubmitting(false);
      setSubmitStatus("success");
      form.reset();
    }, 600);
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="space-y-1">
        <label className="text-sm font-medium">Votre adresse email</label>
        <input
          type="email"
          name="from_email"
          required
          className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring"
        />
      </div>

      <div className="space-y-1">
        <label className="text-sm font-medium">Votre nom et prénom</label>
        <input
          type="text"
          name="name"
          required
          className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring"
        />
      </div>

      <div className="space-y-1">
        <label className="text-sm font-medium">
          Le nom de votre entreprise
        </label>
        <input
          type="text"
          name="company"
          className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring"
        />
      </div>

      <div className="space-y-1">
        <label className="text-sm font-medium">Sujet</label>
        <input
          type="text"
          name="subject"
          required
          className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring"
        />
      </div>

      <div className="space-y-1">
        <label className="text-sm font-medium">Votre message</label>
        <textarea
          name="message"
          required
          rows={5}
          className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring"
        />
      </div>

      <Button variant="default" size="xl" className="w-full" disabled={isSubmitting}>
        {isSubmitting ? "Envoi en cours..." : "Envoyer maintenant"}
      </Button>
      {submitStatus === "success" && (
        <p className="text-green-600 text-sm">Message envoyé avec succès !</p>
      )}
      {submitStatus === "error" && (
        <p className="text-red-600 text-sm">
          Erreur lors de l'envoi. Veuillez réessayer.
        </p>
      )}
    </form>
  );
}
