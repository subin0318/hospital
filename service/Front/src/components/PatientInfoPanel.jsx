function PatientInfoPanel({ patientInfo, onChange }) {
  const update = (field, value) => {
    onChange({ ...patientInfo, [field]: value });
  };

  return (
    <div className="form-group">
      <h3 className="section-title">
        <span>환자 정보</span>
      </h3>

      <div className="patient-grid">
        <label className="field-label">
          <span>나이</span>
          <input
            className="field-input"
            value={patientInfo.age}
            onChange={(e) => update('age', e.target.value)}
            placeholder="예: 5"
          />
        </label>
        <label className="field-label">
          <span>성별</span>
          <select
            className="field-input"
            value={patientInfo.gender}
            onChange={(e) => update('gender', e.target.value)}
          >
            <option value="">선택</option>
            <option value="남">남</option>
            <option value="여">여</option>
            <option value="미상">미상</option>
          </select>
        </label>
      </div>

      <div className="patient-grid">
        <label className="field-label">
          <span>의식 상태</span>
          <select
            className="field-input"
            value={patientInfo.consciousness}
            onChange={(e) => update('consciousness', e.target.value)}
          >
            <option value="명료">명료</option>
            <option value="혼미">혼미</option>
            <option value="무의식">무의식</option>
          </select>
        </label>
        <label className="field-label">
          <span>호흡 상태</span>
          <select
            className="field-input"
            value={patientInfo.breathing}
            onChange={(e) => update('breathing', e.target.value)}
          >
            <option value="정상">정상</option>
            <option value="불안정">불안정</option>
            <option value="곤란">곤란</option>
          </select>
        </label>
      </div>

      <div className="patient-grid">
        <label className="field-label">
          <span>출혈 여부</span>
          <select
            className="field-input"
            value={patientInfo.bleeding}
            onChange={(e) => update('bleeding', e.target.value)}
          >
            <option value="없음">없음</option>
            <option value="있음">있음</option>
            <option value="확인 필요">확인 필요</option>
          </select>
        </label>
        <label className="field-label">
          <span>보호자 연락</span>
          <select
            className="field-input"
            value={patientInfo.guardianContact}
            onChange={(e) => update('guardianContact', e.target.value)}
          >
            <option value="미확인">미확인</option>
            <option value="완료">완료</option>
            <option value="불가">불가</option>
          </select>
        </label>
      </div>

      <label className="field-label">
        <span>구급대원 메모</span>
        <textarea
          className="textarea-input"
          value={patientInfo.memo}
          onChange={(e) => update('memo', e.target.value)}
          placeholder="현장 처치 내용, 특이사항 등을 입력하세요"
        />
      </label>
    </div>
  );
}

export default PatientInfoPanel;
