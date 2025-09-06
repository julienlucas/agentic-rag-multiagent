import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

const trainedModels = [
  {
    id: "1",
    name: "Modèle Portrait Pro",
    status: "ready",
    createdAt: "2 jours",
    trainingImages: 18,
    sampleImages: [
      "/api/placeholder/80/80",
      "/api/placeholder/80/80",
      "/api/placeholder/80/80",
      "/api/placeholder/80/80",
    ],
  },
  {
    id: "2",
    name: "Modèle Business",
    status: "ready",
    createdAt: "5 jours",
    trainingImages: 15,
    sampleImages: [
      "/api/placeholder/80/80",
      "/api/placeholder/80/80",
      "/api/placeholder/80/80",
    ],
  },
  {
    id: "3",
    name: "Modèle Casual",
    status: "training",
    createdAt: "1 heure",
    trainingImages: 20,
    sampleImages: [],
  },
];

interface ModelsProps {
  onSelectModel: (modelId: string) => void;
}

export const Models = ({ onSelectModel }: ModelsProps) => {
  const getStatusColor = (status: string) => {
    switch (status) {
      case "ready":
        return "success";
      case "training":
        return "warning";
      case "failed":
        return "destructive";
      default:
        return "secondary";
    }
  };

  const getStatusText = (status: string) => {
    switch (status) {
      case "training":
        return "En cours d'entraînement";
      default:
        return "";
    }
  };

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-foreground mb-2">
            Mes modèles
          </h2>
          <p className="text-muted-foreground">Gérez vos modèles entraînés</p>
        </div>
        <Button
          onClick={() => {
            /* Navigate to training */
          }}
          className="flex items-center gap-2"
        >
          <span className="text-lg">+</span>
          Nouveau modèle
        </Button>
      </div>

      <Card>
        <CardContent>
          <div className="space-y-4">
            {trainedModels.map((model, index) => (
              <div
                key={model.id}
                className="p-2 border-b border-border last:border-0"
              >
                <div className={`flex-1 min-w-0 flex items-center gap-2 ${index === 0 ? 'mt-3' : '-mt-4'}`}>
                  {/* Model Info */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-4">
                        <p className="font-medium text-foreground truncate cursor-pointer underline hover:no-underline transition-colors">
                          {model.name}
                        </p>
                        <p className="text-sm text-muted-foreground">
                          Créé il y a {model.createdAt} • {model.trainingImages}{" "}
                          photos d'entraînement
                        </p>
                      </div>

                      <div className="flex items-center gap-2">

                        {model.status !== "ready" && (
                          <Badge variant={getStatusColor(model.status) as any} className="border-none">
                            {getStatusText(model.status)}
                          </Badge>
                        )}
                      </div>
                    </div>
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
