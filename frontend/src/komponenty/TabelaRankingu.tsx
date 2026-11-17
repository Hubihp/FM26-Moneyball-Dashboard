import { AllCommunityModule, colorSchemeDark, ModuleRegistry, themeQuartz, type ColDef, type RowClassParams,
  type ColumnState, type GridApi, type IRowNode, type SelectionChangedEvent } from 'ag-grid-community';
import { AG_GRID_LOCALE_PL } from '@ag-grid-community/locale';
import { AgGridReact } from 'ag-grid-react';
import { Badge, Button, Checkbox, Group, Popover, ScrollArea, Stack } from '@mantine/core';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { CZCIONKA_NAGLOWKA, CZCIONKA_TABELI, KOLOR_PODSWIETLENIA } from '../wyglad';
import FiltrKolumny, { czyModelFiltra, opisModelu } from './FiltrKolumny';

import type { Kolumna, Wiersz } from '../api';
import { formatuj, kolorNiedowartosciowania, kolorWyniku, kolorZmiany } from '../format';
import { kluczZawodnika } from '../pamiec';
import { czytaj, zapisz } from '../pamiecSerwera';
import { PrzyciskGwiazdki } from './Gwiazdka';
import { kopiuj, useMenuZawodnika } from './MenuZawodnika';

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
  rowHoverColor: KOLOR_PODSWIETLENIA,
  selectedRowBackgroundColor: 'rgba(18, 184, 134, 0.18)',
  accentColor: '#12b886',
  fontSize: CZCIONKA_TABELI,
  headerFontSize: CZCIONKA_NAGLOWKA,
  rowHeight: 36,
  // okno filtra kolumny jak panele Mantine
  menuBackgroundColor: '#2e2e2e',
  menuBorder: { color: '#424242' },
  menuShadow: '0 8px 24px rgba(0, 0, 0, 0.45)',
  borderRadius: 8,
});

type Props = {
  kolumny: Kolumna[];
  wiersze: Wiersz[];
  mojKlubUid: number | null | undefined;
  // kolejnosc: wiersze tabeli w biezacej kolejnosci (po sortowaniu i filtrach) - do "poprzedni / nastepny" w karcie
  naWybor: (id: string, wiersz?: Wiersz, kolejnosc?: Wiersz[]) => void;
  // pozycja, w ktorej puli sa wiersze (menu kontekstowe: porownanie, karta); wiersz Listy zyczen ma wlasna
  pozycja?: string;
  // filtry kolumn zapamietane poza tabela (zostaja przy zmianie pozycji): model AG Grid {kolumna: filtr}
  filtryKolumn?: ModelFiltrow;
  naFiltryKolumn?: (model: ModelFiltrow) => void;
  // po zamknieciu karty fokus wraca do wiersza ostatnio ogladanego zawodnika
  fokusId?: string | null;
  // zaznaczanie do porownania: wspolny stan (zaznaczeni) dla Rankingu, Okazji i Listy zyczen;
  // naZaznaczenie dostaje zaznaczonych w tej tabeli i ID wszystkich jej wierszy
  zaznaczeni?: string[];
  naZaznaczenie?: (ids: string[], wszystkie: string[]) => void;
  // lista zyczen: klucze zawodnikow z gwiazdka i przelaczanie gwiazdki
  ulubione?: Set<string>;
  przelaczUlubione?: (wiersz: Wiersz) => void;
  // klucz zapamietanego ukladu (sortowanie, kolejnosc, szerokosc, ukryte kolumny), np. "ranking|Napastnik"
  kluczUkladu?: string;
};

export type ModelFiltrow = Record<string, unknown>;

const PREFIKS_UKLADU = 'fm-uklad|';
const PREFIKS_SZEROKOSCI = 'fm-szerokosci|';

