import React, { createContext, useContext, useMemo } from 'react';
import { ConnectionProvider, WalletProvider } from '@solana/wallet-adapter-react';
import { WalletModalProvider } from '@solana/wallet-adapter-react-ui';
import { PhantomWalletAdapter } from '@solana/wallet-adapter-wallets';
import '@solana/wallet-adapter-react-ui/styles.css';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

const WalletContext = createContext({});

export const useWalletContext = () => useContext(WalletContext);

export const WalletContextProvider = ({ children }) => {
  // Use mainnet-beta for data, devnet for execution
  const endpoint = 'https://api.devnet.solana.com';

  const wallets = useMemo(() => [
    new PhantomWalletAdapter(),
  ], []);

  return (
    <ConnectionProvider endpoint={endpoint}>
      <WalletProvider wallets={wallets} autoConnect={false}>
        <WalletModalProvider>
          <WalletContext.Provider value={{ backendUrl: BACKEND_URL }}>
            {children}
          </WalletContext.Provider>
        </WalletModalProvider>
      </WalletProvider>
    </ConnectionProvider>
  );
};