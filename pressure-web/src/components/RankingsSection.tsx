import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { Player, RoleType } from '../types';
import PlayerDrawer from './PlayerDrawer';

interface RankingsSectionProps {
  top10Batters: Player[];
  top10Bowlers: Player[];
}

export const RankingsSection: React.FC<RankingsSectionProps> = ({
  top10Batters,
  top10Bowlers,
}) => {
  const [activeRole, setActiveRole] = useState<RoleType>('batters');
  const [showRaw, setShowRaw] = useState<boolean>(false);
  const [selectedPlayer, setSelectedPlayer] = useState<Player | null>(null);

  const players = activeRole === 'batters' ? top10Batters : top10Bowlers;

  // Maximum rating value for normalizing bar widths (Rinku's raw is 166.6, max shrunk is Narine 45.2)
  const maxVal = showRaw ? 170 : 50;

  const getConfidenceStyle = (confidence: string) => {
    if (confidence === 'Secure') {
      return 'text-emerald-400 bg-emerald-400/10 border-emerald-400/30';
    }
    if (confidence === 'Likely') {
      return 'text-sky-400 bg-sky-400/10 border-sky-400/30';
    }
    return 'text-amber-400 bg-amber-400/10 border-amber-400/30';
  };

  return (
    <section id="rankings" className="py-16 sm:py-24 px-4 sm:px-6 max-w-5xl mx-auto scroll-mt-14">
      {/* Section Header */}
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true }}
        transition={{ duration: 0.4 }}
        className="mb-8"
      >
        <h2 className="text-2xl sm:text-3xl font-bold tracking-tight text-[#E8EAF0]">
          The pressure rankings
        </h2>
        <p className="text-sm sm:text-base text-[#8B93A5] mt-2">
          Players ranked by win probability added per 100 high-pressure balls, adjusted for match context.
        </p>
      </motion.div>

      {/* Controls Bar: Role Tabs + Raw Toggle */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 mb-6">
        {/* Role Tabs */}
        <div className="inline-flex p-1 bg-[#12151C] border border-[#232834] rounded-xl" role="tablist" aria-label="Player categories">
          <button
            role="tab"
            aria-selected={activeRole === 'batters'}
            aria-controls="rankings-panel"
            id="tab-batters"
            onClick={() => setActiveRole('batters')}
            className={`px-4 py-2 rounded-lg text-xs font-semibold transition-colors cursor-pointer ${
              activeRole === 'batters'
                ? 'bg-[#E6007E] text-white'
                : 'text-[#8B93A5] hover:text-[#E8EAF0]'
            }`}
            aria-label="Show Top 10 Batters"
          >
            Batters
          </button>
          <button
            role="tab"
            aria-selected={activeRole === 'bowlers'}
            aria-controls="rankings-panel"
            id="tab-bowlers"
            onClick={() => setActiveRole('bowlers')}
            className={`px-4 py-2 rounded-lg text-xs font-semibold transition-colors cursor-pointer ${
              activeRole === 'bowlers'
                ? 'bg-[#E6007E] text-white'
                : 'text-[#8B93A5] hover:text-[#E8EAF0]'
            }`}
            aria-label="Show Top 10 Bowlers"
          >
            Bowlers
          </button>
        </div>

        {/* Show Raw Toggle */}
        <div className="flex items-center gap-2">
          <button
            type="button"
            role="switch"
            aria-checked={showRaw}
            onClick={() => setShowRaw(!showRaw)}
            className="flex items-center gap-2 text-xs text-[#E8EAF0] cursor-pointer select-none"
            aria-label="Toggle raw or shrunk ratings"
          >
            <div
              className={`w-8 h-4 rounded-full p-0.5 transition-colors ${
                showRaw ? 'bg-[#E6007E]' : 'bg-[#232834]'
              }`}
            >
              <div
                className={`w-3 h-3 rounded-full bg-white transition-transform ${
                  showRaw ? 'translate-x-4' : 'translate-x-0'
                }`}
              />
            </div>
            <span className="font-medium">Show raw numbers</span>
          </button>
        </div>
      </div>

      {/* Explanation Note for Raw Numbers */}
      {showRaw && (
        <motion.div
          initial={{ opacity: 0, height: 0 }}
          animate={{ opacity: 1, height: 'auto' }}
          exit={{ opacity: 0, height: 0 }}
          className="mb-4 text-xs text-[#8B93A5]"
        >
          Raw scores from few balls are unreliable, so we pull them toward the average.
        </motion.div>
      )}

      {/* Ranked List of 10 Players */}
      <div
        id="rankings-panel"
        role="tabpanel"
        aria-labelledby={`tab-${activeRole}`}
        className="bg-[#12151C] border border-[#232834] rounded-2xl divide-y divide-[#232834] overflow-hidden"
      >
        {players.map((player) => {
          const currentRating = showRaw ? player.rawRating : player.shrunkRating;
          const barWidthPercent = Math.min(100, Math.max(8, (currentRating / maxVal) * 100));

          return (
            <div
              key={player.name}
              role="button"
              tabIndex={0}
              aria-label={`View performance details for ${player.name}, ranked number ${player.rank}`}
              onClick={() => setSelectedPlayer(player)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault();
                  setSelectedPlayer(player);
                }
              }}
              className="p-4 sm:px-6 flex items-center justify-between gap-3 sm:gap-6 hover:bg-[#181C26] transition-colors cursor-pointer group focus-visible:bg-[#181C26]"
            >
              {/* Rank & Name */}
              <div className="flex items-center gap-3 sm:gap-4 min-w-[120px] sm:min-w-[200px]">
                <span className="w-5 text-xs font-semibold text-[#5A6275] tabular-nums group-hover:text-[#E6007E] transition-colors">
                  {player.rank}
                </span>
                <span className="text-sm font-semibold text-[#E8EAF0] group-hover:text-white transition-colors truncate">
                  {player.name}
                </span>
              </div>

              {/* Horizontal Rating Bar */}
              <div className="flex-1 flex items-center gap-3 max-w-xs sm:max-w-md">
                <div
                  className="flex-1 h-2 bg-[#232834] rounded-full overflow-hidden"
                  role="progressbar"
                  aria-valuenow={currentRating}
                  aria-valuemin={0}
                  aria-valuemax={maxVal}
                  aria-label={`${player.name} rating bar`}
                >
                  <div
                    className="h-full bg-[#E6007E] rounded-full transition-all duration-300"
                    style={{ width: `${barWidthPercent}%` }}
                  />
                </div>
                <span className="text-xs font-mono font-semibold text-[#E8EAF0] tabular-nums shrink-0 w-12 text-right">
                  +{currentRating.toFixed(1)}
                </span>
              </div>

              {/* Confidence Badge */}
              <div className="shrink-0">
                <span
                  className={`inline-block px-2.5 py-0.5 rounded-full text-[11px] font-medium border ${getConfidenceStyle(
                    player.confidence
                  )}`}
                >
                  {player.confidence}
                </span>
              </div>
            </div>
          );
        })}
      </div>

      {/* Slide-over Player Drawer */}
      <PlayerDrawer
        player={selectedPlayer}
        role={activeRole}
        onClose={() => setSelectedPlayer(null)}
      />
    </section>
  );
};

export default RankingsSection;
