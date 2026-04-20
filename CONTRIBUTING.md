# Contributing Guide

Thank you for your interest in contributing to TradeAdviser! This guide explains how to contribute code, report bugs, and improve the platform.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Making Changes](#making-changes)
- [Code Standards](#code-standards)
- [Testing](#testing)
- [Documentation](#documentation)
- [Pull Request Process](#pull-request-process)
- [Commit Guidelines](#commit-guidelines)

## Code of Conduct

We are committed to providing a welcoming and inclusive environment. Please:

- Be respectful to all contributors
- Welcome diverse perspectives and experiences
- Focus on constructive criticism
- Report inappropriate behavior to maintainers

## Getting Started

### 1. Fork the Repository

```bash
# Go to https://github.com/yourusername/tradeadviser
# Click "Fork" button
```

### 2. Clone Your Fork

```bash
git clone https://github.com/yourusername/tradeadviser.git
cd tradeadviser
git remote add upstream https://github.com/original-owner/tradeadviser.git
```

### 3. Create a Branch

```bash
git checkout -b feature/your-feature-name
# or
git checkout -b fix/your-bug-fix
```

Branch naming conventions:
- `feature/` - New features
- `fix/` - Bug fixes
- `docs/` - Documentation
- `refactor/` - Code refactoring
- `test/` - Test improvements

## Development Setup

### Backend Development

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install development dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Install pre-commit hooks
pre-commit install
```

### Frontend Development

```bash
cd server/frontend

# Install dependencies
npm install

# Start development server
npm run dev
```

### Desktop Development

```bash
cd desktop

# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

## Making Changes

### Code Organization

**Backend** - Follow FastAPI/Python conventions:
```python
# Good structure
from fastapi import APIRouter, Depends
from backend.core.auth_service import get_current_user

router = APIRouter(prefix="/trades", tags=["trades"])

@router.get("/")
async def list_trades(current_user: User = Depends(get_current_user)):
    """List all trades for current user."""
    return []
```

**Frontend** - Follow React conventions:
```jsx
// Good component structure
import { useState, useEffect } from 'react';
import { TradeCard } from './TradeCard';

export function TradesList() {
  const [trades, setTrades] = useState([]);
  
  useEffect(() => {
    fetchTrades();
  }, []);
  
  return (
    <div className="trades-list">
      {trades.map(trade => (
        <TradeCard key={trade.id} trade={trade} />
      ))}
    </div>
  );
}
```

**Desktop** - Follow PySide6 conventions:
```python
# Good widget structure
from PySide6.QtWidgets import QMainWindow, QVBoxLayout

class TradesWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.init_ui()
    
    def init_ui(self):
        """Initialize user interface."""
        layout = QVBoxLayout()
        self.setLayout(layout)
```

## Code Standards

### Python Style

Follow PEP 8:

```bash
# Format code
black backend/
black desktop/

# Check linting
flake8 backend/ --max-line-length=100
pylint backend/

# Type checking
mypy backend/
```

**Code style example**:
```python
# Good
def calculate_portfolio_value(trades: list[Trade]) -> float:
    """Calculate total portfolio value.
    
    Args:
        trades: List of trade objects
    
    Returns:
        Total portfolio value
    """
    total = sum(trade.value for trade in trades)
    return total


# Bad
def calc(t):
    tot = 0
    for i in t:
        tot += i.value
    return tot
```

### JavaScript/React Style

Follow Airbnb style guide:

```bash
# Format code
npm run format

# Check linting
npm run lint
```

**Code style example**:
```javascript
// Good
export function UserCard({ user, onSelect }) {
  const handleClick = () => {
    onSelect(user.id);
  };

  return (
    <div onClick={handleClick} className="user-card">
      <h3>{user.name}</h3>
      <p>{user.email}</p>
    </div>
  );
}

// Bad
function UserCard(props) {
  return <div onClick={() => props.onSelect(props.user.id)}>
    <h3>{props.user.name}</h3>
  </div>
}
```

### Documentation

Add docstrings to all functions:

```python
def execute_trade(user_id: str, trade: TradeCreate) -> Trade:
    """Execute a new trade for the user.
    
    Args:
        user_id: Unique user identifier
        trade: Trade creation schema with details
    
    Returns:
        Created Trade object
    
    Raises:
        ValueError: If trade validation fails
        PermissionError: If user lacks trading permission
    """
    pass
```

## Testing

### Backend Tests

```bash
cd backend

# Run all tests
pytest

# Run with coverage
pytest --cov=. --cov-report=html

# Run specific test
pytest tests/test_trades.py::test_create_trade

# Run with verbose output
pytest -v

# Watch mode
pytest-watch
```

**Test example**:
```python
import pytest
from backend.services.trade_service import create_trade

@pytest.mark.asyncio
async def test_create_trade_success(db_session):
    """Test successful trade creation."""
    # Arrange
    user = await create_test_user(db_session)
    trade_data = {
        "symbol": "AAPL",
        "quantity": 100,
        "price": 150.00
    }
    
    # Act
    result = await create_trade(user.id, trade_data, db_session)
    
    # Assert
    assert result.id is not None
    assert result.symbol == "AAPL"
    assert result.user_id == user.id
```

### Frontend Tests

```bash
cd server/frontend

# Run tests
npm test

# Run with coverage
npm test -- --coverage

# Watch mode
npm test -- --watch
```

**Test example**:
```jsx
import { render, screen, fireEvent } from '@testing-library/react';
import { TradeCard } from './TradeCard';

describe('TradeCard', () => {
  it('displays trade information', () => {
    const trade = { id: '1', symbol: 'AAPL', quantity: 100 };
    render(<TradeCard trade={trade} />);
    
    expect(screen.getByText('AAPL')).toBeInTheDocument();
    expect(screen.getByText('100')).toBeInTheDocument();
  });
  
  it('calls onSelect when clicked', () => {
    const trade = { id: '1', symbol: 'AAPL' };
    const onSelect = jest.fn();
    render(<TradeCard trade={trade} onSelect={onSelect} />);
    
    fireEvent.click(screen.getByRole('button'));
    expect(onSelect).toHaveBeenCalledWith('1');
  });
});
```

### Test Coverage

Maintain minimum coverage:
- **Backend**: 80% of new code
- **Frontend**: 75% of new code

## Documentation

### Update Documentation When:

- Adding new features
- Changing API endpoints
- Modifying configuration
- Fixing significant bugs
- Improving performance

**Documentation files to update**:
- `README.md` - Overview changes
- `API_REFERENCE.md` - API changes
- `ARCHITECTURE.md` - Design changes
- Component JSDoc comments
- Function docstrings

**Example docstring**:
```python
def create_trading_signal(
    symbol: str,
    direction: TradeDirection,
    confidence: float,
    reason: str
) -> Signal:
    """Generate a new trading signal.
    
    This function creates a trading signal based on technical
    or fundamental analysis. The signal includes a confidence
    level indicating the probability of success.
    
    Args:
        symbol: Stock ticker symbol (e.g., 'AAPL')
        direction: BUY or SELL direction
        confidence: Confidence level 0.0-1.0
        reason: Text explanation for the signal
    
    Returns:
        Signal object with unique ID and metadata
    
    Raises:
        ValueError: If confidence not between 0 and 1
        SymbolError: If symbol is invalid
    
    Example:
        >>> signal = create_trading_signal('AAPL', TradeDirection.BUY, 0.85)
        >>> print(signal.id)
        'signal_123'
    """
    pass
```

## Pull Request Process

### 1. Before Submitting

```bash
# Update with latest changes from upstream
git fetch upstream
git rebase upstream/main

# Run tests locally
pytest
npm test

# Run linting
black .
flake8 .
npm run lint
```

### 2. Push Changes

```bash
git push origin feature/your-feature-name
```

### 3. Create Pull Request

On GitHub:
1. Click "Compare & pull request"
2. Fill in PR template:

```markdown
## Description
Brief description of changes

## Type of Change
- [ ] New feature
- [ ] Bug fix
- [ ] Documentation update
- [ ] Refactoring

## Related Issue
Fixes #123

## How to Test
Steps to verify the changes

## Checklist
- [ ] Code follows style guidelines
- [ ] Tests added/updated
- [ ] Documentation updated
- [ ] No breaking changes
```

### 4. Code Review

- Respond promptly to feedback
- Request changes only when necessary
- Be open to suggestions
- Engage constructively

### 5. Merge

Once approved, maintainers will merge your PR.

## Commit Guidelines

### Commit Message Format

```
<type>(<scope>): <subject>

<body>

<footer>
```

**Type**: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`

**Example**:
```
feat(trades): add stop-loss support to trades

Add stop-loss and take-profit support to trade execution.
Users can now set automatic exit prices when creating trades.

Fixes #456
```

### Commit Best Practices

```bash
# Good commits - Small, focused changes
git commit -m "feat(auth): add refresh token endpoint"
git commit -m "fix(portfolio): correct P&L calculation"
git commit -m "test(trades): add test for trade validation"

# Bad commits - Large, unfocused changes
git commit -m "fixed stuff and added features"
git commit -m "Work in progress"
```

## Issues & Bug Reports

### Reporting Bugs

Include:
- Clear description of the issue
- Steps to reproduce
- Expected behavior
- Actual behavior
- Environment details (OS, version)
- Screenshots if applicable

**Bug report template**:
```markdown
## Describe the Bug
Clear description of what went wrong.

## Steps to Reproduce
1. Step 1
2. Step 2
3. Bug occurs

## Expected Behavior
What should happen

## Actual Behavior
What actually happens

## Environment
- OS: Windows 10
- Python: 3.11.0
- Node: 18.14.0
- Browser: Chrome 112

## Screenshots
[If applicable]
```

### Feature Requests

Include:
- Clear description of the feature
- Use case and benefits
- Potential implementation approach
- Any related issues

## Getting Help

- **Documentation**: Check docs/ folder
- **Issues**: Search existing issues
- **Discussions**: Ask in GitHub Discussions
- **Community**: Join our community chat

## Recognition

Contributors will be recognized:
- In the CONTRIBUTORS file
- In release notes
- On the project website

---

**Last Updated**: April 2026

Thank you for contributing to TradeAdviser! 🚀
