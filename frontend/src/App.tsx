import React, { useState } from 'react';
import { Navbar } from './components/Navbar';
import { ForecastPage } from './pages/ForecastPage';
import { AccuracyPage } from './pages/AccuracyPage';

export const App: React.FC = () => {
  const [currentTab, setCurrentTab] = useState<'forecast' | 'accuracy'>('forecast');

  return (
    <div className="app-container">
      <Navbar currentTab={currentTab} onTabChange={setCurrentTab} />
      <main className="workspace" id="main-content">
        {currentTab === 'forecast' ? <ForecastPage /> : <AccuracyPage />}
      </main>
    </div>
  );
};

export default App;
