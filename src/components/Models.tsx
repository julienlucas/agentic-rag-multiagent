import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { useState } from 'react';

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
  const [searchTerm, setSearchTerm] = useState('');

  const filteredModels = trainedModels.filter(model =>
    model.name.toLowerCase().includes(searchTerm.toLowerCase())
  );

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

      <div className="flex justify-end mb-6">
        <Button
          onClick={() => {/* Navigate to training */}}
          className="flex items-center gap-2"
        >
          <span className="text-lg">+</span>
          Nouveau modèle
        </Button>
      </div>

      {/* Search */}
      <div className="mb-6">
        <Input
          type="text"
          placeholder="Rechercher un modèle..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          className="max-w-md"
        />
      </div>

      <div className="space-y-4">
        {filteredModels.map((model) => (
          <Card key={model.id} className="overflow-hidden">
            <CardContent className="p-6">
              <div className="flex items-start gap-4">
                {/* Sample Images */}
                <div className="flex-shrink-0">
                  {model.sampleImages.length > 0 ? (
                    <div className="grid grid-cols-2 gap-1 w-20">
                      {model.sampleImages.slice(0, 4).map((image, index) => (
                        <div key={index} className="aspect-square rounded bg-muted overflow-hidden">
                          <div className="w-full h-full bg-gradient-to-br from-muted to-accent flex items-center justify-center">
                            <span className="text-xs text-muted-foreground">{index + 1}</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="w-20 h-20 rounded bg-muted flex items-center justify-center">
                      <span className="text-xs text-muted-foreground">—</span>
                    </div>
                  )}
                </div>

                {/* Model Info */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between mb-2">
                    <h3 className="text-lg font-semibold text-foreground">{model.name}</h3>
                    <Badge variant={getStatusColor(model.status) as any}>
                      {getStatusText(model.status)}
                    </Badge>
                  </div>
                  <p className="text-sm text-muted-foreground mb-4">
                    Créé il y a {model.createdAt} • {model.trainingImages} photos d'entraînement
                  </p>

                  {/* Actions */}
                  <div className="flex gap-2">
                    <Button
                      variant="default"
                      size="sm"
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
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
};