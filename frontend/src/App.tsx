import { Navigate, Route, Routes } from "react-router-dom";
import { TooltipProvider } from "@/components/ui/tooltip";
import { Toaster } from "@/components/ui/sonner";
import { SiteLayout } from "@/components/site/SiteLayout";
import { Hero } from "@/components/sections/Hero";
import { Evaluation } from "@/components/sections/Evaluation";
import { Pricing } from "@/components/sections/Pricing";
import { DemoPage, LegalNoticePage, PrivacyPage, SecurityPage, TermsPage } from "@/components/pages/LegalPages";
import { AboutPage } from "@/components/pages/AboutPage";
import { PricingPage } from "@/components/pages/PricingPage";
import { ForgotPasswordPage, LoginPage, SignupPage, VerifyEmailPage } from "@/components/auth/AuthPages";
import { AppLayout, RequireAuth } from "@/components/app/AppLayout";
import { ChatPage } from "@/components/app/ChatPage";
import { DocumentsPage } from "@/components/app/DocumentsPage";
import { CreditsPage } from "@/components/app/CreditsPage";
import { AccountPage } from "@/components/app/AccountPage";
import { SessionProvider } from "@/lib/session";

function HomePage() {
  return (
    <>
      <Hero />
      <Evaluation />
      <Pricing />
    </>
  );
}

/*
 * Routes. Le serveur (Django, Vercel) doit renvoyer index.html sur chacune d'elles :
 * /, /a-propos, /tarifs, /demo, /securite, /conditions, /confidentialite, /mentions-legales, /connexion, /inscription, /verifier-email, /mot-de-passe-oublie, /app/*.
 */
export default function App() {
  return (
    <SessionProvider>
      <TooltipProvider delayDuration={150}>
        <Routes>
          <Route element={<SiteLayout />}>
            <Route index element={<HomePage />} />
            <Route path="a-propos" element={<AboutPage />} />
            <Route path="tarifs" element={<PricingPage />} />
            <Route path="demo" element={<DemoPage />} />
            <Route path="securite" element={<SecurityPage />} />
            <Route path="conditions" element={<TermsPage />} />
            <Route path="confidentialite" element={<PrivacyPage />} />
            <Route path="mentions-legales" element={<LegalNoticePage />} />
          </Route>
          <Route element={<SiteLayout footer={false} />}>
            <Route path="connexion" element={<LoginPage />} />
            <Route path="inscription" element={<SignupPage />} />
            <Route path="verifier-email" element={<VerifyEmailPage />} />
            <Route path="mot-de-passe-oublie" element={<ForgotPasswordPage />} />
          </Route>
          <Route path="app" element={<RequireAuth />}>
            <Route element={<AppLayout />}>
              <Route index element={<Navigate to="/app/chat" replace />} />
              <Route path="chat" element={<ChatPage />} />
              <Route path="documents" element={<DocumentsPage />} />
              <Route path="credits" element={<CreditsPage />} />
              <Route path="compte" element={<AccountPage />} />
              <Route path="*" element={<Navigate to="/app/chat" replace />} />
            </Route>
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
        <Toaster />
      </TooltipProvider>
    </SessionProvider>
  );
}
