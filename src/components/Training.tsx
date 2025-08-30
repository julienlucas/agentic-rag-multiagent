import { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Progress } from '@/components/ui/progress';
import { Upload, X, CheckCircle2 } from 'lucide-react';
import { cn } from '@/lib/utils';

interface UploadedFile {
  id: string;
  file: File;
  preview: string;
}

export const Training = () => {
  const [uploadedFiles, setUploadedFiles] = useState<UploadedFile[]>([]);
  const [age, setAge] = useState('');
  const [gender, setGender] = useState('');
  const [isTraining, setIsTraining] = useState(false);
  const [trainingProgress, setTrainingProgress] = useState(0);
  const [trainingComplete, setTrainingComplete] = useState(false);
  const [errors, setErrors] = useState<{ [key: string]: string }>({});

  const handleFileUpload = (files: FileList | null) => {
    if (!files) return;

    const newFiles: UploadedFile[] = [];
    for (let i = 0; i < files.length; i++) {
      const file = files[i];
      if (file.size > 5 * 1024 * 1024) {
        alert(`Le fichier ${file.name} dépasse 5Mo`);
        continue;
      }
      if (uploadedFiles.length + newFiles.length >= 20) {
        alert('Maximum 20 photos autorisées');
        break;
      }
      newFiles.push({
        id: Date.now().toString() + i,
        file,
        preview: URL.createObjectURL(file),
      });
    }
    setUploadedFiles([...uploadedFiles, ...newFiles]);
  };

  const removeFile = (id: string) => {
    setUploadedFiles(uploadedFiles.filter(f => f.id !== id));
  };

  const validateForm = () => {
    const newErrors: { [key: string]: string } = {};
    
    if (!age) newErrors.age = 'L\'âge est obligatoire';
    if (!gender) newErrors.gender = 'Le genre est obligatoire';
    if (uploadedFiles.length < 5) newErrors.files = 'Minimum 5 photos requises';
    
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const startTraining = () => {
    if (!validateForm()) return;
    
    setIsTraining(true);
    setTrainingProgress(0);
    
    // Simulation du training
    const interval = setInterval(() => {
      setTrainingProgress(prev => {
        if (prev >= 100) {
          clearInterval(interval);
          setIsTraining(false);
          setTrainingComplete(true);
          return 100;
        }
        return prev + 10;
      });
    }, 1000);
  };

  if (trainingComplete) {
    return (
      <div className="max-w-2xl mx-auto">
        <Card>
          <CardContent className="pt-6 text-center">
            <CheckCircle2 className="h-16 w-16 text-success mx-auto mb-4" />
            <h2 className="text-2xl font-bold text-foreground mb-2">Entraînement terminé !</h2>
            <p className="text-muted-foreground mb-6">Votre modèle est prêt à générer des images</p>
            <Button onClick={() => setTrainingComplete(false)}>
              Entraîner un nouveau modèle
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (isTraining) {
    return (
      <div className="max-w-2xl mx-auto">
        <Card>
          <CardHeader>
            <CardTitle>Entraînement en cours...</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <Progress value={trainingProgress} className="w-full" />
            <p className="text-center text-muted-foreground">
              {trainingProgress}% - Temps restant: {Math.ceil((100 - trainingProgress) / 10)} minutes
            </p>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto space-y-8">
      <div>
        <h2 className="text-2xl font-bold text-foreground mb-2">Entraînement du modèle</h2>
        <p className="text-muted-foreground">Uploadez vos photos pour entraîner votre modèle personnalisé</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Upload Zone */}
        <Card>
          <CardHeader>
            <CardTitle>Photos d'entraînement</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div
              className={cn(
                "border-2 border-dashed rounded-lg p-8 text-center transition-colors",
                "border-upload-border hover:border-primary hover:bg-upload-hover",
                errors.files && "border-destructive"
              )}
              onDrop={(e) => {
                e.preventDefault();
                handleFileUpload(e.dataTransfer.files);
              }}
              onDragOver={(e) => e.preventDefault()}
            >
              <Upload className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
              <p className="text-lg font-medium text-foreground mb-2">
                Glissez vos photos ici
              </p>
              <p className="text-sm text-muted-foreground mb-4">
                5-20 photos, 5Mo max par photo
              </p>
              <Button
                variant="outline"
                onClick={() => document.getElementById('file-input')?.click()}
              >
                Choisir des fichiers
              </Button>
              <input
                id="file-input"
                type="file"
                multiple
                accept="image/*"
                className="hidden"
                onChange={(e) => handleFileUpload(e.target.files)}
              />
            </div>
            {errors.files && (
              <p className="text-sm text-destructive">{errors.files}</p>
            )}
          </CardContent>
        </Card>

        {/* Form */}
        <Card>
          <CardHeader>
            <CardTitle>Informations personnelles</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="age">Âge *</Label>
              <Input
                id="age"
                type="number"
                value={age}
                onChange={(e) => setAge(e.target.value)}
                className={errors.age ? "border-destructive" : ""}
              />
              {errors.age && (
                <p className="text-sm text-destructive">{errors.age}</p>
              )}
            </div>
            
            <div className="space-y-2">
              <Label htmlFor="gender">Genre *</Label>
              <Select value={gender} onValueChange={setGender}>
                <SelectTrigger className={errors.gender ? "border-destructive" : ""}>
                  <SelectValue placeholder="Sélectionnez votre genre" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="homme">Homme</SelectItem>
                  <SelectItem value="femme">Femme</SelectItem>
                  <SelectItem value="autre">Autre</SelectItem>
                </SelectContent>
              </Select>
              {errors.gender && (
                <p className="text-sm text-destructive">{errors.gender}</p>
              )}
            </div>

            <Button 
              onClick={startTraining} 
              className="w-full"
              disabled={uploadedFiles.length === 0}
            >
              Commencer l'entraînement
            </Button>
          </CardContent>
        </Card>
      </div>

      {/* Uploaded Files */}
      {uploadedFiles.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Photos uploadées ({uploadedFiles.length}/20)</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 sm:grid-cols-4 md:grid-cols-6 gap-4">
              {uploadedFiles.map((file) => (
                <div key={file.id} className="relative group">
                  <img
                    src={file.preview}
                    alt="Preview"
                    className="w-full aspect-square object-cover rounded-lg"
                  />
                  <button
                    onClick={() => removeFile(file.id)}
                    className="absolute -top-2 -right-2 h-6 w-6 bg-destructive text-destructive-foreground rounded-full opacity-0 group-hover:opacity-100 transition-opacity"
                  >
                    <X className="h-4 w-4" />
                  </button>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
};