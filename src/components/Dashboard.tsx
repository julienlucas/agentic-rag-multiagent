import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Moon, Sun, CheckCircle } from 'lucide-react';
import { useState } from 'react';
import { RecentGenerations } from '@/components/ui/recent-generations';
import { RecentImages } from '@/components/ui/recent-images';

const recentPredictions = [
  { id: '1', theme: 'Business', framing: 'Plan buste', createdAt: '2 days ago', image: '/api/placeholder/400/600' },
  { id: '2', theme: 'Harcourt', framing: 'Serré', createdAt: '2 days ago', image: '/api/placeholder/400/500' },
  { id: '3', theme: 'Youtuber', framing: 'Américain', createdAt: '3 days ago', image: '/api/placeholder/600/400' },
  { id: '4', theme: 'Instagram', framing: 'Plein pied', createdAt: '3 days ago', image: '/api/placeholder/300/600' },
  { id: '5', theme: 'Super-héro', framing: 'Taille', createdAt: '4 days ago', image: '/api/placeholder/500/500' },
];

const recentImages = [
  { id: '1', url: '/api/placeholder/300/300', alt: 'Generated photo 1', aspectRatio: '1:1', theme: 'Business' },
  { id: '2', url: '/api/placeholder/400/300', alt: 'Generated photo 2', aspectRatio: '4:3', theme: 'Vacances' },
  { id: '3', url: '/api/placeholder/480/270', alt: 'Generated photo 3', aspectRatio: '16:9', theme: 'Youtuber' },
  { id: '4', url: '/api/placeholder/270/480', alt: 'Generated photo 4', aspectRatio: '9:16', theme: 'Portrait' },
  { id: '5', url: '/api/placeholder/300/300', alt: 'Generated photo 5', aspectRatio: '1:1', theme: 'Sport' },
  { id: '6', url: '/api/placeholder/400/300', alt: 'Generated photo 6', aspectRatio: '4:3', theme: 'Mode' },
  { id: '7', url: '/api/placeholder/480/270', alt: 'Generated photo 7', aspectRatio: '16:9', theme: 'Art' },
  { id: '8', url: '/api/placeholder/270/480', alt: 'Generated photo 8', aspectRatio: '9:16', theme: 'Street' },
  { id: '9', url: '/api/placeholder/300/300', alt: 'Generated photo 9', aspectRatio: '1:1', theme: 'Corporate' },
  { id: '10', url: '/api/placeholder/400/300', alt: 'Generated photo 10', aspectRatio: '4:3', theme: 'Nature' },
  { id: '11', url: '/api/placeholder/480/270', alt: 'Generated photo 11', aspectRatio: '16:9', theme: 'Techno' },
  { id: '12', url: '/api/placeholder/270/480', alt: 'Generated photo 12', aspectRatio: '9:16', theme: 'Fashion' },
  { id: '13', url: '/api/placeholder/300/300', alt: 'Generated photo 13', aspectRatio: '1:1', theme: 'Lifestyle' },
  { id: '14', url: '/api/placeholder/400/300', alt: 'Generated photo 14', aspectRatio: '4:3', theme: 'Travel' },
  { id: '15', url: '/api/placeholder/480/270', alt: 'Generated photo 15', aspectRatio: '16:9', theme: 'Food' },
];

export const Dashboard = () => {
  const [isDark, setIsDark] = useState(false);

  const toggleTheme = () => {
    setIsDark(!isDark);
    // Ici on pourrait ajouter la logique pour changer le thème global
  };


  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-foreground mb-2">Dashboard</h2>
          <p className="text-muted-foreground">
            Aperçu de vos générations récentes
          </p>
        </div>

        <Button
          variant="ghost"
          size="icon"
          onClick={toggleTheme}
          className="h-10 w-10"
        >
          {isDark ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
        </Button>
      </div>

      {/* Onboarding pour nouveaux utilisateurs */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <Card className={`border-dashed border-2 flex flex-col relative ${true ? '' : 'opacity-50'}`}>
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <CardTitle className="text-lg">1. Ajoutez des crédits</CardTitle>
              {true && (
                <CheckCircle className="h-5 w-5 text-green-500" />
              )}
            </div>
          </CardHeader>
          <CardContent className="flex-1 flex flex-col">
            <p className="text-sm text-muted-foreground mb-4">
              Ajoutez des crédits pour commencer
            </p>
            <div className="mt-auto">
              <Button className="w-full">S'inscrire</Button>
            </div>
          </CardContent>
        </Card>

        <Card className={`border-dashed border-2 flex flex-col relative ${false ? '' : 'opacity-50'}`}>
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <CardTitle className="text-lg">2. Entraînez un modèle (3min)</CardTitle>
              {false && (
                <CheckCircle className="h-5 w-5 text-green-500" />
              )}
            </div>
          </CardHeader>
          <CardContent className="flex-1 flex flex-col">
            <p className="text-sm text-muted-foreground mb-4">
              Uploadez 10-20 photos pour entraîner votre modèle personnalisé
            </p>
            <div className="mt-auto">
              <Button variant="outline" className="w-full">
                Entraîner
              </Button>
            </div>
          </CardContent>
        </Card>

        <Card className={`border-dashed border-2 flex flex-col relative ${false ? '' : 'opacity-50'}`}>
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <CardTitle className="text-lg">
                3. Générez des prédictions
              </CardTitle>
              {false && (
                <CheckCircle className="h-5 w-5 text-green-500" />
              )}
            </div>
          </CardHeader>
          <CardContent className="flex-1 flex flex-col">
            <p className="text-sm text-muted-foreground mb-4">
              Créez des images professionnelles avec votre modèle entraîné
            </p>
            <div className="mt-auto">
              <Button variant="outline" className="w-full">
                Générer
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Crédits restants
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-foreground">50</div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Modèles entraînés
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-foreground">2</div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Images générées
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-foreground">47</div>
          </CardContent>
        </Card>
      </div>

      {/* Recent Predictions */}
      <RecentGenerations
        generations={recentPredictions}
        title="Prédictions récentes"
      />

      {/* Recent Images */}
      <RecentImages images={recentImages} />
    </div>
  );
};