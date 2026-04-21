import { PerformanceAuditDashboard } from './performance_audit';
import { useContext } from 'react';
import AuthContext from '../context/AuthProvider';

const PerformanceAuditPage = () => {
  const { auth } = useContext(AuthContext);
  
  return (
    <PerformanceAuditDashboard 
      token={auth?.token} 
      onError={(err) => console.error('Performance audit dashboard error:', err)}
    />
  );
};

export default PerformanceAuditPage;
