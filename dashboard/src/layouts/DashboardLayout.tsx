import { Outlet, Link, useLocation } from "react-router-dom";
import {
  LayoutDashboard,
  Server,
  TerminalSquare,
  ShieldCheck,
  LogOut,
  Moon,
  Sun,
  HeartPulse,
  Zap,
  BarChart2,
  Mic
} from "lucide-react";
import { useEffect, useState } from "react";

export function DashboardLayout() {
  const location = useLocation();
  const [isDark, setIsDark] = useState(true);

  // Toggle dark mode classes on html element
  useEffect(() => {
    if (isDark) {
      document.documentElement.classList.add("dark");
    } else {
      document.documentElement.classList.remove("dark");
    }
  }, [isDark]);

  const navItems = [
    { name: "Overview",     path: "/",          icon: LayoutDashboard },
    { name: "Devices",      path: "/devices",    icon: Server },
    { name: "Commands",     path: "/commands",   icon: TerminalSquare },
    { name: "Live Activity",path: "/activity",   icon: Zap },
    { name: "Voice Control",path: "/voice",      icon: Mic },
    { name: "Audit Logs",   path: "/audit",      icon: ShieldCheck },
    { name: "Analytics",    path: "/analytics",  icon: BarChart2 },
    { name: "System Health",path: "/health",     icon: HeartPulse },
  ];

  return (
    <div className="flex h-screen bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-slate-50">
      {/* Sidebar */}
      <aside className="w-64 border-r border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 flex flex-col">
        <div className="p-6 border-b border-slate-200 dark:border-slate-800">
          <h1 className="text-2xl font-bold bg-gradient-to-r from-blue-600 to-indigo-600 bg-clip-text text-transparent">
            Rudran AI
          </h1>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
            Production Operations Center
          </p>
        </div>

        <nav className="flex-1 p-4 space-y-1 overflow-y-auto">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = location.pathname === item.path;
            return (
              <Link
                key={item.path}
                to={item.path}
                className={`flex items-center gap-3 px-3 py-2 rounded-md transition-colors ${
                  isActive
                    ? "bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400 font-medium"
                    : "text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800/50 hover:text-slate-900 dark:hover:text-slate-200"
                }`}
              >
                <Icon size={18} />
                {item.name}
              </Link>
            );
          })}
        </nav>

        <div className="p-4 border-t border-slate-200 dark:border-slate-800 flex flex-col gap-2">
          <div className="flex items-center justify-between px-3 py-2">
            <span className="text-sm font-medium">Theme</span>
            <button
              onClick={() => setIsDark(!isDark)}
              className="p-1.5 rounded-md bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200"
            >
              {isDark ? <Sun size={16} /> : <Moon size={16} />}
            </button>
          </div>
          <button className="flex items-center gap-3 px-3 py-2 text-sm text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20 rounded-md transition-colors mt-2 w-full text-left">
            <LogOut size={18} />
            Logout (Admin)
          </button>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 flex flex-col overflow-hidden">
        <header className="h-16 border-b border-slate-200 dark:border-slate-800 bg-white/50 dark:bg-slate-900/50 backdrop-blur-sm flex items-center px-8">
          <div className="flex-1"></div>
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2">
              <span className="relative flex h-3 w-3">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-3 w-3 bg-emerald-500"></span>
              </span>
              <span className="text-sm font-medium text-slate-600 dark:text-slate-300">System Online</span>
            </div>
          </div>
        </header>
        
        <div className="flex-1 overflow-auto p-8 relative">
          {/* Dashboard Route Outlet */}
          <Outlet />
        </div>
      </main>
    </div>
  );
}
