import { Alert, Group, Loader, MultiSelect, Stack, Table, Text, Title } from '@mantine/core';
import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';

import { api, type Historia, type PunktHistorii, type Wiersz, type ZapytanieRankingu } from '../api';
import { eur, formatuj, kolorZmiany } from '../format';
import Wykres from './Wykres';

type Props = { id: string; wiersz: Wiersz; zapytanie: ZapytanieRankingu; wersja: number };

const NIZSZE_LEPSZE = ['Stracone piłki/90', 'Strata piłek na podanie'];
export const KOLOR_MALEJ_PROBY = '#fd7e14';

// Punkt wykresu: przy malej probie (ponizej progu minut) puste kolko w kolorze ostrzezenia
export function punktWykresu(wartosc: number | null, p: PunktHistorii | undefined) {
  if (wartosc === null || p === undefined) return null;
  return p.mala_proba
    ? { value: wartosc, symbol: 'emptyCircle', symbolSize: 9, minuty: p.Minuty,
      itemStyle: { color: KOLOR_MALEJ_PROBY, borderColor: KOLOR_MALEJ_PROBY } }
    : { value: wartosc, minuty: p.Minuty };
}

// Ostatnia migawka kazdego sezonu (kolumny tabeli statystyk) - ostatnia to stan biezacy
function ostatniePerSezon(punkty: PunktHistorii[]) {
  const wynik: PunktHistorii[] = [];
  for (const p of punkty) {
    if (wynik.length && wynik[wynik.length - 1].sezon === p.sezon) wynik[wynik.length - 1] = p;
    else wynik.push(p);
  }
  return wynik;
}