// Szerokosc kolumny z tresci: najdluzsza wartosc (po sformatowaniu) i naglowek w dwoch wierszach, zmierzone
// czcionka tabeli; bez kolumn ustawionych recznie. Kolumny z wlasnym wygladem (pasek, gwiazdka) bez zmian.
const BEZ_DOPASOWANIA = new Set(['gwiazdka', 'ag-Grid-SelectionColumn', 'Percentyl']);
const MIN_SZEROKOSCI = 56;
const MAKS_SZEROKOSCI = 340;
const MAKS_WIERSZY_POMIARU = 1500;
let plotno: CanvasRenderingContext2D | null = null;
// krój czcionki faktycznie uzytej w komorkach tabeli (Inter albo czcionka systemowa, gdy Intera nie ma)
const kroj = () => {
  const komorka = document.querySelector('.ag-cell');
  return komorka ? getComputedStyle(komorka).fontFamily : 'system-ui, sans-serif';
};
function szerokoscTekstu(tekst: string, pogrubiony = false, rozmiar = CZCIONKA_TABELI): number {
  plotno ??= document.createElement('canvas').getContext('2d');
  if (!plotno) return tekst.length * 8;
  plotno.font = `${pogrubiony ? 600 : 400} ${rozmiar}px ${kroj()}`;
  return plotno.measureText(tekst).width;
}
function szerokosciZTresci(api: GridApi<Wiersz>, reczne: Record<string, number>) {
  const kolumny = (api.getColumns() ?? []).filter((c) => c.isVisible() && !BEZ_DOPASOWANIA.has(c.getColId())
    && !(c.getColId() in reczne));
  const wiersze: IRowNode<Wiersz>[] = [];
  api.forEachNode((n) => { if (wiersze.length < MAKS_WIERSZY_POMIARU) wiersze.push(n); });
  return kolumny.map((c) => {
    const naglowek = c.getColDef().headerName ?? c.getColId();
    const slowa = naglowek.split(/\s+/);
    // naglowek zawija sie do dwoch wierszy: szerokosc to dluzsze z najdluzszego slowa i polowy calosci
    // + odstepy komorki (i ikona sortowania w kolumnie, po ktorej tabela jest posortowana)
    const szerNaglowka = Math.max(...slowa.map((w) => szerokoscTekstu(w, true, CZCIONKA_NAGLOWKA)),
      szerokoscTekstu(naglowek, true, CZCIONKA_NAGLOWKA) / 2) + (c.getSort() ? 62 : 40);
    const pogrubiony = c.getColId() === 'Piłkarz';
    let szerTresci = 0;
    for (const n of wiersze) {
      const v = api.getCellValue({ rowNode: n, colKey: c, useFormatter: true });
      if (v !== null && v !== undefined) szerTresci = Math.max(szerTresci, szerokoscTekstu(String(v), pogrubiony));
    }
    const szer = Math.round(Math.min(MAKS_SZEROKOSCI, Math.max(MIN_SZEROKOSCI, szerNaglowka, szerTresci * 1.04 + 34)));
    return { key: c.getColId(), newWidth: szer };
  });
}

// Stale obiekty (nie tworzone przy kazdym renderze): nowy obiekt kazal siatce przebudowac kolumny,
// co przywracalo domyslne sortowanie SCORE obok sortowania wybranego przez uzytkownika
const KOLUMNA_ZAZNACZENIA = { pinned: 'left' as const, width: 46, headerTooltip: 'Zaznacz do porównania' };
// Bez ikonek filtra i menu w naglowkach (zabieraly miejsce): filtr kolumny otwiera prawy przycisk na naglowku
const DOMYSLNA_KOLUMNA = { wrapHeaderText: true, autoHeaderHeight: false, width: 120, suppressHeaderFilterButton: true,
  suppressHeaderMenuButton: true };

function wczytajUklad(klucz: string | undefined): ColumnState[] | null {
  if (!klucz) return null;
  try {
    const zapis = czytaj(PREFIKS_UKLADU + klucz);
    return zapis ? (JSON.parse(zapis) as ColumnState[]) : null;
  } catch {
    return null;
  }
}

