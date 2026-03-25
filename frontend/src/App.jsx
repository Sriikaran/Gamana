import { useState } from 'react';
import MainLayout from './components/layout/MainLayout';
import Dashboard from './pages/Dashboard';
import TrafficPage from './pages/TrafficPage';
import SignalsPage from './pages/SignalsPage';
import AlertsPage from './pages/AlertsPage';
import StoryMode from './components/story/StoryMode';

function App() {
  const [activePage, setActivePage] = useState('Dashboard');
  const [showStory, setShowStory] = useState(true);

  if (showStory) {
    return <StoryMode onLaunch={() => setShowStory(false)} />;
  }

  const renderPage = () => {
    switch (activePage) {
      case 'Dashboard':
        return <Dashboard />;
      case 'Traffic':
        return <TrafficPage />;
      case 'Signals':
        return <SignalsPage />;
      case 'Alerts':
        return <AlertsPage />;
      default:
        return <Dashboard />;
    }
  };

  return (
    <MainLayout activePage={activePage} onNavigate={setActivePage}>
      {renderPage()}
    </MainLayout>
  );
}

export default App;
