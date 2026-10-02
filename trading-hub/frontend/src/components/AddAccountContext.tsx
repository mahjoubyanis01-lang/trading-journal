import { createContext, useContext } from 'react';

export const AddAccountContext = createContext<() => void>(() => {});

export function useAddAccount() {
  return useContext(AddAccountContext);
}
