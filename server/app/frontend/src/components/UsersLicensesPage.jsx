import { UsersLicensesDashboard } from './users_licenses';
import { useContext } from 'react';
import AuthContext from '../context/AuthProvider';

const UsersLicensesPage = () => {
  const { auth } = useContext(AuthContext);
  
  return (
    <UsersLicensesDashboard 
      token={auth?.token} 
      onError={(err) => console.error('Users & Licenses dashboard error:', err)}
    />
  );
};

export default UsersLicensesPage;
