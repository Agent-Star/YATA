export const initialAuthState = {
  user: null,
  isAuthenticated: false,
  accounts: [],
};

export function authReducer(state, action) {
  switch (action.type) {
    case 'REGISTER':
      return {
        ...state,
        accounts: [...state.accounts, action.payload.account],
        user: { account: action.payload.account.account },
        isAuthenticated: true,
      };
    case 'LOGIN':
      return {
        ...state,
        user: { account: action.payload.account },
        isAuthenticated: true,
      };
    case 'LOGOUT':
      return {
        ...state,
        user: null,
        isAuthenticated: false,
      };
    default:
      return state;
  }
}
