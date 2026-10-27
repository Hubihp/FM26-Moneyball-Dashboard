import { Alert, Group, Loader, Select, Stack, Table, Text, Title } from '@mantine/core';
import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';

import { api, type PunktHistorii, type ZapytanieRankingu } from '../api';
import { formatuj, kolorZmiany } from '../format';
import { KOLOR_MALEJ_PROBY, punktWykresu } from './HistoriaZawodnika';
import Wykres from './Wykres';

type Props = { wybrani: string[]; zapytanie: ZapytanieRankingu; wersja: number };

// Historia i rozwoj porownywanych zawodnikow: wspolny wykres (kazdy zawodnik = seria) i zestawienie Δ SCORE
export default function HistoriaPorownania({ wybrani, zapytanie, wersja }: Props) {
  const [miara, setMiara] = useState<string>('SCORE');
  const dane = useQuery({
    queryKey: ['historia-wielu', wersja, zapytanie.pozycja, wybrani, zapytanie.wagi, zapytanie.k_baza,
      zapytanie.ignoruj_mnoznik],
    queryFn: () => api.historiaWielu({ pozycja: zapytanie.pozycja, ids: wybrani, wagi: zapytanie.wagi,
      ignoruj_mnoznik: zapytanie.ignoruj_mnoznik, k_baza: zapytanie.k_baza }),
    enabled: wybrani.length > 0,
  });

  const naglowek = <Title order={5}>Historia i rozwój</Title>;
  if (dane.isLoading) return <Stack gap="xs">{naglowek}<Loader size="sm" /></Stack>;
  const zawodnicy = (dane.data?.zawodnicy ?? []).filter((z) => z.punkty.length > 0);
  if (!zawodnicy.length || zawodnicy.every((z) => z.punkty.length < 2)) {
    return (
      <Stack gap="xs">
        {naglowek}
        <Alert color="gray" variant="light">
          Historia powstaje z kolejnych wczytań zapisu kariery - pojawi się, gdy będą co najmniej dwie migawki.
        </Alert>
      </Stack>
    );
  }
  const minMinut = dane.data?.min_minut ?? 1000;
  const statystyki = zawodnicy.find((z) => z.statystyki?.length)?.statystyki ?? [];
  const daty = [...new Set(zawodnicy.flatMap((z) => z.punkty.map((p) => p.data)))].sort();
  const wartosc = (p: PunktHistorii) => (miara === 'SCORE' ? (p.SCORE === null ? null : Math.round(p.SCORE))
    : miara === 'Minuty' ? p.Minuty : p.statystyki[miara] ?? null);

  return (
    <Stack gap="xs">
      <Group justify="space-between" align="end">
        {naglowek}
        <Select size="xs" w={300} label="Na wykresie" value={miara} allowDeselect={false} onChange={(v) => setMiara(v ?? 'SCORE')}
          data={['SCORE', 'Minuty', ...statystyki]} />
      </Group>
      <Wykres
        wysokosc={300}
        opcje={{
          tooltip: {
            trigger: 'axis',
            formatter: (p: unknown) => {
              const lista = p as { axisValue: string; seriesName: string; value: number | null;
                data: { minuty?: number | null; symbol?: string } | null }[];
              const linie = lista.filter((s) => s.data).map((s) => `${s.seriesName}: ${
                s.value === null || s.value === undefined ? '–' : miara === 'SCORE' || miara === 'Minuty'
                  ? Math.round(s.value) : s.value.toFixed(2).replace('.', ',')} (${formatuj(s.data?.minuty, 'int')} min${
                s.data?.symbol ? ' - ⚠ mało minut' : ''})`);
              return [`<b>${lista[0]?.axisValue ?? ''}</b>`, ...linie].join('<br/>');
            },
          },
          legend: { top: 0, type: 'scroll' },
          grid: { left: 50, right: 20, top: 35, bottom: 30 },
          xAxis: { type: 'category', data: daty.map((d) => formatuj(d, 'data')) },
          yAxis: { type: 'value', name: miara.length > 18 ? '' : miara, scale: true },
          series: zawodnicy.map((z) => ({
            name: z.pilkarz ?? z.id, type: 'line', connectNulls: true,
            data: daty.map((d) => {
              const p = z.punkty.find((x) => x.data === d);
              return p ? punktWykresu(wartosc(p), p) : null;
            }),
          })),
        }}
      />
      <Table withTableBorder fz="xs">
        <Table.Thead>
          <Table.Tr>
            <Table.Th>Zawodnik</Table.Th>
            <Table.Th ta="right">Δ SCORE</Table.Th>
            <Table.Th ta="right">Względem migawki</Table.Th>
            <Table.Th ta="right">Minuty wtedy → teraz</Table.Th>
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {zawodnicy.map((z) => {
            const d = z.delta;
            return (
              <Table.Tr key={z.id}>
                <Table.Td>{z.pilkarz}</Table.Td>
                <Table.Td ta="right" style={d ? { color: d.mala_proba ? KOLOR_MALEJ_PROBY : kolorZmiany(d.wartosc),
                  fontWeight: 600, fontStyle: d.mala_proba ? 'italic' : undefined } : undefined}>
                  {d ? `${d.mala_proba ? '⚠ ' : ''}${formatuj(d.wartosc, 'zmiana')}` : '–'}
                </Table.Td>
                <Table.Td ta="right">{d ? formatuj(d.wzgledem, 'data') : '–'}</Table.Td>
                <Table.Td ta="right">
                  {d ? `${formatuj(d.minuty_wtedy, 'int')} → ${formatuj(d.minuty_teraz, 'int')}` : '–'}
                </Table.Td>
              </Table.Tr>
            );
          })}
        </Table.Tbody>
      </Table>
      <Text size="xs" c="dimmed">
        Δ SCORE = zmiana względem ostatniej migawki z wcześniejszego sezonu (te same wagi). ⚠ i puste punkty: okres
        z mniej niż {minMinut} minutami - wynik opiera się na małej próbie.
      </Text>
    </Stack>
  );
}
