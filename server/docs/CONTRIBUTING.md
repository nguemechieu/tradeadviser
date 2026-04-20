# Contributing to TradeAdviser

Thank you for your interest in contributing to TradeAdviser! This document provides guidelines and instructions for contributing to the project.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Making Changes](#making-changes)
- [Coding Standards](#coding-standards)
- [Testing](#testing)
- [Commit Messages](#commit-messages)
- [Pull Requests](#pull-requests)
- [Reporting Bugs](#reporting-bugs)
- [Suggesting Features](#suggesting-features)

---

## Code of Conduct

### Our Pledge

We are committed to providing a welcoming and inclusive environment for all contributors. We pledge to:

- Be respectful and inclusive
- Welcome people of all backgrounds
- Be patient and constructive
- Focus on what is best for the community

### Our Responsibilities

Project maintainers are responsible for clarifying standards of acceptable behavior and taking appropriate corrective action.

### Enforcement

Instances of unacceptable behavior may be reported to the project team at conduct@sopotek.com.

---

## Getting Started

### Prerequisites

- Python 3.10+
- Node.js 18+
- Git
- Docker (optional but recommended)

### Fork and Clone

```bash
# 1. Fork the repository on GitHub
# 2. Clone your fork
git clone https://github.com/YOUR_USERNAME/tradeadviser.git
cd tradeadviser

# 3. Add upstream remote
git remote add upstream https://github.com/sopotek/tradeadviser.git

# 4. Create a branch for your changes
git checkout -b feature/your-feature-name
```

---

## Development Setup

### Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # macOS/Linux
# or
venv\Scripts\activate  # Windows

# Install dependencies including dev tools
pip install -r requirements.txt
pip install pytest pytest-cov black flake8 mypy

# Install pre-commit hooks
pip install pre-commit
pre-commit install
```

### Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Install dev dependencies
npm install --save-dev eslint prettier @testing-library/react jest
```

### Environment Setup

```bash
cp .env.example .env.local

# Edit .env.local with your development settings
# DATABASE_URL=sqlite:///./test.db
# JWT_SECRET_KEY=dev-secret-key
```

### Run Development Servers

```bash
# Terminal 1: Backend
cd backend
source venv/bin/activate
python -m uvicorn main:app --reload

# Terminal 2: Frontend
cd frontend
npm run dev
```

---

## Making Changes

### Branch Naming Convention

```
feature/description          # New features
fix/description              # Bug fixes
docs/description             # Documentation
refactor/description         # Code refactoring
test/description             # Tests
perf/description             # Performance improvements
```

### Example

```bash
git checkout -b feature/add-signal-alerts
git checkout -b fix/portfolio-calculation-bug
```

---

## Coding Standards

### Backend (Python)

#### Style Guide: PEP 8

```bash
# Format code with Black
black backend/

# Check with flake8
flake8 backend/

# Type checking with mypy
mypy backend/
```

#### Python Best Practices

```python
# 1. Type hints
def calculate_sharpe_ratio(returns: List[float]) -> float:
    """Calculate Sharpe ratio from returns."""
    pass

# 2. Docstrings
def execute_trade(self, trade_req: TradeRequest) -> Trade:
    """
    Execute a trade based on the request.
    
    Args:
        trade_req: Trade request with details
        
    Returns:
        Executed trade object
        
    Raises:
        InsufficientFundsError: If account balance is insufficient
    """
    pass

# 3. Exception handling
try:
    execute_trade(req)
except InsufficientFundsError as e:
    logger.error(f"Trade failed: {e}")
    raise

# 4. Logging
logger.info(f"Trade executed: {trade.id}")
logger.warning("Risk threshold approaching")
logger.error("Trade execution failed")
```

#### File Organization

```python
# 1. Imports at top
from typing import List, Dict, Optional
from datetime import datetime
from fastapi import APIRouter, Depends
from sqlalchemy import Column, String, Float

# 2. Constants
DEFAULT_PAGE_SIZE = 50
MAX_POSITION_SIZE = 10000

# 3. Classes/Functions
class TradeService:
    pass

def calculate_position_value() -> float:
    pass
```

### Frontend (JavaScript/React)

#### Style Guide: Airbnb

```bash
# Format with Prettier
npx prettier --write src/

# Lint with ESLint
npx eslint src/
```

#### React Best Practices

```javascript
// 1. Functional components
export const TradeList = ({ trades }) => {
  const [selectedTrade, setSelectedTrade] = useState(null);
  
  return (
    <div>
      {trades.map(trade => (
        <TradeItem key={trade.id} trade={trade} />
      ))}
    </div>
  );
};

// 2. Props validation
import PropTypes from 'prop-types';

TradeList.propTypes = {
  trades: PropTypes.arrayOf(PropTypes.object).isRequired,
};

// 3. Custom hooks
const useTradeData = () => {
  const [trades, setTrades] = useState([]);
  // ...
  return { trades };
};

// 4. Error handling
try {
  const response = await api.getTrades();
  setTrades(response.data);
} catch (error) {
  setError(error.message);
}
```

---

## Testing

### Backend Testing

```bash
cd backend

# Run all tests
pytest

# Run with coverage
pytest --cov=app tests/

# Run specific test file
pytest tests/test_trading_service.py

# Run specific test
pytest tests/test_trading_service.py::test_execute_trade

# Watch mode
ptw
```

#### Writing Tests

```python
import pytest
from app.backend.services.trading_service import TradingService

class TestTradingService:
    @pytest.fixture
    def service(self):
        return TradingService()
    
    def test_execute_trade_success(self, service):
        # Arrange
        trade_req = TradeRequest(symbol="AAPL", quantity=100)
        
        # Act
        result = service.execute_trade(trade_req)
        
        # Assert
        assert result.status == "EXECUTED"
        assert result.quantity == 100
    
    def test_execute_trade_insufficient_funds(self, service):
        # Arrange
        trade_req = TradeRequest(symbol="AAPL", quantity=1000000)
        
        # Act & Assert
        with pytest.raises(InsufficientFundsError):
            service.execute_trade(trade_req)
```

### Frontend Testing

```bash
cd frontend

# Run tests
npm test

# Run with coverage
npm test -- --coverage

# Watch mode
npm test -- --watch
```

#### Writing Tests

```javascript
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import TradeForm from './TradeForm';

describe('TradeForm', () => {
  it('renders form fields', () => {
    render(<TradeForm />);
    expect(screen.getByLabelText(/symbol/i)).toBeInTheDocument();
  });
  
  it('submits form with values', async () => {
    const handleSubmit = jest.fn();
    render(<TradeForm onSubmit={handleSubmit} />);
    
    const button = screen.getByRole('button', { name: /submit/i });
    await userEvent.click(button);
    
    expect(handleSubmit).toHaveBeenCalled();
  });
});
```

### Test Coverage Goals

- **Backend**: 80% minimum
- **Frontend**: 75% minimum
- Critical paths: 100%

---

## Commit Messages

### Commit Message Format

```
<type>(<scope>): <subject>

<body>

<footer>
```

### Types

- `feat`: A new feature
- `fix`: A bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting, etc.)
- `refactor`: Code refactoring
- `perf`: Performance improvements
- `test`: Test additions or changes
- `chore`: Build or dependency changes

### Examples

```
feat(trading): add signal-based trade execution

Implement automatic trade execution based on generated signals.
Includes risk validation and position sizing.

Fixes #123
```

```
fix(portfolio): correct portfolio allocation calculation

The portfolio allocation calculation was not accounting for
cash positions correctly.

Fixes #456
```

```
docs(readme): update installation instructions
```

---

## Pull Requests

### PR Process

1. **Create a descriptive PR title**
   - Follow the same format as commit messages
   - Example: `feat(auth): implement OAuth 2.0 authentication`

2. **PR Description**
   ```markdown
   ## Description
   Brief description of changes
   
   ## Related Issues
   Fixes #123
   
   ## Type of Change
   - [x] Bug fix
   - [ ] New feature
   - [ ] Breaking change
   
   ## Testing
   - [x] Unit tests added
   - [x] Integration tests added
   - [ ] Manual testing done
   
   ## Checklist
   - [x] Code follows style guidelines
   - [x] Self-review completed
   - [x] Comments added for complex logic
   - [x] Tests added/updated
   - [x] Documentation updated
   ```

3. **Code Review**
   - Expect feedback from maintainers
   - Respond to comments constructively
   - Make requested changes in new commits

4. **Merge**
   - Ensure all checks pass
   - Maintainer will merge your PR

### Review Expectations

- Code quality and consistency
- Test coverage
- Documentation
- Performance implications
- Security considerations

---

## Reporting Bugs

### Bug Report Template

```markdown
## Description
Clear description of the bug

## Reproduction Steps
1. Step 1
2. Step 2
3. Step 3

## Expected Behavior
What should happen

## Actual Behavior
What actually happens

## Environment
- OS: [e.g., Windows, macOS, Linux]
- Python version: [e.g., 3.10]
- Node version: [e.g., 18.0]
- TradeAdviser version: [e.g., 1.0.0]

## Screenshots
If applicable

## Logs
```bash
Error messages or logs
```

## Additional Context
Any additional context
```

### Where to Report

- Create an issue on GitHub: https://github.com/sopotek/tradeadviser/issues
- For security issues, email: security@sopotek.com

---

## Suggesting Features

### Feature Request Template

```markdown
## Description
Clear description of the feature

## Motivation
Why is this feature needed?

## Proposed Solution
How should this be implemented?

## Alternatives Considered
Other approaches considered

## Additional Context
Any additional context or examples
```

### Feature Discussion

- Create an issue to discuss with maintainers
- Wait for feedback before starting implementation
- Ensure feature aligns with project goals

---

## Resources

### Documentation
- [Architecture Documentation](../docs/ARCHITECTURE.md)
- [API Documentation](../docs/API.md)
- [Deployment Guide](../docs/DEPLOYMENT.md)

### Tools
- [FastAPI Docs](https://fastapi.tiangolo.com/)
- [React Docs](https://react.dev/)
- [pytest Docs](https://docs.pytest.org/)
- [SQLAlchemy Docs](https://docs.sqlalchemy.org/)

### Getting Help

- GitHub Issues: Ask questions in issues
- Discussions: Community discussions
- Email: contributors@sopotek.com

---

## License

By contributing to TradeAdviser, you agree that your contributions will be licensed under the MIT License.

---

**Thank you for contributing to TradeAdviser!** 🚀

**Last Updated**: April 2026
