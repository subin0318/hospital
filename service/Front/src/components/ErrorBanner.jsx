import { AlertTriangle, CheckCircle2, X } from 'lucide-react';

function ErrorBanner({ message, onClose, type = 'error' }) {
  if (!message) return null;

  const isSuccess = type === 'success';
  const bg = isSuccess ? 'rgba(34, 197, 94, 0.1)' : 'rgba(239, 68, 68, 0.1)';
  const border = isSuccess ? '1px solid rgba(34, 197, 94, 0.3)' : '1px solid rgba(239, 68, 68, 0.3)';
  const color = isSuccess ? '#4ade80' : '#f87171';
  const Icon = isSuccess ? CheckCircle2 : AlertTriangle;

  return (
    <div className="error-banner" style={{
      background: bg,
      border,
      borderRadius: '8px',
      padding: '12px 16px',
      color,
      fontSize: '13px',
      display: 'flex',
      alignItems: 'center',
      gap: '10px',
      marginBottom: '16px'
    }}>
      <Icon size={16} style={{ flexShrink: 0 }} />
      <div style={{ flex: 1, lineHeight: '1.4' }}>{message}</div>
      <button
        onClick={onClose}
        style={{ background: 'transparent', border: 'none', color, cursor: 'pointer', display: 'flex', alignItems: 'center', padding: 0 }}
      >
        <X size={14} />
      </button>
    </div>
  );
}

export default ErrorBanner;
