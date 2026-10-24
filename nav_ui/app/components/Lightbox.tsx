import { useEffect, useRef } from "react";
import { useI18n } from "../lib/i18n";

/** Visionneuse plein écran : l'image occupe tout l'écran ; clic, Échap ou « Fermer » pour sortir. */
export function Lightbox({ src, alt, newTabHref, onClose }: {
  src: string; alt: string; newTabHref?: string; onClose: () => void;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  const { t } = useI18n();

  useEffect(() => {
    const el = ref.current;
    if (el && !el.open) el.showModal();
    return () => el?.close();
  }, []);

  return (
    <dialog ref={ref} className="lightbox" aria-label={alt} onClose={onClose} onClick={onClose}>
      <div className="lightbox-bar" onClick={(e) => e.stopPropagation()}>
        {newTabHref && (
          <a className="btn ghost" href={newTabHref} target="_blank" rel="noopener noreferrer">
            {t("Ouvrir dans un nouvel onglet")}
          </a>
        )}
        <button type="button" className="btn primary" onClick={onClose}>{t("Fermer")}</button>
      </div>
      <img src={src} alt={alt} onClick={(e) => e.stopPropagation()} />
    </dialog>
  );
}
