import { AllCommunityModule, colorSchemeDark, ModuleRegistry, themeQuartz, type ColDef, type RowClassParams,
  type SelectionChangedEvent } from 'ag-grid-community';
import { AG_GRID_LOCALE_PL } from '@ag-grid-community/locale';
import { AgGridReact } from 'ag-grid-react';
import { useCallback, useEffect, useMemo, useRef } from 'react';

import type { Kolumna, Wiersz } from '../api';
import { formatuj, kolorNiedowartosciowania, kolorWyniku, kolorZmiany } from '../format';
import { kluczZawodnika } from '../pamiec';

ModuleRegistry.registerModules([AllCommunityModule]);

// Polskie menu kolumn i filtrow; kilka fraz poprawionych na zwyklejsza polszczyzne
const TEKSTY_PL: Record<string, string> = {
  ...AG_GRID_LOCALE_PL,
  equals: 'Równe',
  notEqual: 'Różne od',
  lessThan: 'Mniejsze niż',
  greaterThan: 'Większe niż',
  lessThanOrEqual: 'Mniejsze lub równe',
  greaterThanOrEqual: 'Większe lub równe',
  inRange: 'W przedziale',
  andCondition: 'i',
  orCondition: 'lub',
  pinColumn: 'Przypnij kolumnę',
  pinLeft: 'Przypnij z lewej',
  pinRight: 'Przypnij z prawej',
  noPin: 'Nie przypinaj',
  autosizeThisColumn: 'Dopasuj szerokość tej kolumny',
  autosizeAllColumns: 'Dopasuj szerokość wszystkich kolumn',
  resetColumns: 'Przywróć kolumny',
  columnFilter: 'Filtr kolumny',
  columnChooser: 'Wybierz kolumny',
  sortAscending: 'Sortuj rosnąco',
  sortDescending: 'Sortuj malejąco',
  sortUnSort: 'Usuń sortowanie',
};

// Szarosci jak w ciemnym motywie Mantine (dark-7 tlo strony, dark-6 naglowki, dark-4 linie)
export const motywTabeli = themeQuartz.withPart(colorSchemeDark).withParams({
  backgroundColor: '#242424',
  foregroundColor: '#c9c9c9',
  headerBackgroundColor: '#2e2e2e',
  chromeBackgroundColor: '#2e2e2e',
  oddRowBackgroundColor: '#272727',
  borderColor: '#424242',
  rowHoverColor: 'rgba(255, 255, 255, 0.05)',
  selectedRowBackgroundColor: 'rgba(18, 184, 134, 0.18)',
  accentColor: '#12b886',
  fontSize: 13,
  headerFontSize: 12,
  rowHeight: 34,
});

type Props = {
  kolumny: Kolumna[];
  wiersze: Wiersz[];
  mojKlubUid: number | null | undefined;
  naWybor: (id: string, wiersz?: Wiersz) => void;
  // zaznaczanie do porownania: wspolny stan (zaznaczeni) dla Rankingu, Okazji i Listy zyczen;
  // naZaznaczenie dostaje zaznaczonych w tej tabeli i ID wszystkich jej wierszy
  zaznaczeni?: string[];
  naZaznaczenie?: (ids: string[], wszystkie: string[]) => void;
  // lista zyczen: klucze zawodnikow z gwiazdka i przelaczanie gwiazdki
  ulubione?: Set<string>;
  przelaczUlubione?: (wiersz: Wiersz) => void;
};

type Kontekst = { ulubione?: Set<string>; przelaczUlubione?: (wiersz: Wiersz) => void };

function Gwiazdka({ data, context }: { data?: Wiersz; context: Kontekst }) {
  if (!data || !context.przelaczUlubione) return null;
  const aktywna = context.ulubione?.has(kluczZawodnika(data)) ?? false;
  return (
    <button type="button" className={`gwiazdka${aktywna ? ' aktywna' : ''}`}
      title={aktywna ? 'Usuń z listy życzeń' : 'Dodaj do listy życzeń'}
      aria-label={aktywna ? 'Usuń z listy życzeń' : 'Dodaj do listy życzeń'} aria-pressed={aktywna}
      onClick={(e) => {
        e.stopPropagation();
        context.przelaczUlubione?.(data);
      }}>
      <svg width="16" height="16" viewBox="0 0 24 24" aria-hidden="true">
        <path d="M12 2.5l2.9 6.1 6.6.8-4.9 4.6 1.3 6.6L12 17.3l-5.9 3.3 1.3-6.6-4.9-4.6 6.6-.8z"
          fill={aktywna ? 'currentColor' : 'none'} stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" />
      </svg>
    </button>
  );
}

