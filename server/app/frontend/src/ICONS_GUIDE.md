# Icon System Guide

## Overview

The TradeAdviser frontend uses a comprehensive icon system with both custom SVG icons and Font Awesome icons. All icons are centralized in `components/Icons.jsx` for easy maintenance and consistency.

## Installation

All dependencies are already configured in `package.json`:

```bash
npm install
```

This includes:
- `@fortawesome/fontawesome-free` - Font Awesome icon library

## Icon Components

### SVG Icons (Custom)

All custom SVG icons are available from `components/Icons.jsx`:

```jsx
import {
  ClipboardIcon,
  XIcon,
  PlusIcon,
  UserIcon,
  CrownIcon,
  AlertIcon,
  LoadingIcon,
  CheckIcon,
  IconText
} from './Icons';
```

#### Available SVG Icons

| Icon | Component | Usage |
|------|-----------|-------|
| Clipboard | `<ClipboardIcon />` | Audit logs, document operations |
| X/Cancel | `<XIcon />` | Close, cancel, remove actions |
| Plus | `<PlusIcon />` | Add, create, new item |
| User | `<UserIcon />` | User profile, create user |
| Crown | `<CrownIcon />` | Super admin, elevated permissions |
| Alert | `<AlertIcon />` | Warnings, error messages |
| Loading | `<LoadingIcon />` | Loading states, processing |
| Check | `<CheckIcon />` | Apply, confirm, success |

### Font Awesome Icons

For additional icons, use Font Awesome (already integrated):

```jsx
import { FAIcon } from './Icons';

// In JSX:
<FAIcon icon="home" title="Home" />
```

### Usage Patterns

#### 1. Simple Icon

```jsx
<ClipboardIcon />
```

#### 2. Icon with Text (Recommended for Buttons)

```jsx
<IconText icon={PlusIcon} text="Add New User" />
```

#### 3. Icon Button

```jsx
<IconButton
  icon={PlusIcon}
  label="Add User"
  onClick={handleClick}
  disabled={false}
/>
```

#### 4. Font Awesome Icon

```jsx
<FAIcon icon="spinner" className="animate" />
```

#### 5. Custom Styling

All SVG icons accept style and className props:

```jsx
<ClipboardIcon 
  style={{ color: '#53b4ff', fontSize: '1.5em' }}
  className="icon-lg"
  title="Custom Title"
/>
```

## Icon Sizing

Icons have built-in responsive sizing. For custom sizes, use CSS classes:

```jsx
<ClipboardIcon className="icon-sm" />   {/* 0.875em */}
<ClipboardIcon />                        {/* 1.2em (default) */}
<ClipboardIcon className="icon-lg" />   {/* 1.5em */}
<ClipboardIcon className="icon-xl" />   {/* 2em */}
```

## Styling

Icons come with default styles in `styles/icons.css`. Key features:

- **Consistent sizing** - All icons standardize to 1.2em
- **Loading animation** - `.icon-loading` class rotates icons
- **Icon buttons** - `.icon-button` styling for button icons
- **Gap spacing** - Automatic spacing between icon and text

## Examples in Components

### UserManagement Component

```jsx
// Import icons
import {
  ClipboardIcon,
  XIcon,
  PlusIcon,
  UserIcon,
  CrownIcon,
  AlertIcon,
  LoadingIcon,
  CheckIcon,
  IconText
} from './Icons';

// Show/Hide Audit Logs
<button>
  <IconText icon={ClipboardIcon} text={showAuditLogs ? 'Hide Audit Logs' : 'Show Audit Logs'} />
</button>

// Add New User
<button>
  <IconText icon={showCreateForm ? XIcon : PlusIcon} text={showCreateForm ? 'Cancel' : 'New User'} />
</button>

// Error Messages
{error && (
  <div>
    <IconText icon={AlertIcon} text={error} />
  </div>
)}

// Loading State
{loading && (
  <p><IconText icon={LoadingIcon} text="Loading users..." /></p>
)}
```

## Best Practices

1. **Always use IconText for buttons** - Provides proper spacing and alignment
   ```jsx
   // ✅ Good
   <IconText icon={PlusIcon} text="Add User" />
   
   // ❌ Avoid
   <PlusIcon /> Add User
   ```

2. **Use semantic icons** - Match the icon to its action
   - ✅ `CheckIcon` for apply/confirm
   - ✅ `PlusIcon` for add/create
   - ❌ Random icons for unrelated actions

3. **Add meaningful titles** - Helps with accessibility
   ```jsx
   <ClipboardIcon title="View audit history" />
   ```

4. **Keep loading animations consistent** - Use `LoadingIcon` for all loading states
   ```jsx
   {loading && <LoadingIcon />}
   ```

5. **Theme consistency** - Don't override icon colors in buttons
   ```jsx
   // ✅ Good - Uses parent button color
   <button><ClipboardIcon /> Audit Logs</button>
   
   // ❌ Avoid - Breaks theme
   <button><ClipboardIcon style={{ color: 'red' }} /> Audit Logs</button>
   ```

## Adding New Icons

To add a new SVG icon:

1. Add the SVG component to `components/Icons.jsx`:

```jsx
export const NewIcon = ({ className = '', style = {}, title = 'New Icon' }) => (
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
    {/* SVG path content */}
  </svg>
);
```

2. Export it from the Icons component
3. Import and use in your component

## Troubleshooting

### Icons not showing
- Ensure `@fortawesome/fontawesome-free` is installed: `npm install`
- Check that CSS imports are in place:
  ```jsx
  import '@fortawesome/fontawesome-free/css/all.min.css';
  ```
- Verify icon component is imported correctly

### Icons not animated
- For loading icons, ensure they have the `.icon-loading` class
- Animations are defined in `styles/icons.css`

### Icon sizing issues
- Icons default to `1.2em` - use className variants for other sizes
- Don't use `width`/`height` on individual icons, use CSS classes instead

## Resources

- [Font Awesome Icons](https://fontawesome.com/icons) - Browse all available FA icons
- [SVG Icon Inspiration](https://feathericons.com/) - Design reference for custom SVGs
