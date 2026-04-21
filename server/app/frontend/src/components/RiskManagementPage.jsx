import { RiskDashboard } from './risk';
import { useContext } from 'react';
import AuthContext from '../context/AuthProvider';

const RiskManagementPage = () => {
  const { auth } = useContext(AuthContext);
  
  return (
    <RiskDashboard 
      token={auth?.token} 
      onError={(err) => console.error('Risk management dashboard error:', err)}
    />
  );
};

export default RiskManagementPage;
