import { useState } from 'react';
import MainLayout from './components/layout/MainLayout';
import Dashboard from './pages/Dashboard';
import StoryMode from './components/story/StoryMode';

function App() {
  const [showDashboard, setShowDashboard] = useState(false);

  return (
    <>
      {!showDashboard ? (
        <StoryMode onLaunch={() => setShowDashboard(true)} />
      ) : (
        <MainLayout>
          <Dashboard />
        </MainLayout>
      )}
    </>
  );
}

export default App;
