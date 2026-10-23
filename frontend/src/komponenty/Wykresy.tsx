import { Group, NumberInput, SegmentedControl, Select, SimpleGrid, Stack, Text, Title } from '@mantine/core';
import { useMemo, useState } from 'react';

import type { Kolumna, Wiersz } from '../api';
import { eur } from '../format';
import Wykres from './Wykres';

type Props = { wiersze: Wiersz[]; kolumny: Kolumna[]; mojKlubUid: number | null | undefined; naWybor: (id: string) => void };

type Punkt = { value: number[]; id: string; name: string };

export default function Wykresy({ wiersze, kolumny, mojKlubUid, naWybor }: Props) {
  const [ile, setIle] = useState(60);
  const [os, setOs] = useState<'Koszt' | 'Wartość_Numeryczna'>('Koszt');
  const statystyki = kolumny.filter((k) => k.statystyka);
  const [stat, setStat] = useState<string | null>(null);
  const wybrana = statystyki.find((k) => k.pole === stat) ?? statystyki[0];

  const { punkty, moi, pareto } = useMemo(() => {
    const zX = wiersze.filter((w) => typeof w[os] === 'number' && (w[os] as number) > 0);
    const punkt = (w: Wiersz): Punkt => ({
      value: [w[os] as number, w['SCORE'] as number, (w['Wiek'] as number) ?? 0],
      id: String(w['ID']),
      name: String(w['Piłkarz']),
    });
    const czyMoj = (w: Wiersz) => mojKlubUid !== null && mojKlubUid !== undefined && w['Klub_UID'] === mojKlubUid;
    const najlepsi = zX.slice(0, ile);
    return {
      punkty: najlepsi.filter((w) => !czyMoj(w)).map(punkt),
      moi: najlepsi.filter(czyMoj).map(punkt),
      // granica Pareto liczona na serwerze dla kosztu - wszyscy widoczni, nie tylko najlepsi
      pareto: os === 'Koszt'
        ? zX.filter((w) => w['Pareto']).map(punkt).sort((a, b) => a.value[0] - b.value[0])
        : [],
    };
  }, [wiersze, ile, os, mojKlubUid]);

  const top10 = useMemo(() => {
    if (!wybrana) return [];
    const z = wiersze.filter((w) => typeof w[wybrana.pole] === 'number');
    z.sort((a, b) => (wybrana.nizsze_lepsze ? 1 : -1) * ((a[wybrana.pole] as number) - (b[wybrana.pole] as number)));
    return z.slice(0, 10).reverse();
  }, [wiersze, wybrana]);

  return (
    <Stack p="md" gap="lg">
      <div>
        <Group justify="space-between">
          <Title order={5}>Wynik vs {os === 'Koszt' ? 'koszt' : 'wartość'} (najlepsi wg SCORE)</Title>
          <SegmentedControl size="xs" value={os} onChange={(v) => setOs(v as typeof os)}
            data={[{ value: 'Koszt', label: 'Koszt (cena + 3 lata pensji)' }, { value: 'Wartość_Numeryczna', label: 'Wartość' }]} />
          <NumberInput size="xs" w={140} min={10} max={500} step={10} value={ile} onChange={(v) => setIle(Number(v) || 60)}
            label="Liczba zawodników" />
        </Group>
        <Text size="xs" c="dimmed">
          Szukaj punktów w lewym górnym rogu: wysoki wynik przy niskim koszcie. Kolor = wiek, bursztynowe punkty = twój klub.
          {os === 'Koszt' ? ' Linia = granica opłacalności (nikt nie jest jednocześnie lepszy i tańszy).' : ''} Kliknij
          punkt, aby otworzyć kartę.
        </Text>
        <Wykres
          wysokosc={480}
          naKlik={(d) => d && typeof d === 'object' && 'id' in d && naWybor(String((d as { id: unknown }).id))}
          opcje={{
            grid: { left: 60, right: 90, top: 30, bottom: 50 },
            tooltip: {
              formatter: (p: unknown) => {
                const d = (p as { data: { name: string; value: number[] } }).data;
                return `<b>${d.name}</b><br/>SCORE ${Math.round(d.value[1])}<br/>${eur(d.value[0])}<br/>wiek ${d.value[2]}`;
              },
            },
            legend: { top: 0, left: 'center', data: ['Zawodnicy', 'Twój klub', 'Granica opłacalności'] },
            xAxis: { type: 'log', name: os === 'Koszt' ? 'Koszt (€)' : 'Wartość (€)', nameLocation: 'middle', nameGap: 30,
              axisLabel: { formatter: (v: number) => eur(v) } },
            yAxis: { type: 'value', name: 'SCORE', scale: true },
            visualMap: { dimension: 2, min: 17, max: 35, calculable: true, right: 0, top: 'middle', seriesIndex: 0,
              inRange: { color: ['#12b886', '#4dabf7', '#be4bdb'] }, text: ['wiek', ''] },
            series: [
              { name: 'Zawodnicy', type: 'scatter', symbolSize: 12, data: punkty },
              { name: 'Twój klub', type: 'scatter', symbolSize: 14, data: moi,
                itemStyle: { color: '#fab005', borderColor: '#fff', borderWidth: 1 } },
              { name: 'Granica opłacalności', type: 'line', step: 'end', data: pareto, symbolSize: 5, z: 1,
                lineStyle: { color: '#868e96', type: 'dashed' }, itemStyle: { color: '#868e96' } },
            ],
          }}
        />
      </div>

      <SimpleGrid cols={1}>
        <Group align="end">
          <Title order={5}>Top 10 w statystyce</Title>
          <Select size="xs" w={320} value={wybrana?.pole ?? null} onChange={setStat}
            data={statystyki.map((k) => ({ value: k.pole, label: k.naglowek + (k.nizsze_lepsze ? ' (mniej = lepiej)' : '') }))} />
        </Group>
        {wybrana && (
          <Wykres
            wysokosc={400}
            naKlik={(d) => d && typeof d === 'object' && 'id' in d && naWybor(String((d as { id: unknown }).id))}
            opcje={{
              grid: { left: 200, right: 40, top: 10, bottom: 30 },
              tooltip: {},
              xAxis: { type: 'value' },
              yAxis: { type: 'category', data: top10.map((w) => `${w['Piłkarz']} (${w['Klub'] ?? '?'})`), axisLabel: { fontSize: 11 } },
              series: [{
                type: 'bar',
                data: top10.map((w) => ({
                  value: w[wybrana.pole] as number,
                  id: String(w['ID']),
                  itemStyle: mojKlubUid !== null && mojKlubUid !== undefined && w['Klub_UID'] === mojKlubUid
                    ? { color: '#fab005' } : undefined,
                })),
                itemStyle: { color: '#12b886' },
                label: { show: true, position: 'right', formatter: (p: { value: unknown }) => Number(p.value).toFixed(2) },
              }],
            }}
          />
        )}
      </SimpleGrid>
    </Stack>
  );
}
