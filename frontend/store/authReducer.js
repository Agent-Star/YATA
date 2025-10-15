export const initialAuthState = {
  user: null,
  isAuthenticated: false,
  accessToken: null,
};

export function authReducer(state, action) {
  switch (action.type) {
    case 'AUTH_SUCCESS':
      return {
        ...state,
        user: action.payload.user || null,
        accessToken: action.payload.accessToken || null,
        isAuthenticated: true,
      };
    case 'SET_USER':
      return {
        ...state,
        user: action.payload.user || null,
        isAuthenticated: Boolean(action.payload.user),
      };
    case 'LOGOUT':
      return {
        ...initialAuthState,
      };
    default:
      return state;
  }
}
