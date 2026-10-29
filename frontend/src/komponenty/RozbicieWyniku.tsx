import { Alert, Loader, Stack, Text, Title } from '@mantine/core';
import { useQuery } from '@tanstack/react-query';

import { api, type ZapytanieRankingu } from '../api';
import { formatuj } from '../format';
import Wykres from './Wykres';

type Props = { id: string; zapytanie: ZapytanieRankingu; wersja: number };

const znak = (x: number) => `${x >= 0 ? '+' : '−'}${Math.abs(x).toFixed(1).replace('.', ',')}`;

// "Skad ten SCORE": wklad kazdej statystyki (waga x odchylenie od sredniej pozycji) i korekta ligowa
export default function RozbicieWyniku({ id, zapytanie, wersja }: Props) {
  const dane = useQuery({
    queryKey: ['rozbicie', wersja, zapytanie.pozycja, id, zapytanie.wagi, zapytanie.ignoruj_mnoznik, zapytanie.k_baza],
    queryFn: () => api.rozbicie({ pozycja: zapytanie.pozycja, id, wagi: zapytanie.wagi,
      ignoruj_mnoznik: zapytanie.ignoruj_mnoznik, k_baza: zapytanie.k_baza }),
  });
  if (dane.isLoading) return <Loader size="sm" />;
  if (dane.error) return <Alert color="red">{(dane.error as Error).message}</Alert>;
  const d = dane.data;
  if (!d) return null;

  const paski = [
    ...d.skladniki.map((s) => ({
      nazwa: `${s.cecha}${s.nizsze_lepsze ? ' (mniej = lepiej)' : ''}`, punkty: s.punkty,
      opis: s.brak_danych ? 'brak danych - przyjęta średnia pozycji'
        : `wartość ${formatuj(s.wartosc, 'dec2')} · waga ${s.waga_proc.toFixed(0)}%`,
      kolor: s.brak_danych ? '#868e96' : s.punkty >= 0 ? '#40c057' : '#fa5252',
    })),
    ...(Math.abs(d.liga) > 0.05 ? [{ nazwa: 'Korekta ligowa', punkty: d.liga, opis: 'siła ligi, w której grał',
      kolor: d.liga >= 0 ? '#4dabf7' : '#fd7e14' }] : []),
  ].reverse();       // na wykresie poziomym pierwszy element jest na dole
  const sumaStatystyk = d.skladniki.reduce((a, s) => a + s.punkty, 0);

  return (
    <Stack gap={4}>
      <Title order={5}>Skąd ten SCORE</Title>
      <Text size="xs" c="dimmed">
        {formatuj(d.start, 'dec1')} (przeciętny zawodnik pozycji) {znak(sumaStatystyk)} (statystyki)
        {Math.abs(d.liga) > 0.05 ? ` ${znak(d.liga)} (liga)` : ''} = {formatuj(d.score, 'dec1')}.
        Wkład statystyki = jej waga × odległość od średniej pozycji (po skurczeniu przy małej liczbie minut).
      </Text>
      <Wykres wysokosc={Math.max(160, paski.length * 26 + 40)} opcje={{
        backgroundColor: 'transparent',
        grid: { left: 250, right: 50, top: 10, bottom: 20 },
        xAxis: { type: 'value', axisLabel: { formatter: (v: number) => znak(v) } },
        yAxis: { type: 'category', data: paski.map((p) => p.nazwa), axisLabel: { width: 240, overflow: 'truncate' } },
        tooltip: {
          trigger: 'item',
          formatter: (p: unknown) => {
            const x = paski[(p as { dataIndex: number }).dataIndex];
            return `${x.nazwa}<br/>${znak(x.punkty)} pkt<br/>${x.opis}`;
          },
        },
        series: [{
          type: 'bar',
          data: paski.map((p) => ({ value: Number(p.punkty.toFixed(2)), itemStyle: { color: p.kolor } })),
          label: { show: true, position: 'right', formatter: (p: { value: unknown }) => znak(Number(p.value)) },
        }],
      }} />
    </Stack>
  );
}
