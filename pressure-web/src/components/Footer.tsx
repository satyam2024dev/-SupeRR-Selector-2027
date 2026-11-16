import React from 'react';

export const Footer: React.FC = () => {
  return (
    <footer className="border-t border-[#232834] bg-[#0B0D12] py-12 px-4 sm:px-6">
      <div className="max-w-5xl mx-auto flex flex-col sm:flex-row items-start sm:items-center justify-between gap-6 text-xs text-[#8B93A5]">
        {/* Credits and Context */}
        <div className="space-y-1">
          <div className="font-medium text-[#E8EAF0]">
            SupeRR Selector Season 2, Round 1 submission &bull; Rajasthan Royals
          </div>
          <div>Built with data from 788 IPL and T20I matches.</div>
        </div>

        {/* Links */}
        <div className="flex items-center gap-4 flex-wrap">
          <a
            href="/report.pdf"
            download="Rajasthan_Royals_SupeRR_Selector_Report.pdf"
            className="hover:text-[#E8EAF0] transition-colors underline underline-offset-4"
          >
            Download report (PDF)
          </a>

          <a
            href="/ranking_batters_all_eligible.csv"
            download="ranking_batters_all_eligible.csv"
            className="hover:text-[#E8EAF0] transition-colors underline underline-offset-4"
          >
            Download batters (CSV)
          </a>

          <a
            href="/ranking_bowlers_all_eligible.csv"
            download="ranking_bowlers_all_eligible.csv"
            className="hover:text-[#E8EAF0] transition-colors underline underline-offset-4"
          >
            Download bowlers (CSV)
          </a>
        </div>
      </div>
    </footer>
  );
};

export default Footer;
