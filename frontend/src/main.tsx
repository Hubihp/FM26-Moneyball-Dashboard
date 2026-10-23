import '@mantine/core/styles.css';
import './style.css';

import { createTheme, MantineProvider } from '@mantine/core';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';

import App from './App';

const klient = new QueryClient({
  defaultOptions: { queries: { refetchOnWindowFocus: false, retry: 1, staleTime: 30_000 } },
});

const motyw = createTheme({ primaryColor: 'teal', defaultRadius: 'md', fontFamily: 'Inter, system-ui, sans-serif' });

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <MantineProvider theme={motyw} defaultColorScheme="dark">
      <QueryClientProvider client={klient}>
        <App />
      </QueryClientProvider>
    </MantineProvider>
  </StrictMode>,
);
