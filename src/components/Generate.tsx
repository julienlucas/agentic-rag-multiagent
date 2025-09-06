import { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group';
import { cn } from '@/lib/utils';
import { RecentGenerations } from "@/components/ui/recent-generations";
import { RecentImages } from "@/components/ui/recent-images";

const themes = [
  { value: 'business', label: 'Business', image: '/horizon.jpg' },
  { value: 'harcourt', label: 'Harcourt style', image: '/hiver.jpg.jpg' },
  { value: 'youtuber', label: 'Youtuber', image: '/horizon-cool.jpg' },
  { value: 'instagramer', label: 'Instagramer', image: '/IMG_2124.jpg' },
  { value: 'superhero', label: 'Super-héro', image: '/horizon.jpg' },
  { value: 'vacation', label: 'Vacances', image: '/hiver.jpg.jpg' },
];

const subThemes = [
  'Classique', 'Moderne', 'Créatif', 'Noir et blanc', 'Couleur', 'Vintage',
  'Gaming', 'Lifestyle', 'Tech', 'Mode', 'Fitness', 'Travel',
  'Marvel', 'DC', 'Original', 'Plage', 'Montagne', 'Ville'
];

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
  { id: '1', theme: 'Business', framing: 'Plan buste', createdAt: '2h', image: '/api/placeholder/150/150' },
  { id: '2', theme: 'Harcourt', framing: 'Serré', createdAt: '4h', image: '/api/placeholder/150/150' },
  { id: '3', theme: 'Youtuber', framing: 'Américain', createdAt: '6h', image: null },
  { id: '4', theme: 'Instagram', framing: 'Plein pied', createdAt: '1j', image: '/api/placeholder/150/150' },
  { id: '5', theme: 'Super-héro', framing: 'Taille', createdAt: '1j', image: null },
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


  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-foreground mb-2">
            Générer des images
          </h2>
          <p className="text-muted-foreground">
            Créez vos photos professionnelles personnalisées
          </p>
        </div>
      </div>

      <div className="space-y-8">
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
                <SelectTrigger
                  className={errors.model ? "border-destructive" : ""}
                >
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
              <Label>Nombre d'images à générer</Label>
              <RadioGroup
                value={imageCount}
                onValueChange={setImageCount}
                className="flex gap-6"
              >
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
            <div className="space-y-3">
              <Label>Thème de photo</Label>
              <div className="flex gap-3 overflow-x-auto pb-2">
                {themes.map((t) => (
                  <div
                    key={t.value}
                    onClick={() => {
                      setTheme(t.value);
                      setSubTheme("");
                    }}
                    className={cn(
                      "relative w-28 h-28 rounded-lg border-2 cursor-pointer transition-all flex-shrink-0 overflow-hidden",
                      theme === t.value
                        ? "border-primary ring-2 ring-primary/20"
                        : "border-border hover:border-primary/50"
                    )}
                  >
                    <img
                      src={t.image}
                      alt={t.label}
                      className="w-full h-full object-cover"
                    />
                    <div className="absolute inset-0 bg-black/40 flex items-center justify-center">
                      <span className="text-xs font-medium text-white text-center px-2">
                        {t.label}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Sub Theme */}
            <div className="space-y-3">
              <Label>Sous-thème</Label>
              <div className="grid grid-cols-3 gap-2">
                {subThemes.map((st) => (
                  <div
                    key={st}
                    onClick={() => setSubTheme(st.toLowerCase())}
                    className={cn(
                      "relative h-12 rounded bg-gray-200 cursor-pointer transition-all",
                      "flex items-center justify-center text-xs font-medium outline-none",
                      subTheme === st.toLowerCase()
                        ? "border-primary bg-primary/30"
                        : "border-border hover:bg-gray-300"
                    )}
                  >
                    {st}
                  </div>
                ))}
              </div>
            </div>

            {/* Format */}
            <div className="space-y-3">
              <Label>Format</Label>
              <div className="grid grid-cols-4 gap-3">
                {formats.map((f) => (
                  <div
                    key={f.value}
                    onClick={() => setFormat(f.value)}
                    className={cn(
                      "relative h-16 rounded-lg bg-gray-200 cursor-pointer transition-all",
                      "flex items-center justify-center",
                      format === f.value
                        ? "border-primary bg-primary/30"
                        : "border-border hover:bg-gray-300"
                    )}
                  >
                    <div className="flex flex-col items-center gap-1">
                      <div
                        className={cn(
                          "bg-foreground/20 rounded",
                          f.value === "1:1" && "w-6 h-6",
                          f.value === "4:3" && "w-8 h-6",
                          f.value === "16:9" && "w-8 h-4",
                          f.value === "9:16" && "w-4 h-8"
                        )}
                      />
                      <span className="text-xs font-medium">{f.label}</span>
                    </div>
                  </div>
                ))}
              </div>
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
              disabled={isGenerating}
            >
              {isGenerating
                ? "Génération en cours..."
                : `Générer ${imageCount} image${
                    imageCount !== "1" ? "s" : ""
                  } (${imageCount} crédit${imageCount !== "1" ? "s" : ""})`}
            </Button>
          </CardContent>
        </Card>

        {/* Recent Images */}
        <RecentImages images={recentImages} />
      </div>
    </div>
  );
};