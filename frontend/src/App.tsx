import { lazy, Suspense, type ReactNode } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import AppShell from "./layout/AppShell";
import { LoadingPanel } from "./components/ui";

const AuctionPage = lazy(() => import("./pages/AuctionPage"));
const BowlingPage = lazy(() => import("./pages/BowlingPage"));
const ComparisonPage = lazy(() => import("./pages/ComparisonPage"));
const DiscoveryPage = lazy(() => import("./pages/DiscoveryPage"));
const MethodologyPage = lazy(() => import("./pages/MethodologyPage"));
const OverviewPage = lazy(() => import("./pages/OverviewPage"));
const RankingsPage = lazy(() => import("./pages/RankingsPage"));

function Page({ children }: { children: ReactNode }) {
  return <Suspense fallback={<LoadingPanel label="Opening scouting section" />}>{children}</Suspense>;
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<AppShell />}>
          <Route index element={<Page><OverviewPage /></Page>} />
          <Route path="rankings" element={<Page><RankingsPage /></Page>} />
          <Route path="discovery" element={<Page><DiscoveryPage /></Page>} />
          <Route path="discovery/:playerId" element={<Page><DiscoveryPage /></Page>} />
          <Route path="comparison" element={<Page><ComparisonPage /></Page>} />
          <Route path="bowling" element={<Page><BowlingPage /></Page>} />
          <Route path="auction" element={<Page><AuctionPage /></Page>} />
          <Route path="methodology" element={<Page><MethodologyPage /></Page>} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
