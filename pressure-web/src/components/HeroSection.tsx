import React from 'react';
import { motion } from 'framer-motion';

interface HeroSectionProps {
  stats: {
    matches: number;
    deliveries: number;
    highPressureBalls: number;
  };
}

export const HeroSection: React.FC<HeroSectionProps> = ({ stats }) => {
  const scrollTo = (id: string) => {
    const el = document.getElementById(id);
    if (el) el.scrollIntoView({ behavior: 'smooth' });
  };

  return (
    <section id="hero" className="pt-20 sm:pt-28 pb-16 px-4 sm:px-6 max-w-5xl mx-auto">
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
        className="text-center max-w-3xl mx-auto space-y-6"
      >
        {/* Headline (max 8 words) */}
        <h1 className="text-4xl sm:text-5xl md:text-6xl font-bold tracking-tight text-[#E8EAF0] leading-[1.1]">
          Who delivers when it matters?
        </h1>

        {/* One sentence (max 20 words) */}
        <p className="text-base sm:text-lg text-[#8B93A5] leading-relaxed max-w-2xl mx-auto">
          We rated every batter and bowler on how they perform in the highest-pressure moments of IPL and T20I games, 2022 to 2026.
        </p>

        {/* One Button */}
        <div className="pt-2">
          <button
            onClick={() => scrollTo('rankings')}
            className="px-6 py-3 rounded-xl bg-[#E6007E] hover:bg-[#CC006F] text-white font-medium text-sm transition-colors cursor-pointer inline-flex items-center gap-2"
            aria-label="See the rankings"
          >
            <span>See the rankings</span>
            <span aria-hidden="true">&darr;</span>
          </button>
        </div>
      </motion.div>

      {/* Three Stats */}
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, delay: 0.1 }}
        className="grid grid-cols-1 sm:grid-cols-3 gap-4 mt-16"
      >
        <div className="bg-[#12151C] border border-[#232834] rounded-xl p-5 text-center">
          <div className="text-2xl sm:text-3xl font-bold text-[#E8EAF0] tabular-nums">
            {stats.matches.toLocaleString()}
          </div>
          <div className="text-xs text-[#8B93A5] mt-1 font-medium">
            matches analysed
          </div>
        </div>

        <div className="bg-[#12151C] border border-[#232834] rounded-xl p-5 text-center">
          <div className="text-2xl sm:text-3xl font-bold text-[#E8EAF0] tabular-nums">
            {stats.deliveries.toLocaleString()}
          </div>
          <div className="text-xs text-[#8B93A5] mt-1 font-medium">
            balls bowled
          </div>
        </div>

        <div className="bg-[#12151C] border border-[#232834] rounded-xl p-5 text-center">
          <div className="text-2xl sm:text-3xl font-bold text-[#E6007E] tabular-nums">
            Top 20%
          </div>
          <div className="text-xs text-[#8B93A5] mt-1 font-medium">
            flagged as high pressure
          </div>
        </div>
      </motion.div>
    </section>
  );
};

export default HeroSection;
