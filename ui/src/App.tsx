import { BrowserRouter, NavLink, Route, Routes } from "react-router-dom";
import ActiveMeeting from "./pages/ActiveMeeting";
import Library from "./pages/Library";
import MeetingDetail from "./pages/MeetingDetail";
import Templates from "./pages/Templates";
import SettingsPage from "./pages/Settings";

function navClass({ isActive }: { isActive: boolean }) {
  return `nav-link${isActive ? " active" : ""}`;
}

export default function App() {
  return (
    <BrowserRouter>
      <div className="app-shell">
        <aside className="sidebar">
          <div className="brand">
            <div className="brand-title">Muesli</div>
            <div className="brand-subtitle">Local AI meeting notes</div>
          </div>
          <nav className="nav-list" aria-label="Primary navigation">
            <NavLink className={navClass} to="/">Meetings</NavLink>
            <NavLink className={navClass} to="/new">Record</NavLink>
            <NavLink className={navClass} to="/templates">Templates</NavLink>
            <NavLink className={navClass} to="/settings">Settings</NavLink>
          </nav>
        </aside>
        <main className="main">
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
