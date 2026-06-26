import requests
import xmltodict
import sqlite3
import os
import json
import re
from dotenv import load_dotenv

"""
전라남도 응급의료 공공데이터 수동 갱신 스크립트.

일일 트래픽 제한을 고려해 자동 주기 호출 대신 관리자가 필요할 때 직접 실행합니다.
실행하면 병원 기본 정보, 중증질환 수용 정보, 최신 응급실 병상 정보를 hospital.db에 반영합니다.
3분 단위 자동 갱신은 운영 단계의 발전 가능성으로 분리합니다.
"""

# 상위 폴더(service)에 있는 .env 파일 로드
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(BASE_DIR, ".env"))

SERVICE_KEY = os.getenv("SERVICE_KEY", "")

BASE_PARAMS = {
    "serviceKey": SERVICE_KEY,
    "pageNo": "1",
    "numOfRows": "200" # 전라남도 전체 조회를 위해 넉넉하게 200 설정
}

def get_items(data):
    """API 응답 데이터에서 item 리스트를 안전하게 추출합니다."""
    body = data.get("response", {}).get("body", {})
    if not body or not body.get("items"):
        return []
    items = body["items"].get("item", [])
    if not isinstance(items, list):
        return [items]
    return items

def clean_hospital_name(raw_name):
    """불필요한 의료법인, 재단 명칭을 제거하여 깔끔한 병원명 추출"""
    if not raw_name:
        return ""
    # 예: "재단법인OO병원", "학교법인OO병원", "(의료법인)OO병원" 등 다양한 형태 정제
    cleaned = re.sub(r'\((의료|재단|사단|사회복지|학교|합자|주식|유한)법인\)|(의료|재단|사단|사회복지|학교|합자|주식|유한)법인\s*([^\s]*재단)?\s*|\(주\)|\(유\)', '', raw_name)
    return cleaned.strip()

def to_nonnegative_int(value):
    if value in (None, ""):
        return 0
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0

def ensure_column(cursor, table_name, column_name, column_type):
    columns = [row[1] for row in cursor.execute(f"PRAGMA table_info({table_name})")]
    if column_name not in columns:
        cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}")

# 1. 응급의료기관 기본정보 및 위치 (getEgytListInfoInqire)
def fetch_hospital_basic_info(cursor):
    url = "https://apis.data.go.kr/B552657/ErmctInfoInqireService/getEgytListInfoInqire"
    params = BASE_PARAMS.copy()
    params.update({
        "Q0": "전라남도"
        # "Q1": "목포시" (주석 처리하여 전라남도 전체 조회)
    })
    
    try:
        res = requests.get(url, params=params, timeout=10)
        res.raise_for_status()
        data = xmltodict.parse(res.text)
        items = get_items(data)
            
        for item in items:
            hpid = item.get("hpid")
            phpid = item.get("phpid")
            raw_dutyName = item.get("dutyName")
            dutyName = clean_hospital_name(raw_dutyName)
            dutyAddr = item.get("dutyAddr")
            dutyTel1 = item.get("dutyTel1")
            dutyTel3 = item.get("dutyTel3")
            wgs84Lat = item.get("wgs84Lat")
            wgs84Lon = item.get("wgs84Lon")
            
            # 좌표가 없는(누락된) 폐업/휴업 기관 등은 라우팅에 쓸 수 없으므로 필터링(제외)
            if not wgs84Lat or not wgs84Lon or float(wgs84Lat) == 0.0 or float(wgs84Lon) == 0.0:
                print(f" [필터링] 좌표 누락 병원 제외: {raw_dutyName}")
                continue
            
            cursor.execute('''
                INSERT INTO hospital_basic_info (hpid, phpid, dutyName, dutyAddr, dutyTel1, dutyTel3, wgs84Lat, wgs84Lon)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(hpid) DO UPDATE SET
                    phpid=excluded.phpid,
                    dutyName=excluded.dutyName,
                    dutyAddr=excluded.dutyAddr,
                    dutyTel1=excluded.dutyTel1,
                    dutyTel3=excluded.dutyTel3,
                    wgs84Lat=excluded.wgs84Lat,
                    wgs84Lon=excluded.wgs84Lon
            ''', (hpid, phpid, dutyName, dutyAddr, dutyTel1, dutyTel3, wgs84Lat, wgs84Lon))
        print(f" 기본 정보 수집 완료 ({len(items)}개 중 유효 병원 추출)")
    except Exception as e:
        print(f" 기본 정보 수집 실패 (기존 데이터 유지): {e}")

