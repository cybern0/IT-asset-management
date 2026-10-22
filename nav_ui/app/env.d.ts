/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** URL de base de l'API, sans slash final (defaut : http://localhost:8000/api/v1) */
  readonly VITE_API_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
