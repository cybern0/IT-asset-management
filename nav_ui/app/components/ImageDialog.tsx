import { useEffect, useRef, useState } from "react";
import { api, ApiError } from "../lib/api";
import { useI18n } from "../lib/i18n";
import { Modal } from "./Modal";

type Props = {
  materielId: string;
  title: string;
  hasImage: boolean;
  onClose: () => void;
  /** Appele apres un envoi ou une suppression : l'appelant recharge la table materiel. */
  onChanged: () => Promise<void> | void;
};

/** Apercu de l'image d'un materiel, avec envoi, remplacement et suppression. */
export function ImageDialog({ materielId, title, hasImage, onClose, onChanged }: Props) {
  const { t } = useI18n();
  const [present, setPresent] = useState(hasImage);
  const [src, setSrc] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [confirming, setConfirming] = useState(false);
  const input = useRef<HTMLInputElement>(null);

  // charge l'image avec l'en-tete d'authentification, puis l'affiche via une URL locale
  useEffect(() => {
    if (!present) { setSrc(null); return; }
    let url: string | null = null;
    let cancelled = false;
    api.blob(`/materiels/${materielId}/image`)
      .then((b) => { if (!cancelled) { url = URL.createObjectURL(b); setSrc(url); } })
      .catch((e) => { if (!cancelled) setError(e instanceof ApiError ? e.message : t("Erreur inattendue.")); });
    return () => { cancelled = true; if (url) URL.revokeObjectURL(url); };
  }, [present, materielId, t]);

  async function run(action: () => Promise<void>) {
    setBusy(true);
    setError("");
    try { await action(); await onChanged(); }
    catch (e) { setError(e instanceof ApiError ? e.message : t("Erreur inattendue.")); }
    finally { setBusy(false); setConfirming(false); }
  }

  function upload(file: File) {
    if (file.size > 5 * 1024 * 1024) { setError(t("Fichier trop volumineux (maximum {n} Mo).", { n: 5 })); return; }
    const form = new FormData();
    form.append("file", file);
    void run(async () => { await api.upload(`/materiels/${materielId}/image`, form); setPresent(true); });
  }

  return (
    <Modal title={title} onClose={onClose}>
      <div className="image-box">
        {present
          ? src ? <img src={src} alt={title} /> : <p className="hint">{t("Chargement…")}</p>
          : <p className="empty">{t("Aucune image pour ce matériel.")}</p>}
      </div>
      <div className="modal-foot">
        <input
          ref={input} type="file" accept="image/jpeg,image/png,image/webp" hidden
          onChange={(e) => { const f = e.target.files?.[0]; e.target.value = ""; if (f) upload(f); }}
        />
        <button type="button" className="btn primary" disabled={busy} onClick={() => input.current?.click()}>
          {busy ? t("Envoi…") : present ? t("Remplacer l’image") : t("Ajouter une image")}
        </button>
        {present && (
          <button
            type="button" className={`btn ${confirming ? "danger" : "ghost"}`} disabled={busy}
            onClick={() => (confirming
              ? void run(async () => { await api.del(`/materiels/${materielId}/image`); setPresent(false); })
              : setConfirming(true))}
          >
            {confirming ? t("Confirmer la suppression") : t("Supprimer l’image")}
          </button>
        )}
        <span className="hint">{t("JPEG, PNG ou WebP, 5 Mo maximum.")}</span>
        {error && <p className="error foot-error" role="alert">{error}</p>}
      </div>
    </Modal>
  );
}
