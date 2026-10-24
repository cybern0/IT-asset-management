import { useEffect, useState } from "react";
import { useParams } from "react-router";
import { api, ApiError } from "../lib/api";

/** /image/:id : l'image du matériel en grand, seule sur la page (ouverte dans un nouvel onglet). */
export default function ImagePage() {
  const { id } = useParams();
  const [src, setSrc] = useState<string | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let url: string | null = null;
    let cancelled = false;
    api.blob(`/materiels/${id}/image`)
      .then((b) => { if (!cancelled) { url = URL.createObjectURL(b); setSrc(url); } })
      .catch((e) => { if (!cancelled) setError(e instanceof ApiError ? e.message : "Image introuvable."); });
    return () => { cancelled = true; if (url) URL.revokeObjectURL(url); };
  }, [id]);

  return (
    <main className="image-page">
      {error ? <p role="alert">{error}</p> : src ? <img src={src} alt={`Matériel ${id}`} /> : <p>Chargement…</p>}
    </main>
  );
}
