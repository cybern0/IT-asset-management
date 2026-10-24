import { useEffect, useState } from "react";
import { api } from "../lib/api";
import { useI18n } from "../lib/i18n";

const MAX_MB = 5;

/** Champ image du formulaire matériel : aperçu + choix du fichier (envoyé à l'enregistrement). */
export function ImageField({ materielId, hasImage, file, onFile, onError, onManage }: {
  materielId: string | null;
  hasImage: boolean;
  file: File | null;
  onFile: (f: File | null) => void;
  onError: (message: string) => void;
  onManage?: () => void;
}) {
  const { t } = useI18n();
  const [src, setSrc] = useState<string | null>(null);

  useEffect(() => {
    let url: string | null = null;
    let cancelled = false;
    if (file) {
      url = URL.createObjectURL(file);
      setSrc(url);
    } else if (materielId && hasImage) {
      api.blob(`/materiels/${materielId}/image`)
        .then((b) => { if (!cancelled) { url = URL.createObjectURL(b); setSrc(url); } })
        .catch(() => setSrc(null));
    } else {
      setSrc(null);
    }
    return () => { cancelled = true; if (url) URL.revokeObjectURL(url); };
  }, [file, materielId, hasImage]);

  function pick(f: File | undefined) {
    onError("");
    if (!f) return onFile(null);
    if (!/^image\/(jpeg|png|webp)$/.test(f.type)) return onError(t("Format non accepté (JPEG, PNG ou WebP)."));
    if (f.size > MAX_MB * 1024 * 1024) return onError(t("Fichier trop volumineux (maximum {n} Mo).", { n: MAX_MB }));
    onFile(f);
  }

  return (
    <div className="image-field">
      <div className="image-preview">
        {src ? <img src={src} alt={t("Image")} /> : <span className="hint">{t("Aucune image")}</span>}
      </div>
      <div className="image-field-side">
        <input type="file" accept="image/jpeg,image/png,image/webp" aria-label={t("Image")}
          onChange={(e) => { pick(e.target.files?.[0]); e.target.value = ""; }} />
        {file && <p className="hint">{t("Sera enregistrée avec le matériel : {x}", { x: file.name })}</p>}
        {file && <button type="button" className="btn ghost" onClick={() => onFile(null)}>{t("Annuler le choix")}</button>}
        {onManage && !file && hasImage && (
          <button type="button" className="btn ghost" onClick={onManage}>{t("Agrandir / supprimer")}</button>
        )}
        <p className="hint">{t("JPEG, PNG ou WebP, 5 Mo maximum.")}</p>
      </div>
    </div>
  );
}
