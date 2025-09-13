import { CheckCircle2, Sparkles } from "lucide-react";
import { Textarea } from "@/components/ui/textarea";
import { Card } from "@/components/ui/card";

interface ChatInterfaceProps {
  answer: string;
  verificationReport: string;
  isLoading: boolean;
}

export function ResponseInputs({
  answer,
  verificationReport,
  isLoading,
}: ChatInterfaceProps) {
  return (
    <div className="space-y-6">
      {/* Answer Area */}
      <Card className="border-none">
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <Sparkles className="w-5 h-5" />
            <h3 className="text-lg font-semibold text-foreground">Réponse</h3>
          </div>

          <div
            contentEditable={false}
            className="text-left h-[200px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background overflow-y-auto resize-y"
            style={{ whiteSpace: "pre-wrap" }}
            dangerouslySetInnerHTML={{
              __html: answer
                ? answer
                    .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
                    .replace(/\*(.*?)\*/g, "<em>$1</em>")
                : "La réponse apparaîtra ici...",
            }}
          />

          {isLoading && (
            <div className="flex items-center gap-2 text-muted-foreground">
              <div className="w-4 h-4 border-2 border-t-transparent rounded-full animate-spin" />
              <span className="text-sm">Traitement en cours...</span>
            </div>
          )}
        </div>
      </Card>

      {/* Verification Report Area */}
      <Card className="border-none">
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="w-5 h-5 text-success" />
            <h3 className="text-lg font-semibold text-foreground">
              Rapport de Vérification
            </h3>
          </div>

          <div
            contentEditable={false}
            className="text-left h-[150px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background overflow-y-auto resize-y"
            style={{ whiteSpace: "pre-wrap" }}
            dangerouslySetInnerHTML={{
              __html: verificationReport
                ? verificationReport
                    .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
                    .replace(/\*(.*?)\*/g, "<em>$1</em>")
                : "Le rapport de vérification de pertinence et fact-checking apparaîtra ici...",
            }}
          />
        </div>
      </Card>
    </div>
  );
}
