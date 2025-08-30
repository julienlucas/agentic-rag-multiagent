import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Moon, Sun } from 'lucide-react';
import { useState } from 'react';

const recentPredictions = [
  { id: '1', title: 'Photo Business - Plan buste', status: 'success', createdAt: '2 days ago' },
  { id: '2', title: 'Photo Harcourt - Serré', status: 'failed', createdAt: '2 days ago' },
  { id: '3', title: 'Photo Youtuber - Américain', status: 'success', createdAt: '3 days ago' },
  { id: '4', title: 'Photo Instagram - Plein pied', status: 'success', createdAt: '3 days ago' },
  { id: '5', title: 'Photo Super-héro - Taille', status: 'processing', createdAt: '4 days ago' },
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

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'success':
        return 'success';
      case 'failed':
        return 'success';
      case 'processing':
        return 'warning';
      default:
        return 'secondary';
    }
  };

  const getStatusText = (status: string) => {
    switch (status) {
      case 'success':
        return 'Terminé';
      case 'failed':
        return 'Terminé';
      case 'processing':
        return 'En cours';
      default:
        return status;
    }
  };

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-foreground mb-2">Dashboard</h2>
          <p className="text-muted-foreground">Aperçu de vos générations récentes</p>
        </div>

        <Button
          variant="ghost"
          size="icon"
          onClick={toggleTheme}
          className="h-10 w-10"
        >
          {isDark ? (
            <Sun className="h-5 w-5" />
          ) : (
            <Moon className="h-5 w-5" />
          )}
        </Button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Crédits restants</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-foreground">50</div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Modèles entraînés</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-foreground">2</div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Images générées</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-foreground">47</div>
          </CardContent>
        </Card>
      </div>

      {/* Recent Predictions */}
      <Card>
        <CardHeader>
          <CardTitle>Prédictions récentes</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {recentPredictions.map((prediction) => (
              <div key={prediction.id} className="flex items-center justify-between py-3 border-b border-border last:border-0">
                <div className="flex-1">
                  <p className="font-medium text-foreground">{prediction.title}</p>
                  <p className="text-sm text-muted-foreground">{prediction.createdAt}</p>
                </div>
                <Badge variant={getStatusColor(prediction.status) as any}>
                  {getStatusText(prediction.status)}
                </Badge>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Recent Images */}
      <Card>
        <CardHeader>
          <CardTitle>15 dernières images générées</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="columns-2 sm:columns-1 md:columns-2 lg:columns-3 gap-4">
            {recentImages.map((image) => (
              <div key={image.id} className="break-inside-avoid group relative">
                <div
                  className={`bg-muted overflow-hidden bg-gradient-to-br from-muted to-accent flex items-center justify-center relative mb-4`}
                  style={{
                    aspectRatio: image.aspectRatio === '1:1' ? '1/1' :
                                 image.aspectRatio === '4:3' ? '4/3' :
                                 image.aspectRatio === '16:9' ? '16/9' : '9/16'
                  }}
                >
                  <span className="text-xs text-muted-foreground">Image {image.id}</span>

                  {/* Overlay au survol */}
                  <div className="absolute inset-0 bg-black/20 opacity-0 group-hover:opacity-100 transition-opacity duration-200 flex items-end justify-end p-3">
                    <Badge variant="secondary" className="text-xs">
                      {image.theme}
                    </Badge>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
};