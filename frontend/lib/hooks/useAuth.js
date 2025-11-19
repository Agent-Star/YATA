import { useAuthContext } from '@store/authContext';

export function useAuth() {
  return useAuthContext();
}
