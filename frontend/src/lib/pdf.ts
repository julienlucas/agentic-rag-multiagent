import workerUrl from "pdfjs-dist/build/pdf.worker.min.mjs?url";

/** pdf.js chargé à la demande (lourd), avec son worker. */
export async function loadPdfjs() {
  const pdfjs = await import("pdfjs-dist");
  pdfjs.GlobalWorkerOptions.workerSrc = workerUrl;
  return pdfjs;
}

/** Nombre de pages d'un PDF local, pour estimer le coût avant l'envoi ; null s'il est illisible. */
export async function countPdfPages(file: File): Promise<number | null> {
  try {
    const pdfjs = await loadPdfjs();
    const doc = await pdfjs.getDocument({ data: new Uint8Array(await file.arrayBuffer()) }).promise;
    const n = doc.numPages;
    await doc.destroy();
    return n;
  } catch {
    return null;
  }
}
