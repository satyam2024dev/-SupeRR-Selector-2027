import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Player } from '../types';
import BootstrapChart from './BootstrapChart';

interface MethodologySectionProps {
  top10Batters: Player[];
  top10Bowlers: Player[];
}

export const MethodologySection: React.FC<MethodologySectionProps> = ({
  top10Batters,
  top10Bowlers,
}) => {
  const [isOpen, setIsOpen] = useState<boolean>(false);

  return (
    <section id="method" className="py-16 sm:py-24 px-4 sm:px-6 max-w-5xl mx-auto scroll-mt-14">
      {/* Section Header */}
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true }}
        transition={{ duration: 0.4 }}
        className="mb-8"
      >
        <h2 className="text-2xl sm:text-3xl font-bold tracking-tight text-[#E8EAF0]">
          How sure are we?
        </h2>
        <p className="text-sm sm:text-base text-[#8B93A5] mt-2">
          We tested rankings across 150 resamples to check their stability against luck.
        </p>
      </motion.div>

      {/* Chart */}
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true }}
        transition={{ duration: 0.4, delay: 0.1 }}
      >
        <BootstrapChart batters={top10Batters} bowlers={top10Bowlers} />
      </motion.div>

      {/* One Callout Card */}
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true }}
        transition={{ duration: 0.4, delay: 0.15 }}
        className="mt-6 bg-[#12151C] border border-[#232834] rounded-xl p-5 flex items-start gap-3"
      >
        <div className="w-2 h-2 rounded-full bg-[#E6007E] mt-1.5 shrink-0" />
        <p className="text-sm font-medium text-[#E8EAF0] leading-snug">
          Narine is the clearest pick; Sooryavanshi and Klaasen are virtually tied.
        </p>
      </motion.div>

      {/* Collapsed "Method and limitations" Accordion */}
      <div className="mt-8 bg-[#12151C] border border-[#232834] rounded-2xl overflow-hidden">
        <button
          onClick={() => setIsOpen(!isOpen)}
          aria-expanded={isOpen}
          aria-label="Toggle method and limitations section"
          className="w-full p-5 sm:p-6 text-left flex items-center justify-between gap-4 hover:bg-[#181C26] transition-colors cursor-pointer select-none"
        >
          <div>
            <span className="text-sm sm:text-base font-semibold text-[#E8EAF0]">
              Method and limitations
            </span>
            <span className="text-xs text-[#8B93A5] block mt-0.5">
              Data scope, win-probability model, shrinkage, and known constraints.
            </span>
          </div>

          <span
            className={`text-xs font-semibold text-[#8B93A5] transition-transform duration-200 ${
              isOpen ? 'rotate-180 text-[#E6007E]' : ''
            }`}
            aria-hidden="true"
          >
            &darr;
          </span>
        </button>

        <AnimatePresence>
          {isOpen && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: 'auto', opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              transition={{ duration: 0.25 }}
              className="overflow-hidden border-t border-[#232834] divide-y divide-[#232834] text-xs sm:text-sm text-[#8B93A5]"
            >
              {/* Item 1: The Data */}
              <div className="p-5 sm:p-6 space-y-1">
                <span className="font-semibold text-[#E8EAF0] block">1. The Data</span>
                <p className="leading-relaxed">
                  788 matches (357 IPL, 431 T20I, 2022–2026) and 188,151 deliveries.
                </p>
                <p className="leading-relaxed">
                  Missing extras runs are calibrated via regression: wide 1.15, no-ball 1.0 + bat runs, bye 2.1, leg-bye 1.3.
                </p>
              </div>

              {/* Item 2: Win-Probability Model */}
              <div className="p-5 sm:p-6 space-y-1">
                <span className="font-semibold text-[#E8EAF0] block">2. Win-Probability Model</span>
                <p className="leading-relaxed">
                  Cross-fitted by match using logistic regression, achieving 0.402 log-loss in chases (baseline 0.692).
                </p>
              </div>

              {/* Item 3: Pressure Index */}
              <div className="p-5 sm:p-6 space-y-1">
                <span className="font-semibold text-[#E8EAF0] block">3. Pressure Index</span>
                <p className="leading-relaxed">
                  Expected absolute win-probability swing across 9 possible outcomes on the next ball.
                </p>
                <p className="leading-relaxed">
                  High pressure is defined as the top 20% of deliveries within each innings and league.
                </p>
              </div>

              {/* Item 4: Rating & Shrinkage */}
              <div className="p-5 sm:p-6 space-y-1">
                <span className="font-semibold text-[#E8EAF0] block">4. Rating and Shrinkage</span>
                <p className="leading-relaxed">
                  Measures win probability added per 100 high-pressure balls above an average player.
                </p>
                <p className="leading-relaxed">
                  Empirical-Bayes shrinkage (DerSimonian-Laird) pulls small-sample scores toward the league mean.
                </p>
                <p className="leading-relaxed">
                  Top-10 lists were stable under most changes to weights and thresholds.
                </p>
              </div>

              {/* Item 5: Eligibility Floor */}
              <div className="p-5 sm:p-6 space-y-1">
                <span className="font-semibold text-[#E8EAF0] block">5. Eligibility Floor</span>
                <p className="leading-relaxed">
                  At least 100 high-pressure balls, 15 high-pressure innings and 150 normal-situation balls.
                </p>
              </div>

              {/* Item 6: Honest Limitations */}
              <div className="p-5 sm:p-6 space-y-2">
                <span className="font-semibold text-[#E8EAF0] block">6. Limitations</span>
                <ul className="space-y-1 list-disc list-inside">
                  <li>Estimated extras runs: The raw feed lacked exact run breakdowns for extras.</li>
                  <li>No venue or pitch data: Match logs do not record boundary sizes, dew, or turf conditions.</li>
                  <li>Situational pressure only: Evaluates scoreboard leverage, not player biological heart rate.</li>
                  <li>Noisy individual ratings: Single-match clutch ratings have high random variance ($r \approx 0.12$ split-half).</li>
                </ul>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </section>
  );
};

export default MethodologySection;
