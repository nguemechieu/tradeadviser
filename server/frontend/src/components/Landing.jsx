import { Link } from 'react-router-dom';
import '../app.css';

const Landing = () => {
  return (
    <section style={{ 
      display: 'flex', 
      flexDirection: 'column', 
      justifyContent: 'center', 
      alignItems: 'center',
      textAlign: 'center',
      gap: '2rem'
    }}>
      <h1>Welcome to TradeAdviser</h1>
      <p style={{ fontSize: '1.1rem', color: '#8ea3bc' }}>
        Intelligent Trading Advisory Platform
      </p>
      
      <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap', justifyContent: 'center' }}>
        <Link to="/login" className="btn btn-primary">
          Sign In
        </Link>
        <Link to="/register" className="btn btn-secondary">
          Create Account
        </Link>
        <Link to="/tradeadviser" className="btn btn-primary">
          Learn More
        </Link>
      </div>

      <div style={{ marginTop: '2rem', maxWidth: '600px' }}>
        <h3>Features</h3>
        <ul style={{ textAlign: 'left', listStyle: 'none' }}>
          <li>✓ Real-time trading signals</li>
          <li>✓ Advanced portfolio analytics</li>
          <li>✓ Risk management tools</li>
          <li>✓ Multi-asset trading support</li>
        </ul>
      </div>
    </section>
  );
};

export default Landing;
