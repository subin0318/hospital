import { Locate, MapPin, Search } from 'lucide-react';

function LocationPanel({
  presets,
  activePreset,
  locationQuery,
  locationError,
  selectedRegion,
  onOpenPostcode,
  onPresetClick,
  onGpsClick,
  gpsLoading
}) {
  return (
    <div>
      <h3 className="section-title">
        <span>기점 위치 설정</span>
        <MapPin size={14} />
      </h3>
      <div className="location-search-form" style={{ display: 'flex', gap: '8px', marginBottom: '8px' }}>
        <div className="location-input-wrap" style={{ flex: 1, display: 'flex', alignItems: 'center', background: 'rgba(15, 23, 42, 0.8)', border: '1px solid var(--border-color)', borderRadius: '8px', padding: '0 12px' }}>
          <Search size={14} style={{ color: 'var(--color-text-secondary)', marginRight: '8px' }} />
          <input
            className="location-input"
            style={{ background: 'transparent', border: 'none', color: 'white', outline: 'none', fontSize: '13px', width: '100%', height: '36px' }}
            type="text"
            value={locationQuery}
            readOnly
            placeholder="주소 검색 버튼을 눌러주세요"
          />
        </div>
        <button
          className="btn-primary"
          style={{ padding: '0 14px', height: '38px', whiteSpace: 'nowrap' }}
          onClick={onOpenPostcode}
        >
          주소 검색
        </button>
      </div>
      <button
        className="btn-primary"
        style={{ width: '100%', height: '38px', marginBottom: '12px', background: 'rgba(16,185,129,0.15)', border: '1px solid rgba(16,185,129,0.4)', color: '#10b981', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '6px' }}
        onClick={onGpsClick}
        disabled={gpsLoading}
      >
        {gpsLoading ? (
          <>
            <span className="loading-spinner" style={{ width: '14px', height: '14px', borderColor: 'rgba(16,185,129,0.3)', borderTopColor: '#10b981' }}></span>
            GPS 위치 확인 중...
          </>
        ) : (
          <>
            <Locate size={14} />
            현재 위치 자동 감지
          </>
        )}
      </button>
      {locationError && <div className="location-error">{locationError}</div>}
      {activePreset === 'GPS 현재 위치' && !locationError && (
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '11px', color: '#10b981', background: 'rgba(16,185,129,0.08)', border: '1px solid rgba(16,185,129,0.25)', borderRadius: '6px', padding: '6px 10px', marginBottom: '8px' }}>
          <Locate size={12} />
          <span>GPS 위치 감지됨 — {locationQuery}</span>
        </div>
      )}
      <div className="preset-grid">
        {presets.map((preset) => (
          <button
            key={preset.name}
            className={`preset-btn ${activePreset === preset.name ? 'active' : ''}`}
            onClick={() => onPresetClick(preset)}
          >
            {preset.name}
          </button>
        ))}
      </div>
      {selectedRegion && (
        <div className="coord-display" style={{ marginTop: '6px' }}>
          추천 기준 지역: <span>{selectedRegion}</span>
        </div>
      )}
    </div>
  );
}

export default LocationPanel;
