import React from 'react';

interface LogoProps {
  size?: 'small' | 'medium' | 'large';
  showText?: boolean;
}

const Logo: React.FC<LogoProps> = ({ size = 'medium', showText = true }) => {
  const sizes = {
    small: 32,
    medium: 48,
    large: 64,
  };

  const dimension = sizes[size];

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
      <svg
        width={dimension}
        height={dimension}
        viewBox="0 0 64 64"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        style={{ flexShrink: 0 }}
      >
        {/* Background Circle */}
        <circle cx="32" cy="32" r="30" fill="url(#gradientBg)" stroke="url(#gradientBorder)" strokeWidth="2" />

        {/* Chart Lines - Representing Trading */}
        <g strokeLinecap="round" strokeLinejoin="round">
          {/* Ascending line representing profit */}
          <path
            d="M 16 48 Q 28 32 40 18"
            stroke="url(#gradientLine)"
            strokeWidth="2.5"
            fill="none"
          />

          {/* Support line */}
          <path
            d="M 14 50 L 46 50"
            stroke="url(#gradientSupport)"
            strokeWidth="1.5"
            fill="none"
            opacity="0.6"
          />

          {/* Data points */}
          <circle cx="16" cy="48" r="2.5" fill="#00d4ff" />
          <circle cx="28" cy="32" r="2.5" fill="#00d4ff" />
          <circle cx="40" cy="18" r="2.5" fill="#0099ff" />
        </g>

        {/* Arrow pointing up (representing growth) */}
        <g>
          <path
            d="M 48 24 L 48 12 M 48 12 L 44 16 M 48 12 L 52 16"
            stroke="url(#gradientArrow)"
            strokeWidth="2"
            fill="none"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </g>

        {/* Gradients */}
        <defs>
          <linearGradient id="gradientBg" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" style={{ stopColor: '#0099ff', stopOpacity: 0.15 }} />
            <stop offset="100%" style={{ stopColor: '#00d4ff', stopOpacity: 0.1 }} />
          </linearGradient>

          <linearGradient id="gradientBorder" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" style={{ stopColor: '#0099ff', stopOpacity: 0.5 }} />
            <stop offset="100%" style={{ stopColor: '#00d4ff', stopOpacity: 0.5 }} />
          </linearGradient>

          <linearGradient id="gradientLine" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" style={{ stopColor: '#00d4ff' }} />
            <stop offset="100%" style={{ stopColor: '#0099ff' }} />
          </linearGradient>

          <linearGradient id="gradientSupport" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" style={{ stopColor: '#00d4ff', stopOpacity: 0.4 }} />
            <stop offset="100%" style={{ stopColor: '#0099ff', stopOpacity: 0.4 }} />
          </linearGradient>

          <linearGradient id="gradientArrow" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" style={{ stopColor: '#00d084' }} />
            <stop offset="100%" style={{ stopColor: '#00d4ff' }} />
          </linearGradient>
        </defs>
      </svg>

      {showText && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
          <span
            style={{
              fontSize: size === 'small' ? '14px' : size === 'medium' ? '18px' : '24px',
              fontWeight: 700,
              background: 'linear-gradient(135deg, #00d4ff, #0099ff)',
              WebkitBackgroundClip: 'text',
              WebkitTextFillColor: 'transparent',
              backgroundClip: 'text',
            }}
          >
            TradeAdviser
          </span>
          <span
            style={{
              fontSize: size === 'small' ? '10px' : size === 'medium' ? '12px' : '14px',
              color: '#a0a0a0',
              fontWeight: 500,
            }}
          >
            Smart Trading
          </span>
        </div>
      )}
    </div>
  );
};

export default Logo;
