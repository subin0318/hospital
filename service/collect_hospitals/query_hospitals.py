import sqlite3
import os
import json

# DB 파일 경로 설정 (현재 스크립트와 같은 폴더에 있는 hospital.db)
db_path = os.path.join(os.path.dirname(__file__), "hospital.db")

def view_all_hospitals():
    # DB 파일이 존재하는지 확인
    if not os.path.exists(db_path):
        print(" DB 파일을 찾을 수 없습니다. 먼저 collect_hospitals.py를 실행해서 데이터를 수집해주세요.")
        return

    # DB 연결
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    query = """
    SELECT 
        b.dutyName, 
        e.hvec, 
        e.hvoc, 
        e.hvgc, 
        b.dutyTel3, 
        e.hvidate,
        b.dutyAddr,
        b.wgs84Lat,
        b.wgs84Lon,
        d.acceptance_json,
        b.is_realtime_available
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
    except sqlite3.OperationalError as e:
        print("DB 스키마가 맞지 않습니다. collect_hospitals.py를 다시 실행해서 DB를 새로 구성해주세요.")
        print(f"상세 에러: {e}")
        return
    
    print(f"\n 현재 전라남도 응급의료기관 종합 정보 (총 {len(rows)}곳)\n")
    print("=" * 60)
    
    for row in rows:
        dutyName = row[0]
        hvec = row[1] if row[1] is not None else 0
        hvoc = row[2] if row[2] is not None else 0
        hvgc = row[3] if row[3] is not None else 0
        dutyTel3 = row[4] if row[4] else "정보없음"
        hvidate = row[5] if row[5] else ""
        dutyAddr = row[6] if row[6] else "정보없음"
        lat = row[7] if row[7] else "정보없음"
        lon = row[8] if row[8] else "정보없음"
        acceptance_json = row[9]
        is_realtime = row[10] if len(row) > 10 and row[10] is not None else 0
        
        # 날짜/시간 포맷 변환 (20260624231442 -> 2026-06-24 23:14:42)
        if hvidate and len(hvidate) >= 14:
            hvidate_fmt = f"{hvidate[:4]}-{hvidate[4:6]}-{hvidate[6:8]} {hvidate[8:10]}:{hvidate[10:12]}:{hvidate[12:14]}"
        else:
            hvidate_fmt = hvidate if hvidate else "불가"
            
        # 가용 병상 수에 따른 직관적인 상태 표시 (3단계 동기화)
        if hvec >= 6:
            status = "원활"
        elif hvec >= 1:
            status = "보통"
        else:
            status = "혼잡"
            
        realtime_status = "연동 완료" if is_realtime == 1 else "연동 실패/미전송"
        
        print(f"[{status}] {dutyName} ({realtime_status})")
        print(f" ‣ 주소: {dutyAddr} (좌표: {lat}, {lon})")
        print(f" ‣ 가용병상: 응급실 {hvec}개 / 수술실 {hvoc}개 / 입원실 {hvgc}개")
        print(f" ‣ 응급실 전화: {dutyTel3}")
        
        # 중증질환 수용가능 정보 분석 (Y인 항목 갯수 파악 등)
        if acceptance_json:
            try:
                acc_data = json.loads(acceptance_json)
                # 'Y' 로 표시된(수용가능한) 질환 갯수 세기
                capable_count = sum(1 for k, v in acc_data.items() if k.startswith('MKioskTy') and v == 'Y')
                print(f" ‣ 중증질환 수용: 총 {capable_count}개 질환 수용 가능 표시됨")
            except:
                print(" ‣ 중증질환 수용: 데이터 파싱 오류")
        else:
            print(" ‣ 중증질환 수용: 정보없음")
            
        print(f" ‣ 갱신시각: {hvidate_fmt}")
        print("-" * 60)
        
    conn.close()

if __name__ == "__main__":
    view_all_hospitals()


# ==========================================
# [hospital.db 테이블 및 속성(컬럼) 정보]
# ==========================================

# 1. hospital_basic_info (병원 기본 정보)
# - hpid: 병원 고유 ID (다른 데이터와 연결하는 핵심 키)
# - phpid: 기관 ID
# - dutyName: 병원 이름 (예: 목포한국병원)
# - dutyAddr: 병원 주소
# - dutyTel1: 병원 대표 전화번호
# - dutyTel3: 응급실 직통 전화번호
# - wgs84Lat: 위도 (지도 표시 및 거리 계산용)
# - wgs84Lon: 경도

# 2. disease_acceptance (중증질환 수용 여부)
# - hpid: 병원 고유 ID
# - acceptance_json: 질환별 수용 가능 여부 JSON (예: MKioskTy1~28)

# 3. emergency_room_beds (실시간 병상 및 장비 정보)
# - hpid: 병원 고유 ID
# - phpid: 기관 ID
# - hvdnm: 당직의
# - hvidate: 수동 갱신으로 가져온 병상 데이터 기준 시각
# [병상 정보]
# - hvec: 일반 응급실 가용 병상 수
# - hvoc: 수술실 가용 병상 수
# - hvgc: 입원실 가용 병상 수
# - hv1: 응급실 음압 격리 병상
# - hv12: 응급실 일반 격리 병상
# [중환자실(ICU) 정보]
# - hvicc: 일반 중환자실
# - hv2: 내과 중환자실
# - hv3: 외과 중환자실
# - hv4: 외과계 중환자실
# - hv5: 내과계 중환자실
# - hv6: 신경외과 중환자실
# - hv7: 약물 중환자실
# - hv8: 화상 중환자실
# - hv9: 외상 중환자실
# - hvcc: 소아 중환자실
# - hvccc: 신경과 중환자실
# - hvncc: 신생아 중환자실
# [장비 및 기타 가용 여부]
# - hvctayn: CT 가용 여부
# - hvmriayn: MRI 가용 여부
# - hvangioayn: 조영촬영기 가용 여부
# - hvventiayn: 인공호흡기 가용 여부
# - hvamyn: 구급차 가용 여부
# - hv10: 인큐베이터(보육기) 가용 여부
# - hv11: 소아 당직의 여부
