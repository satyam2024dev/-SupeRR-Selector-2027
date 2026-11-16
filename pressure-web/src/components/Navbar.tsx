import React, { useState, useEffect } from 'react';

export const Navbar: React.FC = () => {
  const [activeSection, setActiveSection] = useState<string>('hero');

  useEffect(() => {
    const handleScroll = () => {
      const sections = ['hero', 'pressure', 'rankings', 'method'];
      const scrollY = window.scrollY + 120;

      for (const id of sections) {
        const el = document.getElementById(id);
        if (el) {
          const top = el.offsetTop;
          const height = el.offsetHeight;
          if (scrollY >= top && scrollY < top + height) {
            setActiveSection(id);
            break;
          }
        }
      }
    };

    window.addEventListener('scroll', handleScroll, { passive: true });
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  const scrollTo = (id: string) => {
    const el = document.getElementById(id);
    if (el) {
      el.scrollIntoView({ behavior: 'smooth' });
    }
  };

  return (
    <header className="sticky top-0 z-40 w-full bg-[#0B0D12]/95 backdrop-blur-sm border-b border-[#232834]">
      <div className="max-w-5xl mx-auto px-4 sm:px-6 h-14 flex items-center justify-between">
        {/* Brand */}
        <button
          onClick={() => scrollTo('hero')}
          className="flex items-center gap-2 text-sm font-semibold text-[#E8EAF0] hover:text-white transition-colors cursor-pointer"
          aria-label="Back to top"
        >
          <span className="w-2 h-2 rounded-full bg-[#E6007E]" />
          <span>SupeRR Selector</span>
        </button>

        {/* 3 Nav Links */}
        <nav className="flex items-center gap-1 sm:gap-2" aria-label="Page navigation">
          <button
            onClick={() => scrollTo('pressure')}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors cursor-pointer ${
              activeSection === 'pressure'
                ? 'text-[#E6007E] bg-[#E6007E]/10'
                : 'text-[#8B93A5] hover:text-[#E8EAF0]'
            }`}
            aria-label="Navigate to Pressure section"
          >
            Pressure
          </button>
          <button
            onClick={() => scrollTo('rankings')}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors cursor-pointer ${
              activeSection === 'rankings'
                ? 'text-[#E6007E] bg-[#E6007E]/10'
                : 'text-[#8B93A5] hover:text-[#E8EAF0]'
            }`}
            aria-label="Navigate to Rankings section"
          >
            Rankings
          </button>
          <button
            onClick={() => scrollTo('method')}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors cursor-pointer ${
              activeSection === 'method'
                ? 'text-[#E6007E] bg-[#E6007E]/10'
                : 'text-[#8B93A5] hover:text-[#E8EAF0]'
            }`}
            aria-label="Navigate to Method section"
          >
            Method
          </button>
        </nav>
      </div>
    </header>
  );
};

export default Navbar;
