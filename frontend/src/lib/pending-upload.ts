/*
 * Le fichier déposé dans le hero, gardé en mémoire le temps de l'inscription : la page Documents
 * le reprend à son ouverture et le place dans la liste à indexer. Il reste en mémoire jusqu'à ce
 * qu'il soit indexé ou retiré (la page peut se monter plusieurs fois pendant que la session se
 * charge). Navigation SPA seulement : une connexion Google ou un rechargement le perd.
 */
let pending: File[] = [];

export function setPendingUpload(files: File[]) {
  pending = files;
}

export function peekPendingUpload(): File[] {
  return pending;
}

export function clearPendingUpload() {
  pending = [];
}
