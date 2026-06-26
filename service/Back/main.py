import os
import re
import sqlite3
import json
import requests
import xmltodict
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import routing
from dotenv import load_dotenv
from config import (
    REGIONAL_CENTER_HPIDS,
    BED_STATUS_SMOOTH, BED_STATUS_NORMAL,
    PENALTY_ISLAND_REGION, PENALTY_EQUIPMENT_MISSING, PENALTY_REGIONAL_CENTER_LIGHT,
    PENALTY_SPECIAL_BED_MISSING, PENALTY_ICU_BED_MISSING,
    HIRA_SIDO_CD, HIRA_SEARCH_RADIUS_DEFAULT, HIRA_SEARCH_RADIUS_EXPANDED, HIRA_NUM_OF_ROWS,
    ISLAND_REGIONS, HIRA_DEPARTMENT_CODES, NEARBY_REGIONS,
    SERVER_PORT,
)

# 환경변수 로드
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(BASE_DIR, ".env"))

app = FastAPI(title="전라남도 맞춤형 응급의료 지원 시스템 API")

# 프론트엔드(React 등)에서 API를 호출할 수 있도록 CORS 설정 허용
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 실제 운영 환경에서는 허용할 도메인만 지정해야 함
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# DB 파일 경로 동적 설정: 현재 파일(Back/main.py) 기준으로 collect_hospitals/hospital.db 찾기
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "collect_hospitals", "hospital.db")

@app.get("/")
def read_root():
    return {"message": "응급의료 지원 시스템 API 서버가 정상적으로 실행 중입니다."}

@app.get("/api/geocode")
def geocode_address(address: str):
    """주소를 위도와 경도로 변환합니다."""
    kakao_key = os.getenv("KAKAO_API_KEY")
    if not kakao_key:
        return {"status": "error", "message": "KAKAO_API_KEY가 설정되지 않았습니다."}
    
    url = "https://dapi.kakao.com/v2/local/search/address.json"
    headers = {
        "Authorization": f"KakaoAK {kakao_key}"
    }
    params = {
        "query": address
    }
    
    try:
        import requests
        res = requests.get(url, headers=headers, params=params, timeout=5)
        res.raise_for_status()
        data = res.json()
        
        documents = data.get("documents", [])
        if not documents:
            return {"status": "error", "message": "해당 주소의 좌표를 찾을 수 없습니다."}
            
        first_doc = documents[0]
        # x가 경도(longitude), y가 위도(latitude)입니다.
        lon = float(first_doc["x"])
        lat = float(first_doc["y"])
        
        return {
            "status": "success",
            "lat": lat,
            "lon": lon,
            "address": first_doc.get("address_name", address)
        }
    except Exception as e:
        return {"status": "error", "message": f"좌표 변환 실패: {str(e)}"}

@app.get("/api/reverse-geocode")
def reverse_geocode(lat: float, lon: float):
    """위도/경도를 주소와 시군구 정보로 변환합니다 (GPS 위치 확인용)."""
    kakao_key = os.getenv("KAKAO_API_KEY")
    if not kakao_key:
        return {"status": "error", "message": "KAKAO_API_KEY가 설정되지 않았습니다."}

    url = "https://dapi.kakao.com/v2/local/geo/coord2regioncode.json"
    headers = {"Authorization": f"KakaoAK {kakao_key}"}
    params = {"x": lon, "y": lat}

    try:
        res = requests.get(url, headers=headers, params=params, timeout=5)
        res.raise_for_status()
        data = res.json()

        documents = data.get("documents", [])
        if not documents:
            return {"status": "error", "message": "해당 좌표의 주소를 찾을 수 없습니다."}

        # H 타입(법정동) 우선 사용, 없으면 첫 번째 결과
        doc = next((d for d in documents if d.get("region_type") == "H"), documents[0])

        return {
            "status": "success",
            "address": doc.get("address_name", ""),
            "region": doc.get("region_2depth_name", ""),
            "lat": lat,
            "lon": lon
        }
    except Exception as e:
        return {"status": "error", "message": f"주소 변환 실패: {str(e)}"}

