import { useState, useCallback } from "react";
import { Upload, FileText, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";

interface DocumentUploaderProps {
  onUploadFile: (file: File | null) => void;
  selectedFile: File | null;
  isUploading: boolean;
}

const SUPPORTED_EXTENSIONS = [".pdf", ".docx", ".txt", ".md"];

export function DocumentUploader({ selectedFile, onUploadFile, isUploading }: DocumentUploaderProps) {
  const [isDragActive, setIsDragActive] = useState(false);

  const isValidFile = (file: File) =>
    SUPPORTED_EXTENSIONS.some(ext => file.name.toLowerCase().endsWith(ext));

  const processFiles = (files: File[]) => {
    const validFiles = files.filter(isValidFile);
    if (validFiles.length > 0) {
      onUploadFile(validFiles[0]);
    }
  };

  const handleDrag = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setIsDragActive(true);
    } else if (e.type === "dragleave") {
      setIsDragActive(false);
    }
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      e.stopPropagation();
      setIsDragActive(false);
      processFiles(Array.from(e.dataTransfer.files));
    },
    [onUploadFile]
  );

  const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    processFiles(Array.from(e.target.files || []));
  };

  const removeFile = () => {
    onUploadFile(null);
  };

  return (
    <div className="space-y-2">
      {!selectedFile && (
        <Card className="p-8 border-2 border-dashed border-border hover:border-primary/50 transition-colors duration-300">
          <div
            className={`upload-zone rounded-lg p-8 text-center cursor-pointer ${
              isDragActive ? 'drag-active' : ''
            }`}
            onDragEnter={handleDrag}
            onDragLeave={handleDrag}
            onDragOver={handleDrag}
            onDrop={handleDrop}
          >
            <input
              type="file"
              accept=".pdf,.docx,.txt,.md"
              onChange={handleFileInput}
              className="hidden"
              id="file-upload"
            />

            <div className="space-y-4">
              <div className="flex justify-center">
                <Upload className="w-12 h-12 text-primary" />
              </div>

              <div className="space-y-2">
                <h3 className="text-lg font-semibold text-foreground">
                  Déposez le fichier ici
                </h3>
                <p className="text-sm text-muted-foreground">
                  ou
                </p>
                <Button>
                  <label htmlFor="file-upload" className="cursor-pointer">
                    Cliquez pour télécharger un fichier
                  </label>
                </Button>
              </div>

              <p className="text-xs text-muted-foreground">
                Formats supportés: PDF, DOCX, TXT, MD
              </p>
            </div>
          </div>
        </Card>
      )}

      {selectedFile && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h4 className="text-sm font-medium text-foreground">Fichier sélectionné:</h4>
            <Button
              variant="ghost"
              size="sm"
              onClick={removeFile}
              className="text-muted-foreground hover:text-destructive hover:bg-destructive/10"
            >
              <X className="w-4 h-4 mr-1" />
              Retirer le fichier
            </Button>
          </div>
          <div className="space-y-2">
            <div className="flex items-center justify-between bg-muted/50 rounded-lg p-3 border">
              <div className="flex items-center gap-3">
                <FileText className="w-4 h-4 text-primary" />
                <span className="text-sm font-medium text-foreground">
                  {selectedFile.name}
                </span>
                <span className="text-xs text-muted-foreground">
                  ({(selectedFile.size / 1024 / 1024).toFixed(1)} MB)
                </span>
              </div>
            </div>
          </div>

          <Button
            disabled={isUploading}
            className="w-full bg-gradient-primary hover:opacity-90 transition-opacity"
          >
            {isUploading ? "Traitement en cours..." : "Fichier sélectionné"}
          </Button>
        </div>
      )}
    </div>
  );
}