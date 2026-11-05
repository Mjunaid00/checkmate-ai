import { useEffect, useRef, useState } from 'react';
import { Calendar } from 'lucide-react';

/**
 * Text-based date+time input that ALWAYS displays as "dd/mm/yyyy HH:mm",
 * regardless of the browser's locale. The visible value is plain text;
 * a small calendar button reveals the native picker so users still get
 * a calendar UX. The emitted `onChange` value matches `<input type="datetime-local">`
 * — "YYYY-MM-DDTHH:mm" or "" — so the rest of the app keeps working unchanged.
 */
export default function DateTimeField({
  value,
  onChange,
  min,
  className = 'input-field',
  placeholder = 'dd/mm/yyyy HH:mm',
  ...rest
}) {
  const pickerRef = useRef(null);
  const [text, setText] = useState(isoToDisplay(value));

  useEffect(() => {
    // External value changes (form reset, prefilled deadline) keep the UI in sync.
    setText(isoToDisplay(value));
  }, [value]);

  const emit = (digits) => {
    if (digits.length === 12) {
      const iso = `${digits.slice(4, 8)}-${digits.slice(2, 4)}-${digits.slice(0, 2)}T${digits.slice(8, 10)}:${digits.slice(10, 12)}`;
      onChange(iso);
    } else if (digits.length === 0) {
      onChange('');
    }
    // partial input: don't propagate (form-level validation will catch it)
  };

  const handleTextChange = (e) => {
    const digits = e.target.value.replace(/\D/g, '').slice(0, 12);
    let formatted = '';
    if (digits.length >= 1) formatted += digits.slice(0, Math.min(2, digits.length));
    if (digits.length >= 3) formatted += '/' + digits.slice(2, Math.min(4, digits.length));
    if (digits.length >= 5) formatted += '/' + digits.slice(4, Math.min(8, digits.length));
    if (digits.length >= 9) formatted += ' ' + digits.slice(8, Math.min(10, digits.length));
    if (digits.length >= 11) formatted += ':' + digits.slice(10, 12);
    setText(formatted);
    emit(digits);
  };

  const handlePicker = (e) => {
    const iso = e.target.value; // already YYYY-MM-DDTHH:mm
    onChange(iso);
    setText(isoToDisplay(iso));
  };

  const openPicker = () => {
    const el = pickerRef.current;
    if (!el) return;
    if (typeof el.showPicker === 'function') {
      try { el.showPicker(); return; } catch { /* fall through */ }
    }
    el.focus();
    el.click();
  };

  return (
    <div style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
      <input
        type="text"
        inputMode="numeric"
        className={className}
        value={text}
        onChange={handleTextChange}
        placeholder={placeholder}
        style={{ width: '100%', paddingRight: '2.4rem' }}
        {...rest}
      />
      <button
        type="button"
        onClick={openPicker}
        title="Pick from calendar"
        aria-label="Pick date and time"
        style={{
          position: 'absolute',
          right: '0.4rem',
          top: '50%',
          transform: 'translateY(-50%)',
          background: 'transparent',
          border: 'none',
          color: 'var(--text-secondary)',
          cursor: 'pointer',
          padding: '0.25rem',
          display: 'flex',
        }}
      >
        <Calendar size={16} />
      </button>
      {/* Hidden native picker used purely to provide a calendar UX. */}
      <input
        ref={pickerRef}
        type="datetime-local"
        value={value || ''}
        min={min}
        onChange={handlePicker}
        tabIndex={-1}
        aria-hidden="true"
        style={{
          position: 'absolute',
          right: '0.4rem',
          top: '50%',
          transform: 'translateY(-50%)',
          width: 1,
          height: 1,
          opacity: 0,
          pointerEvents: 'none',
        }}
      />
    </div>
  );
}

function isoToDisplay(iso) {
  if (!iso) return '';
  const m = String(iso).match(/^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2})/);
  if (!m) return '';
  return `${m[3]}/${m[2]}/${m[1]} ${m[4]}:${m[5]}`;
}
