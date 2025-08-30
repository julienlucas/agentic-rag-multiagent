import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';

const recentPredictions = [
  { id: '1', title: 'Photo Business - Plan buste', status: 'success', createdAt: '2 days ago' },
  { id: '2', title: 'Photo Harcourt - Serré', status: 'failed', createdAt: '2 days ago' },
  { id: '3', title: 'Photo Youtuber - Américain', status: 'success', createdAt: '3 days ago' },
  { id: '4', title: 'Photo Instagram - Plein pied', status: 'success', createdAt: '3 days ago' },
  { id: '5', title: 'Photo Super-héro - Taille', status: 'processing', createdAt: '4 days ago' },
];

const recentImages = [
  { id: '1', url: '/api/placeholder/150/150', alt: 'Generated photo 1' },
  { id: '2', url: '/api/placeholder/150/150', alt: 'Generated photo 2' },
  { id: '3', url: '/api/placeholder/150/150', alt: 'Generated photo 3' },
  { id: '4', url: '/api/placeholder/150/150', alt: 'Generated photo 4' },
  { id: '5', url: '/api/placeholder/150/150', alt: 'Generated photo 5' },
];

export const Dashboard = () => {
  const getStatusColor = (status: string) => {
    switch (status) {
      case 'success':
        return 'success';
      case 'failed':
        return 'destructive';
      case 'processing':
        return 'warning';
      default:
        return 'secondary';
    }
  };

  const getStatusText = (status: string) => {
    switch (status) {
      case 'success':
        return 'Réussi';
      case 'failed':
        return 'Échoué';
      case 'processing':
        return 'En cours';
      default:
        return status;
    }
  };

  return (
    <div className="space-y-8">
      <div>
        <h2 className="text-2xl font-bold text-foreground mb-2">Dashboard</h2>
        <p className="text-muted-foreground">Aperçu de vos générations récentes</p>
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
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 gap-4">
            {recentImages.map((image) => (
              <div key={image.id} className="aspect-square rounded-lg bg-muted overflow-hidden">
                <div className="w-full h-full bg-gradient-to-br from-muted to-accent flex items-center justify-center">
                  <span className="text-xs text-muted-foreground">Image {image.id}</span>
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
};