import { Group, NumberInput, Select, SimpleGrid, Stack, Text, Title } from '@mantine/core';
import { useMemo, useState } from 'react';

import type { Kolumna, Wiersz } from '../api';
import { eur } from '../format';
import Wykres from './Wykres';

type Props = { wiersze: Wiersz[]; kolumny: Kolumna[]; naWybor: (id: string) => void };

export default function Wykresy({ wiersze, kolumny, naWybor }: Props) {
  const [ile, setIle] = useState(60);
  const statystyki = kolumny.filter((k) => k.statystyka);
  const [stat, setStat] = useState<string | null>(null);
  const wybrana = statystyki.find((k) => k.pole === stat) ?? statystyki[0];

  const punkty = useMemo(
    () =>
      wiersze
        .filter((w) => typeof w['Wartość_Numeryczna'] === 'number' && (w['Wartość_Numeryczna'] as number) > 0)
        .slice(0, ile)
        .map((w) => ({
          value: [w['Wartość_Numeryczna'] as number, w['SCORE'] as number, (w['Wiek'] as number) ?? 0],
          id: String(w['ID']),
          name: String(w['Piłkarz']),
        })),
    [wiersze, ile],
  );

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
          <Title order={5}>Wynik vs wartość (najlepsi wg SCORE, z ceną)</Title>
          <NumberInput size="xs" w={140} min={10} max={500} step={10} value={ile} onChange={(v) => setIle(Number(v) || 60)}
            label="Liczba zawodników" />
        </Group>
        <Text size="xs" c="dimmed">Szukaj punktów w lewym górnym rogu: wysoki wynik przy niskiej cenie. Kolor = wiek. Kliknij punkt, aby otworzyć kartę.</Text>
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
            xAxis: { type: 'log', name: 'Wartość (€)', nameLocation: 'middle', nameGap: 30,
              axisLabel: { formatter: (v: number) => eur(v) } },
            yAxis: { type: 'value', name: 'SCORE', scale: true },
            visualMap: { dimension: 2, min: 17, max: 35, calculable: true, right: 0, top: 'middle',
              inRange: { color: ['#12b886', '#fab005', '#fa5252'] }, text: ['wiek', ''] },
            series: [{ type: 'scatter', symbolSize: 12, data: punkty }],
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
                data: top10.map((w) => ({ value: w[wybrana.pole] as number, id: String(w['ID']) })),
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