@app.get("/api/hospitals")
def get_hospitals():
    """가장 최신 수집된 응급의료기관 정보를 JSON 형태로 반환합니다."""
    if not os.path.exists(DB_PATH):
        return {"status": "error", "message": "DB 파일을 찾을 수 없습니다. 데이터 수집을 먼저 진행해주세요."}

    # DB 연결 (row_factory를 통해 딕셔너리 형태로 결과를 쉽게 가져오도록 설정)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # 수동 갱신으로 저장된 최신 병상 데이터 기준 조회
    query = """
    SELECT 
        b.hpid,
        b.phpid,
        b.dutyName, 
        e.hvec, 
        e.hvoc, 
        e.hvgc, 
        e.hv4,
        e.hv5,
        e.hvicc,
        e.hvcc,
        e.hvccc,
        e.hvncc,
        e.hv2,
        e.hv3,
        e.hv6,
        e.hv7,
        e.hv8,
        e.hv9,
        e.hvctayn,
        e.hvmriayn,
        e.hvangioayn,
        e.hvventiayn,
        e.hv10,
        e.hv11,
        e.hvamyn,
        e.hvdnm,
        e.hv1,
        e.hv12,
        b.dutyTel1,
        b.dutyTel3, 
        e.hvidate,
        b.dutyAddr,
        b.wgs84Lat,
        b.wgs84Lon,
        b.is_realtime_available,
        d.acceptance_json
    FROM hospital_basic_info b
    LEFT JOIN (
        SELECT e1.*
        FROM emergency_room_beds e1
        INNER JOIN (
            SELECT hpid, MAX(hvidate) as max_hvidate
            FROM emergency_room_beds
            GROUP BY hpid
        ) e2 ON e1.hpid = e2.hpid AND e1.hvidate = e2.max_hvidate
    ) e ON b.hpid = e.hpid
    LEFT JOIN disease_acceptance d ON b.hpid = d.hpid
    ORDER BY e.hvec DESC
    """
    
    try:
        cursor.execute(query)
        rows = cursor.fetchall()
    except Exception as e:
        conn.close()
        return {"status": "error", "message": f"DB 조회 실패: {str(e)}"}
    
    results = []
    for row in rows:
        item = dict(row)
        
        # 가용 병상 상태 신호등 텍스트 추가 (프론트엔드 처리 편의)
        hvec = item["hvec"] if item["hvec"] is not None else 0
        item["status"] = get_bed_status(hvec)
        # 권역응급의료센터 여부 플래그 (프론트는 이 값을 직접 사용)
        item["is_regional_center"] = item["hpid"] in REGIONAL_CENTER_HPIDS
        
        # JSON 문자열로 저장된 중증질환 정보를 프론트가 쓰기 편하게 실제 딕셔너리로 변환
        if item.get("acceptance_json"):
            try:
                item["acceptance_info"] = json.loads(item["acceptance_json"])
            except:
                item["acceptance_info"] = {}
            # 파싱이 끝난 원본 문자열 필드는 삭제하여 응답을 깔끔하게 정리
            del item["acceptance_json"]
        else:
            item["acceptance_info"] = {}
            
        results.append(item)
        
    conn.close()
    
    return {
        "status": "success",
        "total_count": len(results),
        "data": results
    }

@app.get("/api/hospital-bed-history")
def get_hospital_bed_history(hpid: str, limit: int = 24):
    """특정 병원의 병상 시계열 기록을 최신순으로 조회한 뒤 시간순으로 반환합니다."""
    if not os.path.exists(DB_PATH):
        return {"status": "error", "message": "DB 파일을 찾을 수 없습니다. 데이터 수집을 먼저 진행해주세요."}

    safe_limit = max(1, min(limit, 200))
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    query = """
    SELECT
        e.hpid,
        b.dutyName,
        b.dutyAddr,
        e.hvidate,
        e.hvec,
        e.hvoc,
        e.hvgc,
        e.hvicc,
        e.hvcc,
        e.hvncc
    FROM emergency_room_beds e
    LEFT JOIN hospital_basic_info b ON e.hpid = b.hpid
    WHERE e.hpid = ?
    ORDER BY e.hvidate DESC
    LIMIT ?
    """

    try:
        cursor.execute(query, (hpid, safe_limit))
        rows = [dict(row) for row in cursor.fetchall()]
    except Exception as e:
        conn.close()
        return {"status": "error", "message": f"병상 추이 조회 실패: {str(e)}"}

    conn.close()
    rows.reverse()

    return {
        "status": "success",
        "hpid": hpid,
        "total_count": len(rows),
        "data": rows
    }

def get_island_penalty(lat, lon):
    """
    사용자 좌표가 도서·산간 지역 안에 있으면 패널티 시간(분)과 사유를 반환한다.
    여러 지역에 동시에 해당하면 가장 큰 패널티만 적용한다.
    """
    max_penalty = 0.0
    region_name = ""
    for name, lat_min, lat_max, lon_min, lon_max in ISLAND_REGIONS:
        if lat_min <= lat <= lat_max and lon_min <= lon <= lon_max:
            max_penalty = PENALTY_ISLAND_REGION   # 도서 지역 기본 패널티 (config.py 관리)
            region_name = name
            break
    return max_penalty, region_name

def clean_hospital_name(raw_name: str) -> str:
    if not raw_name:
        return ""
    cleaned = re.sub(
        r'\((의료|재단|사단|사회복지|학교|합자|주식|유한)법인\)'
        r'|(의료|재단|사단|사회복지|학교|합자|주식|유한)법인\s*([^\s]*재단)?\s*'
        r'|\(주\)|\(유\)',
        '', raw_name
    )
    return cleaned.strip()

