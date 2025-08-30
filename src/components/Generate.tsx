import { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';

const themes = [
  { value: 'business', label: 'Business' },
  { value: 'harcourt', label: 'Harcourt style' },
  { value: 'youtuber', label: 'Youtuber' },
  { value: 'instagramer', label: 'Instagramer' },
  { value: 'superhero', label: 'Super-héro' },
  { value: 'vacation', label: 'Vacances' },
];

const subThemes = {
  business: ['Classique', 'Moderne', 'Créatif'],
  harcourt: ['Noir et blanc', 'Couleur', 'Vintage'],
  youtuber: ['Gaming', 'Lifestyle', 'Tech'],
  instagramer: ['Mode', 'Fitness', 'Travel'],
  superhero: ['Marvel', 'DC', 'Original'],
  vacation: ['Plage', 'Montagne', 'Ville'],
};

const formats = [
  { value: '1:1', label: 'Carré (1:1)' },
  { value: '4:3', label: 'Paysage (4:3)' },
  { value: '16:9', label: 'Large (16:9)' },
  { value: '9:16', label: 'Portrait (9:16)' },
];

const framings = [
  { value: 'full-body', label: 'Plein-pied' },
  { value: 'american', label: 'Américain' },
  { value: 'waist', label: 'Taille' },
  { value: 'bust', label: 'Plan buste/poitrine' },
  { value: 'close', label: 'Serré' },
];

const models = [
  { id: '1', name: 'Modèle Portrait Pro' },
  { id: '2', name: 'Modèle Business' },
];

const recentGenerations = [
  { id: '1', theme: 'Business', framing: 'Plan buste', status: 'success', createdAt: '2h', image: '/api/placeholder/150/150' },
  { id: '2', theme: 'Harcourt', framing: 'Serré', status: 'success', createdAt: '4h', image: '/api/placeholder/150/150' },
  { id: '3', theme: 'Youtuber', framing: 'Américain', status: 'failed', createdAt: '6h', image: null },
  { id: '4', theme: 'Instagram', framing: 'Plein pied', status: 'success', createdAt: '1j', image: '/api/placeholder/150/150' },
  { id: '5', theme: 'Super-héro', framing: 'Taille', status: 'processing', createdAt: '1j', image: null },
];

interface GenerateProps {
  selectedModelId?: string;
}

export const Generate = ({ selectedModelId }: GenerateProps) => {
  const [selectedModel, setSelectedModel] = useState(selectedModelId || '');
  const [theme, setTheme] = useState('business');
  const [subTheme, setSubTheme] = useState('');
  const [imageCount, setImageCount] = useState('1');
  const [format, setFormat] = useState('1:1');
  const [framing, setFraming] = useState('bust');
  const [errors, setErrors] = useState<{ [key: string]: string }>({});
  const [isGenerating, setIsGenerating] = useState(false);

  const validateForm = () => {
    const newErrors: { [key: string]: string } = {};
    
    if (!selectedModel) newErrors.model = 'Sélectionnez un modèle';
    
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleGenerate = () => {
    if (!validateForm()) return;
    
    setIsGenerating(true);
    // Simulation de génération
    setTimeout(() => {
      setIsGenerating(false);
      alert('Images générées avec succès !');
    }, 3000);
  };

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
    <div className="max-w-6xl mx-auto space-y-8">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-foreground mb-2">Générer des images</h2>
          <p className="text-muted-foreground">Créez vos photos professionnelles personnalisées</p>
        </div>
        <div className="text-right">
          <p className="text-sm text-muted-foreground">Crédits disponibles</p>
          <p className="text-2xl font-bold text-primary">50</p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Generation Form */}
        <Card>
          <CardHeader>
            <CardTitle>Paramètres de génération</CardTitle>
          </CardHeader>
          <CardContent className="space-y-6">
            {/* Model Selection */}
            <div className="space-y-2">
              <Label htmlFor="model">Modèle entraîné *</Label>
              <Select value={selectedModel} onValueChange={setSelectedModel}>
                <SelectTrigger className={errors.model ? "border-destructive" : ""}>
                  <SelectValue placeholder="Sélectionnez un modèle" />
                </SelectTrigger>
                <SelectContent>
                  {models.map((model) => (
                    <SelectItem key={model.id} value={model.id}>
                      {model.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {errors.model && (
                <p className="text-sm text-destructive">{errors.model}</p>
              )}
            </div>

            {/* Image Count */}
            <div className="space-y-3">
              <Label>Nombre d'images</Label>
              <RadioGroup value={imageCount} onValueChange={setImageCount} className="flex gap-6">
                <div className="flex items-center space-x-2">
                  <RadioGroupItem value="1" id="count-1" />
                  <Label htmlFor="count-1">1 image</Label>
                </div>
                <div className="flex items-center space-x-2">
                  <RadioGroupItem value="2" id="count-2" />
                  <Label htmlFor="count-2">2 images</Label>
                </div>
                <div className="flex items-center space-x-2">
                  <RadioGroupItem value="3" id="count-3" />
                  <Label htmlFor="count-3">3 images</Label>
                </div>
              </RadioGroup>
            </div>

            {/* Theme */}
            <div className="space-y-2">
              <Label htmlFor="theme">Thème de photo</Label>
              <Select value={theme} onValueChange={(value) => { setTheme(value); setSubTheme(''); }}>
                <SelectTrigger>
                  <SelectValue placeholder="Sélectionnez un thème" />
                </SelectTrigger>
                <SelectContent>
                  {themes.map((t) => (
                    <SelectItem key={t.value} value={t.value}>
                      {t.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Sub Theme */}
            <div className="space-y-2">
              <Label htmlFor="subtheme">Sous-thème</Label>
              <Select value={subTheme} onValueChange={setSubTheme}>
                <SelectTrigger>
                  <SelectValue placeholder="Sélectionnez un sous-thème" />
                </SelectTrigger>
                <SelectContent>
                  {theme && subThemes[theme as keyof typeof subThemes]?.map((st) => (
                    <SelectItem key={st} value={st.toLowerCase()}>
                      {st}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Format */}
            <div className="space-y-2">
              <Label htmlFor="format">Format</Label>
              <Select value={format} onValueChange={setFormat}>
                <SelectTrigger>
                  <SelectValue placeholder="Sélectionnez un format" />
                </SelectTrigger>
                <SelectContent>
                  {formats.map((f) => (
                    <SelectItem key={f.value} value={f.value}>
                      {f.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Framing */}
            <div className="space-y-2">
              <Label htmlFor="framing">Cadrage</Label>
              <Select value={framing} onValueChange={setFraming}>
                <SelectTrigger>
                  <SelectValue placeholder="Sélectionnez un cadrage" />
                </SelectTrigger>
                <SelectContent>
                  {framings.map((f) => (
                    <SelectItem key={f.value} value={f.value}>
                      {f.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Generate Button */}
            <Button 
              onClick={handleGenerate} 
              className="w-full"
              disabled={isGenerating}
            >
              {isGenerating ? 'Génération en cours...' : `Générer ${imageCount} image${imageCount !== '1' ? 's' : ''}`}
            </Button>
          </CardContent>
        </Card>

        {/* Recent Generations */}
        <Card>
          <CardHeader>
            <CardTitle>Générations récentes</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {recentGenerations.map((generation) => (
                <div key={generation.id} className="flex items-center gap-4 p-3 border border-border rounded-lg">
                  {generation.image ? (
                    <div className="w-16 h-16 rounded-lg bg-muted overflow-hidden flex-shrink-0">
                      <div className="w-full h-full bg-gradient-to-br from-muted to-accent flex items-center justify-center">
                        <span className="text-xs text-muted-foreground">IMG</span>
                      </div>
                    </div>
                  ) : (
                    <div className="w-16 h-16 rounded-lg bg-muted flex items-center justify-center flex-shrink-0">
                      <span className="text-xs text-muted-foreground">—</span>
                    </div>
                  )}
                  
                  <div className="flex-1 min-w-0">
                    <p className="font-medium text-foreground truncate">
                      {generation.theme} - {generation.framing}
                    </p>
                    <p className="text-sm text-muted-foreground">Il y a {generation.createdAt}</p>
                  </div>
                  
                  <Badge variant={getStatusColor(generation.status) as any}>
                    {getStatusText(generation.status)}
                  </Badge>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
};