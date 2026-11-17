// Filtr kolumny tabeli (prawy przycisk na naglowku): lista wartosci z checkboxami (tylko wartosci wystepujace
// w kolumnie, puste jako "(brak)"), zakres od-do dla liczb albo zakres dat. Model w pamieci programu:
// { typ: 'lista', wartosci } | { typ: 'zakres', od, do } | { typ: 'tekst', zawiera }.
import { Button, Checkbox, Group, NumberInput, ScrollArea, Stack, Text, TextInput } from '@mantine/core';
import type { CustomFilterProps } from 'ag-grid-react';
import { useGridFilter } from 'ag-grid-react';
import { useCallback, useMemo, useState } from 'react';

import type { Format } from '../api';
import { formatuj } from '../format';

export const BRAK = '(brak)';
// do tylu roznych wartosci kolumna tekstowa ma liste z checkboxami; wiecej (np. nazwiska) - wyszukiwanie tekstu
const MAKS_LISTY = 400;
const MAKS_POKAZANYCH = 300;

export type ModelListy = { typ: 'lista'; wartosci: string[] };
export type ModelZakresu = { typ: 'zakres'; od: number | string | null; do: number | string | null };
export type ModelTekstu = { typ: 'tekst'; zawiera: string };
export type ModelFiltra = ModelListy | ModelZakresu | ModelTekstu;

export type ParametryFiltra = { rodzaj: 'lista' | 'zakres' | 'data'; format: Format };

const klucz = (v: unknown) => (v === null || v === undefined || v === '' ? BRAK : String(v));

export function czyModelFiltra(m: unknown): m is ModelFiltra {
  return !!m && typeof m === 'object' && 'typ' in m;
}

// Opis filtra na plakietce nad tabela
export function opisModelu(m: unknown, format?: Format): string {
  if (!czyModelFiltra(m)) return '';
  if (m.typ === 'lista') return m.wartosci.length <= 3 ? m.wartosci.join(', ') : `${m.wartosci.length} wartości`;
  if (m.typ === 'tekst') return `zawiera „${m.zawiera}”`;
  const f = (v: number | string | null) => (v === null || v === '' ? '…'
    : typeof v === 'number' && format ? formatuj(v, format) : String(v));
  return `${f(m.od)} – ${f(m.do)}`;
}