def get_bed_status(hvec: int) -> str:
    """
    가용 응급실 병상 수에 따른 신호등 상태 분류
    기준값은 config.py의 BED_STATUS_SMOOTH / BED_STATUS_NORMAL로 관리합니다.
    """
    if hvec >= BED_STATUS_SMOOTH:
        return "원활"
    elif hvec >= BED_STATUS_NORMAL:
        return "보통"
    else:
        return "혼잡"

class RecommendRequest(BaseModel):
    lat: float
    lon: float
    symptoms: Optional[List[str]] = []
    general_departments: Optional[List[str]] = []
    raw_text: Optional[str] = None
    severity: Optional[str] = None # "경증" 또는 "중증"
    region: Optional[str] = None

class AnalyzeRequest(BaseModel):
    text: str
    mode: Optional[str] = 'citizen'  # 'citizen' 또는 'ambulance'
    patient_info: Optional[dict] = None

class RouteRequest(BaseModel):
    origin_lat: float
    origin_lon: float
    dest_lat: float
    dest_lon: float

def normalize_region(region: Optional[str]) -> str:
    return (region or "").strip()

def region_allowed(address: str, allowed_regions: List[str]) -> bool:
    if not allowed_regions:
        return True
    return any(region in (address or "") for region in allowed_regions)

def get_allowed_emergency_regions(region: Optional[str]) -> List[str]:
    normalized = normalize_region(region)
    if not normalized:
        return []
    return NEARBY_REGIONS.get(normalized, [normalized])

def get_hira_items(data):
    body = data.get("response", {}).get("body", {})
    items = body.get("items", {}).get("item", [])
    if not isinstance(items, list):
        return [items] if items else []
    return items

def normalize_hira_hospital(item, user_lat, user_lon, symptoms):
    lat = item.get("YPos")
    lon = item.get("XPos")
    if not lat or not lon:
        return None

    try:
        hosp_lat = float(lat)
        hosp_lon = float(lon)
    except (TypeError, ValueError):
        return None

    eta_minutes, eta_source = routing.get_eta_minutes(user_lat, user_lon, hosp_lat, hosp_lon)
    distance_km = routing.calculate_distance(user_lat, user_lon, hosp_lat, hosp_lon)
    department = item.get("dgsbjtCdNm") or item.get("shwSbjtCdNm") or (
        "소아청소년과 우선" if "소아" in symptoms else "일반 진료"
    )
    cl_cd = str(item.get("clCd") or "")
    institution_type = item.get("clCdNm") or "의료기관"
    name = clean_hospital_name(item.get("yadmNm") or "") or "이름 미제공 의료기관"
    eta_desc = "실시간 내비" if eta_source == "kakao" else "직선거리 추정"

    if cl_cd == "1":
        inst_hint = "경증 환자에게 적합한 동네 의원으로 우선 선별되었습니다."
    elif cl_cd in ("11", "21", "31"):
        inst_hint = f"인근 {institution_type} 이용을 안내합니다."
    else:
        inst_hint = f"가까운 {institution_type} 이용을 안내합니다."

    return {
        "hpid": item.get("ykiho") or f"hira-{name}-{lat}-{lon}",
        "care_type": "light",
        "dutyName": name,
        "dutyAddr": item.get("addr") or "주소 정보 없음",
        "dutyTel1": item.get("telno") or "정보없음",
        "dutyTel3": item.get("telno") or "정보없음",
        "wgs84Lat": lat,
        "wgs84Lon": lon,
        "cl_cd": cl_cd,
        "institution_type": institution_type,
        "department": department,
        "distance_km": round(distance_km, 2),
        "eta_minutes": eta_minutes,
        "eta_source": eta_source,
        "expected_time_minutes": eta_minutes,
        "recommend_reason": (
            f"문장 분석 결과 일반 의료기관 우선 안내가 가능한 상황입니다. "
            f"{inst_hint} {department} 진료 가능 기관으로, "
            f"현재 위치에서 약 {round(distance_km, 1)}km · {eta_minutes}분({eta_desc}) 거리입니다."
        ),
    }

def evaluate_acceptance(acceptance_info, symptoms, symptom_mapping):
    """증상별 중증질환 수용 상태를 확정/확인필요/불가로 구분합니다."""
    checks = []
    has_unknown = False

    for symptom in symptoms:
        required_code = symptom_mapping.get(symptom)
        if not required_code:
            continue

        value = acceptance_info.get(required_code)
        if value == "Y":
            status = "confirmed"
            message = "수용 가능 확인"
        elif value == "불가능":
            status = "unavailable"
            message = "수용 불가"
        else:
            status = "unknown"
            message = "정보 미제공 - 전화 확인 필요"
            has_unknown = True

        checks.append({
            "symptom": symptom,
            "code": required_code,
            "value": value or "정보미제공",
            "status": status,
            "message": message
        })

        if status == "unavailable":
            return False, "수용 불가", checks

    if has_unknown:
        return True, "정보 미제공 - 전화 확인 필요", checks

    if checks:
        return True, "수용 가능 확인", checks

    return True, "증상 코드 매칭 없음", checks

