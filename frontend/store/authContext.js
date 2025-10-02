import { createContext, useCallback, useContext, useMemo, useReducer } from 'react';
import { authReducer, initialAuthState } from './authReducer';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [state, dispatch] = useReducer(authReducer, initialAuthState);

  const login = useCallback(
    async ({ account, password }) => {
      const matched = state.accounts.find(
        (item) => item.account === account && item.password === password
      );

      if (!matched) {
        throw new Error('INVALID_CREDENTIALS');
      }

      dispatch({ type: 'LOGIN', payload: { account: matched.account } });
    },
    [state.accounts]
  );

  const register = useCallback(
    async ({ account, password }) => {
      const exists = state.accounts.some((item) => item.account === account);

      if (exists) {
        throw new Error('ACCOUNT_EXISTS');
      }

      const accountRecord = { account, password };

      dispatch({ type: 'REGISTER', payload: { account: accountRecord } });
    },
    [state.accounts]
  );

  const logout = useCallback(() => {
    dispatch({ type: 'LOGOUT' });
  }, []);

  const value = useMemo(
    () => ({
      state,
      login,
      register,
      logout,
    }),
    [state, login, register, logout]
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