# 2. 중증질환자 수용가능정보 (getSrsillDissAceptncPosblInfoInqire)
def fetch_disease_acceptance(cursor):
    url = "https://apis.data.go.kr/B552657/ErmctInfoInqireService/getSrsillDissAceptncPosblInfoInqire"
    params = BASE_PARAMS.copy()
    params.update({
        "STAGE1": "전라남도"
        # "STAGE2": "목포시" (전라남도 전체 조회)
    })
    
    try:
        res = requests.get(url, params=params, timeout=10)
        res.raise_for_status()
        data = xmltodict.parse(res.text)
        items = get_items(data)
            
        for item in items:
            hpid = item.get("hpid")
            # 질환별 코드가 매우 많으므로(MKioskTy1~28), 확장성을 위해 JSON 문자열로 통째로 저장합니다.
            acceptance_data = json.dumps(item, ensure_ascii=False)
            
            cursor.execute('''
                INSERT INTO disease_acceptance (hpid, acceptance_json)
                VALUES (?, ?)
                ON CONFLICT(hpid) DO UPDATE SET
                    acceptance_json=excluded.acceptance_json
            ''', (hpid, acceptance_data))
        print(f" 중증질환자 수용가능정보 수집 완료 ({len(items)}개 병원)")
    except Exception as e:
        print(f" 중증질환자 수용가능정보 수집 실패 (기존 데이터 유지): {e}")

# 3. 실시간 가용병상정보 (getEmrrmRltmUsefulSckbdInfoInqire)
def fetch_realtime_beds(cursor):
    url = "https://apis.data.go.kr/B552657/ErmctInfoInqireService/getEmrrmRltmUsefulSckbdInfoInqire"
    params = BASE_PARAMS.copy()
    params.update({
        "STAGE1": "전라남도"
        # "STAGE2": "목포시" (전라남도 전체 조회)
    })
    
    try:
        res = requests.get(url, params=params, timeout=10)
        res.raise_for_status()
        data = xmltodict.parse(res.text)
        items = get_items(data)
        if not items:
            print(" 실시간 가용병상정보: 수신된 항목 없음 (기존 플래그 유지)")
            return
        # 실시간 데이터 시작 전, 모든 병원의 실시간 가용 여부를 0으로 초기화
        cursor.execute("UPDATE hospital_basic_info SET is_realtime_available = 0")
            
        for item in items:
            hpid = item.get("hpid")
            hvidate = item.get("hvidate")

            realtime_values = {
                "phpid": item.get("phpid"),
                "hvdnm": item.get("hvdnm"),
                "hvec": to_nonnegative_int(item.get("hvec")),
                "hvoc": to_nonnegative_int(item.get("hvoc")),
                "hvgc": to_nonnegative_int(item.get("hvgc")),
                "hv4": to_nonnegative_int(item.get("hv4")),
                "hv5": to_nonnegative_int(item.get("hv5")),
                "hvicc": to_nonnegative_int(item.get("hvicc")),
                "hvcc": to_nonnegative_int(item.get("hvcc")),
                "hvccc": to_nonnegative_int(item.get("hvccc")),
                "hvncc": to_nonnegative_int(item.get("hvncc")),
                "hv2": to_nonnegative_int(item.get("hv2")),
                "hv3": to_nonnegative_int(item.get("hv3")),
                "hv6": to_nonnegative_int(item.get("hv6")),
                "hv7": to_nonnegative_int(item.get("hv7")),
                "hv8": to_nonnegative_int(item.get("hv8")),
                "hv9": to_nonnegative_int(item.get("hv9")),
                "hvctayn": item.get("hvctayn"),
                "hvmriayn": item.get("hvmriayn"),
                "hvangioayn": item.get("hvangioayn"),
                "hvventiayn": item.get("hvventiayn"),
                "hv10": item.get("hv10"),
                "hv11": item.get("hv11"),
                "hvamyn": item.get("hvamyn"),
                "hv1": item.get("hv1"),
                "hv12": item.get("hv12"),
            }
            
            # 수동 갱신 1회 실행에서 받은 최신 병상 값을 저장합니다. (ON CONFLICT DO UPDATE 적용)
            cursor.execute('''
                INSERT INTO emergency_room_beds (
                    hpid, phpid, hvdnm, hvec, hvoc, hvgc, hv4, hv5,
                    hvicc, hvcc, hvccc, hvncc, hv2, hv3, hv6, hv7, hv8, hv9,
                    hvctayn, hvmriayn, hvangioayn, hvventiayn, hv10, hv11, hvamyn,
                    hv1, hv12, hvidate
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(hpid, hvidate) DO UPDATE SET
                    phpid=excluded.phpid,
                    hvdnm=excluded.hvdnm,
                    hvec=excluded.hvec,
                    hvoc=excluded.hvoc,
                    hvgc=excluded.hvgc,
                    hv4=excluded.hv4,
                    hv5=excluded.hv5,
                    hvicc=excluded.hvicc,
                    hvcc=excluded.hvcc,
                    hvccc=excluded.hvccc,
                    hvncc=excluded.hvncc,
                    hv2=excluded.hv2,
                    hv3=excluded.hv3,
                    hv6=excluded.hv6,
                    hv7=excluded.hv7,
                    hv8=excluded.hv8,
                    hv9=excluded.hv9,
                    hvctayn=excluded.hvctayn,
                    hvmriayn=excluded.hvmriayn,
                    hvangioayn=excluded.hvangioayn,
                    hvventiayn=excluded.hvventiayn,
                    hv10=excluded.hv10,
                    hv11=excluded.hv11,
                    hvamyn=excluded.hvamyn,
                    hv1=excluded.hv1,
                    hv12=excluded.hv12
            ''', (
                hpid,
                realtime_values["phpid"],
                realtime_values["hvdnm"],
                realtime_values["hvec"],
                realtime_values["hvoc"],
                realtime_values["hvgc"],
                realtime_values["hv4"],
                realtime_values["hv5"],
                realtime_values["hvicc"],
                realtime_values["hvcc"],
                realtime_values["hvccc"],
                realtime_values["hvncc"],
                realtime_values["hv2"],
                realtime_values["hv3"],
                realtime_values["hv6"],
                realtime_values["hv7"],
                realtime_values["hv8"],
                realtime_values["hv9"],
                realtime_values["hvctayn"],
                realtime_values["hvmriayn"],
                realtime_values["hvangioayn"],
                realtime_values["hvventiayn"],
                realtime_values["hv10"],
                realtime_values["hv11"],
                realtime_values["hvamyn"],
                realtime_values["hv1"],
                realtime_values["hv12"],
                hvidate,
            ))
            
            # 실시간 데이터가 성공적으로 수집된 병원은 플래그를 1로 지정
            cursor.execute("UPDATE hospital_basic_info SET is_realtime_available = 1 WHERE hpid = ?", (hpid,))
        print(f" 실시간 가용병상정보 수집 완료 ({len(items)}개 병원)")
    except Exception as e:
        print(f" 실시간 가용병상정보 수집 실패 (기존 데이터 유지): {e}")