def calculate_equipment_penalty(item, symptoms):
    """
    증상별로 필수/우선인 장비 및 중환자실 여력을 판단하여 패널티 시간(분)을 계산합니다.
    """
    penalty = 0.0
    reasons = []
    
    def is_unavailable(val):
        if val in (None, "", "N", "불가능"):
            return True
        return False

    for symptom in symptoms:
        if symptom == "화상":
            hv8 = item.get("hv8") or 0
            if hv8 <= 0:
                penalty += PENALTY_SPECIAL_BED_MISSING
                reasons.append("화상 중환자실 병상 부족")
                
        elif symptom in ("복부손상", "사지접합"):
            hv9 = item.get("hv9") or 0
            hvctayn = item.get("hvctayn")
            hvangioayn = item.get("hvangioayn")
            
            sub_reasons = []
            if hv9 <= 0:
                sub_reasons.append("외상 중환자실 부족")
            if is_unavailable(hvctayn):
                sub_reasons.append("CT 장비 미확보")
            if is_unavailable(hvangioayn):
                sub_reasons.append("조영촬영기 미확보")
                
            if sub_reasons:
                penalty += PENALTY_EQUIPMENT_MISSING
                reasons.append(f"외상 인프라 부족({', '.join(sub_reasons)})")
                
        elif symptom == "뇌졸중":
            hvctayn = item.get("hvctayn")
            hvmriayn = item.get("hvmriayn")
            
            sub_reasons = []
            if is_unavailable(hvctayn):
                sub_reasons.append("CT 장비 미확보")
            if is_unavailable(hvmriayn):
                sub_reasons.append("MRI 장비 미확보")
                
            if sub_reasons:
                penalty += PENALTY_EQUIPMENT_MISSING
                reasons.append(f"뇌졸중 진단 인프라 부족({', '.join(sub_reasons)})")

        elif symptom in ("심근경색", "흉통"):
            hvicc = item.get("hvicc") or 0
            hvctayn = item.get("hvctayn")
            hvangioayn = item.get("hvangioayn")
            
            sub_reasons = []
            if hvicc <= 0:
                sub_reasons.append("중환자실 부족")
            if is_unavailable(hvctayn):
                sub_reasons.append("CT 장비 미확보")
            if is_unavailable(hvangioayn):
                sub_reasons.append("조영촬영기 미확보")
                
            if sub_reasons:
                penalty += PENALTY_EQUIPMENT_MISSING
                reasons.append(f"심혈관 인프라 부족({', '.join(sub_reasons)})")
                
        elif symptom == "소아":
            hvcc = item.get("hvcc") or 0
            hv11 = item.get("hv11")
            hv10 = item.get("hv10")
            
            sub_reasons = []
            if hvcc <= 0:
                sub_reasons.append("소아 중환자실 부족")
            if is_unavailable(hv11):
                sub_reasons.append("소아 당직의 없음")
            if is_unavailable(hv10):
                sub_reasons.append("인큐베이터 없음")
                
            if sub_reasons:
                penalty += PENALTY_SPECIAL_BED_MISSING
                reasons.append(f"소아 응급 시설 미비({', '.join(sub_reasons)})")
                
        elif symptom == "투석":
            hvicc = item.get("hvicc") or 0
            if hvicc <= 0:
                penalty += PENALTY_ICU_BED_MISSING
                reasons.append("일반 중환자실 병상 부족")
                
    return penalty, reasons

