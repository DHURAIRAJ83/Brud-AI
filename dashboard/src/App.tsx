import { DashboardLayout } from "./layouts/DashboardLayout";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { Overview } from "./pages/Overview";
import { Devices } from "./pages/Devices";
import { Commands } from "./pages/Commands";
import { AuditLogs } from "./pages/AuditLogs";
import { Health } from "./pages/Health";
import { ActivityFeed } from "./pages/ActivityFeed";
import { Analytics } from "./pages/Analytics";
import { VoiceDashboard } from "./pages/VoiceDashboard";

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<DashboardLayout />}>
          <Route index element={<Overview />} />
          <Route path="devices" element={<Devices />} />
          <Route path="commands" element={<Commands />} />
          <Route path="audit" element={<AuditLogs />} />
          <Route path="health" element={<Health />} />
          <Route path="activity" element={<ActivityFeed />} />
          <Route path="analytics" element={<Analytics />} />
          <Route path="voice" element={<VoiceDashboard />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default App;
