import { BrowserRouter, Routes, Route, Link } from "react-router-dom";
import Library from "./pages/Library";
import ActiveMeeting from "./pages/ActiveMeeting";
import MeetingDetail from "./pages/MeetingDetail";
import Templates from "./pages/Templates";

export default function App() {
  return (
    <BrowserRouter>
      <nav style={{ display: "flex", gap: 16, padding: 12, borderBottom: "1px solid #ddd" }}>
        <Link to="/">Library</Link>
        <Link to="/new">New Meeting</Link>
        <Link to="/templates">Templates</Link>
      </nav>
      <div style={{ padding: 16, maxWidth: 820, margin: "0 auto" }}>
        <Routes>
          <Route path="/" element={<Library />} />
          <Route path="/new" element={<ActiveMeeting />} />
          <Route path="/meetings/:id" element={<MeetingDetail />} />
          <Route path="/templates" element={<Templates />} />
        </Routes>
      </div>
    </BrowserRouter>
  );
}
