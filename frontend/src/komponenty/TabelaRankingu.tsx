import { AllCommunityModule, colorSchemeDark, ModuleRegistry, themeQuartz, type ColDef, type RowClassParams,
  type SelectionChangedEvent } from 'ag-grid-community';
import { AgGridReact } from 'ag-grid-react';
import { useMemo } from 'react';

import type { Kolumna, Wiersz } from '../api';
import { formatuj, kolorWyniku } from '../format';

ModuleRegistry.registerModules([AllCommunityModule]);

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
  naZaznaczenie?: (ids: string[]) => void;
};

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

export default function TabelaRankingu({ kolumny, wiersze, mojKlubUid, naWybor, naZaznaczenie }: Props) {
  const definicje = useMemo<ColDef<Wiersz>[]>(
    () =>
      kolumny.map((k) => {
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
        if (k.pole === 'Okazje') {
          Object.assign(def, { width: 200, tooltipField: 'Okazje' });
        }
        if (k.format === 'score') {
          Object.assign(def, {
            pinned: 'left', width: 96, sort: 'desc', wrapHeaderText: false, suppressHeaderFilterButton: true,
            cellClass: 'komorka-score',
            cellStyle: (p: { value: number | null }) => (p.value === null ? null : { backgroundColor: kolorWyniku(p.value) }),
            headerTooltip: 'Skala T: 50 = przeciętny zawodnik pozycji w próbie, +10 = jedno odchylenie wyżej (z korektą ligową).',
          });
        }
        if (k.format === 'pasek') {
          Object.assign(def, { cellRenderer: Pasek, width: 110 });
        }
        if (k.format === 'data') {
          def.filter = 'agTextColumnFilter';
        }
        return def;
      }),
    [kolumny, mojKlubUid],
  );

  const klasaWiersza = useMemo(
    () => (p: RowClassParams<Wiersz>) => (czyMoj(p.data, mojKlubUid) ? 'wiersz-moj-klub' : undefined),
    [mojKlubUid],
  );

  return (
    <div style={{ height: '100%', width: '100%' }}>
      <AgGridReact<Wiersz>
        theme={motywTabeli}
        rowData={wiersze}
        columnDefs={definicje}
        getRowId={(p) => String(p.data['ID'])}
        getRowClass={klasaWiersza}
        rowSelection={naZaznaczenie ? { mode: 'multiRow', checkboxes: true, headerCheckbox: false, enableClickSelection: false } : undefined}
        onSelectionChanged={(e: SelectionChangedEvent<Wiersz>) =>
          naZaznaczenie?.(e.api.getSelectedRows().map((w) => String(w['ID'])))}
        onCellClicked={(e) => {
          if (e.colDef.field === 'Piłkarz' && e.data) naWybor(String(e.data['ID']), e.data);
        }}
        onRowDoubleClicked={(e) => e.data && naWybor(String(e.data['ID']), e.data)}
        selectionColumnDef={{ pinned: 'left', width: 46, headerTooltip: 'Zaznacz do porównania' }}
        defaultColDef={{ wrapHeaderText: true, autoHeaderHeight: true, width: 120 }}
        animateRows={false}
        tooltipShowDelay={300}
      />
    </div>
  );
}
