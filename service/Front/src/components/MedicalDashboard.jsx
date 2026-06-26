import React, { useEffect, useState } from 'react';
import { AlertTriangle, CheckCircle2, Clock, Phone, Trash2 } from 'lucide-react';

const buildChecklist = (transferCase) => {
  const symptoms = transferCase.symptoms || [];
  const items = ['응급실 병상 확인', '담당 의료진 호출', '도착 후 분류 준비', '구급대원 연락 채널 확인'];

  if (symptoms.includes('소아')) {
    items.push('소아 진료 가능 인력 확인');
  }
  if (symptoms.includes('화상')) {
    items.push('화상 처치 물품 준비');
  }
  if (symptoms.includes('뇌졸중')) {
    items.push('뇌졸중 처치 프로토콜 및 영상검사 준비');
  }
  if (symptoms.includes('흉통') || symptoms.includes('심근경색')) {
    items.push('심전도 및 심혈관 처치 준비');
  }
  if (symptoms.includes('복부손상') || symptoms.includes('사지접합')) {
    items.push('외상 처치 장비 확인');
  }

  return items;
};

function MedicalDashboard({ transferCases, onAcceptCase, onClearCases }) {
  const [now, setNow] = useState(new Date());
  const acceptedCases = transferCases.filter((item) => item.status === 'accepted');
  const acceptedByHospital = acceptedCases.reduce((groups, item) => {
    const key = item.hospital.hpid || item.hospital.dutyName;
    if (!groups[key]) {
      groups[key] = {
        hospital: item.hospital,
        cases: []
      };
    }
    groups[key].cases.push(item);
    return groups;
  }, {});

  useEffect(() => {
    const timer = setInterval(() => {
      setNow(new Date());
    }, 10000); // 10초마다 갱신
    return () => clearInterval(timer);
  }, []);

  return (
    <main className="medical-content">
      <div className="medical-header">
        <div>
          <h2>의료진 수신 대시보드</h2>
          <p>구급대원이 생성한 이송 정보 공유 시나리오를 확인합니다.</p>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <span className="results-count">수신 {transferCases.length}건</span>
          {transferCases.length > 0 && (
            <button
              onClick={onClearCases}
              style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '11px', color: '#ef4444', background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.3)', borderRadius: '6px', padding: '4px 10px', cursor: 'pointer' }}
            >
              <Trash2 size={12} /> 기록 전체 삭제
            </button>
          )}
        </div>
      </div>

      {transferCases.length === 0 ? (
        <div className="empty-state medical-empty">
          <AlertTriangle size={24} color="#f59e0b" style={{ marginBottom: '8px' }} />
          <span>아직 수신된 이송 정보가 없습니다. 구급대원 모드에서 이송 통보를 생성해 주세요.</span>
        </div>
      ) : (
        <>
          {acceptedCases.length > 0 && (
            <section className="intake-board">
              <div className="intake-board-header">
                <div>
                  <h3>병원별 수용 확정 환자</h3>
                  <p>수용 확정을 누른 이송 건이 병원 단위 카드로 표시됩니다.</p>
                </div>
                <span className="results-count">확정 {acceptedCases.length}건</span>
              </div>
              <div className="intake-board-grid">
                {Object.values(acceptedByHospital).map(({ hospital, cases }) => (
                  <div className="intake-hospital-card" key={hospital.hpid || hospital.dutyName}>
                    <div className="intake-hospital-title">
                      <span>{hospital.dutyName}</span>
                      <span className="hosp-badge general-hosp">{cases.length}명 수용 중</span>
                    </div>
                    <div className="active-patient-list">
                      {cases.map((item) => (
                        <div className="active-patient-card" key={item.id}>
                          <div className="active-patient-main">
                            <strong>{item.patient.age || '미상'}세 / {item.patient.gender || '미상'}</strong>
                            <span>{item.patient.consciousness || '의식 미확인'} · {item.patient.breathing || '호흡 미확인'}</span>
                          </div>
                          <div className="active-patient-sub">
                            <span>{item.symptoms?.length ? item.symptoms.join(', ') : '증상 미분류'}</span>
                            <span>{item.location?.region || item.location?.label || '위치 미확인'}</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </section>
          )}

          <div className="medical-grid">
            {transferCases.map((item) => {
              const checklist = buildChecklist(item);

              return (
                <div className="medical-card" key={item.id}>
                <div className="card-top">
                  <span className="hospital-name">{item.hospital.dutyName}</span>
                  <span className={`hosp-badge ${item.status === 'accepted' ? 'general-hosp' : 'primary-center'}`}>
                    {item.status === 'accepted' ? '수용 확정' : '수신 대기'}
                  </span>
                </div>

                <div className="medical-meta">
                  {(() => {
                    const expectedMin = item.hospital.expected_time_minutes;
                    const createdAtTime = new Date(item.createdAt);
                    const elapsedMinutes = (now - createdAtTime) / 60000;
                    const remainingMinutes = Math.max(0, Math.round(expectedMin - elapsedMinutes));

                    return (
                      <span className="arrival-chip">
                        <Clock size={14} />
                        <span>{Math.round(expectedMin)}분 ETA</span>
                        {remainingMinutes > 0 ? (
                          <strong className="arrival-chip-danger" title="경과 시간에 따라 실시간 계산된 남은 시간입니다.">
                            잔여 {remainingMinutes}분
                          </strong>
                        ) : (
                          <strong className="arrival-chip-success" title="예상 도착 시간이 경과했습니다.">
                            도착 예정
                          </strong>
                        )}
                      </span>
                    );
                  })()}
                  {(() => { const tel = item.hospital.dutyTel3 || item.hospital.dutyTel1; return tel ? <a href={`tel:${tel}`} style={{ color: 'inherit', textDecoration: 'none', display: 'flex', alignItems: 'center', gap: '4px' }}><Phone size={14} /> {tel}</a> : <span><Phone size={14} /> 연락처 정보없음</span>; })()}
                </div>

                <div className="modal-grid-2">
                  <div className="modal-info-item">
                    <span className="modal-info-label">환자</span>
                    <span className="modal-info-value">{item.patient.age || '미상'}세 / {item.patient.gender || '미상'}</span>
                  </div>
                  <div className="modal-info-item">
                    <span className="modal-info-label">의식</span>
                    <span className="modal-info-value">{item.patient.consciousness}</span>
                  </div>
                  <div className="modal-info-item">
                    <span className="modal-info-label">호흡</span>
                    <span className="modal-info-value">{item.patient.breathing}</span>
                  </div>
                  <div className="modal-info-item" style={{ gridColumn: 'span 2' }}>
                    <span className="modal-info-label">현장 위치</span>
                    <span className="modal-info-value" style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                      <span>{item.location.label || item.location.region}</span>
                      {item.location.lat && item.location.lon && (
                        <a
                          href={`https://map.kakao.com/link/map/현장위치,${item.location.lat},${item.location.lon}`}
                          target="_blank"
                          rel="noopener noreferrer"
                          style={{
                            fontSize: '11px',
                            color: '#3b82f6',
                            textDecoration: 'underline',
                            fontWeight: '600',
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: '2px'
                          }}
                          title="GPS 좌표 기준 카카오맵 지도 보기"
                        >
                          [지도 보기]
                        </a>
                      )}
                    </span>
                  </div>
                </div>

                <div className="modal-section">
                  <div className="modal-section-title">증상 및 현장 메모</div>
                  <div className="modal-reason">
                    {item.rawText || (item.symptoms.length > 0 ? item.symptoms.join(', ') : '증상 정보 없음')}
                    {item.patient.memo && <div style={{ marginTop: '8px' }}>{item.patient.memo}</div>}
                  </div>
                </div>

                {item.status !== 'accepted' ? (
                  <button className="btn-primary btn-accept-case" onClick={() => onAcceptCase(item.id)}>
                    수용 확정
                  </button>
                ) : (
                  <div className="checklist-box">
                    {checklist.map((text) => (
                      <span className="checklist-badge confirmed" key={text}>
                        <CheckCircle2 size={12} /> {text}
                      </span>
                    ))}
                  </div>
                )}
              </div>
              );
            })}
          </div>
        </>
      )}
    </main>
  );
}

export default MedicalDashboard;