export default function FiltrKolumny(props: CustomFilterProps & ParametryFiltra) {
  const { model, onModelChange, api, column, getValue, rodzaj, format } = props;
  const m = czyModelFiltra(model) ? model : null;

  // wartosci wystepujace w kolumnie (wszystkie wiersze tabeli) z liczba wierszy
  const [wartosci, liczbowe] = useMemo(() => {
    const licznik = new Map<string, number>();
    const liczby: number[] = [];
    api.forEachNode((n) => {
      const v = getValue(n);
      licznik.set(klucz(v), (licznik.get(klucz(v)) ?? 0) + 1);
      if (typeof v === 'number' && Number.isFinite(v)) liczby.push(v);
    });
    const lista = [...licznik.entries()].sort((a, b) => (a[0] === BRAK ? 1 : b[0] === BRAK ? -1
      : a[0].localeCompare(b[0], 'pl', { numeric: true })));
    return [lista, liczby] as const;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [api, column, props.model]);

  const doesFilterPass = useCallback((p: { node: Parameters<typeof getValue>[0] }) => {
    if (!m) return true;
    const v = getValue(p.node);
    if (m.typ === 'lista') return m.wartosci.includes(klucz(v));
    if (m.typ === 'tekst') return String(v ?? '').toLowerCase().includes(m.zawiera.toLowerCase());
    if (v === null || v === undefined || v === '') return false;
    if (m.od !== null && m.od !== '' && (v as number | string) < m.od) return false;
    if (m.do !== null && m.do !== '' && (v as number | string) > m.do) return false;
    return true;
  }, [m, getValue]);
  useGridFilter({ doesFilterPass });

  if (rodzaj === 'zakres' || rodzaj === 'data') {
    return <FiltrZakresu model={m?.typ === 'zakres' ? m : null} liczby={liczbowe} data={rodzaj === 'data'}
      format={format} ustaw={(z) => onModelChange(z)} />;
  }
  if (wartosci.length > MAKS_LISTY) {
    return <FiltrTekstu model={m?.typ === 'tekst' ? m : null} ustaw={(t) => onModelChange(t)} />;
  }
  return <FiltrListy model={m?.typ === 'lista' ? m : null} wartosci={wartosci} format={format}
    ustaw={(l) => onModelChange(l)} />;
}

function Panel({ children, wyczysc }: { children: React.ReactNode; wyczysc: () => void }) {
  return (
    <Stack gap="xs" p="sm" w={280} className="filtr-kolumny">
      {children}
      <Group justify="flex-end" gap="xs">
        <Button variant="subtle" color="gray" onClick={wyczysc}>Wyczyść</Button>
      </Group>
    </Stack>
  );
}

function FiltrListy({ model, wartosci, format, ustaw }: {
  model: ModelListy | null; wartosci: readonly (readonly [string, number])[]; format: Format;
  ustaw: (m: ModelListy | null) => void;
}) {
  const [szukaj, setSzukaj] = useState('');
  const wszystkie = wartosci.map(([w]) => w);
  const zaznaczone = new Set(model ? model.wartosci : wszystkie);
  const etykieta = (w: string) => (w === BRAK ? BRAK : format === 'tekst' ? w : formatuj(Number(w), format));
  const widoczne = wartosci.filter(([w]) => !szukaj || etykieta(w).toLowerCase().includes(szukaj.toLowerCase()));
  const zmien = (nowe: Set<string>) => ustaw(nowe.size === wszystkie.length ? null : { typ: 'lista', wartosci: [...nowe] });
  return (
    <Panel wyczysc={() => ustaw(null)}>
      {wartosci.length > 8 && (
        <TextInput placeholder="Szukaj wartości" value={szukaj} onChange={(e) => setSzukaj(e.currentTarget.value)} />
      )}
      <Checkbox label={<b>Zaznacz wszystko</b>} checked={zaznaczone.size === wszystkie.length}
        indeterminate={zaznaczone.size > 0 && zaznaczone.size < wszystkie.length}
        onChange={(e) => zmien(new Set(e.currentTarget.checked ? wszystkie : []))} />
      <ScrollArea.Autosize mah={260} type="auto">
        <Stack gap={6}>
          {widoczne.slice(0, MAKS_POKAZANYCH).map(([w, n]) => (
            <Checkbox key={w} checked={zaznaczone.has(w)}
              label={<Group gap={6} wrap="nowrap"><span>{etykieta(w)}</span><Text span size="xs" c="dimmed">{n}</Text></Group>}
              onChange={(e) => {
                const nowe = new Set(zaznaczone);
                if (e.currentTarget.checked) nowe.add(w);
                else nowe.delete(w);
                zmien(nowe);
              }} />
          ))}
          {widoczne.length > MAKS_POKAZANYCH && (
            <Text size="xs" c="dimmed">i {widoczne.length - MAKS_POKAZANYCH} więcej - zawęź wyszukiwanie</Text>
          )}
        </Stack>
      </ScrollArea.Autosize>
    </Panel>
  );
}

function FiltrZakresu({ model, liczby, data, format, ustaw }: {
  model: ModelZakresu | null; liczby: number[]; data: boolean; format: Format; ustaw: (m: ModelZakresu | null) => void;
}) {
  const min = liczby.length ? Math.min(...liczby) : null;
  const max = liczby.length ? Math.max(...liczby) : null;
  const zmien = (od: number | string | null, doo: number | string | null) =>
    ustaw((od === null || od === '') && (doo === null || doo === '') ? null : { typ: 'zakres', od, do: doo });
  const pole = (v: string | number) => (v === '' ? null : typeof v === 'number' ? v : Number(v));
  return (
    <Panel wyczysc={() => ustaw(null)}>
      {data ? (
        <Group grow gap="xs">
          <TextInput type="date" label="Od" value={String(model?.od ?? '')} onChange={(e) => zmien(e.currentTarget.value || null, model?.do ?? null)} />
          <TextInput type="date" label="Do" value={String(model?.do ?? '')} onChange={(e) => zmien(model?.od ?? null, e.currentTarget.value || null)} />
        </Group>
      ) : (
        <>
          <Group grow gap="xs">
            <NumberInput label="Od" placeholder={min === null ? '' : formatuj(min, format)} value={model?.od ?? ''}
              decimalSeparator="," thousandSeparator=" " onChange={(v) => zmien(pole(v), model?.do ?? null)} />
            <NumberInput label="Do" placeholder={max === null ? '' : formatuj(max, format)} value={model?.do ?? ''}
              decimalSeparator="," thousandSeparator=" " onChange={(v) => zmien(model?.od ?? null, pole(v))} />
          </Group>
          {min !== null && max !== null && (
            <Text size="xs" c="dimmed">W kolumnie: {formatuj(min, format)} – {formatuj(max, format)}</Text>
          )}
        </>
      )}
    </Panel>
  );
}

function FiltrTekstu({ model, ustaw }: { model: ModelTekstu | null; ustaw: (m: ModelTekstu | null) => void }) {
  return (
    <Panel wyczysc={() => ustaw(null)}>
      <TextInput label="Zawiera" placeholder="np. część nazwiska" value={model?.zawiera ?? ''} data-autofocus
        onChange={(e) => ustaw(e.currentTarget.value ? { typ: 'tekst', zawiera: e.currentTarget.value } : null)} />
    </Panel>
  );
}
