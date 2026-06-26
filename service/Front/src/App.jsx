import React, { useEffect, useState } from 'react';
import AppHeader from './components/AppHeader';
import MedicalDashboard from './components/MedicalDashboard';
import CitizenAmbulanceDashboard from './components/CitizenAmbulanceDashboard';
import './App.css';

function App() {
  const [activeMode, setActiveMode] = useState('citizen');
  const [transferCases, setTransferCases] = useState(() => {
    try {
      const saved = localStorage.getItem('transferCases');
      return saved ? JSON.parse(saved) : [];
    } catch {
      return [];
    }
  });

  useEffect(() => {
    try {
      localStorage.setItem('transferCases', JSON.stringify(transferCases));
    } catch {
      // localStorage 용량 초과 등 예외 상황은 무시
    }
  }, [transferCases]);

  const handleAddTransferCase = (transferCase) => {
    setTransferCases((prev) => [transferCase, ...prev]);
  };

  const handleAcceptCase = (caseId) => {
    setTransferCases((prev) => prev.map((item) => (
      item.id === caseId ? { ...item, status: 'accepted' } : item
    )));
  };

  const handleClearCases = () => {
    if (window.confirm('이송 기록을 모두 삭제하시겠습니까?')) {
      setTransferCases([]);
    }
  };

  return (
    <div className="dashboard-container">
      <AppHeader activeMode={activeMode} onModeChange={setActiveMode} />

      {activeMode === 'medical' ? (
        <MedicalDashboard
          transferCases={transferCases}
          onAcceptCase={handleAcceptCase}
          onClearCases={handleClearCases}
        />
      ) : (
        <CitizenAmbulanceDashboard
          activeMode={activeMode}
          onAddTransferCase={handleAddTransferCase}
        />
      )}
    </div>
  );
}

export default App;