function Pasek({ value }: { value: number | null }) {
  if (value === null || value === undefined) return <span>–</span>;
  return (
    <div className="pasek">
      <div className="pasek-tlo" style={{ width: `${Math.max(0, Math.min(100, value))}%` }} />
      <span className="pasek-tekst">{Math.round(value)}</span>
    </div>
  );
}

const czyMoj = (w: Wiersz | undefined, uid: number | null | undefined) =>
  uid !== null && uid !== undefined && w?.['Klub_UID'] === uid;

export default function TabelaRankingu({ kolumny, wiersze, mojKlubUid, naWybor, zaznaczeni, naZaznaczenie, ulubione,
  przelaczUlubione }: Props) {
  const siatka = useRef<AgGridReact<Wiersz>>(null);

  // Pola wyboru zgodne ze wspolnym stanem porownania (np. po przejsciu z innej zakladki)
  const synchronizuj = useCallback(() => {
    const api = siatka.current?.api;
    if (!api || !zaznaczeni) return;
    api.forEachNode((n) => {
      const chce = !!n.data && zaznaczeni.includes(String(n.data['ID']));
      if (n.isSelected() !== chce) n.setSelected(chce, false, 'api');
    });
  }, [zaznaczeni]);
  useEffect(() => {
    synchronizuj();
  }, [synchronizuj, wiersze]);
  const zGwiazdka = !!przelaczUlubione;
  const definicje = useMemo<ColDef<Wiersz>[]>(
    () => [
      ...(zGwiazdka
        ? [{
          colId: 'gwiazdka', headerName: '', headerTooltip: 'Lista życzeń', pinned: 'left' as const, width: 44,
          sortable: false, resizable: false, suppressHeaderMenuButton: true, cellRenderer: Gwiazdka,
          cellStyle: { padding: 0 },
        }]
        : []),
      ...kolumny.map((k) => {
        const def: ColDef<Wiersz> = {
          headerName: k.naglowek,
          field: k.pole,
          headerTooltip: k.naglowek + (k.nizsze_lepsze ? ' (mniej = lepiej)' : ''),
          sortable: true,
          resizable: true,
          valueFormatter: (p) => formatuj(p.value, k.format),
          filter: k.format === 'tekst' ? 'agTextColumnFilter' : 'agNumberColumnFilter',
          minWidth: 70,
          width: k.statystyka ? 118 : undefined,
        };
        if (k.format === 'tekst') {
          def.filter = 'agTextColumnFilter';
        }
        if (k.pole === 'Piłkarz') {
          Object.assign(def, {
            pinned: 'left', minWidth: 170, cellStyle: { cursor: 'pointer', fontWeight: 600 },
            cellClassRules: { 'komorka-moj-klub': (p: { data?: Wiersz }) => czyMoj(p.data, mojKlubUid) },
          });
        }
        if (k.pole === 'Kandydat z pozycji') {
          Object.assign(def, { width: 170, cellClass: 'komorka-kandydat' });
        }
        if (k.pole === 'Niedowartościowanie') {
          Object.assign(def, {
            width: 140,
            headerTooltip: 'Wycena wg wyniku / cena. ×2 = zawodnik gra jak typowy zawodnik dwa razy droższy '
              + '(o tym samym wieku i kontrakcie).',
            cellStyle: (p: { value: number | null }) => {
              const kolor = p.value === null || p.value === undefined ? undefined : kolorNiedowartosciowania(p.value);
              return kolor ? { color: kolor, fontWeight: 700 } : null;
            },
          });
        }
        if (k.pole === 'Wycena wg wyniku') {
          def.headerTooltip = 'Cena typowa dla zawodnika z takim wynikiem, wiekiem i kontraktem (model w obrębie pozycji).';
        }
        if (k.pole === 'Kraj') {
          def.width = 140;
        }
        if (k.pole === 'Okazje') {
          Object.assign(def, { width: 200, tooltipField: 'Okazje' });
        }
        if (k.format === 'score') {
          Object.assign(def, {
            pinned: 'left', width: 108, sort: 'desc', wrapHeaderText: false, suppressHeaderFilterButton: true,
            cellClass: 'komorka-score',
            cellStyle: (p: { value: number | null }) => (p.value === null ? null : { backgroundColor: kolorWyniku(p.value) }),
            headerTooltip: 'Skala T: 50 = przeciętny zawodnik pozycji w próbie, +10 = jedno odchylenie wyżej (z korektą ligową).',
          });
        }
        if (k.format === 'zmiana' || k.format === 'zmiana_proc') {
          const prog = k.format === 'zmiana' ? 2 : 10;
          Object.assign(def, {
            width: 110,
            cellStyle: (p: { value: number | null }) => {
              const kolor = typeof p.value === 'number' ? kolorZmiany(p.value, prog) : undefined;
              return kolor ? { color: kolor, fontWeight: 600 } : null;
            },
          });
          if (k.pole === 'Δ SCORE') {
            def.headerTooltip = 'Zmiana SCORE względem ostatniej migawki z poprzedniego sezonu (te same wagi); '
              + 'liczona przy co najmniej 1000 minutach w obu sezonach.';
          }
          if (k.pole === 'Rozwój vs wiek') {
            def.headerTooltip = 'Zmiana SCORE ponad typową dla zawodników w tym wieku (młodzi zwykle rosną szybciej).';
          }
        }
                if (k.format === 'pasek') {
          Object.assign(def, { cellRenderer: Pasek, width: 110 });
        }
        if (k.format === 'data') {
          def.filter = 'agTextColumnFilter';
        }
        return def;
      }),
    ],
    [kolumny, mojKlubUid, zGwiazdka],
  );

  // Gwiazdki odswiezane bez przebudowy kolumn (przebudowa skasowalaby wybrane sortowanie)
  const kontekst = useRef<Kontekst>({}).current;
  kontekst.ulubione = ulubione;
  kontekst.przelaczUlubione = przelaczUlubione;
  useEffect(() => {
    siatka.current?.api?.refreshCells({ columns: ['gwiazdka'], force: true });
  }, [ulubione]);

  const klasaWiersza = useMemo(
    () => (p: RowClassParams<Wiersz>) => {
      const klasy = [];
      if (czyMoj(p.data, mojKlubUid)) klasy.push('wiersz-moj-klub');
      if (p.data?.['Kandydat']) klasy.push('wiersz-kandydat');
      return klasy.length ? klasy : undefined;
    },
    [mojKlubUid],
  );

  return (
    <div style={{ height: '100%', width: '100%' }}>
      <AgGridReact<Wiersz>
        ref={siatka}
        theme={motywTabeli}
        localeText={TEKSTY_PL}
        context={kontekst}
        rowData={wiersze}
        columnDefs={definicje}
        getRowId={(p) => String(p.data['ID']) + (p.data['Pozycja na liście'] ? `|${p.data['Pozycja na liście']}` : '')}
        getRowClass={klasaWiersza}
        rowSelection={naZaznaczenie ? { mode: 'multiRow', checkboxes: true, headerCheckbox: false, enableClickSelection: false } : undefined}
        onSelectionChanged={(e: SelectionChangedEvent<Wiersz>) => {
          if (e.source === 'api') return;      // zmiana z synchronizacji, nie od uzytkownika
          naZaznaczenie?.(e.api.getSelectedRows().map((w) => String(w['ID'])), wiersze.map((w) => String(w['ID'])));
        }}
        onFirstDataRendered={synchronizuj}
        onCellClicked={(e) => {
          if (e.colDef.field === 'Piłkarz' && e.data) naWybor(String(e.data['ID']), e.data);
        }}
        onRowDoubleClicked={(e) => e.data && naWybor(String(e.data['ID']), e.data)}
        selectionColumnDef={{ pinned: 'left', width: 46, headerTooltip: 'Zaznacz do porównania' }}
        // Stala wysokosc naglowka: autoHeaderHeight liczy ja tylko z wyrenderowanych kolumn (wirtualizacja),
        // wiec po przewinieciu do dlugich nazw caly naglowek rosl. Dluzsze nazwy sa ucinane (pelna w podpowiedzi).
        headerHeight={48}
        defaultColDef={{ wrapHeaderText: true, autoHeaderHeight: false, width: 120 }}
        animateRows={false}
        tooltipShowDelay={300}
      />
    </div>
  );
}
