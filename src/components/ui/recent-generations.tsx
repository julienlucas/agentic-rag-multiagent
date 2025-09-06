import { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { ImageModal } from '@/components/ui/image-modal';

interface Generation {
  id: string;
  theme: string;
  framing: string;
  createdAt: string;
  image?: string | null;
}

interface RecentGenerationsProps {
  generations: Generation[];
  title?: string;
}

export const RecentGenerations = ({ generations, title = "Générations récentes" }: RecentGenerationsProps) => {
  const [selectedImage, setSelectedImage] = useState<{ id: string; theme: string; image: string } | null>(null);

  const openImageModal = (generation: { id: string; theme: string; image: string }) => {
    setSelectedImage(generation);
  };

  const closeImageModal = () => {
    setSelectedImage(null);
  };

  return (
    <>
      <Card>
        <CardHeader>
          <CardTitle>{title}</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {generations.map((generation) => (
              <div key={generation.id} className="flex items-center gap-4 p-3 border-b border-border last:border-0">
                <div className="flex-1 min-w-0 flex items-center gap-2 -mt-4">
                  <p
                    className="font-medium text-foreground truncate cursor-pointer underline hover:no-underline transition-colors"
                    onClick={() => generation.image && openImageModal({ id: generation.id, theme: generation.theme, image: generation.image })}
                  >
                    {generation.theme} - {generation.framing}
                  </p>
                  <p className="text-sm text-muted-foreground">Il y a {generation.createdAt}</p>
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      <ImageModal
        isOpen={!!selectedImage}
        onClose={closeImageModal}
        image={selectedImage}
      />
    </>
  );
};
