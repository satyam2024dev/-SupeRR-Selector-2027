import React, { useState } from 'react';
import { motion } from 'framer-motion';

export const ChaseSimulator: React.FC = () => {
  const [runsNeeded, setRunsNeeded] = useState<number>(36);
  const [ballsLeft, setBallsLeft] = useState<number>(24);
  const [wicketsLost, setWicketsLost] = useState<number>(4);

  // Preset handler
  const setPreset = (type: 'easy' | 'tight' | 'last') => {
    if (type === 'easy') {
      setRunsNeeded(24);
      setBallsLeft(30);
      setWicketsLost(2);
    } else if (type === 'tight') {
      setRunsNeeded(36);
      setBallsLeft(24);
      setWicketsLost(4);
    } else {
      setRunsNeeded(14);
      setBallsLeft(6);
      setWicketsLost(6);
    }
  };

  // Logistic Win Probability approximation (already verified)
  const computeWP = (runs: number, balls: number, wkts: number): number => {
    if (runs <= 0) return 1.0;
    if (balls <= 0 || wkts >= 10) return 0.0;
    const reqRate = (runs / balls) * 6.0;
    const z = 4.2 - 0.40 * reqRate - 0.35 * wkts + 0.02 * balls;
    const prob = 1.0 / (1.0 + Math.exp(-z));
    return Math.min(0.99, Math.max(0.01, prob));
  };

  const wp = computeWP(runsNeeded, ballsLeft, wicketsLost);
  const winPercent = Math.round(wp * 100);

  // Pressure Index calculation
  const uncertainty = 4.0 * wp * (1.0 - wp);
  const urgency = 1.0 + 30.0 / Math.max(ballsLeft, 6);
  const pressureValue = 0.75 + 1.25 * uncertainty * urgency;

  // Pressure label
  const getTension = () => {
    if (ballsLeft <= 12 || pressureValue >= 2.6) {
      return { label: 'Knife edge', color: 'text-[#E6007E] bg-[#E6007E]/10 border-[#E6007E]/30' };
    }
    if (winPercent >= 75 && pressureValue < 1.8) {
      return { label: 'Calm', color: 'text-emerald-400 bg-emerald-400/10 border-emerald-400/30' };
    }
    return { label: 'Tense', color: 'text-amber-400 bg-amber-400/10 border-amber-400/30' };
  };

  const tension = getTension();
  const reqRunRate = ballsLeft > 0 ? ((runsNeeded / ballsLeft) * 6).toFixed(1) : '99.9';

  const isPresetActive = (runs: number, balls: number, wkts: number) =>
    runsNeeded === runs && ballsLeft === balls && wicketsLost === wkts;

  return (
    <section id="pressure" className="py-16 sm:py-24 px-4 sm:px-6 max-w-5xl mx-auto scroll-mt-14">
      {/* Section Header */}
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true }}
        transition={{ duration: 0.4 }}
        className="mb-8"
      >
        <h2 className="text-2xl sm:text-3xl font-bold tracking-tight text-[#E8EAF0]">
          Feel the pressure
        </h2>
        <p className="text-sm sm:text-base text-[#8B93A5] mt-2">
          See how runs needed, balls left, and wickets swing win probability and tension in a chase.
        </p>
      </motion.div>

      {/* Simulator Card */}
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true }}
        transition={{ duration: 0.4, delay: 0.1 }}
        className="bg-[#12151C] border border-[#232834] rounded-2xl p-6 sm:p-8"
      >
        {/* Presets and Illustrative Tag */}
        <div className="flex flex-wrap items-center justify-between gap-4 pb-6 border-b border-[#232834]">
          <div className="flex items-center gap-2">
            <span className="text-xs text-[#8B93A5] font-medium mr-1">Presets:</span>
            <button
              onClick={() => setPreset('easy')}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors cursor-pointer ${
                isPresetActive(24, 30, 2)
                  ? 'bg-[#E6007E] text-white'
                  : 'bg-[#1C212B] text-[#E8EAF0] hover:bg-[#232834]'
              }`}
              aria-label="Set Easy chase scenario (24 runs, 30 balls, 2 wickets)"
            >
              Easy chase
            </button>
            <button
              onClick={() => setPreset('tight')}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors cursor-pointer ${
                isPresetActive(36, 24, 4)
                  ? 'bg-[#E6007E] text-white'
                  : 'bg-[#1C212B] text-[#E8EAF0] hover:bg-[#232834]'
              }`}
              aria-label="Set Tight finish scenario (36 runs, 24 balls, 4 wickets)"
            >
              Tight finish
            </button>
            <button
              onClick={() => setPreset('last')}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors cursor-pointer ${
                isPresetActive(14, 6, 6)
                  ? 'bg-[#E6007E] text-white'
                  : 'bg-[#1C212B] text-[#E8EAF0] hover:bg-[#232834]'
              }`}
              aria-label="Set Last over scenario (14 runs, 6 balls, 6 wickets)"
            >
              Last over
            </button>
          </div>

          <span className="text-[11px] font-medium px-2.5 py-1 rounded bg-[#1C212B] text-[#8B93A5] border border-[#232834]">
            Illustrative
          </span>
        </div>

        {/* Sliders & Readout Grid */}
        <div className="grid grid-cols-1 md:grid-cols-12 gap-8 items-center pt-6">
          {/* Sliders (7 cols) */}
          <div className="md:col-span-7 space-y-6">
            {/* Slider 1: Runs Needed */}
            <div>
              <div className="flex justify-between items-center text-xs mb-2">
                <label htmlFor="runs-slider" className="text-[#8B93A5] font-medium cursor-pointer">
                  Runs needed
                </label>
                <span className="text-sm font-semibold text-[#E8EAF0] tabular-nums">
                  {runsNeeded} runs
                </span>
              </div>
              <input
                id="runs-slider"
                type="range"
                min="1"
                max="100"
                value={runsNeeded}
                onChange={(e) => setRunsNeeded(Number(e.target.value))}
                className="w-full h-1.5 bg-[#232834] rounded-lg appearance-none cursor-pointer accent-[#E6007E]"
                aria-label="Runs needed"
                aria-valuemin={1}
                aria-valuemax={100}
                aria-valuenow={runsNeeded}
              />
              <div className="flex justify-between text-[11px] text-[#5A6275] mt-1 tabular-nums">
                <span>1</span>
                <span>50</span>
                <span>100</span>
              </div>
            </div>

            {/* Slider 2: Balls Left */}
            <div>
              <div className="flex justify-between items-center text-xs mb-2">
                <label htmlFor="balls-slider" className="text-[#8B93A5] font-medium cursor-pointer">
                  Balls left
                </label>
                <span className="text-sm font-semibold text-[#E8EAF0] tabular-nums">
                  {ballsLeft} balls ({Math.floor(ballsLeft / 6)}.{ballsLeft % 6} ov)
                </span>
              </div>
              <input
                id="balls-slider"
                type="range"
                min="1"
                max="60"
                value={ballsLeft}
                onChange={(e) => setBallsLeft(Number(e.target.value))}
                className="w-full h-1.5 bg-[#232834] rounded-lg appearance-none cursor-pointer accent-[#E6007E]"
                aria-label="Balls left"
                aria-valuemin={1}
                aria-valuemax={60}
                aria-valuenow={ballsLeft}
              />
              <div className="flex justify-between text-[11px] text-[#5A6275] mt-1 tabular-nums">
                <span>1</span>
                <span>30</span>
                <span>60</span>
              </div>
            </div>

            {/* Slider 3: Wickets Lost */}
            <div>
              <div className="flex justify-between items-center text-xs mb-2">
                <label htmlFor="wickets-slider" className="text-[#8B93A5] font-medium cursor-pointer">
                  Wickets lost
                </label>
                <span className="text-sm font-semibold text-[#E8EAF0] tabular-nums">
                  {wicketsLost} / 10
                </span>
              </div>
              <input
                id="wickets-slider"
                type="range"
                min="0"
                max="9"
                value={wicketsLost}
                onChange={(e) => setWicketsLost(Number(e.target.value))}
                className="w-full h-1.5 bg-[#232834] rounded-lg appearance-none cursor-pointer accent-[#E6007E]"
                aria-label="Wickets lost"
                aria-valuemin={0}
                aria-valuemax={9}
                aria-valuenow={wicketsLost}
              />
              <div className="flex justify-between text-[11px] text-[#5A6275] mt-1 tabular-nums">
                <span>0 (cruising)</span>
                <span>5</span>
                <span>9 (last pair)</span>
              </div>
            </div>
          </div>

          {/* Big Live Readout (5 cols) */}
          <div className="md:col-span-5 bg-[#0B0D12] border border-[#232834] rounded-xl p-6 text-center space-y-4">
            <div>
              <div className="text-xs text-[#8B93A5] font-medium">Chasing win chance</div>
              <div className="text-5xl sm:text-6xl font-bold text-[#E8EAF0] tabular-nums tracking-tight mt-1">
                {winPercent}%
              </div>
            </div>

            {/* Win Chance Progress Bar */}
            <div className="w-full h-2 bg-[#232834] rounded-full overflow-hidden" role="progressbar" aria-valuenow={winPercent} aria-valuemin={0} aria-valuemax={100} aria-label="Chasing win chance">
              <div
                className="h-full bg-[#E6007E] transition-all duration-200"
                style={{ width: `${winPercent}%` }}
              />
            </div>

            {/* Tension Badge & Req Rate */}
            <div className="flex items-center justify-between pt-2 border-t border-[#232834] text-xs">
              <span className="text-[#8B93A5]">
                Req Rate: <strong className="text-[#E8EAF0] tabular-nums">{reqRunRate}</strong>
              </span>

              <span
                className={`px-2.5 py-0.5 rounded-full text-xs font-semibold border ${tension.color}`}
              >
                {tension.label}
              </span>
            </div>
          </div>
        </div>
      </motion.div>
    </section>
  );
};

export default ChaseSimulator;
