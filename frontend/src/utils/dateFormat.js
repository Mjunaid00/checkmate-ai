// Centralised date formatting helpers.
// Project standard: dd/mm/yyyy for dates, dd/mm/yyyy HH:mm for date+time.

const LOCALE = 'en-GB'; // en-GB renders as dd/mm/yyyy

function toDate(v) {
  if (v == null || v === '') return null;
  const d = v instanceof Date ? v : new Date(v);
  return Number.isNaN(d.getTime()) ? null : d;
}

// "27/06/2026"
export function formatDate(v) {
  const d = toDate(v);
  if (!d) return '';
  return d.toLocaleDateString(LOCALE, { day: '2-digit', month: '2-digit', year: 'numeric' });
}

// "27/06/2026 14:30"
export function formatDateTime(v) {
  const d = toDate(v);
  if (!d) return '';
  return `${formatDate(d)} ${d.toLocaleTimeString(LOCALE, { hour: '2-digit', minute: '2-digit', hour12: false })}`;
}

// "14:30"
export function formatTime(v) {
  const d = toDate(v);
  if (!d) return '';
  return d.toLocaleTimeString(LOCALE, { hour: '2-digit', minute: '2-digit', hour12: false });
}

// "27 Jun" — short axis labels
export function formatDateShort(v) {
  const d = toDate(v);
  if (!d) return '';
  return d.toLocaleDateString(LOCALE, { day: '2-digit', month: 'short' });
}

// "June 2026" — month picker headers
export function formatMonthYear(v) {
  const d = toDate(v);
  if (!d) return '';
  return d.toLocaleDateString(LOCALE, { month: 'long', year: 'numeric' });
}

// "Mon, 27 Jun" — calendar/today widget
export function formatWeekdayDate(v) {
  const d = toDate(v);
  if (!d) return '';
  return d.toLocaleDateString(LOCALE, { weekday: 'short', day: '2-digit', month: 'short' });
}

// Local "now" formatted for the min attribute on <input type="datetime-local">.
// Returns "YYYY-MM-DDTHH:mm" — the only format that input accepts.
export function nowForDatetimeLocal() {
  const d = new Date();
  const pad = (n) => String(n).padStart(2, '0');
  return (
    `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}` +
    `T${pad(d.getHours())}:${pad(d.getMinutes())}`
  );
}

// "YYYY-MM-DDTHH:mm" for a given date — handy when prefilling a datetime-local
export function toDatetimeLocalValue(v) {
  const d = toDate(v);
  if (!d) return '';
  const pad = (n) => String(n).padStart(2, '0');
  return (
    `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}` +
    `T${pad(d.getHours())}:${pad(d.getMinutes())}`
  );
}

// True if the value is in the past (used to block past-dated assignments / quizzes).
export function isPast(v) {
  const d = toDate(v);
  if (!d) return false;
  return d.getTime() < Date.now();
}

// Convert a datetime-local value ("YYYY-MM-DDTHH:mm", LOCAL time) into an
// ISO-8601 UTC string for the API. The backend compares deadlines in UTC, so
// sending the raw local value shifted every deadline by the UTC offset.
// Returns '' for empty/invalid input (the backend treats '' as "no deadline").
export function toApiDatetime(localValue) {
  if (!localValue) return '';
  const d = new Date(localValue);
  return Number.isNaN(d.getTime()) ? '' : d.toISOString();
}
