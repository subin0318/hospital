import React, { useState, useEffect } from 'react';
import MapComponent from './MapComponent';
import ErrorBanner from './ErrorBanner';
import LocationPanel from './LocationPanel';
import SymptomPanel from './SymptomPanel';
import RoutingFilterPanel from './RoutingFilterPanel';
import RecommendationResults from './RecommendationResults';
import HospitalDetailModal from './HospitalDetailModal';
import PatientInfoPanel from './PatientInfoPanel';
import { LOCATION_PRESETS, SYMPTOM_TAGS } from '../constants';
import { extractRegion } from '../utils';
import '../App.css';

function CitizenAmbulanceDashboard({ activeMode, onAddTransferCase }) {
  // 위치 상태
  const [userLat, setUserLat] = useState(34.8160);
  const [userLon, setUserLon] = useState(126.4630);
  const [activePreset, setActivePreset] = useState('전남도청');
  const [locationQuery, setLocationQuery] = useState('전남도청');
  const [selectedRegion, setSelectedRegion] = useState('무안군');
  const [locationError, setLocationError] = useState('');
  const [isLocationConfirmed, setIsLocationConfirmed] = useState(true);

  // 증상 및 분석 상태
  const [rawText, setRawText] = useState('');
  const [selectedSymptoms, setSelectedSymptoms] = useState([]);
  const [generalDepartments, setGeneralDepartments] = useState([]);
  const [severity, setSeverity] = useState('중증'); // '경증' 또는 '중증'
  const [aiSeverity, setAiSeverity] = useState('중증'); // AI가 판단한 severity (토글 복원 기준)
  const [careRoute, setCareRoute] = useState('emergency');
  const [routeReason, setRouteReason] = useState('');
  const [isLightForced, setIsLightForced] = useState(false); // 경증 분산 필터 토글
  const [isSymptomJudged, setIsSymptomJudged] = useState(false);
  const [aiNoSymptomMessage, setAiNoSymptomMessage] = useState(''); // AI가 증상을 못 찾은 경우 안내
  const [errorMessage, setErrorMessage] = useState(''); // 시스템 및 AI 에러 메시지 배너
  const [successMessage, setSuccessMessage] = useState(''); // 이송 통보 등 성공 알림 배너

  // 추천 결과 상태
  const [hospitals, setHospitals] = useState([]);
  const [loading, setLoading] = useState(false);
  const [aiAnalyzing, setAiAnalyzing] = useState(false);
  const [gpsLoading, setGpsLoading] = useState(false);
  const [recommendationScope, setRecommendationScope] = useState('');

  // 상세 보기 모달 상태
  const [selectedHospital, setSelectedHospital] = useState(null);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [routePath, setRoutePath] = useState(null);
  const [routeSource, setRouteSource] = useState(null); // 'kakao' | 'fallback' | null
  const [patientInfo, setPatientInfo] = useState({
    age: '',
    gender: '',
    consciousness: '명료',
    breathing: '정상',
    bleeding: '없음',
    guardianContact: '미확인',
    memo: ''
  });

  // 병원 추천 API 호출
  const fetchRecommendations = async (overrideSymptoms = null, overrideSeverity = null, overrideDepartments = null) => {
    setLoading(true);
    setErrorMessage('');
    try {
      const activeSymptoms = overrideSymptoms !== null ? overrideSymptoms : selectedSymptoms;
      const activeDepartments = overrideDepartments !== null ? overrideDepartments : generalDepartments;
      const activeSeverity = overrideSeverity !== null ? overrideSeverity : (isLightForced ? '경증' : severity);
      const endpoint = activeSeverity === '경증' ? '/api/recommend-light' : '/api/recommend';

      const response = await fetch(endpoint, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          lat: userLat,
          lon: userLon,
          symptoms: activeSymptoms,
          general_departments: activeDepartments,
          severity: activeSeverity,
          region: selectedRegion
        })
      });

      const result = await response.json();
      if (result.status === 'success') {
        setHospitals(result.data || []);
        setRecommendationScope(result.region_scope || '');
        if (result.severity) {
          setSeverity(result.severity);
        }
        if (result.is_ai_error) {
          setErrorMessage('AI 분석에 실패하여 기본 증상 기반으로 병원을 조회했습니다. 증상을 직접 선택해 주세요.');
        }
      } else {
        setErrorMessage(result.message || '병원 추천 정보 조회에 실패했습니다.');
        console.error(result.message);
      }
    } catch (err) {
      setErrorMessage('서버와의 통신 오류가 발생했습니다.');
      console.error('API 호출 오류:', err);
    } finally {
      setLoading(false);
    }
  };

  // 지도 클릭 핸들러
  const handleMapClick = (lat, lon) => {
    setUserLat(parseFloat(lat.toFixed(6)));
    setUserLon(parseFloat(lon.toFixed(6)));
    setActivePreset('사용자 지정 위치');
    setLocationQuery('사용자 지정 위치');
    setSelectedRegion('');
    setLocationError('');
    setIsLocationConfirmed(true);
    setIsSymptomJudged(false);
    setGeneralDepartments([]);
    setRouteReason('');
    setHospitals([]);
    setRecommendationScope('');
    setSelectedHospital(null);
    setIsModalOpen(false);
  };

  // 프리셋 변경 핸들러
  const handlePresetClick = (preset) => {
    setUserLat(preset.lat);
    setUserLon(preset.lon);
    setActivePreset(preset.name);
    setLocationQuery(preset.name);
    setSelectedRegion(preset.region);
    setLocationError('');
    setIsLocationConfirmed(true);
    setIsSymptomJudged(false);
    setGeneralDepartments([]);
    setRouteReason('');
    setHospitals([]);
    setRecommendationScope('');
    setSelectedHospital(null);
    setIsModalOpen(false);
  };

  // GPS 현재 위치 감지 핸들러
  const handleGpsLocation = () => {
    if (!navigator.geolocation) {
      setLocationError('이 브라우저는 GPS 위치 기능을 지원하지 않습니다.');
      return;
    }

    setGpsLoading(true);
    setLocationError('');

    const applyLocation = (lat, lon, address, region) => {
      setUserLat(lat);
      setUserLon(lon);
      setLocationQuery(address);
      setSelectedRegion(region);
      setActivePreset('GPS 현재 위치');
      setIsLocationConfirmed(true);
      setIsSymptomJudged(false);
      setGeneralDepartments([]);
      setRouteReason('');
      setHospitals([]);
      setRecommendationScope('');
      setSelectedHospital(null);
      setIsModalOpen(false);
    };

    navigator.geolocation.getCurrentPosition(
      async (position) => {
        const lat = parseFloat(position.coords.latitude.toFixed(6));
        const lon = parseFloat(position.coords.longitude.toFixed(6));
        const coordFallback = `GPS (${lat.toFixed(4)}°N, ${lon.toFixed(4)}°E)`;
        try {
          const res = await fetch(`/api/reverse-geocode?lat=${lat}&lon=${lon}`);
          const result = await res.json();
          if (result.status === 'success' && result.address) {
            applyLocation(lat, lon, result.address, result.region || extractRegion(result.address));
          } else {
            applyLocation(lat, lon, coordFallback, '');
          }
        } catch {
          applyLocation(lat, lon, coordFallback, '');
        } finally {
          setGpsLoading(false);
        }
      },
      (error) => {
        setGpsLoading(false);
        const messages = {
          [error.PERMISSION_DENIED]: 'GPS 위치 권한이 거부되었습니다. 브라우저 설정에서 위치 접근을 허용해 주세요.',
          [error.POSITION_UNAVAILABLE]: '현재 위치를 확인할 수 없습니다. 주소 검색을 이용해 주세요.',
          [error.TIMEOUT]: 'GPS 위치 확인이 시간 초과되었습니다. 다시 시도해 주세요.',
        };
        setLocationError(messages[error.code] || '위치 정보를 가져오는 데 실패했습니다.');
      },
      { enableHighAccuracy: true, timeout: 10000, maximumAge: 30000 }
    );
  };

  // Daum 우편번호 서비스 팝업 실행 핸들러
  const handleOpenPostcode = () => {
    if (!window.daum || !window.daum.Postcode) {
      setLocationError('주소 서비스 스크립트가 아직 로드되지 않았습니다. 잠시 후 다시 시도해 주세요.');
      return;
    }

    new window.daum.Postcode({
      oncomplete: async (data) => {
        const address = data.roadAddress || data.address;
        const region = data.sigungu || extractRegion(address);
        setLocationQuery(address);
        setSelectedRegion(region);
        setLocationError('');
        setLoading(true);

        try {
          const res = await fetch(`/api/geocode?address=${encodeURIComponent(address)}`);
          const result = await res.json();
          if (result.status === 'success') {
            setUserLat(result.lat);
            setUserLon(result.lon);
            setActivePreset('검색된 위치');
            setLocationQuery(result.address);
            setSelectedRegion(result.region || region || extractRegion(result.address));
            setIsLocationConfirmed(true);
            setIsSymptomJudged(false);
            setGeneralDepartments([]);
            setRouteReason('');
            setHospitals([]);
            setRecommendationScope('');
            setSelectedHospital(null);
            setIsModalOpen(false);
          } else {
            setLocationError(result.message || '좌표 변환에 실패했습니다.');
            setIsLocationConfirmed(false);
          }
        } catch (err) {
          console.error('주소 검색 에러:', err);
          setLocationError('서버 연결 중 오류가 발생했습니다.');
        } finally {
          setLoading(false);
        }
      }
    }).open();
  };

  // AI 자연어 증상 분석 핸들러
  const handleAiAnalysis = async () => {
    if (!rawText.trim()) {
      setAiNoSymptomMessage('분석할 증상 문장을 먼저 입력해 주세요.');
      return;
    }
    if (!isLocationConfirmed) {
      setLocationError('주소 검색으로 출발 위치를 먼저 확정해 주세요.');
      return;
    }

    setAiAnalyzing(true);
    setErrorMessage('');
    try {
      const response = await fetch('/api/analyze-symptoms', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          text: rawText,
          mode: activeMode === 'ambulance' ? 'ambulance' : 'citizen',
          patient_info: activeMode === 'ambulance' ? patientInfo : null
        })
      });
      const result = await response.json();
      if (result.status === 'success') {
        if (result.is_ai_error) {
          setErrorMessage('Gemini AI 증상 분석에 실패했습니다. 아래 태그에서 증상을 직접 선택해 주세요.');
          setAiNoSymptomMessage('AI 분석에 실패했습니다. 증상을 직접 선택해 주세요.');
          setSelectedSymptoms([]);
          setIsSymptomJudged(false);
          setHospitals([]);
          return;
        }

        const symptoms = result.extracted_symptoms || [];
        const departments = result.general_departments || [];
        const detectedSeverity = result.severity || '중증';
        const detectedRoute = result.care_route || (detectedSeverity === '경증' ? 'general' : 'emergency');
        const detectedReason = result.route_reason || '';

        setSelectedSymptoms(symptoms);
        setGeneralDepartments(departments);
        setSeverity(detectedSeverity);
        setAiSeverity(detectedSeverity); // AI 판단값 별도 보존
        setCareRoute(detectedRoute);
        setRouteReason(detectedReason);

        if (detectedRoute === 'general' || detectedSeverity === '경증') {
          setIsLightForced(true);
        } else {
          setIsLightForced(false);
        }

        if (detectedRoute === 'call_first') {
          setAiNoSymptomMessage(detectedReason || '문장 분석 결과만으로 안내 경로가 애매합니다. 119 또는 의료기관 전화 확인을 먼저 권장합니다.');
          setIsSymptomJudged(false);
          setHospitals([]);
          setRecommendationScope('');
        } else if (symptoms.length === 0 && departments.length === 0) {
          setAiNoSymptomMessage('입력하신 문장에서 공공데이터 검색에 사용할 증상 또는 진료과 키워드를 찾지 못했습니다. 증상 태그를 직접 선택하거나 다시 입력해 주세요.');
          setIsSymptomJudged(false);
          setHospitals([]);
          setRecommendationScope('');
        } else {
          setAiNoSymptomMessage('');
          setIsSymptomJudged(true);
          fetchRecommendations(symptoms, detectedRoute === 'general' ? '경증' : detectedSeverity, departments);
        }
      } else {
        setErrorMessage(result.message || 'AI 증상 분석 중 오류가 발생했습니다.');
      }
    } catch (err) {
      setErrorMessage('서버와의 통신 오류로 AI 증상 분석을 완료하지 못했습니다.');
      console.error('AI 분석 실패:', err);
    } finally {
      setAiAnalyzing(false);
    }
  };

  // 증상 태그 선택 토글
  const handleSymptomTagToggle = (tag) => {
    if (!isLocationConfirmed) {
      setLocationError('주소 검색으로 출발 위치를 먼저 확정해 주세요.');
      return;
    }

    let updated;
    if (selectedSymptoms.includes(tag)) {
      updated = selectedSymptoms.filter(s => s !== tag);
    } else {
      updated = [...selectedSymptoms, tag];
    }
    setSelectedSymptoms(updated);
    setGeneralDepartments([]);
    setRouteReason('');
    setCareRoute('emergency');
    setIsSymptomJudged(updated.length > 0);

    if (updated.length > 0) {
      fetchRecommendations(updated, null, []);
    } else {
      setHospitals([]);
      setRecommendationScope('');
    }
  };

  // 혼잡도 신호등 클래스 반환 — 백엔드 API 응답의 status 필드('원활'/'보통'/'혼잡') 기반
  const getCongestionClass = (status) => {
    if (status === '원활') return { label: '원활', style: 'green' };
    if (status === '보통') return { label: '보통', style: 'orange' };
    return { label: '혼잡/불가', style: 'red' };
  };

  const handleTransferCase = (hospital) => {
    const transferCase = {
      id: `${Date.now()}-${hospital.hpid}`,
      status: 'pending',
      createdAt: new Date().toISOString(),
      hospital,
      patient: patientInfo,
      rawText,
      symptoms: selectedSymptoms,
      generalDepartments,
      routeReason,
      severity,
      location: {
        label: locationQuery,
        region: selectedRegion,
        lat: userLat,
        lon: userLon
      }
    };

    onAddTransferCase(transferCase);
    setSuccessMessage(`${hospital.dutyName}으로 이송 정보 공유 카드가 생성되었습니다. 의료진 모드에서 확인할 수 있습니다.`);
  };

  const handleHospitalSelect = (hosp) => {
    setSelectedHospital(hosp);
    setIsModalOpen(true);
  };

  const handleModalClose = () => {
    setIsModalOpen(false);
    // selectedHospital은 유지 → routePath도 지도에 유지
  };

  // 병원 선택 시 카카오 모빌리티 실제 도로 경로 요청 (실패 시 직선 경로 대체)
  useEffect(() => {
    if (!selectedHospital) {
      setRoutePath(null);
      setRouteSource(null);
      return;
    }
    const destLat = parseFloat(selectedHospital.wgs84Lat);
    const destLon = parseFloat(selectedHospital.wgs84Lon);
    if (isNaN(destLat) || isNaN(destLon)) return;

    fetch('/api/route', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        origin_lat: userLat,
        origin_lon: userLon,
        dest_lat: destLat,
        dest_lon: destLon
      })
    })
      .then(res => res.json())
      .then(result => {
        if (result.status === 'success' && result.path) {
          setRoutePath(result.path);
          setRouteSource(result.source || 'fallback');
        } else {
          setRoutePath(null);
          setRouteSource(null);
          setErrorMessage(result.message || '경로 정보를 불러오지 못했습니다. 병원 추천 결과는 그대로 확인할 수 있습니다.');
        }
      })
      .catch(() => {
        setRoutePath(null);
        setRouteSource(null);
        setErrorMessage('서버와의 통신 오류로 경로선을 표시하지 못했습니다. 병원 추천 결과는 그대로 확인할 수 있습니다.');
      });
  }, [selectedHospital, userLat, userLon]);

  return (
    <>
      <div className="dashboard-grid">
        <aside className="sidebar">
          <ErrorBanner
            message={errorMessage}
            onClose={() => setErrorMessage('')}
          />
          <ErrorBanner
            type="success"
            message={successMessage}
            onClose={() => setSuccessMessage('')}
          />

          <LocationPanel
            presets={LOCATION_PRESETS}
            activePreset={activePreset}
            locationQuery={locationQuery}
            locationError={locationError}
            selectedRegion={selectedRegion}
            onOpenPostcode={handleOpenPostcode}
            onPresetClick={handlePresetClick}
            onGpsClick={handleGpsLocation}
            gpsLoading={gpsLoading}
          />

          {activeMode === 'ambulance' && (
            <PatientInfoPanel
              patientInfo={patientInfo}
              onChange={setPatientInfo}
            />
          )}

          <SymptomPanel
            rawText={rawText}
            selectedSymptoms={selectedSymptoms}
            symptomTags={SYMPTOM_TAGS}
            aiAnalyzing={aiAnalyzing}
            aiNoSymptomMessage={aiNoSymptomMessage}
            isLocationConfirmed={isLocationConfirmed}
            onRawTextChange={setRawText}
            onAiAnalysis={handleAiAnalysis}
            onSymptomTagToggle={handleSymptomTagToggle}
          />

          <RoutingFilterPanel
            aiSeverity={aiSeverity}
            careRoute={careRoute}
            routeReason={routeReason}
            isLightForced={isLightForced}
            isLocationConfirmed={isLocationConfirmed}
            isSymptomJudged={isSymptomJudged}
            selectedSymptoms={selectedSymptoms}
            onLightForcedChange={setIsLightForced}
            onFetchRecommendations={fetchRecommendations}
          />
        </aside>

        <main className="main-content">
          <div className="map-container-wrapper">
            <MapComponent
              userLat={userLat}
              userLon={userLon}
              hospitals={hospitals}
              onMapClick={handleMapClick}
              onHospitalSelect={handleHospitalSelect}
              selectedHospital={selectedHospital}
              activeMode={activeMode}
              routePath={routePath}
              routeSource={routeSource}
            />
          </div>

          <RecommendationResults
            loading={loading}
            isLocationConfirmed={isLocationConfirmed}
            isSymptomJudged={isSymptomJudged}
            isLightForced={isLightForced}
            severity={severity}
            recommendationScope={recommendationScope}
            hospitals={hospitals}
            selectedHospital={selectedHospital}
            onHospitalSelect={handleHospitalSelect}
            getCongestionClass={getCongestionClass}
          />
        </main>
      </div>

      <HospitalDetailModal
        selectedHospital={selectedHospital}
        isOpen={isModalOpen}
        onClose={handleModalClose}
            activeMode={activeMode}
            onTransfer={handleTransferCase}
            onScenarioNotice={setSuccessMessage}
          />
    </>
  );
}

export default CitizenAmbulanceDashboard;
