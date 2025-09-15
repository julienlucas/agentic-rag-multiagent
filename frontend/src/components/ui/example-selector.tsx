import { useState, useEffect } from "react";
import { FileText, Download, X, Check } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useTimer } from "@/hooks/useTimer";

interface Example {
  id: string;
  title: string;
  description: string;
  file_paths?: string[];
  type: string;
  question?: string;
}

interface ExampleSelectorProps {
  onExampleSelect: (example: Example) => void;
  selectedExample: Example | null;
  examples: Example[];
  onLoadExample: () => void;
  onRemoveExample: () => void;
  isLoading: boolean;
  documentLoaded: boolean;
}

export function ExampleSelector({
  onExampleSelect,
  selectedExample,
  examples,
  onLoadExample,
  onRemoveExample,
  isLoading,
  documentLoaded,
}: ExampleSelectorProps) {
  const { elapsedTime, finalTime, startTimer } = useTimer(isLoading);

  const handleExampleChange = (value: string) => {
    const example = examples.find((ex) => ex.id === value);
    if (example) {
      onExampleSelect(example);
    }
  };

  const handleLoadExample = () => {
    startTimer();
    onLoadExample();
  };

  return (
    <Card className="border-none">
      <div className="flex items-center gap-2 mb-2">
        <FileText className="w-5 h-5 text-primary" />
        <h3 className="text-lg font-semibold text-foreground">Exemple</h3>
      </div>

      {!selectedExample ? (
        <div className="space-y-2">
          <div className="space-y-2">
            <label className="text-left text-sm font-medium text-foreground">
              Sélectionner un Exemple ✨
            </label>
            <Select onValueChange={handleExampleChange}>
              <SelectTrigger className="w-full bg-background hover:bg-muted/50 transition-colors">
                <SelectValue placeholder="Choisissez un exemple de document technique..." />
              </SelectTrigger>
              <SelectContent className="bg-popover border border-border shadow-lg">
                {examples.map((example) => (
                  <SelectItem
                    key={example.id}
                    value={example.id}
                    className="hover:bg-muted focus:bg-muted"
                  >
                    <div className="space-y-1">
                      <div className="font-medium">{example.title}</div>
                    </div>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>
      ) : (
        <div className="space-y-4">
          <div className="flex items-center justify-between relative -mb-3 ">
            <h4 className="font-medium text-foreground">
              {selectedExample.title}
            </h4>
            <Button
              variant="ghost"
              size="sm"
              onClick={onRemoveExample}
              className="text-muted-foreground hover:text-destructive hover:bg-destructive/10"
            >
              <X className="w-4 h-4" />
            </Button>
          </div>

          <p className="text-left text-sm text-muted-foreground">
            {selectedExample.description}
          </p>

          {!documentLoaded && (
            <div className="space-y-2">
              <Button
                onClick={handleLoadExample}
                disabled={isLoading}
                className="w-full"
              >
                {isLoading ? (
                  <div className="flex items-center gap-2">
                    <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                    Chargement...
                  </div>
                ) : selectedExample.type === "uploaded" ? (
                  "Fichier chargé"
                ) : (
                  "Charger le fichier"
                )}
                <Download className="w-4 h-4" />
              </Button>

              {isLoading && (
                <div className="text-left flex items-center gap-2 text-muted-foreground text-sm">
                  <div className="w-4 h-4 border-2 border-t-transparent rounded-full animate-spin" />
                  <span>Temps écoulé: {elapsedTime}s</span>
                </div>
              )}
            </div>
          )}

          {!isLoading && finalTime !== null && (
            <div className="text-left flex items-center gap-2 text-green-600 text-sm">
              <Check className="w-4 h-4" />
              <span>Chargé en {finalTime}s</span>
            </div>
          )}
        </div>
      )}
    </Card>
  );
}
