import { Outlet } from "react-router";
import { Sidebar } from "../components/Sidebar";
import { I18nProvider } from "../lib/i18n";
import { StoreProvider } from "../lib/store";

export default function Shell() {
  return (
    <I18nProvider>
      <StoreProvider>
        <div className="app">
          <Sidebar />
          <main className="content">
            <Outlet />
          </main>
        </div>
      </StoreProvider>
    </I18nProvider>
  );
}
