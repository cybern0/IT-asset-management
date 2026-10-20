import { Outlet } from "react-router";
import { Sidebar } from "../components/Sidebar";
import { StoreProvider } from "../lib/store";

export default function Shell() {
  return (
    <StoreProvider>
      <div className="app">
        <Sidebar />
        <main className="content">
          <Outlet />
        </main>
      </div>
    </StoreProvider>
  );
}
