import { Navigate } from 'react-router-dom';
import { useAppContext } from '../contexts/AppContext';

export const ProtectedRoute = ({ children }) => {
  const { isAuthenticated } = useAppContext();

  if (!isAuthenticated) {
    return <Navigate to="/" replace />;
  }

  return children;
};
