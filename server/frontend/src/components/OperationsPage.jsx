import { OperationsDashboard } from './operations';
import { useContext } from 'react';
import AuthContext from '../context/AuthProvider';

const OperationsPage = () => {
  const { auth } = useContext(AuthContext);
  
  return (
    <OperationsDashboard 
      token={auth?.token} 
      onError={(err) => console.error('Operations dashboard error:', err)}
    />
  );
};

export default OperationsPage;