def generate_recommend_reason(hvec, expected_time_minutes, eta_source, symptoms, acceptance_status, penalty_reasons, severity="중증", is_regional_center=False):
    eta_desc = "실시간 내비" if eta_source == "kakao" else "직선거리 추정"
    symptoms_str = ", ".join(symptoms) if symptoms else ""
    
    penalty_text = ""
    # "경증 환자 대형 응급실 분산 유도"는 설명 문구가 따로 있으므로 패널티 텍스트에서 분리
    display_penalties = [r for r in penalty_reasons if r != "경증 환자 대형 응급실 분산 유도"]
    if display_penalties:
        penalty_text = f" (주의: {', '.join(display_penalties)} 지연 + 패널티 포함)"
        
    if severity == "경증":
        if is_regional_center:
            return f"이 병원은 대형 권역센터이나, 문장 분석 결과 일반 의료기관 우선 안내가 가능한 상황으로 분류되어 응급실 과밀화 방지 대기 패널티(+30분)가 반영되었습니다. 인근 종합병원 이용을 권장합니다."
        else:
            return f"문장 분석 결과 일반 의료기관 우선 안내가 가능한 상황으로 분류되어, 대형 권역센터 대신 인근의 종합병원/야간진료 병원으로 우선 추천되었습니다. 예상 소요 시간은 {expected_time_minutes}분({eta_desc}){penalty_text}입니다."
        
    if not symptoms:
        return f"이 병원은 일반 응급실 가용 병상이 {hvec}개 있으며, 현재 위치에서 예상 소요 시간은 {expected_time_minutes}분({eta_desc})입니다."
        
    if acceptance_status == "수용 가능 확인":
        return f"이 병원은 [{symptoms_str}] 수용이 가능하며, 응급실 가용 병상 {hvec}개가 확보되어 있습니다. 예상 소요 시간은 {expected_time_minutes}분({eta_desc}){penalty_text}으로 처치가 가능해 우선 추천되었습니다."
    elif acceptance_status == "정보 미제공 - 전화 확인 필요":
        return f"이 병원은 예상 소요 시간 {expected_time_minutes}분({eta_desc}){penalty_text}으로 가까운 위치에 있으나, [{symptoms_str}] 수용 여부가 정보미제공 상태이므로 이송 전 전화 확인이 필요합니다."
    else:
        return f"이 병원은 예상 소요 시간은 {expected_time_minutes}분({eta_desc}){penalty_text}이며, 이송 전 상세 수용 정보를 확인하시길 권장합니다."

@app.post("/api/analyze-symptoms")
def analyze_symptoms_api(req: AnalyzeRequest):
    """자연어 증상 텍스트를 분석하여 구조화된 키워드 배열과 중증도를 반환합니다."""
    import llm_engine
    extracted_data = llm_engine.extract_symptoms(
        req.text,
        mode=req.mode or 'citizen',
        patient_info=req.patient_info
    )
    return {
        "status": "success",
        "extracted_symptoms": extracted_data.get("symptoms", []),
        "severity": extracted_data.get("severity", "중증"),
        "care_route": extracted_data.get("care_route", "emergency"),
        "general_departments": extracted_data.get("general_departments", []),
        "route_reason": extracted_data.get("route_reason", ""),
        "is_ai_error": extracted_data.get("is_ai_error", False)
    }

@app.post("/api/route")
def get_route(req: RouteRequest):
    """카카오 모빌리티 경로 API에서 실제 도로 경로 좌표를 반환합니다. API 실패 시 직선 경로로 대체합니다."""
    fallback_path = [[req.origin_lat, req.origin_lon], [req.dest_lat, req.dest_lon]]

    kakao_key = os.getenv("KAKAO_API_KEY")
    if not kakao_key:
        return {"status": "success", "path": fallback_path, "source": "fallback"}

    url = "https://apis-navi.kakaomobility.com/v1/directions"
    headers = {"Authorization": f"KakaoAK {kakao_key}"}
    params = {
        "origin": f"{req.origin_lon},{req.origin_lat}",
        "destination": f"{req.dest_lon},{req.dest_lat}",
        "priority": "TIME"
    }

    try:
        res = requests.get(url, headers=headers, params=params, timeout=5)
        res.raise_for_status()
        data = res.json()

        routes = data.get("routes", [])
        if not routes or routes[0].get("result_code") != 0:
            return {"status": "success", "path": fallback_path, "source": "fallback"}

        # vertexes 배열은 [lon1, lat1, lon2, lat2, ...] 순서 — Leaflet용 [lat, lon]으로 변환
        path = []
        for section in routes[0].get("sections", []):
            for road in section.get("roads", []):
                verts = road.get("vertexes", [])
                for i in range(0, len(verts) - 1, 2):
                    path.append([verts[i + 1], verts[i]])

        if not path:
            return {"status": "success", "path": fallback_path, "source": "fallback"}

        return {"status": "success", "path": path, "source": "kakao"}
    except Exception:
        return {"status": "success", "path": fallback_path, "source": "fallback"}

