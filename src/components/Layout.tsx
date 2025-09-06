import { ReactNode } from 'react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { LayoutDashboard, GraduationCap, Database, Wand2 } from 'lucide-react';

interface LayoutProps {
  children: ReactNode;
  activeTab: string;
  onTabChange: (tab: string) => void;
}

const navigation = [
  { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { id: 'training', label: 'Entraînement', icon: GraduationCap },
  { id: 'models', label: 'Modèles', icon: Database },
  { id: 'generate', label: 'Générer des prédictions', icon: Wand2 },
];

export const Layout = ({ children, activeTab, onTabChange }: LayoutProps) => {
  return (
    <div className="min-h-screen bg-background flex flex-col">
      <header className="border-b border-border bg-card">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-8">
              <h1 className="text-2xl font-bold text-foreground">ProShoot</h1>
              <nav className="flex space-x-4">
                {navigation.map((item) => {
                  const Icon = item.icon;
                  return (
                    <button
                      key={item.id}
                      onClick={() => onTabChange(item.id)}
                      className={cn(
                        "flex items-center gap-2 border-b-2 py-4 px-1 text-sm font-medium transition-colors",
                        activeTab === item.id
                          ? "border-nav-active text-nav-active"
                          : "border-transparent text-nav-inactive hover:text-foreground hover:border-border"
                      )}
                    >
                      <Icon className="h-4 w-4" />
                      {item.label}
                    </button>
                  );
                })}
              </nav>
            </div>
            <div className="flex items-center space-x-4">
              <span className="text-sm text-muted-foreground">
                50 crédits restants
              </span>
              <Button>Ajouter des crédits</Button>
            </div>
          </div>
        </div>
      </header>

      {/* Content */}
      <main className="flex-1 mx-auto w-full max-w-7xl px-4 sm:px-6 lg:px-8 py-8">
        {children}
      </main>

      <footer className="border-t border-border bg-card mt-auto">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-4">
          <p className="text-sm text-muted-foreground">
            © {new Date().getFullYear()} ProShoot. Tous droits réservés. Fais avec 💙
          </p>
        </div>
      </footer>
    </div>
  );
};