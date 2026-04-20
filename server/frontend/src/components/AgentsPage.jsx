import { AgentsDashboard } from './agents';
import { useContext } from 'react';
import AuthContext from '../context/AuthProvider';

const AgentsPage = () => {
  const { auth } = useContext(AuthContext);
  
  return (
    <AgentsDashboard 
      token={auth?.token} 
      onError={(err) => console.error('Agents dashboard error:', err)}
    />
  );
};

export default AgentsPage;
