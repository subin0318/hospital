import { AlertTriangle, MapPin, Search, Sparkles } from 'lucide-react';
import { formatUpdateStatus } from '../utils';

function RecommendationResults({
  loading,
  isLocationConfirmed,
  isSymptomJudged,
  isLightForced,
  severity,
  recommendationScope,
  hospitals,
  selectedHospital,
  onHospitalSelect,
  getCongestionClass
}) {
  return (
    <div className="results-area">
      <div className="results-header">
        <div className="results-title">
          <Search size={16} color="#3b82f6" />
          <span>{isLightForced || severity === '경증' ? '경증 분산 추천 의료기관' : '도착 시각순 추천 응급의료기관'}</span>
          <span className="results-count">최적 후보 Top 5</span>
        </div>
        <div style={{ fontSize: '11px', color: 'var(--color-text-secondary)' }}>
          {loading
            ? '검색 중...'
            : !isLocationConfirmed
              ? '주소 검색 대기'
              : !isSymptomJudged
                ? '증상 판단 대기'
                : recommendationScope
                  ? `${recommendationScope} 기준 ${hospitals.length}개 기관`
                  : `총 ${hospitals.length}개 기관 분석 완료`}
        </div>
      </div>

      <div className="results-grid">
        {loading ? (
          <div className="empty-state">
            <span className="loading-spinner" style={{ width: '24px', height: '24px', marginBottom: '8px' }}></span>
            <span>최적의 응급 의료 기관 정보를 실시간으로 계산하는 중입니다...</span>
          </div>
        ) : !isLocationConfirmed ? (
          <div className="empty-state">
            <MapPin size={24} color="#3b82f6" style={{ marginBottom: '8px' }} />
            <span>주소 검색으로 출발 위치를 먼저 확정해 주세요.</span>
          </div>
        ) : !isSymptomJudged ? (
          <div className="empty-state">
            <Sparkles size={24} color="#6366f1" style={{ marginBottom: '8px' }} />
            <span>증상을 입력해 AI 판단을 받거나 주요 증상을 선택하면 의료기관을 추천합니다.</span>
          </div>
        ) : hospitals.length > 0 ? (
          hospitals.map((hosp, idx) => {
            const isLightCare = hosp.care_type === 'light';
            const congestion = getCongestionClass(hosp.status);  // 백엔드 status 필드 사용
            const isRegional = !!hosp.is_regional_center;  // 백엔드 API 응답 플래그 사용

            return (
              <div
                key={hosp.hpid}
                className={`hospital-card ${selectedHospital?.hpid === hosp.hpid ? 'selected' : ''}`}
                onClick={() => onHospitalSelect(hosp)}
              >
                <div className="card-top">
                  <span className="hospital-name">
                    [{idx + 1}] {hosp.dutyName}
                  </span>
                  <span className={`hosp-badge ${isRegional ? 'primary-center' : 'general-hosp'}`}>
                    {isLightCare ? (hosp.institution_type || '일반진료') : (isRegional ? '권역센터' : '종합병원')}
                  </span>
                </div>

                <div>
                  <div className="eta-area">
                    <span className="eta-number">
                      {Math.round(hosp.expected_time_minutes)}
                    </span>
                    <span className="eta-unit">분 소요</span>
                    <span className="eta-source">
                      {hosp.eta_source === 'kakao' ? '카카오내비' : '직선거리'}
                    </span>
                  </div>

                  {isLightCare ? (
                    <>
                      <div className="info-row">
                        <span>기관 유형:</span>
                        <span className="info-value">{hosp.institution_type || '의료기관'}</span>
                      </div>
                      <div className="info-row">
                        <span>우선 진료:</span>
                        <span className="info-value">{hosp.department || '일반 진료'}</span>
                      </div>
                      <div className="info-row" style={{ fontSize: '11px', marginTop: '4px', color: 'var(--color-text-secondary)' }}>
                        <span>직선 거리:</span>
                        <span>{hosp.distance_km}km</span>
                      </div>
                    </>
                  ) : (
                    <>
                      <div className="info-row">
                        <span>응급실 병상:</span>
                        <span className="info-value">{hosp.hvec}개 가용</span>
                      </div>

                      <div className="info-row">
                        <span>도착 시 혼잡도:</span>
                        <span className={`signal-indicator ${congestion.style}`}>
                          <span className={`signal-dot ${congestion.style}`}></span>
                          {congestion.label}
                        </span>
                      </div>

                      <div className="info-row" style={{ fontSize: '11px', marginTop: '4px', color: 'var(--color-text-secondary)' }}>
                        <span>소재지:</span>
                        <span>{hosp.region_label || '전라남도'}</span>
                      </div>
                      <div className="info-row" style={{ fontSize: '11px', color: 'var(--color-text-secondary)' }}>
                        <span>정보 갱신:</span>
                        <span>{formatUpdateStatus(hosp.hvidate)}</span>
                      </div>
                    </>
                  )}
                </div>

                {hosp.acceptance_checks && hosp.acceptance_checks.length > 0 && (
                  <div className="checklist-box">
                    {hosp.acceptance_checks.map((check, cIdx) => (
                      <span
                        key={cIdx}
                        className={`checklist-badge ${check.status}`}
                        title={check.message}
                      >
                        {check.symptom}: {check.value === 'Y' ? '수용' : check.value === '불가능' ? '불가' : '확인요망'}
                      </span>
                    ))}
                  </div>
                )}

                <div className="recommend-reason-box">
                  {hosp.recommend_reason}
                </div>

                <button
                  type="button"
                  className="btn-secondary card-detail-btn"
                  onClick={(event) => {
                    event.stopPropagation();
                    onHospitalSelect(hosp);
                  }}
                >
                  상세 보기
                </button>
              </div>
            );
          })
        ) : (
          <div className="empty-state">
            <AlertTriangle size={24} color="#f59e0b" style={{ marginBottom: '8px' }} />
            <span>조건에 부합하는 수용 가능한 응급 병원이 없습니다. 증상을 조절하거나 인근 다른 기점을 선택해 주세요.</span>
          </div>
        )}
      </div>
    </div>
  );
}

export default RecommendationResults;