type Kontekst = { ulubione?: Set<string>; przelaczUlubione?: (wiersz: Wiersz) => void };

function Gwiazdka({ data, context }: { data?: Wiersz; context: Kontekst }) {
  if (!data || !context.przelaczUlubione) return null;
  const aktywna = context.ulubione?.has(kluczZawodnika(data)) ?? false;
  return <PrzyciskGwiazdki aktywna={aktywna} przelacz={() => context.przelaczUlubione?.(data)} />;
}

// Niedowartosciowanie z oznaczeniem U21: cena mlodego zawodnika zawiera potencjal, ktorego model nie widzi
function Niedowartosciowanie({ value, data }: { value: number | null; data?: Wiersz }) {
  if (value === null || value === undefined) return <span>–</span>;
  return (
    <span>
      {formatuj(value, 'mnoznik')}
      {data?.['U21'] ? (
        <span className="znacznik-u21" title="U21: cena zawiera potencjał, którego model nie widzi - wskaźnik jest zaniżony">
          U21
        </span>
      ) : null}
    </span>
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

const MALA_PROBA_MINUT = 900;

export default function TabelaRankingu({ kolumny, wiersze, mojKlubUid, naWybor, zaznaczeni, naZaznaczenie, ulubione,
  przelaczUlubione, kluczUkladu, pozycja, filtryKolumn, naFiltryKolumn, fokusId }: Props) {
  const siatka = useRef<AgGridReact<Wiersz>>(null);
  const menu = useMenuZawodnika();

  // wiersze w kolejnosci widocznej w tabeli (sortowanie i filtry kolumn)
  const kolejnosc = () => {
    const lista: Wiersz[] = [];
    siatka.current?.api?.forEachNodeAfterFilterAndSort((n) => { if (n.data) lista.push(n.data); });
    return lista;
  };
  const otworz = (w: Wiersz) => naWybor(String(w['ID']), w, kolejnosc());

  // Filtry kolumn trzymane poza tabela: nalozenie po zbudowaniu kolumn i przy zmianie z zewnatrz
  const filtryRef = useRef(filtryKolumn);
  filtryRef.current = filtryKolumn;
  const nalozFiltry = useCallback(() => {
    const api = siatka.current?.api;
    const model = filtryRef.current;
    if (!api || !model) return;
    // tylko filtry w obecnym formacie (dawne filtry tekstowe/liczbowe AG Grid sa pomijane)
    const dostepne = Object.fromEntries(Object.entries(model).filter(([kol, f]) => api.getColumn(kol) && czyModelFiltra(f)));
    if (JSON.stringify(api.getFilterModel()) !== JSON.stringify(dostepne)) api.setFilterModel(dostepne);
  }, []);
  useEffect(() => {
    nalozFiltry();
  }, [filtryKolumn, nalozFiltry]);

  // po zamknieciu karty: fokus na wierszu ostatnio ogladanego zawodnika (dalsza nawigacja strzalkami)
  const poprzedniFokus = useRef<string | null>(null);
  useEffect(() => {
    const api = siatka.current?.api;
    const wczesniej = poprzedniFokus.current;
    poprzedniFokus.current = fokusId ?? null;
    if (!api || fokusId || !wczesniej) return;
    const wezel = api.getRowNode(wczesniej);
    if (wezel?.rowIndex === null || wezel?.rowIndex === undefined || !wezel.displayed) return;
    api.ensureIndexVisible(wezel.rowIndex);
    window.setTimeout(() => api.setFocusedCell(wezel.rowIndex!, 'Piłkarz', wezel.rowPinned), 60);
  }, [fokusId]);
  const [ukryte, setUkryte] = useState<string[]>([]);

  // Uklad tabeli zapamietany w pamieci interfejsu: zapis po kazdej zmianie, odtworzenie po zbudowaniu kolumn
  const odtwarzanie = useRef(false);
  // szerokosci ustawione recznie (przeciagniecie krawedzi) - reszte program dopasowuje do zawartosci
  const reczne = useRef<Record<string, number>>({});
  useEffect(() => {
    try {
      reczne.current = kluczUkladu ? JSON.parse(czytaj(PREFIKS_SZEROKOSCI + kluczUkladu) || '{}') : {};
    } catch {
      reczne.current = {};
    }
  }, [kluczUkladu]);
  const dopasujSzerokosci = useCallback(() => {
    const api = siatka.current?.api;
    if (!api) return;
    const szerokosci = szerokosciZTresci(api, reczne.current);
    if (szerokosci.length) api.setColumnWidths(szerokosci, true, 'api');
  }, []);
  const zapiszUklad = useCallback(() => {
    const api = siatka.current?.api;
    if (!api) return;
    // szerokosc w ukladzie tylko dla kolumn zmienionych recznie (reszta liczona z tresci)
    const stan = api.getColumnState().map(({ width, ...c }) => (c.colId in reczne.current ? { ...c, width } : c));
    const nowe = stan.filter((c) => c.hide).map((c) => c.colId);
    setUkryte((stare) => (stare.join('|') === nowe.join('|') ? stare : nowe));
    if (!kluczUkladu || odtwarzanie.current) return;
    zapisz(PREFIKS_UKLADU + kluczUkladu, JSON.stringify(stan));
  }, [kluczUkladu]);
  const odtworzUklad = useCallback(() => {
    const api = siatka.current?.api;
    const uklad = wczytajUklad(kluczUkladu);
    if (!api || !uklad) return;
    odtwarzanie.current = true;
    api.applyColumnState({ state: uklad.map(({ width, ...c }) => (c.colId in reczne.current ? { ...c, width } : c)),
      applyOrder: true });
    odtwarzanie.current = false;
    setUkryte(uklad.filter((c) => c.hide).map((c) => c.colId));
  }, [kluczUkladu]);
  const przywrocUklad = () => {
    if (kluczUkladu) {
      zapisz(PREFIKS_UKLADU + kluczUkladu, null);
      zapisz(PREFIKS_SZEROKOSCI + kluczUkladu, null);
    }
    reczne.current = {};
    siatka.current?.api?.resetColumnState();
    setUkryte([]);
    dopasujSzerokosci();
  };
  const przelaczKolumne = (pole: string, widoczna: boolean) => {
    siatka.current?.api?.setColumnsVisible([pole], widoczna);
    zapiszUklad();
  };

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
          // filtr pod prawym przyciskiem: lista wartosci (tekst), zakres (liczby) albo zakres dat
          filter: FiltrKolumny,
          filterParams: { rodzaj: k.format === 'tekst' ? 'lista' : k.format === 'data' ? 'data' : 'zakres', format: k.format },
          minWidth: MIN_SZEROKOSCI,
        };
        if (k.pole === 'Piłkarz') {
          Object.assign(def, {
            pinned: 'left', minWidth: 140, cellStyle: { cursor: 'pointer', fontWeight: 600 },
            // niepelne statystyki (czesc minut w rozgrywkach bez szczegolowych statystyk): znak ostrzezenia
            valueFormatter: (p: { value: unknown; data?: Wiersz }) =>
              `${p.data?.['Statystyki_niepełne'] ? '⚠ ' : ''}${String(p.value ?? '')}`,
            tooltipValueGetter: (p: { data?: Wiersz }) => (p.data?.['Statystyki_niepełne']
              ? 'Niepełne statystyki: część minut w rozgrywkach bez szczegółowych statystyk - te statystyki liczone '
                + 'z pozostałych minut albo przyjęte na poziomie średniej pozycji' : null),
            cellClassRules: { 'komorka-moj-klub': (p: { data?: Wiersz }) => czyMoj(p.data, mojKlubUid) },
          });
        }
        if (k.pole === 'Kandydat z pozycji') {
          Object.assign(def, { cellClass: 'komorka-kandydat' });
        }
        if (k.pole === 'Niedowartościowanie') {
          Object.assign(def, {
            width: 120,
            headerTooltip: 'Wycena wg wyniku / cena. ×2 = zawodnik gra jak typowy zawodnik dwa razy droższy '
              + '(o tym samym wieku i kontrakcie). U21: wskaźnik zaniżony - cena młodych zawiera potencjał.',
            cellRenderer: Niedowartosciowanie,
            cellStyle: (p: { value: number | null }) => {
              const kolor = p.value === null || p.value === undefined ? undefined : kolorNiedowartosciowania(p.value);
              return kolor ? { color: kolor, fontWeight: 700 } : null;
            },
          });
        }
        if (k.pole === 'Wycena wg wyniku') {
          def.headerTooltip = 'Cena typowa dla zawodnika z takim wynikiem, wiekiem i kontraktem (model w obrębie pozycji).';
        }
        if (k.pole === 'Minuty') {
          // mala proba: SCORE bez zmian, ale mniej pewny (pomaranczowo, z podpowiedzia)
          Object.assign(def, {
            cellStyle: (p: { value: number | null }) => (typeof p.value === 'number' && p.value < MALA_PROBA_MINUT
              ? { color: '#fd7e14' } : null),
            tooltipValueGetter: (p: { value: number | null }) => (typeof p.value === 'number' && p.value < MALA_PROBA_MINUT
              ? `Mała próba (poniżej ${MALA_PROBA_MINUT} minut) - SCORE mniej pewny` : null),
          });
        }
        if (k.pole === 'Kraj') {
          def.width = 140;
        }
        if (k.pole === 'Liga') {
          // czesc minut poza liga klubu (rezerwy, mlodziez, inny klub): gwiazdka i opis, mnoznik wazony minutami
          Object.assign(def, {
            valueFormatter: (p: { value: unknown; data?: Wiersz }) => `${String(p.value ?? '')}${
              typeof p.data?.['Udział_poza_ligą_klubu'] === 'number' && p.data['Udział_poza_ligą_klubu'] >= 0.25 ? ' *' : ''}`,
            tooltipValueGetter: (p: { data?: Wiersz }) => (p.data?.['Ligi_gry']
              ? `Gdzie grał: ${String(p.data['Ligi_gry'])}. Mnożnik ligi w SCORE ważony minutami.` : null),
          });
        }
        if (k.pole === 'Prognoza SCORE') {
          Object.assign(def, {
            width: 120,
            headerTooltip: 'SCORE za rok: obecny SCORE z częściowym powrotem w stronę średniej pozycji (część wyniku z '
              + 'jednego sezonu to szczęście) plus typowa zmiana w tym wieku. Stabilność i krzywa wieku są liczone z '
              + 'historii kariery (gdy jest), inaczej z wartości typowych.',
            cellStyle: (p: { value: number | null }) => (p.value === null || p.value === undefined ? null
              : { color: kolorWyniku(p.value), fontWeight: 600 }),
          });
        }
        if (k.pole === 'Okazje') {
          Object.assign(def, { width: 200, tooltipField: 'Okazje' });
        }
        if (k.format === 'score') {
          Object.assign(def, {
            pinned: 'left', width: 108, sort: kolumny.some((x) => x.sortuj) ? null : 'desc', wrapHeaderText: false,
            suppressHeaderFilterButton: true,
            cellClass: 'komorka-score',
            cellStyle: (p: { value: number | null }) => (p.value === null ? null : { backgroundColor: kolorWyniku(p.value) }),
            headerTooltip: 'Skala T: 50 = przeciętny zawodnik pozycji w próbie, +10 = jedno odchylenie wyżej (z korektą ligową).',
          });
        }
        if (k.format === 'zmiana') {
          const prog = 2;
          Object.assign(def, {
            width: 110,
            cellStyle: (p: { value: number | null }) => {
              const kolor = typeof p.value === 'number' ? kolorZmiany(p.value, prog) : undefined;
              return kolor ? { color: kolor, fontWeight: 600 } : null;
            },
          });
          if (k.pole === 'Δ SCORE') {
            def.headerTooltip = 'Zmiana SCORE względem ostatniej migawki z poprzedniego sezonu (te same wagi). '
              + '⚠ i pomarańczowa kursywa = mała próba: mniej niż 1000 minut w którymś sezonie, wynik mniej pewny.';
            // mala proba: pomaranczowa kursywa z ostrzezeniem
            def.valueFormatter = (p: { value: unknown; data?: Wiersz }) =>
              typeof p.value === 'number' ? `${p.data?.['Δ_mała_próba'] ? '⚠ ' : ''}${formatuj(p.value, 'zmiana')}` : '';
            def.tooltipValueGetter = (p: { data?: Wiersz }) =>
              p.data?.['Δ_mała_próba'] ? 'Mała próba: mniej niż 1000 minut w którymś sezonie - zmiana mniej pewna' : null;
            def.cellStyle = (p: { value: number | null; data?: Wiersz }): Record<string, string> | null => {
              if (typeof p.value !== 'number') return null;
              if (p.data?.['Δ_mała_próba']) return { color: '#fd7e14', fontStyle: 'italic' };
              const kolor = kolorZmiany(p.value, prog);
              return kolor ? { color: kolor, fontWeight: '600' } : null;
            };
          }
        }
                if (k.sortuj) {
          Object.assign(def, { sort: 'desc', pinned: 'left', width: 130 });
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
    <div style={{ height: '100%', width: '100%', display: 'flex', flexDirection: 'column', gap: 4 }}>
      <Group gap="xs" justify="space-between" wrap="nowrap" align="center">
        <Group gap={6} style={{ minWidth: 0 }}>
          {Object.entries(filtryKolumn ?? {}).filter(([, f]) => czyModelFiltra(f)).map(([kol, f]) => (
            <Badge key={kol} variant="light" color="teal" tt="none" style={{ cursor: 'pointer' }}
              title="Filtr kolumny - kliknij, aby usunąć"
              onClick={() => {
                const { [kol]: _usuniety, ...reszta } = filtryKolumn ?? {};
                naFiltryKolumn?.(reszta);
              }}>
              {kolumny.find((k) => k.pole === kol)?.naglowek ?? kol}: {opisModelu(f, kolumny.find((k) => k.pole === kol)?.format)} ×
            </Badge>
          ))}
        </Group>
        <Group gap="xs" wrap="nowrap">
        <Popover position="bottom-end" shadow="md" withArrow>
          <Popover.Target>
            <Button variant="subtle">
              Kolumny{ukryte.length ? ` (ukryte: ${ukryte.length})` : ''}
            </Button>
          </Popover.Target>
          <Popover.Dropdown>
            <ScrollArea.Autosize mah={360} type="auto">
              <Stack gap={4}>
                {kolumny.filter((k) => k.pole !== 'Piłkarz').map((k) => (
                  <Checkbox key={k.pole} label={k.naglowek} checked={!ukryte.includes(k.pole)}
                    onChange={(e) => przelaczKolumne(k.pole, e.currentTarget.checked)} />
                ))}
              </Stack>
            </ScrollArea.Autosize>
          </Popover.Dropdown>
        </Popover>
        {kluczUkladu && (
          <Button variant="subtle" color="gray" onClick={przywrocUklad}
            title="Domyślne sortowanie, kolejność, szerokości i widoczność kolumn">
            Przywróć układ
          </Button>
        )}
        </Group>
      </Group>
      {/* prawy przycisk na naglowku otwiera filtr kolumny - bez menu przegladarki */}
      <div style={{ flex: 1, minHeight: 0 }}
        onContextMenu={(e) => { if ((e.target as HTMLElement).closest('.ag-header')) e.preventDefault(); }}>
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
        onFirstDataRendered={() => { synchronizuj(); dopasujSzerokosci(); }}
        onRowDataUpdated={dopasujSzerokosci}
        onCellClicked={(e) => {
          if (e.colDef.field === 'Piłkarz' && e.data) otworz(e.data);
        }}
        onRowDoubleClicked={(e) => e.data && otworz(e.data)}
        // prawy przycisk: menu zawodnika zamiast menu przegladarki
        preventDefaultOnContextMenu
        onCellContextMenu={(e) => {
          const w = e.data;
          const zdarzenie = e.event as MouseEvent | null;
          if (!w || !zdarzenie) return;
          menu.otworzMenu(zdarzenie, { id: String(w['ID']), pozycja: String(w['Pozycja na liście'] ?? pozycja ?? ''),
            pilkarz: String(w['Piłkarz'] ?? ''), wiersz: w });
        }}
        // Enter: karta zawodnika; Ctrl+C: wartosc pola z fokusem (zaznaczony tekst kopiuje sie po staremu)
        onCellKeyDown={(e) => {
          const k = e.event as KeyboardEvent | null;
          if (!k || !e.data) return;
          if (k.key === 'Enter' && !k.ctrlKey && !k.altKey) {
            k.preventDefault();
            otworz(e.data);
          } else if ((k.ctrlKey || k.metaKey) && k.key.toLowerCase() === 'c' && 'column' in e && !window.getSelection()?.toString()) {
            const wartosc = e.api.getCellValue({ rowNode: e.node, colKey: e.column, useFormatter: true });
            const tekst = wartosc === null || wartosc === undefined ? '' : String(wartosc).replace(/^⚠ /, '');
            if (tekst) {
              k.preventDefault();
              void kopiuj(tekst).then((ok) => menu.komunikat(ok ? `Skopiowano: ${tekst}` : 'Nie udało się skopiować'));
            }
          }
        }}
        // prawy przycisk na naglowku kolumny: jej filtr
        onColumnHeaderContextMenu={(e) => {
          if (!e.column || !('getColDef' in e.column) || !e.column.getColDef().filter) return;
          e.api.showColumnFilter(e.column);
        }}
        onFilterChanged={(e) => {
          if (!naFiltryKolumn || e.source === 'api') return;
          naFiltryKolumn(e.api.getFilterModel() as ModelFiltrow);
        }}
        selectionColumnDef={KOLUMNA_ZAZNACZENIA}
        // Stala wysokosc naglowka: autoHeaderHeight liczy ja tylko z wyrenderowanych kolumn (wirtualizacja),
        // wiec po przewinieciu do dlugich nazw caly naglowek rosl. Dluzsze nazwy sa ucinane (pelna w podpowiedzi).
        headerHeight={48}
        defaultColDef={DOMYSLNA_KOLUMNA}
        animateRows={false}
        tooltipShowDelay={300}
        onNewColumnsLoaded={() => { odtworzUklad(); nalozFiltry(); dopasujSzerokosci(); }}
        onGridReady={() => { odtworzUklad(); nalozFiltry(); }}
        onSortChanged={() => { zapiszUklad(); dopasujSzerokosci(); }}
        onColumnMoved={(e) => e.finished && zapiszUklad()}
        onColumnResized={(e) => {
          if (!e.finished || e.source !== 'uiColumnResized') return;
          // reczna zmiana szerokosci: zapamietana i wazniejsza niz dopasowanie do tresci
          for (const c of e.columns ?? []) reczne.current[c.getColId()] = c.getActualWidth();
          if (kluczUkladu) zapisz(PREFIKS_SZEROKOSCI + kluczUkladu, JSON.stringify(reczne.current));
          zapiszUklad();
        }}
        onColumnVisible={zapiszUklad}
        onColumnPinned={zapiszUklad}
      />
      </div>
    </div>
  );
}
