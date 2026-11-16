import React from 'react';
import pressureDataRaw from './data/pressureData.json';
import { PressureDataset } from './types';

// Components (Only the required 5 sections + minimal nav & footer)
import Navbar from './components/Navbar';
import HeroSection from './components/HeroSection';
import ChaseSimulator from './components/ChaseSimulator';
import RankingsSection from './components/RankingsSection';
import MethodologySection from './components/MethodologySection';
import Footer from './components/Footer';

const dataset = pressureDataRaw as unknown as PressureDataset;

export const App: React.FC = () => {
  return (
    <div className="min-h-screen bg-[#0B0D12] text-[#E8EAF0] font-sans antialiased selection:bg-[#E6007E] selection:text-white">
      {/* Sticky Minimal Navigation */}
      <Navbar />

      {/* Main Content (Strictly the 5 Sections) */}
      <main>
        {/* 1. HERO */}
        <HeroSection stats={dataset.heroStats} />

        {/* 2. FEEL THE PRESSURE (Interactive Simulator) */}
        <ChaseSimulator />

        {/* 3. THE RANKINGS (with 4. Player Drawer on click) */}
        <RankingsSection
          top10Batters={dataset.top10Batters}
          top10Bowlers={dataset.top10Bowlers}
        />

        {/* 5. HOW SURE ARE WE? (Bootstrap chart + Method accordion) */}
        <MethodologySection
          top10Batters={dataset.top10Batters}
          top10Bowlers={dataset.top10Bowlers}
        />
      </main>

      {/* Minimal Footer */}
      <Footer />
    </div>
  );
};

export default App;
