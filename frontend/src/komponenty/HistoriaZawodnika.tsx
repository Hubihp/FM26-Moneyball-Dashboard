import { Alert, Group, Loader, Stack, Table, Text, Title } from '@mantine/core';
import { useQuery } from '@tanstack/react-query';

import { api, type Wiersz, type ZapytanieRankingu } from '../api';
import { eur, formatuj, kolorZmiany } from '../format';
import Wykres from './Wykres';

type Props = { id: string; wiersz: Wiersz; zapytanie: ZapytanieRankingu; wersja: number };

const NIZSZE_LEPSZE = ['Stracone piłki/90', 'Strata piłek na podanie'];

// Historia i rozwoj zawodnika z migawek kolejnych wczytan zapisu kariery
export default function HistoriaZawodnika({ id, wiersz, zapytanie, wersja }: Props) {
  const historia = useQuery({
    queryKey: ['historia', wersja, zapytanie.pozycja, id, zapytanie.wagi, zapytanie.k_baza, zapytanie.ignoruj_mnoznik],
    queryFn: () => api.historia({ pozycja: zapytanie.pozycja, id, wagi: zapytanie.wagi,
      ignoruj_mnoznik: zapytanie.ignoruj_mnoznik, k_baza: zapytanie.k_baza }),
  });

  const naglowek = <Title order={5}>Historia i rozwój</Title>;
  if (historia.isLoading) return <Stack gap="xs">{naglowek}<Loader size="sm" /></Stack>;
  const punkty = historia.data?.punkty ?? [];
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
  const poprzedni = [...punkty].reverse().find((p) => p.sezon < punkty[punkty.length - 1].sezon);
  const teraz = punkty[punkty.length - 1];
  const zmiana = (a: number | null | undefined, b: number | null | undefined) =>
    (a === null || a === undefined || b === null || b === undefined ? null : b - a);
  const dScore = wiersz['Δ SCORE'] as number | null | undefined;

  return (
    <Stack gap="xs">
      {naglowek}
      <Group gap="lg">
        <Text size="sm">Δ SCORE (sezon): <b style={{ color: typeof dScore === 'number' ? kolorZmiany(dScore) : undefined }}>
          {formatuj(dScore, 'zmiana')}</b></Text>
        <Text size="sm">Rozwój na tle wieku: <b>{formatuj(wiersz['Rozwój vs wiek'], 'zmiana')}</b></Text>
        <Text size="sm">Δ wartości: <b>{formatuj(wiersz['Δ wartości'], 'zmiana_proc')}</b></Text>
        {wiersz['Nowe pozycje'] ? <Text size="sm">Nowe pozycje: <b>{String(wiersz['Nowe pozycje'])}</b></Text> : null}
      </Group>
      {dScore === null || dScore === undefined ? (
        <Text size="xs" c="dimmed">
          Zmiana sezonowa jest liczona przy co najmniej {historia.data?.min_minut} minutach w obu sezonach.
        </Text>
      ) : null}
      <Wykres
        wysokosc={260}
        opcje={{
          tooltip: { trigger: 'axis' },
          legend: { top: 0 },
          grid: { left: 50, right: 70, top: 35, bottom: 30 },
          xAxis: { type: 'category', data: punkty.map((p) => formatuj(p.data, 'data')) },
          yAxis: [
            { type: 'value', name: 'SCORE', scale: true },
            { type: 'value', name: 'Wartość', axisLabel: { formatter: (v: number) => eur(v) } },
          ],
          series: [
            { name: 'SCORE', type: 'line', data: punkty.map((p) => (p.SCORE === null ? null : Math.round(p.SCORE))),
              connectNulls: true },
            { name: 'Wartość', type: 'line', yAxisIndex: 1, data: punkty.map((p) => p.Wartość), connectNulls: true,
              tooltip: { valueFormatter: (v) => eur(v as number) } },
          ],
        }}
      />
      {poprzedni && (
        <Table striped withTableBorder fz="xs">
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Statystyka</Table.Th>
              <Table.Th ta="right">Sezon {poprzedni.sezon}/{(poprzedni.sezon + 1) % 100}</Table.Th>
              <Table.Th ta="right">Teraz</Table.Th>
              <Table.Th ta="right">Zmiana</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {[['Minuty', poprzedni.Minuty, teraz.Minuty] as const,
              ...(historia.data?.statystyki ?? []).map((k) => [k, poprzedni.statystyki[k], teraz.statystyki[k]] as const)]
              .map(([nazwa, a, b]) => {
                const z = zmiana(a, b);
                const lepiej = z === null ? null : NIZSZE_LEPSZE.includes(nazwa) ? -z : z;
                return (
                  <Table.Tr key={nazwa}>
                    <Table.Td>{nazwa}{NIZSZE_LEPSZE.includes(nazwa) ? ' (mniej = lepiej)' : ''}</Table.Td>
                    <Table.Td ta="right">{formatuj(a, nazwa === 'Minuty' ? 'int' : 'dec2')}</Table.Td>
                    <Table.Td ta="right">{formatuj(b, nazwa === 'Minuty' ? 'int' : 'dec2')}</Table.Td>
                    <Table.Td ta="right" style={{ color: lepiej === null || nazwa === 'Minuty' ? undefined
                      : lepiej > 0 ? '#69db7c' : lepiej < 0 ? '#ff8787' : undefined }}>
                      {z === null ? '–' : `${z > 0 ? '+' : ''}${nazwa === 'Minuty' ? Math.round(z) : z.toFixed(2).replace('.', ',')}`}
                    </Table.Td>
                  </Table.Tr>
                );
              })}
          </Table.Tbody>
        </Table>
      )}
    </Stack>
  );
}
