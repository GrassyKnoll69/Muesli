import { useCallback, useEffect, useState } from "react";
import { BrowserRouter, NavLink, Route, Routes } from "react-router-dom";
import ActiveMeeting from "./pages/ActiveMeeting";
import Library from "./pages/Library";
import MeetingDetail from "./pages/MeetingDetail";
import Templates from "./pages/Templates";
import SettingsPage from "./pages/Settings";
import Onboarding from "./components/Onboarding";
import { api, Health } from "./api/client";

function navClass({ isActive }: { isActive: boolean }) {
  return `nav-link${isActive ? " active" : ""}`;
}

export default function App() {
  const [theme, setTheme] = useState<"light" | "dark">(() => {
    const saved = window.localStorage.getItem("muesli-theme");
    return saved === "dark" ? "dark" : "light";
  });

  const [health, setHealth] = useState<Health | null>(null);

  const refreshHealth = useCallback(() => {
    api.getHealth().then(setHealth).catch(() => setHealth(null));
  }, []);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    window.localStorage.setItem("muesli-theme", theme);
  }, [theme]);

  useEffect(() => {
    refreshHealth();
  }, [refreshHealth]);

  return (
    <BrowserRouter>
      <div className="app-shell">
        <aside className="sidebar">
          <div className="brand">
            <div className="brand-title">Muesli</div>
            <div className="brand-subtitle">Local AI meeting notes</div>
          </div>
          <label className="theme-switch">
            <span>Light</span>
            <input
              aria-label="Use dark mode"
              checked={theme === "dark"}
              onChange={(event) => setTheme(event.target.checked ? "dark" : "light")}
              type="checkbox"
            />
            <span className="theme-slider" aria-hidden="true" />
            <span>Dark</span>
          </label>
          <nav className="nav-list" aria-label="Primary navigation">
            <NavLink className={navClass} to="/">Meetings</NavLink>
            <NavLink className={navClass} to="/new">Record</NavLink>
            <NavLink className={navClass} to="/templates">Templates</NavLink>
            <NavLink className={navClass} to="/settings">Settings</NavLink>
          </nav>
        </aside>
        <main className="main">
          <Onboarding health={health} onRefresh={refreshHealth} />
          <Routes>
            <Route path="/" element={<Library />} />
            <Route path="/new" element={<ActiveMeeting />} />
            <Route path="/meetings/:id" element={<MeetingDetail />} />
            <Route path="/templates" element={<Templates />} />
            <Route path="/settings" element={<SettingsPage />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}