// Rozwoj atrybutow (1-20) miedzy migawkami: wykres wybranych atrybutow i tabela zmian od pierwszej migawki
function RozwojAtrybutow({ dane }: { dane: Historia }) {
  const punkty = dane.punkty.filter((p) => p.atrybuty && Object.keys(p.atrybuty).length > 0);
  const nazwy = dane.nazwy_atrybutow ?? {};
  const pierwszy = punkty[0];
  const ostatni = punkty[punkty.length - 1];
  const zmiany = punkty.length >= 2 ? Object.keys(nazwy)
    .map((a) => {
      const od = pierwszy.atrybuty?.[a] ?? null;
      const doo = ostatni.atrybuty?.[a] ?? null;
      return { a, od, doo, z: od === null || doo === null ? null : doo - od };
    })
    .filter((x) => x.od !== null || x.doo !== null) : [];
  const kluczowe = (dane.atrybuty_kluczowe ?? []).filter((a) => zmiany.some((x) => x.a === a));
  const [wybrane, setWybrane] = useState<string[] | null>(null);
  const naWykresie = wybrane ?? kluczowe.slice(0, 6);
  if (punkty.length < 2) {
    return (
      <Text size="xs" c="dimmed">
        Rozwój atrybutów: potrzebne są co najmniej dwie migawki z atrybutami (zapisywane od wersji 2.3; starsze
        migawki program uzupełnia w tle z zapisów w folderze gry).
      </Text>
    );
  }
  const zmienione = zmiany.filter((x) => x.z !== null && x.z !== 0).sort((a, b) => (b.z ?? 0) - (a.z ?? 0));
  const suma = zmiany.reduce((acc, x) => acc + (x.z ?? 0), 0);
  return (
    <Stack gap="xs">
      <Title order={6}>Rozwój atrybutów</Title>
      <Text size="xs" c="dimmed">
        Od {formatuj(pierwszy.data, 'data')} do {formatuj(ostatni.data, 'data')}: suma zmian {suma > 0 ? '+' : ''}{suma},
        wzrosło {zmiany.filter((x) => (x.z ?? 0) > 0).length}, spadło {zmiany.filter((x) => (x.z ?? 0) < 0).length}.
        Atrybuty z zapisu gry (w grze widoczne po skautingu).
      </Text>
      <MultiSelect size="xs" label="Atrybuty na wykresie" placeholder="Wybierz atrybuty" searchable clearable
        data={zmiany.map((x) => ({ value: x.a, label: nazwy[x.a] ?? x.a }))}
        value={naWykresie} onChange={setWybrane} />
      <Wykres
        wysokosc={240}
        opcje={{
          tooltip: { trigger: 'axis' },
          legend: { top: 0, type: 'scroll' },
          grid: { left: 40, right: 20, top: 35, bottom: 30 },
          xAxis: { type: 'category', data: punkty.map((p) => formatuj(p.data, 'data')) },
          yAxis: { type: 'value', min: 0, max: 20, interval: 5 },
          series: naWykresie.map((a) => ({
            name: nazwy[a] ?? a, type: 'line' as const, connectNulls: true,
            data: punkty.map((p) => p.atrybuty?.[a] ?? null),
          })),
        }}
      />
      {zmienione.length > 0 ? (
        <Table striped withTableBorder fz="xs">
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Atrybut</Table.Th>
              <Table.Th ta="right">{formatuj(pierwszy.data, 'data')}</Table.Th>
              <Table.Th ta="right">Teraz</Table.Th>
              <Table.Th ta="right">Zmiana</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {zmienione.map((x) => (
              <Table.Tr key={x.a}>
                <Table.Td>{nazwy[x.a] ?? x.a}{kluczowe.includes(x.a) ? ' ★' : ''}</Table.Td>
                <Table.Td ta="right">{x.od ?? '–'}</Table.Td>
                <Table.Td ta="right">{x.doo ?? '–'}</Table.Td>
                <Table.Td ta="right" style={{ color: (x.z ?? 0) > 0 ? '#69db7c' : '#ff8787' }}>
                  {(x.z ?? 0) > 0 ? '+' : ''}{x.z}
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      ) : <Text size="xs" c="dimmed">Bez zmian atrybutów w tym okresie.</Text>}
      <Text size="xs" c="dimmed">★ - atrybut kluczowy którejś roli FM tej pozycji.</Text>
    </Stack>
  );
}

const etykietaSezonu = (p: PunktHistorii) => `${p.sezon}/${String((p.sezon + 1) % 100).padStart(2, '0')}`;

// Historia i rozwoj zawodnika z migawek kolejnych wczytan zapisu kariery
export default function HistoriaZawodnika({ id, wiersz, zapytanie, wersja }: Props) {
  const historia = useQuery({
    queryKey: ['historia', wersja, zapytanie.pozycja, id, zapytanie.wagi, zapytanie.k_baza, zapytanie.ignoruj_mnoznik],
    queryFn: () => api.historia({ pozycja: zapytanie.pozycja, id, wagi: zapytanie.wagi,
      ignoruj_mnoznik: zapytanie.ignoruj_mnoznik, k_baza: zapytanie.k_baza }),
  });

  const naglowek = <Title order={5}>Historia i rozwój</Title>;
  if (historia.isLoading) return <Stack gap="xs">{naglowek}<Loader size="sm" /></Stack>;
  const dane = historia.data;
  const punkty = dane?.punkty ?? [];
  if (punkty.length < 2) {
    return (
      <Stack gap="xs">
        {naglowek}
        <Alert color="gray" variant="light">
          Historia powstaje z kolejnych wczytań zapisu tej kariery (jedna migawka na miesiąc w grze). Zmiany względem
          poprzedniego sezonu pojawią się, gdy będzie migawka z wcześniejszego sezonu.
        </Alert>
      </Stack>
    );
  }
  const minMinut = dane?.min_minut ?? 1000;
  const sezony = ostatniePerSezon(punkty);
  const delta = dane?.delta;
  const dScore = wiersz['Δ SCORE'] as number | null | undefined;
  const dMalaProba = !!wiersz['Δ_mała_próba'];
  const innaPozycja = punkty.filter((p) => p.inna_pozycja);
  const malaProba = punkty.some((p) => p.mala_proba);

  return (
    <Stack gap="xs">
      {naglowek}
      <Group gap="lg">
        <Text size="sm" title={dMalaProba ? `Mniej niż ${minMinut} minut w którymś sezonie - zmiana mniej pewna` : undefined}>
          Δ SCORE: <b style={{ color: dMalaProba ? KOLOR_MALEJ_PROBY : typeof dScore === 'number' ? kolorZmiany(dScore) : undefined,
            fontStyle: dMalaProba ? 'italic' : undefined }}>
            {dMalaProba ? '⚠ ' : ''}{formatuj(dScore, 'zmiana')}</b></Text>
        <Text size="sm">Δ percentyl: <b>{formatuj(wiersz['Δ percentyl'], 'zmiana')}</b></Text>
        {delta && <Text size="sm" c="dimmed">względem migawki z {formatuj(delta.wzgledem, 'data')}</Text>}
        {wiersz['Nowe pozycje'] ? <Text size="sm">Nowe pozycje: <b>{String(wiersz['Nowe pozycje'])}</b></Text> : null}
      </Group>
      {dMalaProba && delta && (
        <Text size="xs" c="orange">
          ⚠ Zmiana z małej liczby minut ({formatuj(delta.minuty_wtedy, 'int')} → {formatuj(delta.minuty_teraz, 'int')} min,
          poniżej {minMinut} w którymś sezonie) - traktuj ostrożnie.
        </Text>
      )}
      {innaPozycja.length > 0 && (
        <Text size="xs" c="dimmed">
          W migawkach z {innaPozycja.map((p) => formatuj(p.data, 'data')).join(', ')} zawodnik nie miał tej pozycji
          (grał wtedy: {[...new Set(innaPozycja.map((p) => p.pozycje_wtedy).filter(Boolean))].join('; ') || '?'}) - SCORE
          policzony według jej kryteriów, na skali zawodników, którzy wtedy na niej grali.
        </Text>
      )}
      <Wykres
        wysokosc={260}
        opcje={{
          tooltip: {
            trigger: 'axis',
            formatter: (p: unknown) => {
              const lista = p as { axisValue: string; seriesName: string; value: number | null; dataIndex: number }[];
              const punkt = punkty[lista[0]?.dataIndex ?? 0];
              const linie = lista.map((s) => `${s.seriesName}: ${s.value === null || s.value === undefined ? '–'
                : s.seriesName === 'Wartość' ? eur(s.value) : Math.round(s.value)}`);
              const minuty = `${formatuj(punkt?.Minuty, 'int')} min${punkt?.mala_proba ? ' - ⚠ mało minut' : ''}`;
              return [`<b>${lista[0]?.axisValue ?? ''}</b>`, ...linie, minuty].join('<br/>');
            },
          },
          legend: { top: 0 },
          grid: { left: 50, right: 70, top: 35, bottom: 30 },
          xAxis: { type: 'category', data: punkty.map((p) => formatuj(p.data, 'data')) },
          yAxis: [
            { type: 'value', name: 'SCORE', scale: true },
            { type: 'value', name: 'Wartość', axisLabel: { formatter: (v: number) => eur(v) } },
          ],
          series: [
            { name: 'SCORE', type: 'line', connectNulls: true,
              data: punkty.map((p) => punktWykresu(p.SCORE === null ? null : Math.round(p.SCORE), p)) },
            { name: 'Wartość', type: 'line', yAxisIndex: 1, connectNulls: true,
              data: punkty.map((p) => punktWykresu(p.Wartość, p)) },
          ],
        }}
      />
      <Table striped withTableBorder fz="xs">
        <Table.Thead>
          <Table.Tr>
            <Table.Th>Statystyka</Table.Th>
            {sezony.map((p, i) => (
              <Table.Th key={p.data} ta="right" style={p.mala_proba ? { color: KOLOR_MALEJ_PROBY } : undefined}
                title={p.mala_proba ? `Mniej niż ${minMinut} minut - dane z małej próby` : undefined}>
                {p.mala_proba ? '⚠ ' : ''}{i === sezony.length - 1 ? 'Teraz' : `Sezon ${etykietaSezonu(p)}`}
              </Table.Th>
            ))}
            {sezony.length > 1 && <Table.Th ta="right">Zmiana (ostatni sezon)</Table.Th>}
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {['Minuty', 'SCORE', ...(dane?.statystyki ?? [])].map((nazwa) => {
            const wartosc = (p: PunktHistorii) => (nazwa === 'Minuty' ? p.Minuty : nazwa === 'SCORE' ? p.SCORE
              : p.statystyki[nazwa] ?? null);
            const fmt = nazwa === 'Minuty' || nazwa === 'SCORE' ? 'int' : 'dec2';
            const [a, b] = sezony.length > 1 ? [wartosc(sezony[sezony.length - 2]), wartosc(sezony[sezony.length - 1])]
              : [null, null];
            const z = a === null || b === null ? null : b - a;
            const lepiej = z === null ? null : NIZSZE_LEPSZE.includes(nazwa) ? -z : z;
            return (
              <Table.Tr key={nazwa}>
                <Table.Td>{nazwa}{NIZSZE_LEPSZE.includes(nazwa) ? ' (mniej = lepiej)' : ''}</Table.Td>
                {sezony.map((p) => (
                  <Table.Td key={p.data} ta="right"
                    style={p.mala_proba ? { color: KOLOR_MALEJ_PROBY, fontStyle: 'italic' } : undefined}>
                    {formatuj(wartosc(p), fmt)}
                  </Table.Td>
                ))}
                {sezony.length > 1 && (
                  <Table.Td ta="right" style={{ color: lepiej === null || nazwa === 'Minuty' ? undefined
                    : lepiej > 0 ? '#69db7c' : lepiej < 0 ? '#ff8787' : undefined }}>
                    {z === null ? '–' : `${z > 0 ? '+' : ''}${fmt === 'int' ? Math.round(z) : z.toFixed(2).replace('.', ',')}`}
                  </Table.Td>
                )}
              </Table.Tr>
            );
          })}
        </Table.Tbody>
      </Table>
      {malaProba && (
        <Text size="xs" c="orange">
          ⚠ / pusty punkt = okres z mniej niż {minMinut} minutami: statystyki /90 i SCORE opierają się na małej próbie.
        </Text>
      )}
      {dane && <RozwojAtrybutow dane={dane} />}
      {(dane?.brak.length ?? 0) > 0 && (
        <Text size="xs" c="dimmed">
          Brak zawodnika w migawkach z: {dane!.brak.map((d) => formatuj(d, 'data')).join(', ')} (np. poniżej progu minut
          przy wczytywaniu zapisu albo liga nie była wczytana).
        </Text>
      )}
    </Stack>
  );
}
