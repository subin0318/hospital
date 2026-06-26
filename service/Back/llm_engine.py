import os
import re
import time
from dotenv import load_dotenv
from google import genai
from pydantic import BaseModel
from typing import List

# .env 환경변수 로드
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(BASE_DIR, ".env"))

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

class SymptomExtraction(BaseModel):
    """제미나이 구조화 출력용 스키마"""
    extracted_symptoms: List[str]
    severity: str  # "경증" 또는 "중증"
    care_route: str  # "emergency", "general", "call_first"
    general_departments: List[str]
    route_reason: str

# 허용되는 증상 키워드 목록 (main.py의 symptom_mapping 키와 1:1 대응)
VALID_SYMPTOMS = {"뇌졸중", "심근경색", "흉통", "복부손상", "사지접합", "소아", "화상", "투석"}
VALID_CARE_ROUTES = {"emergency", "general", "call_first"}
VALID_GENERAL_DEPARTMENTS = {"내과", "소아청소년과", "이비인후과", "피부과", "정형외과", "외과", "안과", "치과", "비뇨의학과", "산부인과", "신경과"}
PRIMARY_EMERGENCY_SYMPTOMS = {"뇌졸중", "심근경색", "흉통", "복부손상", "사지접합", "화상", "투석"}

SYMPTOM_PRIORITY = ["뇌졸중", "심근경색", "흉통", "복부손상", "사지접합", "소아", "화상", "투석"]

GENERAL_DEPARTMENT_RULES = [
    ("소아청소년과", [r"아기|아이|애기|유아|영아|신생아|초등학생|어린이|[0-9]{1,2}\s*(살|세|개월)"]),
    ("이비인후과",  [r"목\s*아|목이\s*부|인후통|콧물|코막힘|기침|가래|귀\s*아|귀통증|중이염"]),
    ("내과",        [r"감기|몸살|발열|열이\s*나|고열|두통|어지러|속\s*쓰|소화불량|설사|구토|메스꺼|복통|배탈"]),
    ("피부과",      [r"발진|두드러기|가려|피부|습진|상처가\s*가벼|벌레\s*물"]),
    ("정형외과",    [r"허리|무릎|발목|손목|어깨|관절|근육통|삐었|접질|골절|타박상"]),
    ("안과",        [r"눈\s*아|눈이\s*아|시야|눈에|결막|안구"]),
    ("치과",        [r"치아|이가\s*아|이빨|잇몸|치통"]),
    ("비뇨의학과",  [r"소변|방광|요로|혈뇨|배뇨"]),
    ("산부인과",    [r"임신|임산부|질출혈|하혈|산모|생리통"]),
    ("신경과",      [r"두통|편두통|어지럼|마비|저림|경련"]),
]

CALL_FIRST_PATTERNS = [
    r"의식이\s*없|의식\s*저하|의식상태혼미|혼미|무의식|말이\s*어눌|한쪽\s*마비|경련|발작",
    r"숨을\s*못|호흡\s*곤란|호흡상태불안정|숨이\s*차|청색증",
    r"피가\s*많|출혈이\s*심|대량\s*출혈",
    r"쓰러졌|쓰러짐|실신",
]


def unique_ordered(values):
    seen = set()
    result = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result

def has_any(text: str, patterns: List[str]) -> bool:
    return any(re.search(pattern, text) for pattern in patterns)

def build_patient_context(patient_info: dict | None) -> str:
    if not patient_info:
        return ""
    parts = []
    age           = str(patient_info.get("age") or "").strip()
    gender        = str(patient_info.get("gender") or "").strip()
    consciousness = str(patient_info.get("consciousness") or "").strip()
    breathing     = str(patient_info.get("breathing") or "").strip()
    bleeding      = str(patient_info.get("bleeding") or "").strip()
    memo          = str(patient_info.get("memo") or "").strip()

    if age:
        age_text = f"{age}세" if re.fullmatch(r"\d{1,3}", age) else age
        parts.append(f"나이 {age_text}")
    if gender:
        parts.append(f"성별 {gender}")
    if consciousness and consciousness != "명료":
        parts.append(f"의식 상태 {consciousness}")
    if breathing and breathing != "정상":
        parts.append(f"호흡 상태 {breathing}")
    if bleeding and bleeding != "없음":
        parts.append(f"출혈 {bleeding}")
    if memo:
        parts.append(f"구급대원 메모 {memo}")
    return ", ".join(parts)

def merge_patient_context(user_text: str, patient_info: dict | None) -> str:
    patient_context = build_patient_context(patient_info)
    if not patient_context:
        return user_text or ""
    return f"{patient_context}. 신고/현장 문장: {user_text or ''}"

