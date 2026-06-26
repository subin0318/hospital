import React, { useEffect, useRef } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import hospitalImage from '../../img/hospital.png';

const MapComponent = ({ userLat, userLon, hospitals, onMapClick, onHospitalSelect, selectedHospital, activeMode = 'citizen', routePath, routeSource }) => {
  const mapContainerRef = useRef(null);
  const mapInstanceRef = useRef(null);
  const userMarkerRef = useRef(null);
  const hospitalMarkersRef = useRef([]);
  const routePolylineRef = useRef(null);
  const onMapClickRef = useRef(onMapClick);
  const initialCenterRef = useRef([userLat, userLon]);

  useEffect(() => {
    onMapClickRef.current = onMapClick;
  }, [onMapClick]);

  useEffect(() => {
    const map = mapInstanceRef.current;
    if (!map) return;

    const timer = window.setTimeout(() => {
      map.invalidateSize();
      map.setView([userLat, userLon], map.getZoom());
    }, 120);

    return () => window.clearTimeout(timer);
  }, [activeMode, userLat, userLon]);

  // 1. Initialize Map
  useEffect(() => {
    if (!mapContainerRef.current) return;

    // CartoDB Positron - Faint, clean, minimal base map with NO commercial label noise
    const baseLayer = L.tileLayer(
      'https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png',
      {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
        subdomains: 'abcd',
        maxZoom: 20,
      }
    );

    const map = L.map(mapContainerRef.current, {
      center: initialCenterRef.current,
      zoom: 12,
      layers: [baseLayer],
      zoomControl: true,
    });

    mapInstanceRef.current = map;

    // Listen to Map Clicks to set coordinates
    map.on('click', (e) => {
      if (onMapClickRef.current) {
        onMapClickRef.current(e.latlng.lat, e.latlng.lng);
      }
    });

    return () => {
      map.off();
      map.remove();
      mapInstanceRef.current = null;
    };
  }, []); // Run once on mount

  // 2. Update User Location Marker & Center View when coordinates change
  useEffect(() => {
    const map = mapInstanceRef.current;
    if (!map) return;

    // Set map view center
    map.setView([userLat, userLon], map.getZoom());

    // Create or update user marker
    if (userMarkerRef.current) {
      userMarkerRef.current.setLatLng([userLat, userLon]);
    } else {
      // Pulsing blue dot for user
      const userIcon = L.divIcon({
        className: 'custom-user-marker',
        html: '<div class="user-marker-pulse"></div>',
        iconSize: [24, 24],
        iconAnchor: [12, 12]
      });

      userMarkerRef.current = L.marker([userLat, userLon], {
        icon: userIcon,
        zIndexOffset: 1000
      })
        .addTo(map)
        .bindPopup(activeMode === 'ambulance' ? '구급대원 현장 위치' : '내 가상 위치');
    }
  }, [userLat, userLon, activeMode]);

  useEffect(() => {
    if (!userMarkerRef.current) return;
    userMarkerRef.current.bindPopup(activeMode === 'ambulance' ? '구급대원 현장 위치' : '내 가상 위치');
  }, [activeMode]);

  // 3. Update Hospital Markers
  useEffect(() => {
    const map = mapInstanceRef.current;
    if (!map) return;

    // Remove existing hospital markers
    hospitalMarkersRef.current.forEach((marker) => marker.remove());
    hospitalMarkersRef.current = [];

    // Add new markers for recommended hospitals
    hospitals.forEach((hosp) => {
      const lat = parseFloat(hosp.wgs84Lat);
      const lon = parseFloat(hosp.wgs84Lon);
      if (isNaN(lat) || isNaN(lon)) return;

      // Color coding based on recommendation type and bed status.
      const isLightCare = hosp.care_type === 'light';
      const isRed = !isLightCare && hosp.status === '혼잡';        // 백엔드 status 필드 사용
      const isOrange = !isLightCare && hosp.status === '보통';     // 백엔드 status 필드 사용
      const color = isLightCare ? '#3b82f6' : isRed ? '#ef4444' : isOrange ? '#f59e0b' : '#10b981';

      const hospitalIcon = L.divIcon({
        className: 'custom-hospital-marker',
        html: `
          <div style="
            width: 42px;
            height: 42px;
            border: 2px solid ${color};
            border-radius: 12px;
            background: rgba(255,255,255,0.95);
            box-shadow: 0 4px 12px rgba(15,23,42,0.35);
            display: flex;
            justify-content: center;
            align-items: center;
            overflow: hidden;
          ">
            <img src="${hospitalImage}" alt="" style="width: 38px; height: 38px; object-fit: contain;" />
          </div>
        `,
        iconSize: [42, 42],
        iconAnchor: [21, 42],
        popupAnchor: [0, -38]
      });

      const popupHtml = `
        <div style="padding: 4px; font-family: sans-serif;">
          <h4 style="margin: 0 0 6px 0; font-size: 13px; font-weight: 700; color: white;">${hosp.dutyName}</h4>
          <p style="margin: 0 0 4px 0; font-size: 11px; color: #94a3b8;">${isLightCare ? `기관 유형: <strong style="color: ${color}">${hosp.institution_type || '의료기관'}</strong>` : `가용 병상: <strong style="color: ${color}">${hosp.hvec}개</strong>`}</p>
          <p style="margin: 0; font-size: 11px; color: #94a3b8;">소요 시간: <strong>${Math.round(hosp.expected_time_minutes)}분</strong></p>
        </div>
      `;

      const marker = L.marker([lat, lon], { icon: hospitalIcon })
        .addTo(map)
        .bindPopup(popupHtml);

      // Tag marker with ID and add click event
      marker.hpid = hosp.hpid;
      marker.on('click', () => {
        if (onHospitalSelect) {
          onHospitalSelect(hosp);
        }
      });

      hospitalMarkersRef.current.push(marker);
    });
  }, [hospitals, onHospitalSelect]);

  // 4. Draw route polyline when routePath changes
  useEffect(() => {
    const map = mapInstanceRef.current;
    if (!map) return;

    if (routePolylineRef.current) {
      routePolylineRef.current.remove();
      routePolylineRef.current = null;
    }

    if (routePath && routePath.length > 1) {
      const isFallback = routeSource === 'fallback';
      routePolylineRef.current = L.polyline(routePath, {
        color: isFallback ? '#94a3b8' : '#3b82f6',
        weight: isFallback ? 3 : 5,
        opacity: 0.85,
        dashArray: isFallback ? '8, 7' : null,
        lineJoin: 'round',
        lineCap: 'round',
      }).addTo(map);

      map.fitBounds(routePolylineRef.current.getBounds(), { padding: [50, 50] });
    }
  }, [routePath, routeSource]);

  // 5. Zoom to selected hospital marker on the map when chosen in the card list
  useEffect(() => {
    if (!selectedHospital) return;
    const map = mapInstanceRef.current;
    if (!map) return;

    const marker = hospitalMarkersRef.current.find(m => m.hpid === selectedHospital.hpid);
    if (marker) {
      marker.openPopup();
      map.setView(marker.getLatLng(), Math.max(13, map.getZoom()));
    }
  }, [selectedHospital]);

  return <div ref={mapContainerRef} style={{ width: '100%', height: '100%' }} />;
};

export default MapComponent;
