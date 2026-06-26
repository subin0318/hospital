import { Activity } from 'lucide-react';

function AppHeader({ activeMode, onModeChange }) {
  return (
    <header className="header">
      <div className="header-logo">
        <Activity size={24} color="#3b82f6" />
        <h1>응급 패스</h1>
        <span className="header-badge">
          {activeMode === 'citizen' ? '시민 모드' : activeMode === 'ambulance' ? '구급대원 모드' : '의료진 모드'}
        </span>
      </div>
      <div className="mode-selectors">
        <button className={`mode-btn ${activeMode === 'citizen' ? 'active' : ''}`} onClick={() => onModeChange('citizen')}>시민 모드</button>
        <button className={`mode-btn ${activeMode === 'ambulance' ? 'active' : ''}`} onClick={() => onModeChange('ambulance')}>구급대원 모드</button>
        <button className={`mode-btn ${activeMode === 'medical' ? 'active' : ''}`} onClick={() => onModeChange('medical')}>의료진 모드</button>
      </div>
    </header>
  );
}

export default AppHeader;