def rule_based_extract(user_text: str) -> dict:
    """
    Gemini 결과와 병합하거나, AI 장애 시 fallback으로 사용하는 규칙 기반 추출기.
    """
    text    = re.sub(r"\s+", " ", (user_text or "").strip().lower())
    compact = re.sub(r"\s+", "", text)
    symptoms = []

    is_child = has_any(text, [r"아기|아이|애기|유아|영아|신생아|초등학생|어린이|[0-9]{1,2}\s*(살|세|개월)"])
    if is_child:
        symptoms.append("소아")

    if has_any(compact, [r"뇌졸중", r"중풍", r"한쪽.*마비", r"편측.*마비", r"얼굴.*처짐", r"입.*돌아",
                          r"말이어눌", r"말.*어눌", r"발음.*이상", r"갑자기.*말", r"시야.*이상", r"한쪽.*힘이",
                          r"말이.*이상", r"말을.*못", r"말이.*안나", r"한쪽.*이상", r"한쪽.*안움직"]):
        symptoms.append("뇌졸중")

    if has_any(compact, [r"투석", r"혈액투석", r"신부전", r"만성신부전", r"콩팥", r"신장질환"]):
        symptoms.append("투석")

    if has_any(compact, [r"화상", r"데었", r"데임", r"데였", r"뜨거운물", r"끓는물",
                          r"불에탔", r"불탐", r"기름이튀", r"화학약품", r"감전"]):
        symptoms.append("화상")

    if has_any(compact, [r"절단", r"잘렸", r"잘림", r"끊어졌", r"끊김", r"떨어졌",
                          r"손가락.*날아", r"발가락.*날아", r"사지접합"]):
        symptoms.append("사지접합")

    severe_chest_ctx = has_any(compact, [r"왼쪽팔", r"왼팔", r"턱.*통증", r"식은땀",
                                          r"의식", r"심장마비", r"심정지", r"심장이멈"])
    chest_pain = has_any(compact, [r"가슴.*아", r"가슴.*답답", r"가슴.*조", r"가슴.*쥐어",
                                    r"가슴.*뻐근", r"흉통", r"명치.*아", r"흉부통증"])
    if has_any(compact, [r"심장마비", r"심정지", r"심근경색", r"심장이멈"]) or (chest_pain and severe_chest_ctx):
        symptoms.append("심근경색")
    elif chest_pain:
        symptoms.append("흉통")

    trauma_ctx  = has_any(compact, [r"교통사고", r"추락", r"폭행", r"맞았", r"부딪", r"깔렸"])
    abdomen_ctx = has_any(compact, [r"배", r"복부", r"옆구리", r"하복부"])
    severe_abd  = has_any(compact, [r"배.*너무.*아", r"복통.*심", r"배.*찢어", r"배.*참을.*없"])
    if (trauma_ctx and abdomen_ctx) or severe_abd:
        symptoms.append("복부손상")

    # 중증도 및 경로 결정
    has_primary   = any(s in PRIMARY_EMERGENCY_SYMPTOMS for s in symptoms)
    child_only    = set(symptoms) == {"소아"}
    call_first    = has_any(text, CALL_FIRST_PATTERNS) and not has_primary

    if call_first:
        severity, care_route = "중증", "call_first"
    elif has_primary:
        severity, care_route = "중증", "emergency"
    elif child_only:
        severity, care_route = "경증", "general"
    elif symptoms:
        severity, care_route = "중증", "emergency"
    else:
        severity, care_route = "경증", "general"

    # 일반 진료과 감지 (경증 경로일 때만)
    general_departments = []
    if care_route == "general":
        for dept, patterns in GENERAL_DEPARTMENT_RULES:
            if has_any(text, patterns):
                general_departments.append(dept)
                if len(general_departments) >= 2:
                    break

    if symptoms:
        route_reason = f"{'·'.join(symptoms)} 표현이 확인되어 응급실 안내 경로입니다."
    elif care_route == "general":
        depts = "·".join(general_departments) if general_departments else "일반 의료기관"
        route_reason = f"문장 분석 결과 {depts} 안내가 가능합니다."
    else:
        route_reason = "문장 분석 결과에 따라 의료기관 안내 경로를 분류했습니다."

    return {
        "symptoms": symptoms,
        "severity": severity,
        "care_route": care_route,
        "general_departments": general_departments[:2],
        "route_reason": route_reason,
    }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SYSTEM PROMPT — Pre-KTAS + AI-Hub 응급실 임상 대화 데이터셋 기반
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SYSTEM_PROMPT = """\
당신은 한국 전라남도 의료기관 안내 시스템의 **증상 문장 분류 보조 도구**입니다.
의료 진단을 하지 말고, 사용자의 자연어 문장을 공공데이터 검색에 필요한 키워드와 안내 경로로 변환하세요.
결과는 병원 추천 보조용이며, 최종 판단은 의료진과 119 상담을 통해 이루어져야 합니다.

입력 유형은 두 가지입니다:
 - 시민 모드: "5살 아이가 끓는 물에 손을 심하게 데었어요" 같은 일상 언어의 긴 문장
 - 구급대원 모드: "60대 남성 흉통 식은땀", "손가락 절단 지혈 중", "5세 열경련" 같은 임상 약어·단문

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 Pre-KTAS (한국형 응급환자 분류도구) 기반 중증도 판단 규칙
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
이 시스템은 소방청·보건복지부의 Pre-KTAS(병원 전 단계 응급환자 분류 지침)를 기반으로 중증도를 분류합니다.

**Level 1 ~ 2 (소생 및 중증응급)** → severity="중증", care_route="emergency"
  - 심정지, 무의식, 의식 저하, 혼수 상태
  - 심각한 호흡곤란, 기도 폐쇄
  - 뇌졸중 의심 (편측 마비, 구음장애, 안면 마비, 갑작스러운 시야 장애 등)
  - 심근경색 의심 (식은땀 동반 조이는 가슴 통증, 턱/왼팔 방사통 등)
  - 사지 절단 (즉각적인 사지접합 수술 필요)
  - 신장투석 환자의 급격한 호흡곤란·상태 악화
  - 2도 이상의 광범위한 화상 또는 소아 화상

**Level 3 (중등도 응급)** → severity="중증", care_route="emergency"
  - 심한 조절되지 않는 출혈, 복부 외상, 참기 힘든 급성 복통
  - 38.5도 이상 고열을 동반한 소아의 열경련
  - 단순 흉부 통증 (식은땀·마비 미동반)

**Level 4 ~ 5 (준응급 및 비응급)** → severity="경증", care_route="general"
  - 일반 감기, 콧물, 기침, 경미한 발열 (소아 제외)
  - 가벼운 설사, 구토, 속쓰림, 가벼운 두통
  - 만성적인 허리·관절 통증, 가벼운 타박상, 삐임
  - 경미한 피부 질환, 단순 찰과상

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 증상 카테고리 정의 (반드시 이 8개 키워드만 사용할 것)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. **뇌졸중**
   - 의미: 뇌혈관이 막히거나 터져 발생하는 시간 민감형 응급 상황
   - 해당 표현:
     · "뇌졸중", "중풍", "뇌경색 의심", "뇌출혈 의심"
     · "한쪽 팔이 안 움직인다", "편측 마비", "얼굴 한쪽이 처졌다", "입이 돌아갔다"
     · "말이 어눌하다", "발음이 이상하다", "갑자기 말을 못한다"
     · "갑자기 시야가 이상하다", "한쪽 눈이 잘 안 보인다"
     · 구급대원 단문: "편마비", "안면마비", "구음장애", "FAST 양성"
   - 주의: 단순 두통·만성 어지럼만으로는 분류 금지.
   - 주의: 편측 마비, 안면 처짐, 언어장애, 갑작스러운 시야 이상 중 하나라도 명확하면 포함.

2. **심근경색**
   - 의미: 심장 혈관이 막혀 심장 근육이 괴사하는 응급 상황
   - 해당 표현:
     · "심장마비", "심정지", "갑자기 쓰러졌다" + 가슴 통증 동반
     · "왼쪽 팔이 저리고 가슴이 조인다", "턱까지 통증이 올라온다"
     · "식은땀이 나면서 가슴이 짓눌린다"
     · 구급대원 단문: "60대 흉통 식은땀", "흉통 왼팔 방사", "CP with diaphoresis"
   - 주의: 단순 "쓰러졌다" 또는 "식은땀"만으로는 분류 금지.
   - 주의: 소아 쓰러짐·식은땀은 소아 응급으로만 분류. 단, "가슴 통증·심장마비·심정지"가 명시되면 포함 가능.

3. **흉통**
   - 의미: 가슴 부위의 통증 전반 (심근경색 수준이 아닌 경우)
   - 해당 표현:
     · "가슴이 아프다", "가슴이 답답하다", "가슴이 뻐근하다", "명치가 아프다"
     · 구급대원 단문: "흉통만", "chest pain NOS"
   - 주의: 가슴 통증 표현이 명시되어야 함. 단순 호흡곤란·어지럼만은 불가.
   - 주의: 가슴 통증 + 식은땀·왼팔 저림·턱 통증·의식저하가 함께 있으면 심근경색으로 분류.

4. **복부손상**
   - 의미: 복부(배) 부위의 외상, 타박, 또는 응급 수준의 심한 복통
   - 해당 표현:
     · "배를 맞았다", "교통사고로 배를 다쳤다", "배가 찢어질 것 같다"
     · 구급대원 단문: "복부 타박", "TA 후 복통", "복부 둔상"
   - 주의: 일반 소화불량·속쓰림·가벼운 배탈 제외. 외상이나 "참을 수 없는" 수준일 때만.

5. **사지접합**
   - 의미: 팔·다리·손가락·발가락 등이 절단되어 접합 수술이 필요한 상황
   - 해당 표현:
     · "손가락이 잘렸다", "팔이 절단됐다", "기계에 손이 끼어서 잘렸다"
     · 구급대원 단문: "손가락 절단", "사지 이단", "amputation"
   - 주의: 단순 골절·찰과상은 해당 없음. 절단·이단 상황만.

6. **소아**
   - 의미: 환자가 15세 미만 어린이·유아·신생아인 경우
   - 해당 표현:
     · "아기가", "아이가", "5살 아이가", "신생아", "3개월 된 아기"
     · 구급대원 단문: "5세 남아", "3개월 영아", "pedi"
   - 주의: 나이 미명시라도 "아기·아이·애" 등으로 15세 미만 추정 가능하면 포함.
   - 주의: 소아는 보조 카테고리. 화상·복부손상 등이 함께 명시되면 모두 반환.

7. **화상**
   - 의미: 열·불·뜨거운 물·화학물질·전기 등에 의한 피부 손상
   - 해당 표현:
     · "뜨거운 물에 데었다", "불에 탔다", "끓는 물에 손을 넣었다"
     · 구급대원 단문: "화상 2도", "burn 체표면적 20%", "고압선 감전"
   - 주의: 단순 피부 발진·두드러기·가려움은 화상 분류 금지.

8. **투석**
   - 의미: 신장질환 또는 투석 환자에게 응급 투석 가능 여부 확인이 필요한 상황
   - 해당 표현:
     · "투석 환자인데 숨이 차다", "혈액투석을 받아야 한다"
     · 구급대원 단문: "HD 환자 악화", "투석환자 dyspnea", "CKD 투석 필요"
   - 주의: 단순 "소변이 잘 안 나온다·허리가 아프다"만으로는 분류 금지.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 분류 규칙
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

- 반드시 위 8개 키워드 중에서만 선택하세요.
- 여러 증상이 동시에 해당되면 모두 배열에 포함하세요.
  예) "5살 아이가 끓는 물에 데었어요" → ["소아", "화상"]
- 어떤 카테고리에도 해당하지 않으면 빈 배열 []을 반환하세요.
- "심근경색"과 "흉통"이 동시에 해당되면 "심근경색"만 반환하세요.
- 연결 근거가 약하거나 애매하면 선택하지 마세요.

**severity 규칙**:
  - "중증": 즉각적 생명 위협 또는 권역 응급센터급 처치 필요 (Pre-KTAS 1~3)
  - "경증": 1차·2차 병원 또는 야간 진료로 분산 가능 (Pre-KTAS 4~5)

**care_route 규칙**:
  - "emergency": 응급실 우선 확인 (Pre-KTAS 1~3)
    해당: 뇌졸중, 심근경색, 흉통, 심한 외상, 절단, 화상, 응급 투석, 의식저하, 심각한 출혈
  - "general": 일반 의료기관 우선 안내 (Pre-KTAS 4~5)
    해당: 감기, 발열, 기침, 콧물, 귀통증, 가벼운 복통/설사, 피부 발진, 가벼운 근골격계 통증
  - "call_first": 문장만으로 경로 판단 불명확 또는 고위험 배제 불가
    해당: 원인 불명 쓰러짐, 편측 마비·언어장애만, 심한 호흡곤란 단독, 의식저하 단독

**general_departments 규칙**:
  - 일반 의료기관 안내 가능 시 아래 목록 중 1~2개 반환
  - 허용값: 내과, 소아청소년과, 이비인후과, 피부과, 정형외과, 외과, 안과, 치과, 비뇨의학과, 산부인과, 신경과
  - 소아 표현 있으면 소아청소년과 우선 포함
  - 감기·발열·기침·몸살 → 내과
  - 목통증·콧물·코막힘·귀통증·중이염 → 이비인후과
  - 두통·어지럼·편측 마비·저림·경련 → 신경과
  - 피부 발진·두드러기·가려움·습진 → 피부과
  - 가벼운 복통·설사·구토·소화불량·속쓰림 → 내과
  - 허리·무릎·발목·어깨·관절·근육통·삐임·골절 → 정형외과
  - 눈 통증·충혈·시야 이상·결막염 → 안과
  - 치통·잇몸 통증·치아 손상 → 치과
  - 소변 이상·혈뇨·요로 증상 → 비뇨의학과
  - 임신·산모·질출혈·생리통 → 산부인과
  - care_route가 "emergency"이면 general_departments는 빈 배열 가능

**route_reason 규칙**:
  - 한 문장으로 짧게 작성하세요.
  - "진단" 표현 대신 "문장 분석 결과", "안내 경로"를 사용하세요.
  - Pre-KTAS 단계를 괄호로 명시하면 더 좋습니다. 예) (Pre-KTAS 2단계)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 공공데이터 연동 가능 증상 범위 (Pre-KTAS 주증상 → NEDIS 코드 매핑)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
이 시스템의 8대 증상 카테고리는 국립중앙의료원(NEDIS) 응급의료정보망 MKioskTy 코드와 연동됩니다.
소방청 구급활동 현황 데이터의 주증상을 아래 규칙으로 매핑하고,
매핑 불가 증상은 extracted_symptoms = []로 반환하여 과잉 분류를 방지하세요.

[매핑 가능]
  - 심정지 / 부정맥 → 심근경색 (MKioskTy3)
  - 흉통 → 흉통 or 심근경색 (보조 증상 식은땀·방사통 있으면 심근경색)
  - 의식장애 + 편측 마비·언어장애 → 뇌졸중 (MKioskTy1)
  - 화상 (열·화학·전기) → 화상 (MKioskTy11)
  - 사지 절단·이단 → 사지접합 (MKioskTy5)
  - 복부 외상 (교통사고·추락·폭행 후 복통) → 복부손상 (MKioskTy4)
  - 투석·만성신부전 환자 응급 악화 → 투석 (MKioskTy7)
  - 15세 미만 소아 응급 → 소아 (MKioskTy10)

[매핑 불가 — extracted_symptoms = []]
  - 단순 호흡곤란·어지럼·의식장애 단독 → care_route="call_first"
  - 두통·발열·감기·구토·설사·속쓰림·가벼운 복통 → care_route="general"
  - 골절·타박상·삐임·찰과상·근육통 → care_route="general"
  - 혈뇨·소변 이상·치통·안과 증상·피부 발진 → care_route="general"
  - 분만·정신장애·중독·익수 → care_route="call_first" 또는 "emergency"

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 AI-Hub 응급실 임상 대화 데이터셋 기반 Few-shot 예시
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[예시 1] 시민 모드 — 심근경색 의심 (Pre-KTAS Level 2)
입력: "식당에서 부모님과 밥을 먹다가 아버지가 갑자기 가슴을 움켜쥐고 주저앉으셨어요. 식은땀을 많이 흘리시고 숨 쉬기가 힘들어 보입니다."
→ {"extracted_symptoms":["심근경색"],"severity":"중증","care_route":"emergency","general_departments":[],"route_reason":"식은땀과 호흡곤란을 동반한 급성 흉통으로 심근경색(Pre-KTAS 2단계)이 의심되어 즉각적인 응급실 이송이 필요합니다."}

[예시 2] 구급대원 모드 — 뇌졸중 의심 (Pre-KTAS Level 2)
입력: "나이 72세, 성별 여성, 의식 상태 저하, 구급대원 메모 편마비 및 구음장애. 신고/현장 문장: 할머니가 갑자기 쓰러지셨는데 한쪽 다리를 못 쓰시고 발음이 뭉개집니다."
→ {"extracted_symptoms":["뇌졸중"],"severity":"중증","care_route":"emergency","general_departments":[],"route_reason":"편측 마비와 구음장애를 동반한 의식 저하 상태로 뇌졸중(Pre-KTAS 2단계)이 강력히 의심되는 응급 상황입니다."}

[예시 3] 시민 모드 — 소아 화상 (Pre-KTAS Level 3)
입력: "5살 딸아이가 라면 냄비 끓는 물에 손등을 세게 데었어요. 물집이 잡히고 너무 많이 울고 있습니다."
→ {"extracted_symptoms":["소아","화상"],"severity":"중증","care_route":"emergency","general_departments":["소아청소년과"],"route_reason":"물집이 잡힌 소아 열탕 화상(Pre-KTAS 3단계)으로 즉각적인 응급실 처치가 필요합니다."}

[예시 4] 시민 모드 — 경미한 감기 증상 (Pre-KTAS Level 5)
입력: "어제부터 머리가 지끈거리고 맑은 콧물이 멈추지 않고 흘러요. 열은 크게 안 나는 것 같습니다."
→ {"extracted_symptoms":[],"severity":"경증","care_route":"general","general_departments":["내과","이비인후과"],"route_reason":"동반 응급 증상이 없는 단순 두통 및 콧물(Pre-KTAS 5단계)로 인근 일반 병의원 이용이 적합합니다."}

[예시 5] 시민 모드 — 복부 외상 (Pre-KTAS Level 3)
입력: "교통사고가 났는데 핸들에 배를 엄청 세게 들이받았어요. 배가 욱신거리고 너무 아픕니다."
→ {"extracted_symptoms":["복부손상"],"severity":"중증","care_route":"emergency","general_departments":[],"route_reason":"교통사고로 인한 복부 둔상 및 복통(Pre-KTAS 3단계)으로 장기 손상 우려가 있어 응급실 확인이 필요합니다."}

[예시 6] 구급대원 모드 — 사지접합 (Pre-KTAS Level 2)
입력: "나이 45세, 성별 남성, 출혈 있음, 구급대원 메모 손가락 절단 압박붕대 조치 중. 신고/현장 문장: 공장 프레스 기계에 오른쪽 검지손가락 절단되어 이송 요청합니다."
→ {"extracted_symptoms":["사지접합"],"severity":"중증","care_route":"emergency","general_departments":[],"route_reason":"우측 검지 절단(Pre-KTAS 2단계)으로 신속한 사지접합 전문 처치 및 응급실 이송이 필요합니다."}

[예시 7] 시민 모드 — 단순 흉부 통증 (Pre-KTAS Level 3)
입력: "어제 무거운 짐을 들고 나서부터 숨을 깊게 들이마실 때 가슴 근처가 결리고 찌릿찌릿 아파요."
→ {"extracted_symptoms":["흉통"],"severity":"중증","care_route":"emergency","general_departments":[],"route_reason":"식은땀·마비 등 동반 증상이 없는 흉부 통증(Pre-KTAS 3단계)으로 응급실 확인이 필요합니다."}

[예시 8] 구급대원 모드 — 투석 환자 응급 악화 (Pre-KTAS Level 2)
입력: "나이 68세, 성별 남성, 호흡 상태 곤란, 구급대원 메모 HD 환자 호흡곤란. 신고/현장 문장: 혈액투석 받던 환자가 갑자기 숨이 차고 의식이 흐릿해요."
→ {"extracted_symptoms":["투석"],"severity":"중증","care_route":"emergency","general_departments":[],"route_reason":"혈액투석 환자의 급성 호흡곤란 및 의식 저하(Pre-KTAS 2단계)로 즉각 이송이 필요합니다."}

[예시 9] 시민 모드 — 소아 고열 (Pre-KTAS Level 4)
입력: "아기가 어젯밤부터 열이 38도가 넘어요. 많이 칭얼대는데 다른 증상은 없는 것 같아요."
→ {"extracted_symptoms":["소아"],"severity":"경증","care_route":"general","general_departments":["소아청소년과"],"route_reason":"동반 응급 증상이 없는 소아 발열(Pre-KTAS 4단계)로 소아청소년과 외래 진료가 적합합니다."}

[예시 10] 시민 모드 — 소아 경련 (Pre-KTAS Level 2)
입력: "7살 아이가 갑자기 몸을 떨고 경기를 해요. 눈을 흰자로 뒤집고 있어요."
→ {"extracted_symptoms":["소아"],"severity":"중증","care_route":"emergency","general_departments":[],"route_reason":"소아 경련 발작(Pre-KTAS 2단계)으로 즉각적인 응급 처치가 필요합니다."}

[예시 11] 시민 모드 — 원인 불명 쓰러짐 (call_first)
입력: "갑자기 쓰러졌어요."
→ {"extracted_symptoms":[],"severity":"중증","care_route":"call_first","general_departments":[],"route_reason":"쓰러짐만으로는 원인 판단이 어려워 119 또는 의료기관 전화 확인이 먼저 필요합니다."}

[예시 12] 시민 모드 — 복합 증상 (화상 + 복부손상)
입력: "뜨거운 물에 팔을 데었고, 배도 너무 아파서 참기가 힘들어요."
→ {"extracted_symptoms":["화상","복부손상"],"severity":"중증","care_route":"emergency","general_departments":[],"route_reason":"화상과 심한 복통이 동반된 응급 상황(Pre-KTAS 3단계)으로 응급실 우선 확인이 필요합니다."}

[예시 13] 시민 모드 — 허리 통증 (Pre-KTAS Level 5)
입력: "허리가 며칠째 아프고 다리도 저려요."
→ {"extracted_symptoms":[],"severity":"경증","care_route":"general","general_departments":["정형외과","신경과"],"route_reason":"문장 분석 결과 근골격계 증상(Pre-KTAS 5단계)으로 일반 의료기관 안내가 가능합니다."}

[예시 14] 구급대원 모드 — 뇌졸중 단문
입력: "68세 여성 편마비 안면마비 구음장애"
→ {"extracted_symptoms":["뇌졸중"],"severity":"중증","care_route":"emergency","general_departments":[],"route_reason":"편마비·안면마비·구음장애 3가지 증상으로 뇌졸중(Pre-KTAS 2단계)이 강력히 의심됩니다."}

[예시 15] 구급대원 모드 — 심근경색 단문
입력: "60대 남성 흉통 식은땀"
→ {"extracted_symptoms":["심근경색"],"severity":"중증","care_route":"emergency","general_departments":[],"route_reason":"흉통과 식은땀 복합으로 심근경색(Pre-KTAS 2단계) 의심 응급 경로입니다."}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 AI-Hub 구어체 표현 추가 예시 (정형 문구 외 일상 표현 대응)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[예시 16] 구어체 뇌졸중 — "말이 이상해요" 패턴
입력: "아빠가 갑자기 말을 제대로 못 하고 한쪽 팔을 못 올려요."
→ {"extracted_symptoms":["뇌졸중"],"severity":"중증","care_route":"emergency","general_departments":[],"route_reason":"언어장애와 편측 상지 마비 표현으로 뇌졸중(Pre-KTAS 2단계)이 의심됩니다."}

[예시 17] 구어체 심근경색 — "가슴이 조여드는" 패턴
입력: "갑자기 가슴이 막 조여드는 것 같고 왼쪽 팔이 좀 이상한 느낌이에요."
→ {"extracted_symptoms":["심근경색"],"severity":"중증","care_route":"emergency","general_departments":[],"route_reason":"가슴 조임과 왼팔 이상감으로 심근경색(Pre-KTAS 2단계)이 의심되는 응급 상황입니다."}

[예시 18] 구어체 사지접합 — "날아갔어요" 패턴
입력: "공장에서 기계에 손가락 두 개가 날아갔어요. 피가 엄청 나요."
→ {"extracted_symptoms":["사지접합"],"severity":"중증","care_route":"emergency","general_departments":[],"route_reason":"손가락 절단(Pre-KTAS 2단계)으로 즉각적인 사지접합 처치가 필요합니다."}

[예시 19] 구어체 소아 경련 — "몸이 굳고 경기" 패턴
입력: "애가 펄펄 끓는데 갑자기 몸이 딱딱하게 굳고 경기를 해요."
→ {"extracted_symptoms":["소아"],"severity":"중증","care_route":"emergency","general_departments":[],"route_reason":"소아 고열 경련(Pre-KTAS 2단계)으로 즉각적인 응급 처치가 필요합니다."}

[예시 20] 매핑 불가 — 단순 호흡곤란·어지럼 (call_first)
입력: "갑자기 숨이 막히는 것 같고 어지러워요."
→ {"extracted_symptoms":[],"severity":"중증","care_route":"call_first","general_departments":[],"route_reason":"갑작스러운 호흡곤란·어지럼은 NEDIS 8대 코드와 직접 매핑이 어려워 119 전화 확인이 먼저 필요합니다."}

[예시 21] 매핑 불가 — 의식 없는 환자 구어체 (call_first)
입력: "엄마가 화장실에서 쓰러져 있는데 불러도 대답을 안 해요."
→ {"extracted_symptoms":[],"severity":"중증","care_route":"call_first","general_departments":[],"route_reason":"의식 저하·반응 없음은 원인 불명으로 즉시 119 신고가 필요합니다."}

[예시 22] 매핑 불가 — 발목 삐임 (경증)
입력: "운동하다 발목을 삐었는데 많이 부어올랐어요."
→ {"extracted_symptoms":[],"severity":"경증","care_route":"general","general_departments":["정형외과"],"route_reason":"발목 염좌는 8대 중증질환 코드에 해당하지 않아 정형외과 외래 안내가 적합합니다."}

[예시 23] 매핑 불가 — 혈뇨 (경증)
입력: "소변에 피가 섞여 나오는 것 같아요."
→ {"extracted_symptoms":[],"severity":"경증","care_route":"general","general_departments":["비뇨의학과"],"route_reason":"혈뇨는 8대 중증질환 코드에 해당하지 않아 비뇨의학과 외래 안내가 적합합니다."}
"""


