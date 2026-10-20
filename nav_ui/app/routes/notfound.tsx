import { Link } from "react-router";

export default function NotFound() {
  return (
    <div className="pane">
      <div className="pane-body">
        <p className="empty">
          Cette page n’existe pas. <Link to="/assets/materiel/computers">Retour au matériel</Link>
        </p>
      </div>
    </div>
  );
}
