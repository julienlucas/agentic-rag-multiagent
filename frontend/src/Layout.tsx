import { ReactNode } from 'react';
import { Bot, Sparkles } from "lucide-react";

interface LayoutProps {
  children: ReactNode;
}

export const Layout = ({ children }: LayoutProps) => {
  return (
    <div className="min-h-screen bg-background flex flex-col">
      <header className="border-b border-border bg-card">
        <div className="px-4 py-2 -mt-7 sm:px-6 lg:px-8">
          <div className="flex items-center justify-center gap-2 mb-1">
            <div className="relative">
              <Bot className="w-8 h-8 text-primary animate-glow" />
            </div>
            <h1 className="text-3xl font-bold gradient-text">DocChat</h1>
          </div>
        </div>
      </header>

      <main className="flex-1 mx-auto w-full max-w-7xl px-4 sm:px-6 lg:px-8 py-8">
        {children}
      </main>

      <footer className="border-t border-border bg-card mt-auto">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-4 -mb-8">
          <p className="text-sm">
            Propulsé par{" "}
            <span className="font-semibold text-primary">Mistral OCR</span> et{" "}
            <span className="font-semibold">LangGraph</span>
          </p>
        </div>
      </footer>
    </div>
  );
};