@app.post("/api/recommend-light")
def recommend_light_hospitals(req: RecommendRequest):
    """
    경증 환자는 응급실 대신 가까운 일반 병원/의원으로 분산 안내합니다.
    - 진료과 멀티 검색: AI가 추출한 과목 코드 최대 2개를 각각 HIRA API로 검색·병합합니다.
    - 동적 반경 확장: 결과 < 3개이면 30km → 50km로 자동 확장합니다.
    - 기관 종별 우선순위: 경증 환자에게는 의원(1) → 병원(11) → 종합병원(21) 순으로 정렬합니다.
    """
    hira_key = os.getenv("HIRA_SERVICE_KEY")
    if not hira_key:
        return {
            "status": "error",
            "message": "HIRA_SERVICE_KEY가 설정되지 않았습니다. service/.env에 건강보험심사평가원 병원정보서비스 키를 추가해 주세요."
        }

    # AI가 추출한 진료과 목록에서 HIRA 과목코드 수집 (최대 2개, 중복 제거)
    dept_codes: list[str] = []
    for department in req.general_departments or []:
        code = HIRA_DEPARTMENT_CODES.get(department)
        if code and code not in dept_codes:
            dept_codes.append(code)
    if not dept_codes:
        for symptom in req.symptoms or []:
            code = HIRA_DEPARTMENT_CODES.get(symptom)
            if code and code not in dept_codes:
                dept_codes.append(code)
    dept_codes = dept_codes[:2]

    url = "https://apis.data.go.kr/B551182/hospInfoServicev2/getHospBasisList"
    target_region = normalize_region(req.region)

    def fetch_hira_rows(dept_code=None, radius=HIRA_SEARCH_RADIUS_DEFAULT):
        params = {
            "serviceKey": hira_key,
            "pageNo": "1",
            "numOfRows": str(HIRA_NUM_OF_ROWS),
            "sidoCd": HIRA_SIDO_CD,   # 전라남도 (config.py 관리)
            "xPos": str(req.lon),
            "yPos": str(req.lat),
            "radius": str(radius),
        }
        if dept_code:
            params["dgsbjtCd"] = dept_code
        res = requests.get(url, params=params, timeout=8)
        res.raise_for_status()
        data = xmltodict.parse(res.text)
        return get_hira_items(data)

    def collect_rows(codes, radius, existing=None):
        """codes 목록의 각 과목코드(None이면 전체)로 HIRA를 조회하고 ykiho 기준으로 dedup."""
        rows: dict = dict(existing) if existing else {}
        for code in codes:
            for row in fetch_hira_rows(dept_code=code, radius=radius):
                key = row.get("ykiho") or f"{row.get('yadmNm')}-{row.get('YPos')}-{row.get('XPos')}"
                rows.setdefault(key, row)
        return rows

    def filter_and_normalize(rows):
        result = []
        for row in rows.values():
            if target_region and not region_allowed(row.get("addr", ""), [target_region]):
                continue
            item = normalize_hira_hospital(row, req.lat, req.lon, req.symptoms or [])
            if item:
                result.append(item)
        return result

    # 경증 환자: 의원(1) → 병원(11) → 종합병원(21) → 상급종합(31) 순 우선
    INST_PRIORITY = {"1": 0, "11": 1, "21": 2, "31": 3}

    try:
        # 1단계: 진료과별 멀티 검색 (기본 반경)
        search_codes = dept_codes if dept_codes else [None]
        raw_rows = collect_rows(search_codes, radius=HIRA_SEARCH_RADIUS_DEFAULT)
        normalized = filter_and_normalize(raw_rows)

        # 2단계: 결과 부족 시 진료과 무관 전체 검색 추가 (기본 반경)
        if len(normalized) < 3 and dept_codes:
            raw_rows = collect_rows([None], radius=HIRA_SEARCH_RADIUS_DEFAULT, existing=raw_rows)
            normalized = filter_and_normalize(raw_rows)

        # 3단계: 여전히 부족하면 반경 확장 (도서·산간 대응, config.HIRA_SEARCH_RADIUS_EXPANDED)
        if len(normalized) < 3:
            raw_rows = collect_rows([None], radius=HIRA_SEARCH_RADIUS_EXPANDED, existing=raw_rows)
            normalized = filter_and_normalize(raw_rows)

        # 4단계: 기관 종별 우선순위 + ETA 기준 정렬
        normalized.sort(key=lambda h: (
            INST_PRIORITY.get(h.get("cl_cd", ""), 1),
            h["expected_time_minutes"],
            h["distance_km"],
        ))

        return {
            "status": "success",
            "severity": "경증",
            "region_scope": target_region or "지역 미지정",
            "total_recommended": len(normalized),
            "data": normalized[:5]
        }
    except Exception as e:
        return {"status": "error", "message": f"일반 병원 추천 조회 실패: {str(e)}"}

