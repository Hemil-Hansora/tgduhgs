import React from 'react';

interface NavbarProps {
  currentTab: 'forecast' | 'accuracy';
  onTabChange: (tab: 'forecast' | 'accuracy') => void;
}

export const Navbar: React.FC<NavbarProps> = ({ currentTab, onTabChange }) => {
  return (
    <header className="navbar" role="banner">
      <div className="brand">
        <div className="brand-mark" aria-hidden="true">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M9.59 4.59A2 2 0 1 1 11 8H2m10.59 11.41A2 2 0 1 0 14 16H2m15.73-8.27A2.5 2.5 0 1 1 19.5 12H2" />
          </svg>
        </div>
        <div className="brand-text">
          <span className="brand-name">Wind Forecast Monitor</span>
          <span className="brand-sub">Day-Ahead Buying Desk · Elexon BMRS</span>
        </div>
      </div>

      <nav className="nav" aria-label="Main">
        <button
          type="button"
          className={`nav-btn ${currentTab === 'forecast' ? 'is-active' : ''}`}
          onClick={() => onTabChange('forecast')}
          aria-current={currentTab === 'forecast' ? 'page' : undefined}
        >
          Forecast view
        </button>

        <button
          type="button"
          className={`nav-btn ${currentTab === 'accuracy' ? 'is-active' : ''}`}
          onClick={() => onTabChange('accuracy')}
          aria-current={currentTab === 'accuracy' ? 'page' : undefined}
        >
          Accuracy view
        </button>
      </nav>
    </header>
  );
};
