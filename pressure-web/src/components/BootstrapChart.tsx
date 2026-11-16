import React, { useState } from 'react';
import { Player, RoleType } from '../types';

interface BootstrapChartProps {
  batters: Player[];
  bowlers: Player[];
}

export const BootstrapChart: React.FC<BootstrapChartProps> = ({ batters, bowlers }) => {
  const [activeRole, setActiveRole] = useState<RoleType>('batters');
  const players = activeRole === 'batters' ? batters : bowlers;

  const maxRank = 22;
  const chartHeight = 320;
  const paddingLeft = 140;
  const paddingRight = 30;
  const paddingTop = 25;
  const paddingBottom = 35;
  const rowHeight = (chartHeight - paddingTop - paddingBottom) / players.length;

  const rankToX = (rank: number, width: number) => {
    const usableWidth = width - paddingLeft - paddingRight;
    const clamped = Math.max(1, Math.min(rank, maxRank));
    return paddingLeft + ((clamped - 1) / (maxRank - 1)) * usableWidth;
  };

  return (
    <div className="bg-[#12151C] border border-[#232834] rounded-2xl p-6 sm:p-8">
      {/* Role Switcher */}
      <div className="flex items-center justify-between gap-4 mb-6">
        <span className="text-xs font-semibold text-[#8B93A5] uppercase tracking-wider">
          Rank Range in 150 Resamples
        </span>

        <div className="inline-flex p-1 bg-[#0B0D12] border border-[#232834] rounded-xl" role="tablist" aria-label="Bootstrap chart role switch">
          <button
            role="tab"
            aria-selected={activeRole === 'batters'}
            onClick={() => setActiveRole('batters')}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-colors cursor-pointer ${
              activeRole === 'batters'
                ? 'bg-[#E6007E] text-white'
                : 'text-[#8B93A5] hover:text-[#E8EAF0]'
            }`}
            aria-label="Show rank ranges for batters"
          >
            Batters
          </button>
          <button
            role="tab"
            aria-selected={activeRole === 'bowlers'}
            onClick={() => setActiveRole('bowlers')}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-colors cursor-pointer ${
              activeRole === 'bowlers'
                ? 'bg-[#E6007E] text-white'
                : 'text-[#8B93A5] hover:text-[#E8EAF0]'
            }`}
            aria-label="Show rank ranges for bowlers"
          >
            Bowlers
          </button>
        </div>
      </div>

      {/* SVG Visualization */}
      <div className="w-full overflow-x-auto">
        <svg
          viewBox={`0 0 650 ${chartHeight}`}
          className="w-full min-w-[500px] h-auto select-none"
          role="img"
          aria-label={`Bootstrap rank stability chart showing median rank and 80% range for top 10 ${activeRole} across 150 resamples`}
        >
          {/* Rank Grid Lines */}
          {[1, 5, 10, 15, 20].map((r) => {
            const x = rankToX(r, 650);
            const isCutoff = r === 10;
            return (
              <g key={r}>
                <line
                  x1={x}
                  y1={paddingTop - 5}
                  x2={x}
                  y2={chartHeight - paddingBottom + 5}
                  stroke={isCutoff ? '#E6007E' : '#232834'}
                  strokeWidth={isCutoff ? 1.5 : 1}
                  strokeDasharray={isCutoff ? '3 3' : 'none'}
                />
                <text
                  x={x}
                  y={chartHeight - paddingBottom + 20}
                  textAnchor="middle"
                  className={`text-[11px] tabular-nums font-medium ${
                    isCutoff ? 'fill-[#E6007E] font-semibold' : 'fill-[#5A6275]'
                  }`}
                >
                  Rank {r}
                </text>
              </g>
            );
          })}

          {/* Top 10 Cutoff Label */}
          <text
            x={rankToX(10, 650)}
            y={paddingTop - 10}
            textAnchor="middle"
            className="text-[10px] uppercase font-semibold tracking-wider fill-[#E6007E]"
          >
            Top 10 cutoff
          </text>

          {/* Players */}
          {players.map((p, idx) => {
            const y = paddingTop + idx * rowHeight + rowHeight / 2;
            const xLow = rankToX(p.bootLow, 650);
            const xMed = rankToX(p.bootMedian, 650);
            const xHigh = rankToX(p.bootHigh, 650);

            return (
              <g key={p.name}>
                {/* Player Name */}
                <text
                  x={paddingLeft - 12}
                  y={y + 4}
                  textAnchor="end"
                  className="text-xs font-medium fill-[#E8EAF0]"
                >
                  #{p.rank} {p.name}
                </text>

                {/* Range Line */}
                <line
                  x1={xLow}
                  y1={y}
                  x2={xHigh}
                  y2={y}
                  stroke="#E6007E"
                  strokeWidth={2}
                  strokeLinecap="round"
                  strokeOpacity={0.7}
                />

                {/* Whisker caps */}
                <line x1={xLow} y1={y - 3} x2={xLow} y2={y + 3} stroke="#E6007E" strokeWidth={1.5} />
                <line x1={xHigh} y1={y - 3} x2={xHigh} y2={y + 3} stroke="#E6007E" strokeWidth={1.5} />

                {/* Median Dot */}
                <circle
                  cx={xMed}
                  cy={y}
                  r={4}
                  fill="#E6007E"
                  stroke="#12151C"
                  strokeWidth={1.5}
                />

                {/* Score badge on the right */}
                <text
                  x={640}
                  y={y + 4}
                  textAnchor="end"
                  className="text-[11px] font-mono tabular-nums fill-[#8B93A5]"
                >
                  {p.pTop10 >= 0.8 ? '90%+' : `${Math.round(p.pTop10 * 100)}%`} top 10
                </text>
              </g>
            );
          })}
        </svg>
      </div>

      {/* Legend */}
      <div className="mt-4 pt-4 border-t border-[#232834] flex flex-wrap items-center justify-between gap-4 text-xs text-[#8B93A5]">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-[#E6007E]" />
            <span>Median simulated rank</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-4 h-0.5 bg-[#E6007E]" />
            <span>80% range</span>
          </div>
        </div>
        <div className="text-[11px] text-[#5A6275]">
          Bootstrap resamples: 150 matches with replacement
        </div>
      </div>
    </div>
  );
};

export default BootstrapChart;
