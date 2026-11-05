import { useTheme } from '../contexts/ThemeContext';
import { Sun, Moon, Monitor, Sunset } from 'lucide-react';

const themeConfig = {
  light:        { icon: Sun,     label: 'Light',       color: '#F59E0B' },
  dark:         { icon: Moon,    label: 'Dark',        color: '#60A5FA' },
  gray:         { icon: Monitor, label: 'Gray',        color: '#9CA3AF' },
  'night-light':{ icon: Sunset,  label: 'Night Light', color: '#E0A458' },
};

export default function ThemeSwitcher({ compact = false }) {
  const { theme, setTheme, themes } = useTheme();

  if (compact) {
    const cfg = themeConfig[theme];
    const Icon = cfg.icon;
    const nextIdx = (themes.indexOf(theme) + 1) % themes.length;
    return (
      <button
        onClick={() => setTheme(themes[nextIdx])}
        title={`Switch to ${themeConfig[themes[nextIdx]].label}`}
        style={{
          background: 'transparent',
          border: '1px solid var(--border-color)',
          borderRadius: '0.5rem',
          padding: '0.5rem',
          cursor: 'pointer',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: cfg.color,
          transition: 'all 0.2s ease',
        }}
      >
        <Icon size={18} />
      </button>
    );
  }

  return (
    <div style={{ display: 'flex', gap: '0.5rem' }}>
      {themes.map(t => {
        const cfg = themeConfig[t];
        const Icon = cfg.icon;
        const isActive = theme === t;
        return (
          <button
            key={t}
            onClick={() => setTheme(t)}
            title={cfg.label}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '0.4rem',
              padding: '0.5rem 0.75rem',
              borderRadius: '0.5rem',
              border: isActive ? `2px solid ${cfg.color}` : '1px solid var(--border-color)',
              background: isActive ? 'var(--accent-soft)' : 'transparent',
              color: isActive ? cfg.color : 'var(--text-secondary)',
              cursor: 'pointer',
              fontSize: '0.82rem',
              fontWeight: isActive ? 600 : 400,
              transition: 'all 0.2s ease',
            }}
          >
            <Icon size={15} />
            {cfg.label}
          </button>
        );
      })}
    </div>
  );
}
