import { useState, useEffect } from "react";
import { Send, MessageCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Card } from "@/components/ui/card";

interface QuestionInputProps {
  hasDocument: boolean;
  isLoading: boolean;
  onQuestionSubmit: (question: string) => void;
  preloadedQuestion?: string;
  documentLoaded: boolean;
}

export function QuestionInput({
  hasDocument,
  isLoading,
  documentLoaded,
  onQuestionSubmit,
  preloadedQuestion,
}: QuestionInputProps) {
  const [question, setQuestion] = useState("");
  const [hasSubmitted, setHasSubmitted] = useState(false);
  const [elapsedTime, setElapsedTime] = useState(0);
  const [startTime, setStartTime] = useState<number | null>(null);

  // Pré-charger la question quand elle change (sauf si on vient de soumettre)
  useEffect(() => {
    if (!hasSubmitted) {
      setQuestion(preloadedQuestion || "");
    }
  }, [preloadedQuestion, hasSubmitted]);

  // Réinitialiser hasSubmitted quand une nouvelle preloadedQuestion arrive
  useEffect(() => {
    if (preloadedQuestion) {
      setHasSubmitted(false);
    }
  }, [preloadedQuestion]);

  // Timer pour le compteur de temps
  useEffect(() => {
    let interval: NodeJS.Timeout;

    if (isLoading && startTime) {
      interval = setInterval(() => {
        setElapsedTime(Math.floor((Date.now() - startTime) / 1000));
      }, 1000);
    }

    return () => {
      if (interval) clearInterval(interval);
    };
  }, [isLoading, startTime]);

  // Réinitialiser le timer quand le loading s'arrête
  useEffect(() => {
    if (!isLoading) {
      setElapsedTime(0);
      setStartTime(null);
    }
  }, [isLoading]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!question.trim() || !hasDocument) return;

    setStartTime(Date.now());
    setElapsedTime(0);
    onQuestionSubmit(question);
    setQuestion("");
    setHasSubmitted(true);
  };

  return (
    <Card className="border-none">
      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <MessageCircle className="w-5 h-5 text-primary" />
            <label className="text-lg font-semibold text-foreground">
              Question
            </label>
          </div>
          <Textarea
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="Posez votre question sur le document..."
            disabled={!hasDocument}
          />
        </div>

        <Button
          type="submit"
          className="w-full"
          disabled={
            !question.trim() || !hasDocument || isLoading || !documentLoaded
          }
        >
          {isLoading ? (
            <div className="flex items-center gap-2">
              <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
              Traitement en cours...
            </div>
          ) : (
            <div className="flex items-center gap-2 ">
              Envoyer
              <Send className="w-5 h-5" />
            </div>
          )}
        </Button>

        {isLoading && (
          <div className="text-left flex items-center gap-2 text-muted-foreground text-sm">
            <div className="w-4 h-4 border-2 border-t-transparent rounded-full animate-spin" />
            <span>Temps écoulé: {elapsedTime}s</span>
          </div>
        )}
      </form>
    </Card>
  );
}
