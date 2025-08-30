import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';

const trainedModels = [
  {
    id: '1',
    name: 'Modèle Portrait Pro',
    status: 'ready',
    createdAt: '2 jours',
    trainingImages: 18,
    sampleImages: [
      '/api/placeholder/80/80',
      '/api/placeholder/80/80',
      '/api/placeholder/80/80',
      '/api/placeholder/80/80',
    ]
  },
  {
    id: '2',
    name: 'Modèle Business',
    status: 'ready',
    createdAt: '5 jours',
    trainingImages: 15,
    sampleImages: [
      '/api/placeholder/80/80',
      '/api/placeholder/80/80',
      '/api/placeholder/80/80',
    ]
  },
  {
    id: '3',
    name: 'Modèle Casual',
    status: 'training',
    createdAt: '1 heure',
    trainingImages: 20,
    sampleImages: []
  },
];

interface ModelsProps {
  onSelectModel: (modelId: string) => void;
}

export const Models = ({ onSelectModel }: ModelsProps) => {
  const getStatusColor = (status: string) => {
    switch (status) {
      case 'ready':
        return 'success';
      case 'training':
        return 'warning';
      case 'failed':
        return 'destructive';
      default:
        return 'secondary';
    }
  };

  const getStatusText = (status: string) => {
    switch (status) {
      case 'ready':
        return 'Prêt';
      case 'training':
        return 'En cours';
      case 'failed':
        return 'Échoué';
      default:
        return status;
    }
  };

  return (
    <div className="space-y-8">
      <div>
        <h2 className="text-2xl font-bold text-foreground mb-2">Mes modèles</h2>
        <p className="text-muted-foreground">Gérez vos modèles entraînés</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {trainedModels.map((model) => (
          <Card key={model.id} className="overflow-hidden">
            <CardHeader className="pb-4">
              <div className="flex items-center justify-between">
                <CardTitle className="text-lg">{model.name}</CardTitle>
                <Badge variant={getStatusColor(model.status) as any}>
                  {getStatusText(model.status)}
                </Badge>
              </div>
              <div className="text-sm text-muted-foreground">
                Créé il y a {model.createdAt} • {model.trainingImages} photos
              </div>
            </CardHeader>
            
            <CardContent className="space-y-4">
              {/* Sample Images */}
              {model.sampleImages.length > 0 ? (
                <div>
                  <p className="text-sm font-medium text-foreground mb-2">Photos d'entraînement</p>
                  <div className="grid grid-cols-4 gap-2">
                    {model.sampleImages.map((image, index) => (
                      <div key={index} className="aspect-square rounded bg-muted overflow-hidden">
                        <div className="w-full h-full bg-gradient-to-br from-muted to-accent flex items-center justify-center">
                          <span className="text-xs text-muted-foreground">{index + 1}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ) : (
                <div className="text-center py-4">
                  <p className="text-sm text-muted-foreground">Entraînement en cours...</p>
                </div>
              )}

              {/* Actions */}
              <div className="flex gap-2">
                <Button
                  variant="default"
                  size="sm"
                  className="flex-1"
                  disabled={model.status !== 'ready'}
                  onClick={() => onSelectModel(model.id)}
                >
                  Générer des images
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={model.status !== 'ready'}
                >
                  Détails
                </Button>
              </div>
            </CardContent>
          </Card>
        ))}

        {/* Add New Model Card */}
        <Card className="border-dashed border-2 border-upload-border hover:border-primary transition-colors cursor-pointer">
          <CardContent className="flex flex-col items-center justify-center h-full min-h-[300px] p-6">
            <div className="h-12 w-12 rounded-full bg-upload-zone flex items-center justify-center mb-4">
              <span className="text-2xl">+</span>
            </div>
            <h3 className="font-medium text-foreground mb-2">Nouveau modèle</h3>
            <p className="text-sm text-muted-foreground text-center">
              Entraînez un nouveau modèle avec vos photos
            </p>
          </CardContent>
        </Card>
      </div>
    </div>
  );
};