def diversify_by_region(results: list, user_region: Optional[str] = None, max_per_region: int = 2, total: int = 5) -> list:
    """
    공공데이터 병원 소재지(dutyAddr)를 시군 단위로 파싱하여
    같은 시군에서 최대 max_per_region개만 추천되도록 결과를 다양화합니다.
    사용자의 실제 거주/현재 지역(user_region) 병원은 다양화 제한(max_per_region)을 받지 않고 우선 추천됩니다.
    정렬 우선순위(수용가능 > 기대시간)는 유지하되, 타 지역 쏠림을 방지합니다.
    """
    ALL_REGIONS = list(NEARBY_REGIONS.keys())

    def extract_region_from_addr(addr: str) -> str:
        for region in ALL_REGIONS:
            if region in (addr or ""):
                return region
        return "기타"

    region_count: dict = {}
    selected = []
    deferred = []

    for hospital in results:
        region = extract_region_from_addr(hospital.get("dutyAddr", ""))
        hospital["region_label"] = region  # 프론트에서 시군명 표시용
        
        # 사용자의 실제 위치와 병원의 지역이 일치한다면 다양성 필터 패널티(개수 제한) 제외
        is_user_region = user_region and (user_region in region or region in user_region)
        
        if is_user_region or region_count.get(region, 0) < max_per_region:
            region_count[region] = region_count.get(region, 0) + 1
            selected.append(hospital)
        else:
            deferred.append(hospital)
        if len(selected) >= total:
            break

    # 다양성 확보 후에도 5개 미만이면 deferred에서 기대시간순으로 채움
    for hospital in deferred:
        if len(selected) >= total:
            break
        selected.append(hospital)

    return selected