def init_db(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 1. 기본 정보 테이블 (위도/경도, 주소 포함)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS hospital_basic_info (
            hpid TEXT PRIMARY KEY,
            phpid TEXT,
            dutyName TEXT,
            dutyAddr TEXT,
            dutyTel1 TEXT,
            dutyTel3 TEXT,
            wgs84Lat TEXT,
            wgs84Lon TEXT
        )
    ''')
    ensure_column(cursor, "hospital_basic_info", "phpid", "TEXT")
    ensure_column(cursor, "hospital_basic_info", "is_realtime_available", "INTEGER DEFAULT 0")
    
    # 2. 중증질환 수용정보 테이블
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS disease_acceptance (
            hpid TEXT PRIMARY KEY,
            acceptance_json TEXT
        )
    ''')
    
    # 3. 실시간 병상정보 테이블
    # hpid+hvidate 기준으로 누적 저장하여 병상 변화 추이를 조회할 수 있게 유지합니다.
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS emergency_room_beds (
            hpid TEXT,
            phpid TEXT,
            hvdnm TEXT,
            hvec INTEGER,
            hvoc INTEGER,
            hvgc INTEGER,
            hv4 INTEGER,
            hv5 INTEGER,
            hvicc INTEGER,
            hvcc INTEGER,
            hvccc INTEGER,
            hvncc INTEGER,
            hv2 INTEGER,
            hv3 INTEGER,
            hv6 INTEGER,
            hv7 INTEGER,
            hv8 INTEGER,
            hv9 INTEGER,
            hvctayn TEXT,
            hvmriayn TEXT,
            hvangioayn TEXT,
            hvventiayn TEXT,
            hv10 TEXT,
            hv11 TEXT,
            hvamyn TEXT,
            hv1 TEXT,
            hv12 TEXT,
            hvidate TEXT,
            PRIMARY KEY (hpid, hvidate)
        )
    ''')
    
    return conn, cursor

if __name__ == "__main__":
    db_path = os.path.join(os.path.dirname(__file__), "hospital.db")
    conn, cursor = init_db(db_path)
    
    print("수동 데이터 갱신을 시작합니다...")
    fetch_hospital_basic_info(cursor)
    fetch_disease_acceptance(cursor)
    fetch_realtime_beds(cursor)
    
    conn.commit()
    conn.close()
    print("\n 최신 데이터 저장이 완료되었습니다!")
