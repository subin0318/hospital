import { Phone, X } from 'lucide-react';
import { formatUpdateStatus } from '../utils';

function HospitalDetailModal({ selectedHospital, isOpen, onClose, activeMode = 'citizen', onTransfer, onScenarioNotice }) {
  if (!isOpen || !selectedHospital) return null;

  return (
    <div className="hospital-detail-modal-overlay" onClick={onClose}>
      <div className="hospital-detail-modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div className="modal-title">
            {selectedHospital.dutyName}
            <div style={{ fontSize: '11px', color: 'var(--color-text-secondary)', marginTop: '4px', fontWeight: '400' }}>
              {selectedHospital.dutyAddr}
            </div>
          </div>
          <button className="btn-close" onClick={onClose}>
            <X size={20} />
          </button>
        </div>

        <div className="modal-section">
          <div className="modal-section-title">추천 최적화 결과</div>
          <div className="modal-reason">
            {selectedHospital.recommend_reason}
          </div>
        </div>

        {selectedHospital.care_type === 'light' ? (
          <div className="modal-section">
            <div className="modal-section-title">경증 분산 안내 정보</div>
            <div className="modal-grid-2">
              <div className="modal-info-item">
                <span className="modal-info-label">기관 유형</span>
                <span className="modal-info-value">{selectedHospital.institution_type || '의료기관'}</span>
              </div>
              <div className="modal-info-item">
                <span className="modal-info-label">우선 진료</span>
                <span className="modal-info-value">{selectedHospital.department || '일반 진료'}</span>
              </div>
              <div className="modal-info-item">
                <span className="modal-info-label">거리</span>
                <span className="modal-info-value">{selectedHospital.distance_km}km</span>
              </div>
              <div className="modal-info-item">
                <span className="modal-info-label">예상 소요</span>
                <span className="modal-info-value">{Math.round(selectedHospital.expected_time_minutes)}분</span>
              </div>
            </div>
          </div>
        ) : (
          <>
            <div className="modal-section">
              <div className="modal-section-title" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span>가용 병상 정보</span>
                <span style={{ fontSize: '11px', fontWeight: 'normal', color: 'var(--color-text-secondary)' }}>
                  갱신시각: {formatUpdateStatus(selectedHospital.hvidate)}
                </span>
              </div>
              <div className="modal-grid-2">
                <div className="modal-info-item">
                  <span className="modal-info-label">일반 응급실 가용 병상</span>
                  <span className="modal-info-value" style={{ color: selectedHospital.status !== '혼잡' ? 'var(--color-success)' : 'var(--color-danger)' }}>
                    {selectedHospital.hvec}개
                  </span>
                </div>
                <div className="modal-info-item">
                  <span className="modal-info-label">일반 중환자실 (ICU)</span>
                  <span className="modal-info-value">{selectedHospital.hvicc || 0}개</span>
                </div>
                <div className="modal-info-item">
                  <span className="modal-info-label">소아 중환자실</span>
                  <span className="modal-info-value">{selectedHospital.hvcc || 0}개</span>
                </div>
                <div className="modal-info-item">
                  <span className="modal-info-label">신생아 중환자실</span>
                  <span className="modal-info-value">{selectedHospital.hvncc || 0}개</span>
                </div>
              </div>
            </div>

            <div className="modal-section">
              <div className="modal-section-title">의료 장비 상태</div>
              <div className="modal-grid-2">
                <div className="modal-info-item">
                  <span className="modal-info-label">CT 가능 여부</span>
                  <span className="modal-info-value">{selectedHospital.hvctayn || '정보없음'}</span>
                </div>
                <div className="modal-info-item">
                  <span className="modal-info-label">MRI 가능 여부</span>
                  <span className="modal-info-value">{selectedHospital.hvmriayn || '정보없음'}</span>
                </div>
                <div className="modal-info-item">
                  <span className="modal-info-label">조영촬영기(Angio)</span>
                  <span className="modal-info-value">{selectedHospital.hvangioayn || '정보없음'}</span>
                </div>
                <div className="modal-info-item">
                  <span className="modal-info-label">인공호흡기</span>
                  <span className="modal-info-value">{selectedHospital.hvventiayn || '정보없음'}</span>
                </div>
              </div>
            </div>
          </>
        )}

        <div className="modal-section">
          <div className="modal-section-title">기관 연락처</div>
          {(() => {
            const tel = selectedHospital.dutyTel3 || selectedHospital.dutyTel1;
            return tel ? (
              <a href={`tel:${tel}`} style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--color-primary)', fontWeight: '700', fontSize: '14px', textDecoration: 'none' }}>
                <Phone size={16} />
                <span>응급실 직통: {tel}</span>
              </a>
            ) : (
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--color-primary)', fontWeight: '700', fontSize: '14px' }}>
                <Phone size={16} />
                <span>연락처 정보없음</span>
              </div>
            );
          })()}
        </div>

        <div className="modal-footer">
          <button className="btn-secondary" onClick={onClose}>닫기</button>
          <button
            className="btn-primary"
            onClick={() => {
              if (activeMode === 'ambulance' && onTransfer) {
                onTransfer(selectedHospital);
              } else {
                onScenarioNotice?.(`${selectedHospital.dutyName}으로 이송 대기 통보 및 경로 안내 시나리오를 확인했습니다. 실제 응급의료정보망 연동은 향후 확장 예정입니다.`);
              }
              onClose();
            }}
          >
            {activeMode === 'ambulance' ? '이송 통보 생성' : '이송 통보 시나리오 확인'}
          </button>
        </div>
      </div>
    </div>
  );
}

export default HospitalDetailModal;