@app.post("/api/recommend")
def recommend_hospitals(req: RecommendRequest):
    """
    환자의 위치와 증상을 받아 '응급실 뺑뺑이 방지' 및 '경증 환자 분산' 로직이 적용된 최적의 병원 리스트를 추천합니다.
    """
    severity = "중증"  # 기본값은 중증
    if req.severity:
        severity = req.severity

    ai_error = False
    if req.raw_text and not req.symptoms:
        import llm_engine
        extracted_data = llm_engine.extract_symptoms(req.raw_text)
        extracted_symptoms = extracted_data.get("symptoms", [])
        ai_error = extracted_data.get("is_ai_error", False)
        if not req.severity:
            severity = extracted_data.get("severity", "중증")
        # 프론트에서 증상 배열을 넘기지 않은 예외 상황에만 자연어를 분석합니다.
        req.symptoms = list(set(req.symptoms + extracted_symptoms))
        req.general_departments = extracted_data.get("general_departments", [])

    if not os.path.exists(DB_PATH):
        return {"status": "error", "message": "DB 파일을 찾을 수 없습니다."}

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    query = """
    SELECT 
        b.hpid, b.phpid, b.dutyName,
        e.hvec, e.hvoc, e.hvgc, e.hv4, e.hv5,
        e.hvicc, e.hvcc, e.hvccc, e.hvncc, e.hv2, e.hv3, e.hv6, e.hv7, e.hv8, e.hv9,
        e.hvctayn, e.hvmriayn, e.hvangioayn, e.hvventiayn, e.hv10, e.hv11, e.hvamyn,
        e.hvdnm, e.hv1, e.hv12,
        b.dutyTel1,
        b.dutyTel3, 
        e.hvidate, b.dutyAddr, b.wgs84Lat, b.wgs84Lon, b.is_realtime_available, d.acceptance_json
    FROM hospital_basic_info b
    LEFT JOIN (
        SELECT e1.* FROM emergency_room_beds e1
        INNER JOIN (
            SELECT hpid, MAX(hvidate) as max_hvidate
            FROM emergency_room_beds GROUP BY hpid
        ) e2 ON e1.hpid = e2.hpid AND e1.hvidate = e2.max_hvidate
    ) e ON b.hpid = e.hpid
    LEFT JOIN disease_acceptance d ON b.hpid = d.hpid
    """
    cursor.execute(query)
    rows = cursor.fetchall()
    conn.close()
    
    # AI가 추출한 증상 카테고리를 공공데이터 중증질환 수용 가능 코드로 변환
    # 출처: 국립중앙의료원 응급의료포털 공공데이터 API - 응급의료기관 중증질환자 수용가능 정보 조회 서비스
    # MKioskTy 코드 정의: 1=뇌졸중, 3=심장질환, 4=복부외상, 5=사지절단, 7=신장투석, 10=소아응급, 11=화상
    symptom_mapping = {
        "뇌졸중": "MKioskTy1",    # 뇌졸중 수용 가능 여부
        "심근경색": "MKioskTy3",  # 심장질환(심근경색/협심증) 수용 가능 여부
        "흉통":    "MKioskTy3",   # 심장질환 동일 코드 사용 (흉통은 심장질환 수용 여부와 연동)
        "복부손상": "MKioskTy4",  # 복부외상 수용 가능 여부
        "사지접합": "MKioskTy5",  # 사지절단 및 접합 수용 가능 여부
        "소아":    "MKioskTy10",  # 소아 응급 수용 가능 여부
        "화상":    "MKioskTy11",  # 화상 환자 수용 가능 여부
        "투석":    "MKioskTy7",   # 투석(신장) 가능 여부
    }
    
    allowed_regions = get_allowed_emergency_regions(req.region)
    results = []
    for row in rows:
        item = dict(row)
        if not region_allowed(item.get("dutyAddr", ""), allowed_regions):
            continue
        
        # [필터링 1] 위도/경도가 없는 폐업/오류 병원 제외
        if not item["wgs84Lat"] or not item["wgs84Lon"]:
            continue
            
        # [필터링 2] 실시간 정보가 미연동되었거나 응급실 병상(hvec)이 0개 이하면 제외
        is_realtime = item.get("is_realtime_available") or 0
        hvec = item["hvec"] if item["hvec"] is not None else 0
        if is_realtime == 0 or hvec <= 0:
            continue
            
        # [필터링 3] 증상 기반 중증질환 수용 여부 확인
        acceptance_info = {}
        if item.get("acceptance_json"):
            try:
                acceptance_info = json.loads(item["acceptance_json"])
            except:
                pass
                
        # [필터링 3] 공공데이터가 "정보미제공"인 병원은 탈락시키지 않고 확인 필요로 표시
        can_treat, acceptance_status, acceptance_checks = evaluate_acceptance(
            acceptance_info,
            req.symptoms,
            symptom_mapping
        )
        
        if not can_treat:
            continue # 치료 불가능하므로 추천 후보에서 탈락
            
        # [점수 산출] ETA 및 기대 시간(Expected Time) 계산
        hosp_lat = float(item["wgs84Lat"])
        hosp_lon = float(item["wgs84Lon"])
        eta_minutes, eta_source = routing.get_eta_minutes(req.lat, req.lon, hosp_lat, hosp_lon)
        expected_time_minutes = routing.calculate_expected_time(hvec, eta_minutes)
        
        # 도서·산간 패널티 추가
        island_penalty, island_region = get_island_penalty(req.lat, req.lon)
        penalty_reasons = []
        if island_penalty > 0:
            expected_time_minutes += island_penalty
            penalty_reasons.append(f"도서·산간 지역 이동 패널티 ({island_region})")
        
        # 장비 및 중환자실 패널티 적용
        equipment_penalty, equip_reasons = calculate_equipment_penalty(item, req.symptoms)
        expected_time_minutes = expected_time_minutes + equipment_penalty
        penalty_reasons.extend(equip_reasons)
        
        # [경증 환자 분산 라우팅 로직]
        # REGIONAL_CENTER_HPIDS는 config.py에서 모듈 레벨로 import됨
        is_regional_center = item["hpid"] in REGIONAL_CENTER_HPIDS
        if severity == "경증" and is_regional_center:
            expected_time_minutes += PENALTY_REGIONAL_CENTER_LIGHT   # 경증 권역센터 분산 패널티 (config.py)
            penalty_reasons.append("경증 환자 대형 응급실 분산 유도")
            
        expected_time_minutes = round(expected_time_minutes, 2)
        
        # 추천 사유 동적 생성
        recommend_reason = generate_recommend_reason(
            hvec, expected_time_minutes, eta_source, req.symptoms, acceptance_status, penalty_reasons, severity, is_regional_center
        )
        
        item["eta_minutes"] = eta_minutes
        item["eta_source"] = eta_source
        item["expected_time_minutes"] = expected_time_minutes
        item["status"] = get_bed_status(hvec)
        item["is_regional_center"] = is_regional_center   # 프론트 배지 표시용 플래그
        item["acceptance_status"] = acceptance_status
        item["acceptance_checks"] = acceptance_checks
        item["recommend_reason"] = recommend_reason
        
        # 프론트엔드로 보낼 때 필요 없는 내부 데이터 정리
        if "acceptance_json" in item:
            del item["acceptance_json"]
            
        results.append(item)
        
    # 수용 가능이 확인된 병원을 먼저 보여주고, 같은 상태에서는 기대 시간이 짧은 순서로 정렬
    status_priority = {
        "수용 가능 확인": 0,
        "정보 미제공 - 전화 확인 필요": 1,
        "증상 코드 매칭 없음": 2
    }
    results.sort(key=lambda x: (
        status_priority.get(x["acceptance_status"], 9),
        x["expected_time_minutes"]
    ))

    return {
        "status": "success",
        "severity": severity,
        "is_ai_error": ai_error,
        "region_scope": ", ".join(allowed_regions) if allowed_regions else "지역 미지정",
        "total_recommended": len(results),
        # 공공데이터 소재지 주소를 시군 단위로 파싱하여 지역 다양성 보장 후 상위 5개 추천
        # 사용자의 현재 지역 병원은 상한 제한 없이 우선 추천
        "data": diversify_by_region(results, user_region=req.region)
    }

if __name__ == "__main__":
    import uvicorn
    # 로컬 테스트용 실행: python main.py
    # 포트는 config.SERVER_PORT 또는 .env의 SERVER_PORT 환경변수로 덮어쓸 수 있습니다.
    port = int(os.getenv("SERVER_PORT", str(SERVER_PORT)))
    uvicorn.run(app, host="0.0.0.0", port=port)
