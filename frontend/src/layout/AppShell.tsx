import { useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { Activity, BarChart3, BookOpen, GitCompare, LayoutDashboard, Menu, Search, Target, Trophy, X } from "lucide-react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import { useApi } from "../api/client";
import type { ReactNode } from "react";

const navigation = [
  { label: "Overview", to: "/", icon: LayoutDashboard },
  { label: "Batter Rankings", to: "/rankings", icon: Trophy },
  { label: "Player Discovery", to: "/discovery", icon: Search },
  { label: "Player Comparison", to: "/comparison", icon: GitCompare },
  { label: "Bowling Intelligence", to: "/bowling", icon: BarChart3 },
  { label: "RR Auction Targets", to: "/auction", icon: Target },
  { label: "Methodology", to: "/methodology", icon: BookOpen },
];

function Wordmark() {
  return (
    <div className="brand-lockup">
      <div className="brand-mark" aria-hidden="true"><span>S</span><i /></div>
      <div className="brand-copy"><strong>SupeRR Selector</strong><span>2027 AUCTION INTELLIGENCE</span></div>
    </div>
  );
}

function LocalApiStatus() {
  const { data, loading, error } = useApi<{ status: string }>("/health");
  const online = data?.status === "ok";
  return (
    <div className={`api-status ${online ? "api-online" : error ? "api-offline" : "api-pending"}`} title="The API is configured for localhost only">
      <span className="api-pulse" />
      <span>{online ? "Local data connected" : loading ? "Checking local API" : "API not connected"}</span>
    </div>
  );
}

function NavigationLinks({ onNavigate }: { onNavigate?: () => void }) {
  return (
    <nav className="primary-nav" aria-label="Main navigation">
      <div className="nav-kicker">SCOUTING WORKSPACE</div>
      {navigation.map(({ label, to, icon: Icon }) => (
        <NavLink key={to} to={to} end={to === "/"} onClick={onNavigate} className={({ isActive }) => `nav-link ${isActive ? "nav-link-active" : ""}`}>
          <Icon size={17} strokeWidth={1.8} aria-hidden="true" />
          <span>{label}</span>
          {to === "/auction" ? <span className="nav-new">NEW</span> : null}
        </NavLink>
      ))}
    </nav>
  );
}

function Sidebar() {
  return (
    <aside className="sidebar desktop-sidebar">
      <Wordmark />
      <div className="sidebar-rule" />
      <NavigationLinks />
      <div className="sidebar-bottom">
        <div className="sidebar-season"><span className="season-orbit"><Activity size={15} /></span><div><strong>IPL 2027</strong><small>Performance + availability</small></div></div>
        <div className="sidebar-footnote">Decision support from validated local evidence.</div>
      </div>
    </aside>
  );
}

function MobileNavigation({ open, onClose }: { open: boolean; onClose: () => void }) {
  return (
    <AnimatePresence>
      {open ? (
        <>
          <motion.button className="mobile-scrim" aria-label="Close navigation" onClick={onClose} initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} />
          <motion.aside className="sidebar mobile-drawer" aria-label="Mobile navigation" initial={{ x: -310 }} animate={{ x: 0 }} exit={{ x: -310 }} transition={{ type: "spring", stiffness: 320, damping: 34 }}>
            <div className="mobile-drawer-head"><Wordmark /><button className="icon-button" aria-label="Close menu" onClick={onClose}><X size={19} /></button></div>
            <div className="sidebar-rule" />
            <NavigationLinks onNavigate={onClose} />
            <div className="sidebar-bottom"><div className="sidebar-footnote">Decision support from validated local evidence.</div></div>
          </motion.aside>
        </>
      ) : null}
    </AnimatePresence>
  );
}

function PageTransition({ children }: { children: ReactNode }) {
  const reduceMotion = useReducedMotion();
  return (
    <motion.div
      key={useLocation().pathname}
      className="page-transition"
      initial={reduceMotion ? false : { opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: reduceMotion ? 0 : 0.2 }}
    >{children}</motion.div>
  );
}

export default function AppShell() {
  const [mobileOpen, setMobileOpen] = useState(false);
  const location = useLocation();
  const current = location.pathname.startsWith("/discovery/")
    ? "Player Discovery"
    : navigation.find((item) => item.to === location.pathname)?.label ?? "Overview";
  return (
    <div className="app-frame">
      <Sidebar />
      <div className="main-column">
        <header className="topbar">
          <button className="mobile-menu-button icon-button" aria-label="Open navigation" onClick={() => setMobileOpen(true)}><Menu size={20} /></button>
          <div className="mobile-wordmark"><Wordmark /></div>
          <div className="topbar-crumb"><span>SupeRR Selector 2027</span><i>/</i><strong>{current}</strong></div>
          <div className="topbar-right"><span className="local-chip">LOCAL WORKSPACE</span><LocalApiStatus /></div>
        </header>
        <main id="main-content" className="main-content" tabIndex={-1}>
          <PageTransition><Outlet /></PageTransition>
        </main>
        <footer className="app-footer"><span>SupeRR Selector 2027</span><span>Validated evidence. Transparent limits.</span></footer>
      </div>
      <MobileNavigation open={mobileOpen} onClose={() => setMobileOpen(false)} />
    </div>
  );
}
