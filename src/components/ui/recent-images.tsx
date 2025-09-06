import { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { ImageModal } from '@/components/ui/image-modal';

interface RecentImage {
  id: string;
  url: string;
  alt: string;
  aspectRatio: string;
  theme: string;
}

interface RecentImagesProps {
  images: RecentImage[];
  title?: string;
}

export const RecentImages = ({ images, title = "Dernières images générées" }: RecentImagesProps) => {
  const [selectedImage, setSelectedImage] = useState<{ id: string; theme: string; image: string } | null>(null);

  const openImageModal = (image: { id: string; theme: string; image: string }) => {
    setSelectedImage(image);
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
          <div className="columns-2 sm:columns-1 md:columns-2 lg:columns-3 gap-4">
            {images.map((image) => (
              <div key={image.id} className="break-inside-avoid group relative cursor-pointer" onClick={() => openImageModal({ id: image.id, theme: image.theme, image: image.url })}>
                <div
                  className={`bg-gray-200 overflow-hidden from-muted to-accent flex items-center justify-center relative mb-4`}
                  style={{
                    aspectRatio:
                      image.aspectRatio === "1:1"
                        ? "1/1"
                        : image.aspectRatio === "4:3"
                        ? "4/3"
                        : image.aspectRatio === "16:9"
                        ? "16/9"
                        : "9/16",
                  }}
                >
                  <span className="text-xs text-muted-foreground">
                    Image {image.id}
                  </span>

                  {/* Overlay au survol */}
                  <div className="absolute inset-0 bg-black/20 opacity-0 group-hover:opacity-100 transition-opacity duration-200 flex items-end justify-end p-3">
                    <Badge
                      variant="secondary"
                      className="text-xs rounded-sm hover:bg-white"
                    >
                      {image.theme}
                    </Badge>
                  </div>
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
