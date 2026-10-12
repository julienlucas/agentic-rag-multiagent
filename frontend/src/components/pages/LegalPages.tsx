import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { Container } from "@/components/site/primitives";
import { DemoChat } from "@/components/rag/DemoChat";

/*
 * Pages de confiance : sécurité, conditions, confidentialité, mentions légales, et la démo.
 * Les textes juridiques sont des BROUILLONS : les champs [entre crochets] sont à compléter, et
 * l'ensemble à faire relire avant la mise en production.
 */

const UPDATED = "12 octobre 2026";

function Doc({ eyebrow, title, intro, children }: { eyebrow: string; title: string; intro?: ReactNode; children: ReactNode }) {
  return (
    <section id="top" className="bg-paper">
      <Container width="narrow" className="py-16 sm:py-24">
        <span className="meta">{eyebrow}</span>
        <h1 className="display-lg mt-4">{title}</h1>
        {intro ? <div className="copy mt-5">{intro}</div> : null}
        <p className="meta mt-4">Mise à jour : {UPDATED}</p>
        <div className="legal mt-12 space-y-10">{children}</div>
      </Container>
    </section>
  );
}

function Block({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="border-t border-hairline pt-8">
      <h2 className="display-sm">{title}</h2>
      <div className="mt-4 space-y-3 leading-relaxed text-ink-muted [&_strong]:font-medium [&_strong]:text-ink [&_li]:ml-5 [&_li]:list-disc [&_li]:pl-1">
        {children}
      </div>
    </div>
  );
}

const SUBPROCESSORS: [string, string, string][] = [
  ["Railway", "Hébergement de l'API, de la base de données et des fichiers", "Région UE"],
  ["Vercel", "Hébergement du site", "Réseau mondial (pages publiques seulement)"],
  ["Amazon Web Services (Bedrock)", "Modèles Claude (Anthropic) et Cohere : réponses, embeddings, reranking", "Paris et Francfort"],
  ["Mistral AI", "Lecture (OCR) des PDF, documents bureautiques et images", "France"],
  ["Qdrant Cloud", "Index de recherche (passages et vecteurs)", "Région UE"],
  ["Stripe", "Paiement des recharges de crédits", "UE / États-Unis"],
  ["LangChain (LangSmith)", "Suivi de la qualité des réponses (traces des questions)", "États-Unis"],
];

export function SecurityPage() {
  return (
    <Doc
      eyebrow="sécurité"
      title="Vos documents restent les vôtres"
      intro={<p>Comment vos fichiers sont isolés, stockés, traités et supprimés.</p>}
    >
      <Block title="Un espace isolé par compte">
        <p>
          Chaque compte a son propre espace dans l'index de recherche. L'espace est déterminé par le serveur à partir
          de votre session, jamais par une valeur envoyée par le navigateur : toute lecture, recherche ou suppression
          est filtrée sur votre espace. Un autre compte ne peut ni voir, ni interroger, ni ouvrir vos documents, même
          en connaissant leur identifiant.
        </p>
      </Block>
      <Block title="Hébergement en Union européenne">
        <p>
          Les fichiers, la base de données et l'index sont hébergés dans l'UE. Les modèles d'IA sont appelés dans des
          régions européennes (Paris, Francfort) ; la lecture des documents est faite par Mistral AI, en France.
        </p>
      </Block>
      <Block title="Pas d'entraînement sur vos données">
        <p>
          Vos documents et vos questions servent uniquement à vous répondre. Les fournisseurs de modèles utilisés
          (Anthropic via Amazon Bedrock, Cohere, Mistral) ne les utilisent pas pour entraîner leurs modèles.
        </p>
      </Block>
      <Block title="Transport et accès">
        <ul>
          <li>Connexions chiffrées (HTTPS) de bout en bout.</li>
          <li>Session par cookie sécurisé, protection contre les requêtes intersites (CSRF) sur toute écriture.</li>
          <li>Adresse e-mail vérifiée par code avant l'ouverture d'un espace.</li>
          <li>Chaque fichier est contrôlé à la réception : son contenu doit correspondre à son extension.</li>
        </ul>
      </Block>
      <Block title="Suppression">
        <p>
          Supprimer un document efface ses passages et ses pages de l'index ; le fichier original est effacé dès
          qu'aucun espace ne l'utilise plus. Supprimer votre compte (Compte → Supprimer) efface tout : documents,
          index, conversations et historique de crédits.
        </p>
      </Block>
      <Block title="Signaler une faille">
        <p>
          Écrivez à <strong>[adresse de contact sécurité]</strong>. Nous répondons sous 72 heures et vous tenons
          informé jusqu'à la correction.
        </p>
      </Block>
    </Doc>
  );
}

