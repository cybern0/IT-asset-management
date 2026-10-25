import { useEffect, useRef, type ReactNode } from "react";
import { useI18n } from "../lib/i18n";

/** Fenetre modale native (<dialog>) : Echap et clic sur le fond ferment la fenetre. */
export function Modal({ title, onClose, wide, children }: {
  title: string; onClose: () => void; wide?: boolean; children: ReactNode;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  const { t } = useI18n();

  useEffect(() => {
    const el = ref.current;
    if (el && !el.open) el.showModal();
    // pas de close() au demontage : en mode dev (StrictMode) il declenchait onClose et refermait la fenetre aussitot
  }, []);

  return (
    <dialog
      ref={ref} className={`modal${wide ? " wide" : ""}`} aria-label={title}
      onClose={onClose} onClick={(e) => { if (e.target === ref.current) onClose(); }}
    >
      <div className="modal-head">
        <h2>{title}</h2>
        <button type="button" className="btn ghost" onClick={onClose}>{t("Fermer")}</button>
      </div>
      <div className="modal-body">{children}</div>
    </dialog>
  );
}
