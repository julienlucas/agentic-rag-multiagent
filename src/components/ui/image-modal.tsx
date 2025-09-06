import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Download, X } from 'lucide-react';

interface ImageModalProps {
  isOpen: boolean;
  onClose: () => void;
  image: {
    id: string;
    theme: string;
    image?: string;
    url?: string;
    aspectRatio: string;
  } | null;
}

export const ImageModal = ({ isOpen, onClose, image }: ImageModalProps) => {
  if (!isOpen || !image) return null;

  const downloadImage = () => {
    const link = document.createElement('a');
    link.href = image.image || image.url || '';
    link.download = `${image.theme}.jpg`;
    link.click();
  };

  return (
    <div
      className="fixed -top-8 inset-0 bg-black/40 flex items-start justify-center z-50 pt-10 pb-10"
      onClick={onClose}
    >
      {/* Bouton de fermeture en haut à gauche */}
      <Button
        variant="ghost"
        size="icon"
        onClick={onClose}
        className="absolute top-2 left-2 h-8 w-8 z-10"
      >
        <X className="h-14 w-14 text-white" />
      </Button>

      <div
        className="bg-background w-full max-w-4xl flex flex-col overflow-hidden rounded-lg"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex-1 flex flex-col items-center justify-center p-4">
          <div
            key={image.id}
            className="break-inside-avoid group relative cursor-pointer"
            style={{
              //  aspectRatio:
              //    image.aspectRatio === "1:1"
              //      ? "1/1"
              //      : image.aspectRatio === "4:3"
              //      ? "4/3"
              //      : image.aspectRatio === "16:9"
              //      ? "16/9"
              //      : "9/16",
              width: "100%",
              maxWidth: "calc(100vw - 80px)",
              maxHeight: "calc(100vh - 200px)",
            }}
          >
            <div
              className={`bg-muted overflow-hidden bg-gradient-to-br from-muted to-accent flex items-center justify-center relative w-full h-full`}
            >
              <span className="text-xs text-muted-foreground">
                Image {image.id}
              </span>
            </div>
          </div>

          <div className="flex items-center justify-end gap-4 mt-4 w-full">
            <Button variant="secondary">
              {image.theme}
            </Button>

            <Button onClick={downloadImage} size="sm">
              <Download className="h-4 w-4 mr-2" />
              Télécharger
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
};
