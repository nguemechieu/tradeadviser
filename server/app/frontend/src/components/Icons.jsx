import '../styles/icons.css';

/**
 * Icon Components for TradeAdviser
 * Provides consistent icon usage throughout the app using Font Awesome and custom SVG icons
 */

// Font Awesome Icon Wrapper (requires Font Awesome CSS to be imported)
export const FAIcon = ({ icon, className = '', style = {}, title = '' }) => (
  <i 
    className={`fas fa-${icon} ${className}`}
    style={{ ...style, marginRight: '0.5rem' }}
    title={title}
    aria-hidden="true"
  />
);

// Custom SVG Icons
export const ClipboardIcon = ({ className = '', style = {}, title = 'Clipboard' }) => (
  <svg
    className={`icon ${className}`}
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    strokeLinecap="round"
    strokeLinejoin="round"
    style={{ width: '1.2em', height: '1.2em', marginRight: '0.5rem', ...style }}
    title={title}
  >
    <path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2" />
    <rect x="8" y="2" width="8" height="4" rx="1" ry="1" />
  </svg>
);

export const XIcon = ({ className = '', style = {}, title = 'Cancel' }) => (
  <svg
    className={`icon ${className}`}
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    strokeLinecap="round"
    strokeLinejoin="round"
    style={{ width: '1.2em', height: '1.2em', marginRight: '0.5rem', ...style }}
    title={title}
  >
    <line x1="18" y1="6" x2="6" y2="18" />
    <line x1="6" y1="6" x2="18" y2="18" />
  </svg>
);

export const PlusIcon = ({ className = '', style = {}, title = 'Add' }) => (
  <svg
    className={`icon ${className}`}
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    strokeLinecap="round"
    strokeLinejoin="round"
    style={{ width: '1.2em', height: '1.2em', marginRight: '0.5rem', ...style }}
    title={title}
  >
    <line x1="12" y1="5" x2="12" y2="19" />
    <line x1="5" y1="12" x2="19" y2="12" />
  </svg>
);

export const UserIcon = ({ className = '', style = {}, title = 'User' }) => (
  <svg
    className={`icon ${className}`}
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    strokeLinecap="round"
    strokeLinejoin="round"
    style={{ width: '1.2em', height: '1.2em', marginRight: '0.5rem', ...style }}
    title={title}
  >
    <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
    <circle cx="12" cy="7" r="4" />
  </svg>
);

export const CrownIcon = ({ className = '', style = {}, title = 'Super Admin' }) => (
  <svg
    className={`icon ${className}`}
    viewBox="0 0 24 24"
    fill="currentColor"
    style={{ width: '1.2em', height: '1.2em', marginRight: '0.5rem', ...style }}
    title={title}
  >
    <path d="M2 3h20l-2.62 7.89a2 2 0 0 1-1.88 1.36H6.5a2 2 0 0 1-1.88-1.36L2 3z" />
    <path d="M6 10v9a2 2 0 0 0 2 2h8a2 2 0 0 0 2-2v-9" />
    <line x1="9" y1="3" x2="9" y2="10" />
    <line x1="12" y1="3" x2="12" y2="10" />
    <line x1="15" y1="3" x2="15" y2="10" />
  </svg>
);

export const AlertIcon = ({ className = '', style = {}, title = 'Alert' }) => (
  <svg
    className={`icon ${className}`}
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    strokeLinecap="round"
    strokeLinejoin="round"
    style={{ width: '1.2em', height: '1.2em', marginRight: '0.5rem', ...style }}
    title={title}
  >
    <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3.05h16.94a2 2 0 0 0 1.71-3.05L13.71 3.86a2 2 0 0 0-3.42 0z" />
    <line x1="12" y1="9" x2="12" y2="13" />
    <line x1="12" y1="17" x2="12.01" y2="17" />
  </svg>
);

export const LoadingIcon = ({ className = '', style = {}, title = 'Loading' }) => (
  <svg
    className={`icon icon-loading ${className}`}
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    strokeLinecap="round"
    strokeLinejoin="round"
    style={{ width: '1.2em', height: '1.2em', marginRight: '0.5rem', ...style }}
    title={title}
  >
    <circle cx="12" cy="12" r="10" />
    <path d="M12 2a10 10 0 0 1 8.46 14.46" strokeDasharray="5" />
  </svg>
);

export const CheckIcon = ({ className = '', style = {}, title = 'Apply' }) => (
  <svg
    className={`icon ${className}`}
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    strokeLinecap="round"
    strokeLinejoin="round"
    style={{ width: '1.2em', height: '1.2em', marginRight: '0.5rem', ...style }}
    title={title}
  >
    <polyline points="20 6 9 17 4 12" />
  </svg>
);

/**
 * Composite Icon Buttons
 */
export const IconButton = ({ 
  icon: Icon, 
  label, 
  onClick, 
  disabled = false, 
  className = '', 
  title = '',
  style = {}
}) => (
  <button
    onClick={onClick}
    disabled={disabled}
    className={`icon-button ${className}`}
    title={title || label}
    style={style}
  >
    <Icon />
    {label}
  </button>
);

/**
 * Icon with text wrapper
 */
export const IconText = ({ icon: Icon, text, className = '' }) => (
  <span className={`icon-text ${className}`}>
    <Icon />
    {text}
  </span>
);
