import { AlertTriangle, Info } from 'lucide-react';

const RED_FLAG_SYMPTOMS = [
  '의식을 잃거나 깨우기 힘든 경우',
  '갑자기 숨이 차거나 청색증이 나타나는 경우',
  '한쪽 팔·다리에 힘이 빠지거나 말이 어눌한 경우',
  '가슴이 심하게 조여들거나 식은땀이 동반되는 경우',
  '심한 출혈이 멈추지 않거나 사지 절단 상황',
];

function RoutingFilterPanel({
  aiSeverity,
  careRoute,
  routeReason,
  isLightForced,
  isLocationConfirmed,
  isSymptomJudged,
  selectedSymptoms,
  onLightForcedChange,
  onFetchRecommendations
}) {
  const routeLabel = careRoute === 'general'
    ? '일반 의료기관 우선 안내'
    : careRoute === 'call_first'
      ? '전화 확인 우선 권장'
      : '응급실 우선 확인 필요';

  return (
    <div className="form-group">
      <h3 className="section-title">
        <span>라우팅 최적화 필터</span>
      </h3>

      <div className="toggle-switch-container">
        <div className="toggle-label">
          <span className="toggle-title">경증 환자 사전 분산</span>
          <span className="toggle-desc">대형 병원 대신 인근 종합병원 유도</span>
        </div>
        <label className="switch">
          <input
            type="checkbox"
            checked={isLightForced}
            onChange={(e) => {
              const nextLightForced = e.target.checked;
              onLightForcedChange(nextLightForced);
              if (isLocationConfirmed && isSymptomJudged) {
                onFetchRecommendations(selectedSymptoms, nextLightForced ? '경증' : aiSeverity);
              }
            }}
          />
          <span className="slider"></span>
        </label>
      </div>

      <div style={{ fontSize: '11px', color: 'var(--color-text-secondary)', display: 'flex', gap: '6px', alignItems: 'center', background: 'rgba(30,41,59,0.3)', padding: '8px', borderRadius: '6px', border: '1px solid var(--border-color)' }}>
        <Info size={14} color="#3b82f6" style={{ flexShrink: 0 }} />
        <span>
          AI 안내 분류: <strong>{routeLabel}</strong> | 적용: <strong>{isLightForced ? '경증 분산' : aiSeverity}</strong>
        </span>
      </div>
      {routeReason && (
        <div style={{ marginTop: '8px', fontSize: '11px', color: 'var(--color-text-secondary)', lineHeight: '1.45' }}>
          {routeReason}
        </div>
      )}

      {isSymptomJudged && (isLightForced || careRoute === 'general') && (
        <div style={{ marginTop: '10px', background: 'rgba(245,158,11,0.08)', border: '1px solid rgba(245,158,11,0.35)', borderRadius: '8px', padding: '10px 12px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '11px', fontWeight: '700', color: '#fbbf24', marginBottom: '7px' }}>
            <AlertTriangle size={13} />
            <span>경증 분류이더라도 아래 증상이 있다면 즉시 119에 전화하세요</span>
          </div>
          <ul style={{ margin: 0, paddingLeft: '15px', fontSize: '11px', color: 'var(--color-text-secondary)', lineHeight: '1.75' }}>
            {RED_FLAG_SYMPTOMS.map(s => <li key={s}>{s}</li>)}
          </ul>
        </div>
      )}
    </div>
  );
}

export default RoutingFilterPanel;
