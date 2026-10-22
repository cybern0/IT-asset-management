// Variables d'environnement du frontend (fichier .env, prefixe VITE_ obligatoire)
const raw = import.meta.env.VITE_API_URL ?? "http://localhost:8000/api/v1";

export const API_URL: string = raw.replace(/\/+$/, "");
