import '@mantine/core/styles.css';
import './style.css';

import {
  Autocomplete, Button, Card, Checkbox, createTheme, FileInput, MantineProvider, MultiSelect, NumberInput,
  Badge, SegmentedControl, Select, Switch, Table, Tabs, Textarea, TextInput, Title, Tooltip,
} from '@mantine/core';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';

import App from './App';
import { KOLOR_PODSWIETLENIA } from './wyglad';
import { wczytajPamiec } from './pamiecSerwera';

const klient = new QueryClient({
  // dane zmieniaja sie tylko z wersja danych serwera (jest w kluczu zapytan) - bez ponownego pobierania przy
  // powrocie na karte; zapytania bez wersji (stan, lista zapisow) maja wlasny staleTime
  defaultOptions: { queries: { refetchOnWindowFocus: false, retry: 1, staleTime: Infinity, gcTime: 30 * 60_000 } },
});

// Jeden rozmiar pol i przyciskow w calej aplikacji (sm = 36 px wysokosci); wyjatki tylko dla akcji w wierszach tabel
const ROZMIAR = { size: 'sm' } as const;
const motyw = createTheme({
  primaryColor: 'teal',
  defaultRadius: 'md',
  fontFamily: 'Inter, system-ui, sans-serif',
  // jedna skala naglowkow sekcji: h4 tytul zakladki, h5 sekcja, h6 podsekcja
  headings: {
    fontFamily: 'Inter, system-ui, sans-serif', fontWeight: '600',
    sizes: { h4: { fontSize: '18px', lineHeight: '1.3' }, h5: { fontSize: '16px', lineHeight: '1.35' },
      h6: { fontSize: '14px', lineHeight: '1.4' } },
  },
  components: {
    Button: Button.extend({ defaultProps: ROZMIAR }),
    TextInput: TextInput.extend({ defaultProps: ROZMIAR }),
    NumberInput: NumberInput.extend({ defaultProps: ROZMIAR }),
    Select: Select.extend({ defaultProps: ROZMIAR }),
    MultiSelect: MultiSelect.extend({ defaultProps: ROZMIAR }),
    Autocomplete: Autocomplete.extend({ defaultProps: ROZMIAR }),
    FileInput: FileInput.extend({ defaultProps: ROZMIAR }),
    Textarea: Textarea.extend({ defaultProps: ROZMIAR }),
    SegmentedControl: SegmentedControl.extend({ defaultProps: ROZMIAR }),
    Switch: Switch.extend({ defaultProps: ROZMIAR }),
    Checkbox: Checkbox.extend({ defaultProps: ROZMIAR }),
    Card: Card.extend({ defaultProps: { padding: 'sm', radius: 'md' } }),
    // wszystkie tabele: ta sama czcionka, odstepy, ramka i zielone podswietlenie wiersza pod kursorem
    Table: Table.extend({
      defaultProps: { fz: 'sm', verticalSpacing: 6, horizontalSpacing: 'sm', withTableBorder: true,
        highlightOnHover: true, highlightOnHoverColor: KOLOR_PODSWIETLENIA },
    }),
    Title: Title.extend({ defaultProps: { order: 5 } }),
    Badge: Badge.extend({ defaultProps: { radius: 'sm' } }),
    Tooltip: Tooltip.extend({ defaultProps: { withArrow: true, openDelay: 200 } }),
    // jeden margines zakladek (tresc karty zaczyna sie w tym samym miejscu na kazdej zakladce)
    Tabs: Tabs.extend({ styles: { panel: { padding: 'var(--mantine-spacing-md)' } } }),
  },
});

// pamiec interfejsu (lista zyczen, filtry, uklad tabel) musi byc wczytana przed pierwszym renderem
void wczytajPamiec().finally(() => {
  createRoot(document.getElementById('root')!).render(
    <StrictMode>
      <MantineProvider theme={motyw} defaultColorScheme="dark">
        <QueryClientProvider client={klient}>
          <App />
        </QueryClientProvider>
      </MantineProvider>
    </StrictMode>,
  );
  // pomiar czasu startu programu (dziennik ~/.fm_moneyball/logi): interfejs gotowy
  void fetch('/api/system/gotowe', { method: 'POST' }).catch(() => undefined);
});
