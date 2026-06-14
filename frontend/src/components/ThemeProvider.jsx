import React, { createContext, useContext, useState, useEffect } from 'react';

const ThemeContext = createContext({
  theme: 'rudran-dark',
  setTheme: () => {},
});

export function useTheme() {
  return useContext(ThemeContext);
}

export function ThemeProvider({ children }) {
  const [theme, setThemeState] = useState(() => {
    return localStorage.getItem('theme_choice') || 'rudran-dark';
  });

  const applyTheme = (currentTheme) => {
    let activeClass = 'theme-rudran-dark';
    
    if (currentTheme === 'system') {
      const isSystemDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
      activeClass = isSystemDark ? 'theme-rudran-dark' : 'theme-modern-light';
    } else if (currentTheme === 'tamil-heritage') {
      activeClass = 'theme-tamil-heritage';
    } else if (currentTheme === 'modern-light') {
      activeClass = 'theme-modern-light';
    }

    // Apply class to html/body elements
    const root = document.documentElement;
    root.classList.remove('theme-rudran-dark', 'theme-tamil-heritage', 'theme-modern-light');
    root.classList.add(activeClass);
  };

  useEffect(() => {
    applyTheme(theme);
    localStorage.setItem('theme_choice', theme);

    // If system theme is selected, listen for system theme changes
    if (theme === 'system') {
      const media = window.matchMedia('(prefers-color-scheme: dark)');
      const listener = () => applyTheme('system');
      media.addEventListener('change', listener);
      return () => media.removeEventListener('change', listener);
    }
  }, [theme]);

  const setTheme = (newTheme) => {
    setThemeState(newTheme);
  };

  return (
    <ThemeContext.Provider value={{ theme, setTheme }}>
      {children}
    </ThemeContext.Provider>
  );
}

export function ThemeSwitcher() {
  const { theme, setTheme } = useTheme();

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', background: 'var(--color-surface-2)', padding: '4px', borderRadius: 'var(--radius-md)', border: '1px solid var(--color-border)' }}>
      {[
        { id: 'rudran-dark',    label: '🌌 Dark',     color: '#7c5cfc' },
        { id: 'tamil-heritage', label: '🕌 Heritage', color: '#d97706' },
        { id: 'modern-light',   label: '☀️ Light',    color: '#3b82f6' },
        { id: 'system',         label: '💻 System',   color: '#8b5cf6' }
      ].map(opt => (
        <button
          key={opt.id}
          id={`theme-select-${opt.id}`}
          onClick={() => setTheme(opt.id)}
          style={{
            background: theme === opt.id ? opt.color : 'transparent',
            color: theme === opt.id ? '#ffffff' : 'var(--color-text-muted)',
            border: 'none',
            borderRadius: '6px',
            padding: '4px 10px',
            fontSize: '0.72rem',
            fontWeight: 600,
            cursor: 'pointer',
            transition: 'all 0.15s ease',
            fontFamily: 'inherit'
          }}
        >
          {opt.label}
        </button>
      ))}
    </div>
  );
}
