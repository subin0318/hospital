import math
import os
import time
import requests
from dotenv import load_dotenv
from config import ETA_FALLBACK_SPEED_KMH, ETA_CACHE_TTL_SEC, PENALTY_BOUNCE

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(BASE_DIR, ".env"))

KAKAO_API_KEY = os.getenv("KAKAO_API_KEY")

# ETA 캐시 구조 및 TTL 설정
_eta_cache: dict = {}          # 키: (user_lat, user_lon, hosp_lat, hosp_lon) 튜플
_ETA_CACHE_TTL = ETA_CACHE_TTL_SEC   # 유효 시간 (config.py에서 관리)

def _cache_key(user_lat, user_lon, hosp_lat, hosp_lon):
    """
    사용자 좌표는 100m 단위(소수점 3자리)로 내림/반올림 처리하여 
    미세한 GPS 오차로 인한 캐시 미스를 방지하고, 병원 좌표는 5자리까지 사용합니다.
    """
    return (round(user_lat, 3), round(user_lon, 3), round(hosp_lat, 5), round(hosp_lon, 5))

def calculate_distance(lat1, lon1, lat2, lon2):
    """
    Haversine 공식을 사용하여 두 좌표(위도/경도) 사이의 직선 거리를 킬로미터(km) 단위로 계산합니다.
    """
    R = 6371.0 # 지구의 반지름 (km)

    lat1_rad = math.radians(lat1)
    lon1_rad = math.radians(lon1)
    lat2_rad = math.radians(lat2)
    lon2_rad = math.radians(lon2)

    dlon = lon2_rad - lon1_rad
    dlat = lat2_rad - lat1_rad

    a = math.sin(dlat / 2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    distance = R * c
    return distance

def get_eta_minutes(user_lat, user_lon, hosp_lat, hosp_lon):
    """
    카카오모빌리티 '자동차 길찾기' API를 활용하여 실제 실시간 소요 시간(분)을 계산합니다.
    API 키가 없거나 호출에 실패할 경우, 하버사인 기반 직선거리(Mock) 로직으로 폴백(Fallback)합니다.
    반환값: (소요시간_분: int, 산출소스: str)
    """
    key = _cache_key(user_lat, user_lon, hosp_lat, hosp_lon)
    now = time.time()
    
    # 캐시 히트 체크
    if key in _eta_cache:
        cache_data = _eta_cache[key]
        if now - cache_data["timestamp"] < _ETA_CACHE_TTL:
            return cache_data["eta"], cache_data["source"]
            
    if KAKAO_API_KEY:
        url = "https://apis-navi.kakaomobility.com/v1/directions"
        headers = {
            "Authorization": f"KakaoAK {KAKAO_API_KEY}"
        }
        params = {
            # 카카오는 경도(longitude), 위도(latitude) 순서로 좌표를 받습니다.
            "origin": f"{user_lon},{user_lat}",
            "destination": f"{hosp_lon},{hosp_lat}",
            "priority": "TIME" # 최단시간 기준
        }
        
        try:
            # 2초 타임아웃으로 빠른 실패 유도 (응급 시스템이므로 길찾기 API가 응답이 늦으면 바로 직선거리로 전환)
            res = requests.get(url, headers=headers, params=params, timeout=2)
            res.raise_for_status()
            data = res.json()
            
            # 카카오 응답 데이터에서 소요 시간(초) 추출
            duration_sec = data['routes'][0]['summary']['duration']
            eta_minutes = duration_sec / 60.0
            val = max(1, int(eta_minutes))
            _eta_cache[key] = {"eta": val, "source": "kakao", "timestamp": now}
            return val, "kakao"
            
        except Exception as e:
            print(f" 카카오내비 API 호출 실패 (직선거리로 대체): {e}")
            pass # 실패 시 아래의 기본 직선거리 로직으로 넘어감

    # [Fallback] API 키가 없거나 호출 실패 시 하버사인 직선거리 기반 계산 (속도: config.ETA_FALLBACK_SPEED_KMH)
    distance_km = calculate_distance(user_lat, user_lon, hosp_lat, hosp_lon)
    speed_km_per_min = ETA_FALLBACK_SPEED_KMH / 60.0
    eta_minutes = distance_km / speed_km_per_min
    val = max(1, int(eta_minutes))
    _eta_cache[key] = {"eta": val, "source": "fallback", "timestamp": now}
    return val, "fallback"

def calculate_expected_time(hvec, eta_minutes):
    """
    [대안 A: 뺑뺑이 확률 모델]
    "도착했을 때 병상이 남아있을 확률"을 고려하여 실질적인 기대 소요 시간(Expected Time)을 계산합니다.
    
    기대시간 = (성공 확률 * ETA) + (실패 확률 * (ETA + 뺑뺑이 패널티))
    """
    # 1. 잔여 병상 수에 따른 '도착 시 성공 확률' 추정 (경험적 수치)
    if hvec >= 10:
        p_success = 0.98  # 거의 무조건 성공
    elif hvec >= 5:
        p_success = 0.85  # 매우 안전
    elif hvec >= 3:
        p_success = 0.60  # 약간 불안
    elif hvec == 2:
        p_success = 0.40  # 뺑뺑이 위험 높음
    elif hvec == 1:
        p_success = 0.20  # 가는 도중 뺏길 확률 매우 높음
    else:
        p_success = 0.00  # 이미 병상 없음 (필터링되겠지만 방어 코드)
        
    p_fail = 1.0 - p_success
    
    # 2. 뺑뺑이 패널티: 다른 병원으로 다시 이동하고 수속하는 데 걸리는 평균 추가 시간 (config.PENALTY_BOUNCE)
    BOUNCE_PENALTY_MINUTES = PENALTY_BOUNCE
    
    # 3. 기대 시간 계산
    # 성공 시: 그냥 ETA
    # 실패 시: ETA(갔다가 허탕침) + 뺑뺑이 패널티(다른 병원으로 이동)
    expected_time = (p_success * eta_minutes) + (p_fail * (eta_minutes + BOUNCE_PENALTY_MINUTES))
    
    # 점수가 아니라 시간(분)이므로, 낮을수록 좋습니다.
    return round(expected_time, 2)
