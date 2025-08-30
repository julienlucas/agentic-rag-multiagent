import { ReactNode } from 'react';
import { cn } from '@/lib/utils';

interface LayoutProps {
  children: ReactNode;
  activeTab: string;
  onTabChange: (tab: string) => void;
}

const navigation = [
  { id: 'dashboard', label: 'Dashboard' },
  { id: 'training', label: 'Entraînement' },
  { id: 'models', label: 'Modèles' },
  { id: 'generate', label: 'Générer' },
];

export const Layout = ({ children, activeTab, onTabChange }: LayoutProps) => {
  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="border-b border-border bg-card">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="flex h-16 items-center justify-between">
            <div className="flex items-center">
              <h1 className="text-xl font-semibold text-foreground">AI Photo Studio</h1>
            </div>
            <div className="flex items-center space-x-4">
              <span className="text-sm text-muted-foreground">50 crédits restants</span>
              <div className="h-8 w-8 rounded-full bg-primary" />
            </div>
          </div>
        </div>
      </header>

      {/* Navigation */}
      <nav className="border-b border-border bg-card">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="flex space-x-8">
            {navigation.map((item) => (
              <button
                key={item.id}
                onClick={() => onTabChange(item.id)}
                className={cn(
                  "border-b-2 py-4 px-1 text-sm font-medium transition-colors",
                  activeTab === item.id
                    ? "border-nav-active text-nav-active"
                    : "border-transparent text-nav-inactive hover:text-foreground hover:border-border"
                )}
              >
                {item.label}
              </button>
            ))}
          </div>
        </div>
      </nav>

      {/* Content */}
      <main className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-8">
        {children}
      </main>
    </div>
  );
};