def extract_symptoms(user_text: str, mode: str = 'citizen', patient_info: dict | None = None) -> dict:
    """
    사용자의 자연어 입력을 Gemini API로 분석하여 증상 키워드·중증도·안내경로를 반환합니다.

    Args:
        user_text: 분석할 자연어 문장
        mode: 'citizen'(시민) 또는 'ambulance'(구급대원)
        patient_info: 구급대원 모드의 구조화 환자 정보
    """
    analysis_text = merge_patient_context(user_text, patient_info if mode == 'ambulance' else None)
    rule_result   = rule_based_extract(analysis_text)

    if not GEMINI_API_KEY:
        print("Warning: GEMINI_API_KEY is not set.")
        return {**rule_result, "route_reason": f"{rule_result['route_reason']} AI 분석을 사용할 수 없어 규칙 기반으로 보완했습니다.", "is_ai_error": True}

    mode_label = "구급대원 (임상 용어·약어·단문 포함 가능)" if mode == 'ambulance' else "일반 시민 (일상 언어 문장)"
    user_prompt = (
        f"[입력자 유형] {mode_label}\n\n"
        f"[입력 문장]\n{analysis_text}\n\n"
        "[분석 절차]\n"
        "① 환자 정보: 나이·대상(소아 여부) 확인\n"
        "② 신체 부위·증상: 통증 위치·강도·성격 추출\n"
        "③ 사건 경위: 외상·사고·기저질환(투석 등) 여부 확인\n"
        "④ 8개 카테고리 매칭: 각 카테고리 기준으로 해당 여부 판단\n"
        "⑤ Pre-KTAS 단계 적용: 중증도·안내경로 최종 결정\n\n"
        "위 절차를 바탕으로 JSON 형식으로 결과를 반환하세요."
    )

    try:
        client = genai.Client(api_key=GEMINI_API_KEY)

        response = None
        for attempt in range(3):
            try:
                response = client.models.generate_content(
                    model='gemini-2.5-flash',
                    contents=user_prompt,
                    config={
                        'system_instruction': SYSTEM_PROMPT,
                        'response_mime_type': 'application/json',
                        'response_schema': SymptomExtraction,
                        'temperature': 0.0,
                        'thinking_config': {'thinking_budget': 1024},
                    },
                )
                break
            except Exception:
                if attempt == 2:
                    raise
                time.sleep(1.0)

        # 구조화 출력 파싱
        if hasattr(response, 'parsed') and response.parsed:
            raw                = response.parsed.extracted_symptoms
            severity           = response.parsed.severity
            care_route         = response.parsed.care_route
            general_departments = response.parsed.general_departments
            route_reason       = response.parsed.route_reason
        else:
            raw                = []
            severity           = "중증"
            care_route         = "call_first"
            general_departments = []
            route_reason       = "분석 결과를 확인하지 못해 전화 확인이 필요합니다."

        # 허용 키워드만 통과 + 규칙 기반 결과 병합
        validated = unique_ordered([s for s in raw if s in VALID_SYMPTOMS] + rule_result["symptoms"])

        # 심근경색이 있으면 흉통 제거 (상위 개념)
        if "심근경색" in validated and "흉통" in validated:
            validated.remove("흉통")

        if severity not in ["경증", "중증"]:
            severity = "중증"

        if care_route not in VALID_CARE_ROUTES:
            care_route = "emergency" if severity == "중증" else "general"

        validated_departments = unique_ordered(
            [d for d in general_departments if d in VALID_GENERAL_DEPARTMENTS]
            + rule_result["general_departments"]
        )[:2]

        has_primary = any(s in PRIMARY_EMERGENCY_SYMPTOMS for s in validated)
        if has_primary:
            care_route = "emergency"

        if care_route == "general":
            severity = "경증"
        elif care_route == "emergency":
            severity = "중증"

        if not route_reason:
            route_reason = rule_result["route_reason"] or "문장 분석 결과에 따라 의료기관 안내 경로를 분류했습니다."

        return {
            "symptoms": validated,
            "severity": severity,
            "care_route": care_route,
            "general_departments": validated_departments,
            "route_reason": route_reason,
            "is_ai_error": False,
        }

    except Exception as e:
        print(f"Error during symptom extraction: {e}")
        return {**rule_result, "route_reason": f"{rule_result['route_reason']} AI 분석 중 오류가 발생해 규칙 기반으로 보완했습니다.", "is_ai_error": True}


if __name__ == "__main__":
    test_cases = [
        "가슴이 너무 아프고 답답해요.",
        "왼쪽 팔이 저리면서 가슴이 짓눌리는 것 같고 식은땀이 나요.",
        "5살 아이가 끓는 물에 손을 데었어요.",
        "교통사고로 배를 심하게 부딪혔어요.",
        "공장에서 기계에 손가락이 잘렸습니다.",
        "투석 환자인데 갑자기 숨이 차고 상태가 나빠졌어요.",
        "갑자기 한쪽 팔에 힘이 빠지고 말이 어눌해요.",
        "얼굴 한쪽이 처지고 발음이 이상합니다.",
        "아기가 갑자기 경기를 해요.",
        "머리가 아프고 감기 기운이 있어요.",
        "60대 남성 흉통 식은땀",
        "68세 여성 편마비 안면마비 구음장애",
    ]
    for text in test_cases:
        result = extract_symptoms(text)
        print(f"입력: {text}")
        print(f"  → {result}")
        print()
