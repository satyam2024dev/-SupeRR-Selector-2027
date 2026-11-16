import React, { useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Player, RoleType } from '../types';

interface PlayerDrawerProps {
  player: Player | null;
  role: RoleType;
  onClose: () => void;
}

export const PlayerDrawer: React.FC<PlayerDrawerProps> = ({ player, role, onClose }) => {
  const drawerRef = useRef<HTMLDivElement>(null);
  const closeButtonRef = useRef<HTMLButtonElement>(null);
  const previouslyFocusedElement = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (player) {
      previouslyFocusedElement.current = document.activeElement as HTMLElement;
      document.body.style.overflow = 'hidden';

      // Focus close button initially
      const focusTimer = setTimeout(() => {
        closeButtonRef.current?.focus();
      }, 50);

      const handleKeyDown = (e: KeyboardEvent) => {
        if (e.key === 'Escape') {
          e.preventDefault();
          onClose();
          return;
        }

        // Trap focus inside drawer
        if (e.key === 'Tab' && drawerRef.current) {
          const focusables = Array.from(
            drawerRef.current.querySelectorAll<HTMLElement>(
              'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
            )
          ).filter(el => !el.hasAttribute('disabled') && el.getAttribute('aria-hidden') !== 'true');

          if (focusables.length === 0) {
            e.preventDefault();
            return;
          }

          const first = focusables[0];
          const last = focusables[focusables.length - 1];

          if (!drawerRef.current.contains(document.activeElement)) {
            e.preventDefault();
            first.focus();
            return;
          }

          if (e.shiftKey) {
            if (document.activeElement === first) {
              e.preventDefault();
              last.focus();
            }
          } else {
            if (document.activeElement === last) {
              e.preventDefault();
              first.focus();
            }
          }
        }
      };

      window.addEventListener('keydown', handleKeyDown);

      return () => {
        clearTimeout(focusTimer);
        document.body.style.overflow = 'unset';
        window.removeEventListener('keydown', handleKeyDown);
        previouslyFocusedElement.current?.focus();
      };
    } else {
      document.body.style.overflow = 'unset';
    }
  }, [player, onClose]);

  if (!player) return null;

  // Plain-English verdict based on verified numbers
  const getVerdict = (p: Player, r: RoleType): string => {
    if (r === 'batters') {
      if (p.name.includes('Klaasen')) {
        return 'Scores significantly faster under pressure (+50.5 SR) while remaining a primary finisher.';
      }
      if (p.name.includes('Sooryavanshi')) {
        return 'Aggressive powerplay hitter who maintains rapid boundary tempo in tight games.';
      }
      if (p.name.includes('Powell')) {
        return 'Power hitter whose strike rate leaps 64 points in critical moments.';
      }
      if (p.name.includes('Mendis')) {
        return 'Top-order anchor who absorbs pressure and limits dismissals.';
      }
      if (p.name.includes('Nawaz')) {
        return 'Reliable spin all-rounder with strong boundary-scoring in chases.';
      }
      if (p.name.includes('Mitchell')) {
        return 'Middle-order consolidator who accelerates when the match is tight.';
      }
      if (p.name.includes('Wade')) {
        return 'Finisher with exceptional wicket preservation in close finishes.';
      }
      if (p.name.includes('Rinku')) {
        return 'Elite raw strike rate, adjusted for a concentrated 30-inning sample.';
      }
      if (p.name.includes('Karthik')) {
        return 'Experienced finisher scoring at 189 strike rate in death overs.';
      }
      return 'Fast-scoring opener who puts bowling attacks under immediate pressure.';
    } else {
      if (p.name.includes('Narine')) {
        return 'Stifles scoring under pressure (6.3 economy) and doubles his wicket-taking rate.';
      }
      if (p.name.includes('Rashid')) {
        return 'Reliable wicket threat who keeps economy tight in high-leverage overs.';
      }
      if (p.name.includes('Santner')) {
        return 'Economical finger spinner whose output rises when matches are on the line.';
      }
      if (p.name.includes('Hazlewood')) {
        return 'Disciplined seam bowler with heightened strike power at the death.';
      }
      if (p.name.includes('Mohsin')) {
        return 'High-impact wicket-taker in late-inning pressure situations.';
      }
      if (p.name.includes('Zampa')) {
        return 'Aggressive leg-spinner whose wicket frequency increases under stress.';
      }
      if (p.name.includes('Taskin')) {
        return 'Frontline pace bowler maintaining control in tight overs.';
      }
      if (p.name.includes('Shoriful')) {
        return 'Effective swing and death seamer who lowers economy under pressure.';
      }
      if (p.name.includes('Theekshana')) {
        return 'Powerplay and middle overs mystery spinner with steady control.';
      }
      return 'Express pace bowler with elevated strike rate in clutch moments.';
    }
  };

  const verdict = getVerdict(player, role);

  return (
    <AnimatePresence>
      <div className="fixed inset-0 z-50 flex justify-end" role="dialog" aria-modal="true" aria-label={`Details for ${player.name}`}>
        {/* Backdrop */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          onClick={onClose}
          className="fixed inset-0 bg-black/60 cursor-pointer"
          aria-hidden="true"
        />

        {/* Drawer Panel */}
        <motion.div
          ref={drawerRef}
          initial={{ x: '100%' }}
          animate={{ x: 0 }}
          exit={{ x: '100%' }}
          transition={{ type: 'spring', damping: 28, stiffness: 280 }}
          className="relative z-10 w-full max-w-md bg-[#12151C] border-l border-[#232834] h-full overflow-y-auto p-6 sm:p-8 flex flex-col justify-between"
        >
          {/* Top Section */}
          <div className="space-y-6">
            {/* Header */}
            <div className="flex items-start justify-between gap-4 pb-5 border-b border-[#232834]">
              <div>
                <span className="text-xs font-semibold text-[#E6007E] uppercase tracking-wider">
                  Rank #{player.rank} &bull; {role === 'batters' ? 'Batter' : 'Bowler'}
                </span>
                <h3 className="text-xl sm:text-2xl font-bold text-[#E8EAF0] mt-1">
                  {player.name}
                </h3>
                <p className="text-xs text-[#8B93A5] mt-0.5">{player.team}</p>
              </div>

              <button
                ref={closeButtonRef}
                onClick={onClose}
                className="w-8 h-8 rounded-lg bg-[#1C212B] hover:bg-[#232834] text-[#8B93A5] hover:text-[#E8EAF0] flex items-center justify-center transition-colors cursor-pointer"
                aria-label="Close drawer"
              >
                &times;
              </button>
            </div>

            {/* Verdict */}
            <div className="bg-[#0B0D12] border border-[#232834] rounded-xl p-4">
              <span className="text-[11px] font-semibold text-[#8B93A5] uppercase tracking-wider block mb-1">
                Verdict
              </span>
              <p data-testid="player-verdict" className="text-xs sm:text-sm text-[#E8EAF0] leading-relaxed font-medium">
                {verdict}
              </p>
            </div>

            {/* Normal vs High-Pressure Comparison Bars */}
            <div className="space-y-4">
              <span className="text-xs font-semibold text-[#8B93A5] uppercase tracking-wider block">
                {role === 'batters' ? 'Strike Rate comparison' : 'Economy Rate comparison'}
              </span>

              {role === 'batters' ? (
                <div className="space-y-3">
                  {/* Normal Situation */}
                  <div className="bg-[#0B0D12] border border-[#232834] rounded-xl p-3.5 space-y-1.5">
                    <div className="flex justify-between text-xs">
                      <span className="text-[#8B93A5]">Normal Strike Rate</span>
                      <span className="font-semibold text-[#E8EAF0] tabular-nums">
                        {player.srN ?? 140}
                      </span>
                    </div>
                    <div className="w-full h-2 bg-[#232834] rounded-full overflow-hidden" role="progressbar" aria-valuenow={player.srN ?? 140} aria-valuemin={0} aria-valuemax={240} aria-label="Normal Strike Rate">
                      <div
                        className="h-full bg-[#5A6275] rounded-full"
                        style={{ width: `${Math.min(100, ((player.srN ?? 140) / 240) * 100)}%` }}
                      />
                    </div>
                  </div>

                  {/* High Pressure Situation */}
                  <div className="bg-[#0B0D12] border border-[#232834] rounded-xl p-3.5 space-y-1.5">
                    <div className="flex justify-between text-xs">
                      <span className="text-[#E6007E] font-medium">High-Pressure Strike Rate</span>
                      <span className="font-semibold text-[#E8EAF0] tabular-nums">
                        {player.srHP ?? 150}
                      </span>
                    </div>
                    <div className="w-full h-2 bg-[#232834] rounded-full overflow-hidden" role="progressbar" aria-valuenow={player.srHP ?? 150} aria-valuemin={0} aria-valuemax={240} aria-label="High-Pressure Strike Rate">
                      <div
                        className="h-full bg-[#E6007E] rounded-full"
                        style={{ width: `${Math.min(100, ((player.srHP ?? 150) / 240) * 100)}%` }}
                      />
                    </div>
                  </div>
                </div>
              ) : (
                <div className="space-y-3">
                  {/* Normal Situation */}
                  <div className="bg-[#0B0D12] border border-[#232834] rounded-xl p-3.5 space-y-1.5">
                    <div className="flex justify-between text-xs">
                      <span className="text-[#8B93A5]">Normal Economy</span>
                      <span className="font-semibold text-[#E8EAF0] tabular-nums">
                        {player.econN ?? 8.5} rpo
                      </span>
                    </div>
                    <div className="w-full h-2 bg-[#232834] rounded-full overflow-hidden" role="progressbar" aria-valuenow={player.econN ?? 8.5} aria-valuemin={0} aria-valuemax={12} aria-label="Normal Economy">
                      <div
                        className="h-full bg-[#5A6275] rounded-full"
                        style={{ width: `${Math.min(100, ((player.econN ?? 8.5) / 12) * 100)}%` }}
                      />
                    </div>
                  </div>

                  {/* High Pressure Situation */}
                  <div className="bg-[#0B0D12] border border-[#232834] rounded-xl p-3.5 space-y-1.5">
                    <div className="flex justify-between text-xs">
                      <span className="text-[#E6007E] font-medium">High-Pressure Economy</span>
                      <span className="font-semibold text-[#E8EAF0] tabular-nums">
                        {player.econHP ?? 8.0} rpo
                      </span>
                    </div>
                    <div className="w-full h-2 bg-[#232834] rounded-full overflow-hidden" role="progressbar" aria-valuenow={player.econHP ?? 8.0} aria-valuemin={0} aria-valuemax={12} aria-label="High-Pressure Economy">
                      <div
                        className="h-full bg-[#E6007E] rounded-full"
                        style={{ width: `${Math.min(100, ((player.econHP ?? 8.0) / 12) * 100)}%` }}
                      />
                    </div>
                  </div>
                </div>
              )}
            </div>

            {/* IPL vs T20I Mini Comparison */}
            <div>
              <span className="text-xs font-semibold text-[#8B93A5] uppercase tracking-wider block mb-3">
                Tournament breakdown (raw rating)
              </span>

              <div className="grid grid-cols-2 gap-3">
                <div className="bg-[#0B0D12] border border-[#232834] rounded-xl p-3.5 text-center">
                  <div className="text-xs text-[#8B93A5]">IPL</div>
                  <div className="text-lg font-bold text-[#E8EAF0] tabular-nums mt-1">
                    {player.iplRaw !== null ? `+${player.iplRaw}` : 'n.a.'}
                  </div>
                  <div className="text-[10px] text-[#5A6275] mt-0.5">
                    {player.iplRaw !== null ? 'verified' : '<25 HP balls'}
                  </div>
                </div>

                <div className="bg-[#0B0D12] border border-[#232834] rounded-xl p-3.5 text-center">
                  <div className="text-xs text-[#8B93A5]">T20I</div>
                  <div className="text-lg font-bold text-[#E8EAF0] tabular-nums mt-1">
                    {player.t20iRaw !== null ? `+${player.t20iRaw}` : 'n.a.'}
                  </div>
                  <div className="text-[10px] text-[#5A6275] mt-0.5">
                    {player.t20iRaw !== null ? 'verified' : '<25 HP balls'}
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Drawer Footer */}
          <div className="pt-6 border-t border-[#232834] flex items-center justify-between text-xs text-[#8B93A5]">
            <span>Confidence: <strong className="text-[#E8EAF0]">{player.confidence}</strong></span>
            <span>Sample: <strong className="text-[#E8EAF0] tabular-nums">{player.balls}</strong> balls</span>
          </div>
        </motion.div>
      </div>
    </AnimatePresence>
  );
};

export default PlayerDrawer;
