import { createContext, useCallback, useContext, useEffect, useMemo, useReducer } from 'react';
import { authReducer, initialAuthState } from './authReducer';
import {
  login as loginRequest,
  register as registerRequest,
  logout as logoutRequest,
  fetchProfile,
} from '@lib/services/auth';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [state, dispatch] = useReducer(authReducer, initialAuthState);

  const login = useCallback(
    async ({ account, password }) => {
      const data = await loginRequest({ account, password });
      dispatch({
        type: 'AUTH_SUCCESS',
        payload: {
          user: data?.user || null,
          accessToken: data?.accessToken || null,
        },
      });
      return data;
    },
    []
  );

  const register = useCallback(
    async ({ account, password }) => {
      const data = await registerRequest({ account, password });
      dispatch({
        type: 'AUTH_SUCCESS',
        payload: {
          user: data?.user || null,
          accessToken: data?.accessToken || null,
        },
      });
      return data;
    },
    []
  );

  const logout = useCallback(async () => {
    try {
      await logoutRequest();
    } finally {
      dispatch({ type: 'LOGOUT' });
    }
  }, []);

  const refreshProfile = useCallback(async () => {
    const data = await fetchProfile();
    dispatch({
      type: 'SET_USER',
      payload: { user: data?.user || null },
    });
    return data?.user || null;
  }, []);

  useEffect(() => {
    refreshProfile().catch(() => {});
  }, [refreshProfile]);

  const value = useMemo(
    () => ({
      state,
      login,
      register,
      logout,
      refreshProfile,
    }),
    [state, login, register, logout, refreshProfile]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuthContext() {
  const context = useContext(AuthContext);

  if (!context) {
    throw new Error('useAuthContext must be used within AuthProvider');
  }

  return context;
}
