import { Sparkles } from 'lucide-react';

function SymptomPanel({
  rawText,
  selectedSymptoms,
  symptomTags,
  aiAnalyzing,
  aiNoSymptomMessage,
  isLocationConfirmed,
  onRawTextChange,
  onAiAnalysis,
  onSymptomTagToggle
}) {
  return (
    <>
      <div className="form-group">
        <h3 className="section-title">
          <span>AI 증상 문장 분석</span>
          <Sparkles size={14} color="#6366f1" />
        </h3>
        <textarea
          className="textarea-input"
          placeholder="예시: 5살 아이가 끓는 물에 손을 심하게 데었어요"
          value={rawText}
          onChange={(e) => onRawTextChange(e.target.value)}
        />
        <div style={{ fontSize: '11px', color: 'var(--color-text-muted)', lineHeight: '1.45', marginTop: '-4px', marginBottom: '6px' }}>
          ※ 경증/중증 판단이 모호할 때는 환자의 상태(의식, 호흡, 출혈 등)와 세부 증상을 상세히 작성하여 AI 분석을 요청하시면 Pre-KTAS(병원 전 단계 응급환자 분류 지침) 기준으로 객관적 분류를 제안합니다. 응급 상황 시에는 즉시 119 또는 인근 응급실로 방문해 주세요.
        </div>
        <button
          className="btn-primary"
          onClick={onAiAnalysis}
          disabled={aiAnalyzing}
        >
          {aiAnalyzing ? (
            <>
              <span className="loading-spinner"></span>
              AI 분석 중...
            </>
          ) : (
            <>
              <Sparkles size={14} />
              자연어 분석 요청
            </>
          )}
        </button>
        {aiNoSymptomMessage && (
          <div style={{ marginTop: '8px', fontSize: '11px', color: '#f59e0b', background: 'rgba(245,158,11,0.1)', border: '1px solid rgba(245,158,11,0.3)', borderRadius: '6px', padding: '8px 10px' }}>
            {aiNoSymptomMessage}
          </div>
        )}
      </div>

      <div>
        <h3 className="section-title">
          <span>주요 증상 선택</span>
        </h3>
        <div className="symptoms-selector-grid">
          {symptomTags.map((tag) => (
            <button
              key={tag}
              className={`symptom-tag ${selectedSymptoms.includes(tag) ? 'active' : ''}`}
              onClick={() => onSymptomTagToggle(tag)}
              disabled={!isLocationConfirmed}
            >
              {tag}
            </button>
          ))}
        </div>
      </div>
    </>
  );
}

export default SymptomPanel;