export function TermsPage() {
  return (
    <Doc eyebrow="légal" title="Conditions d'utilisation" intro={<p>Brouillon à faire relire avant la mise en production.</p>}>
      <Block title="1. Le service">
        <p>
          Agentic Search permet de déposer des documents et de leur poser des questions. Le service est édité par
          <strong> [raison sociale]</strong> (voir les <Link to="/mentions-legales" className="text-brand-deep underline">mentions légales</Link>).
        </p>
      </Block>
      <Block title="2. Compte">
        <p>
          Un compte par personne, ouvert avec une adresse e-mail vérifiée. Vous êtes responsable de la confidentialité
          de votre mot de passe et des documents que vous déposez, dont vous devez détenir les droits.
        </p>
      </Block>
      <Block title="3. Crédits et paiement">
        <ul>
          <li>Le service fonctionne au crédit prépayé : 1 crédit = 0,01 € TTC.</li>
          <li>Une question coûte 20 crédits ; l'indexation d'une page, 1 crédit (offerte dans l'offre gratuite).</li>
          <li>Le coût d'une indexation est affiché avant qu'elle soit lancée. Une action qui échoue est remboursée en crédits.</li>
          <li>Les crédits n'expirent pas. Ils ne sont pas remboursables en argent, sauf obligation légale.</li>
          <li>Droit de rétractation : en lançant l'utilisation des crédits, vous demandez l'exécution immédiate du service. [à valider]</li>
        </ul>
      </Block>
      <Block title="4. Réponses générées">
        <p>
          Les réponses sont produites par des modèles d'IA à partir de vos documents et citent leurs sources. Elles
          peuvent contenir des erreurs : vérifiez les passages cités avant toute décision importante. Le service
          ne fournit pas de conseil financier, juridique ou médical.
        </p>
      </Block>
      <Block title="5. Usage acceptable">
        <p>
          Interdits : déposer des contenus illicites ou dont vous n'avez pas les droits, contourner les quotas ou
          l'isolation des espaces, revendre l'accès au service sans accord.
        </p>
      </Block>
      <Block title="6. Responsabilité, résiliation, droit applicable">
        <p>
          [à compléter] Vous pouvez supprimer votre compte à tout moment. Droit applicable : droit français ;
          tribunaux compétents : [ville].
        </p>
      </Block>
    </Doc>
  );
}

export function PrivacyPage() {
  return (
    <Doc eyebrow="légal" title="Politique de confidentialité" intro={<p>Brouillon à faire relire avant la mise en production.</p>}>
      <Block title="Responsable du traitement">
        <p><strong>[raison sociale]</strong>, [adresse]. Contact : <strong>[e-mail]</strong>.</p>
      </Block>
      <Block title="Données traitées">
        <ul>
          <li><strong>Compte</strong> : adresse e-mail, mot de passe (chiffré, jamais lisible).</li>
          <li><strong>Documents</strong> : les fichiers déposés, leur texte et leur index de recherche.</li>
          <li><strong>Usage</strong> : questions, réponses, votes, mouvements de crédits.</li>
          <li><strong>Paiement</strong> : traité par Stripe ; nous ne voyons jamais votre numéro de carte.</li>
        </ul>
      </Block>
      <Block title="Finalités et bases légales">
        <p>
          Fournir le service (exécution du contrat), facturer (obligation légale), améliorer la qualité des réponses
          à partir des votes et des traces (intérêt légitime, désactivable sur demande).
        </p>
      </Block>
      <Block title="Durée de conservation">
        <p>
          Documents et conversations : tant que le compte existe. Factures : 10 ans. Comptes inactifs : [durée] après
          la dernière connexion, après avertissement par e-mail.
        </p>
      </Block>
      <Block title="Sous-traitants">
        <div className="overflow-x-auto rounded-[var(--radius-media)] border border-hairline">
          <table className="w-full min-w-[34rem] text-left text-sm">
            <thead className="bg-paper-2 text-ink">
              <tr>
                <th className="px-4 py-3 font-medium">Prestataire</th>
                <th className="px-4 py-3 font-medium">Rôle</th>
                <th className="px-4 py-3 font-medium">Localisation</th>
              </tr>
            </thead>
            <tbody>
              {SUBPROCESSORS.map(([who, what, where]) => (
                <tr key={who} className="border-t border-hairline">
                  <td className="px-4 py-3 text-ink">{who}</td>
                  <td className="px-4 py-3">{what}</td>
                  <td className="px-4 py-3">{where}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Block>
      <Block title="Vos droits">
        <p>
          Accès, rectification, effacement, portabilité, opposition : écrivez à <strong>[e-mail]</strong>, ou supprimez
          directement votre compte depuis l'app. Vous pouvez saisir la CNIL (cnil.fr).
        </p>
      </Block>
      <Block title="Cookies">
        <p>
          Seulement deux cookies techniques, indispensables : la session (rester connecté) et la protection CSRF.
          Aucun cookie publicitaire ni de mesure d'audience.
        </p>
      </Block>
    </Doc>
  );
}

export function LegalNoticePage() {
  return (
    <Doc eyebrow="légal" title="Mentions légales">
      <Block title="Éditeur">
        <p>
          <strong>[raison sociale]</strong>, [forme juridique] au capital de [montant], immatriculée sous le numéro
          [SIREN] au RCS de [ville]. Siège : [adresse]. Directeur de la publication : [nom]. Contact : [e-mail].
        </p>
      </Block>
      <Block title="Hébergement">
        <p>
          API, base de données et fichiers : Railway Corporation, [adresse], région UE. Site : Vercel Inc.,
          440 N Barranca Ave #4133, Covina, CA 91723, États-Unis.
        </p>
      </Block>
      <Block title="Propriété intellectuelle">
        <p>
          Le code du moteur de recherche est publié en open source sur GitHub, sous sa licence. Les marques et
          contenus du site restent la propriété de leurs auteurs.
        </p>
      </Block>
    </Doc>
  );
}

export function DemoPage() {
  return (
    <section id="top" className="bg-paper">
      <Container className="py-14 sm:py-20">
        <span className="meta">démo</span>
        <h1 className="display-lg mt-4">Essayez sur deux rapports annuels</h1>
        <p className="copy mt-4">
          Chargez le 10-K 2022 d'AMD ou de Boeing (120 et 190 pages, chargement immédiat), puis posez une question :
          l'agent cherche, lit les pages et cite ses sources. Pour vos propres documents,{" "}
          <Link to="/inscription" className="font-medium text-brand-deep underline underline-offset-4">créez un espace gratuit</Link>.
        </p>
        <div className="mt-10">
          <DemoChat />
        </div>
      </Container>
    </section>
  );
}
