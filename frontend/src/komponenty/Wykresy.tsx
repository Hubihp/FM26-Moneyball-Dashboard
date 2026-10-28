import { Group, NumberInput, SegmentedControl, Stack, Text, Title } from '@mantine/core';
import { useMemo, useState } from 'react';

import type { Kolumna, ModelWyceny, Wiersz } from '../api';
import { eur } from '../format';
import Wykres from './Wykres';

type Props = {
  wiersze: Wiersz[];
  kolumny: Kolumna[];
  modelWyceny: ModelWyceny | undefined;
  mojKlubUid: number | null | undefined;
  naWybor: (id: string) => void;
};

const MAKS_PUNKTOW_WYCENY = 1500;
const PROG_SLABEGO_MODELU = 0.25;
const procent = (x: number) => `${x > 0 ? '+' : ''}${Math.round(x)}%`;

type Punkt = { value: number[]; id: string; name: string };

export default function Wykresy({ wiersze, kolumny, modelWyceny, mojKlubUid, naWybor }: Props) {
  const [ile, setIle] = useState(60);
  const [os, setOs] = useState<'Koszt' | 'Wartość_Numeryczna'>('Koszt');
  const maRozwoj = kolumny.some((k) => k.pole === 'Δ SCORE');

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

  // Cena vs wycena wg wyniku: punkty nad przekatna sa tansze, niz wynika z gry
  const wycena = useMemo(() => {
    const czyMoj = (w: Wiersz) => mojKlubUid !== null && mojKlubUid !== undefined && w['Klub_UID'] === mojKlubUid;
    const zCena = wiersze
      .filter((w) => typeof w['Wartość_Numeryczna'] === 'number' && (w['Wartość_Numeryczna'] as number) > 0
        && typeof w['Wycena wg wyniku'] === 'number')
      .slice(0, MAKS_PUNKTOW_WYCENY);
    const punkt = (w: Wiersz) => ({
      value: [w['Wartość_Numeryczna'] as number, w['Wycena wg wyniku'] as number, (w['Wiek'] as number) ?? 0,
        w['SCORE'] as number],
      id: String(w['ID']),
      name: String(w['Piłkarz']),
      // U21: romb - cena zawiera potencjal, ktorego model nie widzi (punkt jest zanizony)
      ...(w['U21'] ? { symbol: 'diamond', symbolSize: 11, u21: true } : {}),
    });
    const wartosci = zCena.flatMap((w) => [w['Wartość_Numeryczna'] as number, w['Wycena wg wyniku'] as number]);
    return {
      punkty: zCena.filter((w) => !czyMoj(w)).map(punkt),
      moi: zCena.filter(czyMoj).map(punkt),
      zakres: wartosci.length ? [Math.min(...wartosci), Math.max(...wartosci)] : null,
    };
  }, [wiersze, mojKlubUid]);

  // Wiek vs SCORE: mlodzi z wysokim wynikiem (talenty do kupienia przed wzrostem ceny) i rozwoj (Δ SCORE)
  const wiekowe = useMemo(() => {
    const czyMoj = (w: Wiersz) => mojKlubUid !== null && mojKlubUid !== undefined && w['Klub_UID'] === mojKlubUid;
    const punkt = (w: Wiersz, y: unknown) => ({
      value: [w['Wiek'] as number, y as number, (w['Wartość_Numeryczna'] as number) ?? 0],
      id: String(w['ID']), name: String(w['Piłkarz']),
      ...(czyMoj(w) ? { itemStyle: { color: '#fab005', borderColor: '#fff', borderWidth: 1 } } : {}),
    });
    const zWiekiem = wiersze.filter((w) => typeof w['Wiek'] === 'number').slice(0, MAKS_PUNKTOW_WYCENY);
    const ceny = zWiekiem.map((w) => w['Wartość_Numeryczna']).filter((x): x is number => typeof x === 'number' && x > 0);
    return {
      wynik: zWiekiem.filter((w) => typeof w['SCORE'] === 'number').map((w) => punkt(w, w['SCORE'])),
      rozwoj: zWiekiem.filter((w) => typeof w['Δ SCORE'] === 'number').map((w) => punkt(w, w['Δ SCORE'])),
      cenaMax: ceny.length ? Math.max(...ceny) : 1,
    };
  }, [wiersze, mojKlubUid]);

  const tooltipWieku = (nazwaY: string) => ({
    formatter: (p: unknown) => {
      const d = (p as { data: { name?: string; value: number[] } }).data;
      if (!d.name) return '';
      return `<b>${d.name}</b><br/>wiek ${d.value[0]} · ${nazwaY} ${d.value[1] > 0 && nazwaY === 'Δ SCORE' ? '+' : ''}`
        + `${d.value[1].toFixed(1).replace('.', ',')}<br/>cena ${eur(d.value[2])}`;
    },
  });
  const klik = (d: unknown) => d && typeof d === 'object' && 'id' in d && naWybor(String((d as { id: unknown }).id));
  const mapaCeny = {
    dimension: 2, min: 0, max: wiekowe.cenaMax, calculable: true, right: 0, top: 'middle', seriesIndex: 0,
    inRange: { color: ['#12b886', '#fab005', '#fa5252'] }, text: ['cena', ''],
    formatter: (v: unknown) => eur(Number(v)),
  };

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
          {os === 'Koszt' ? ' Linia = granica wynik/koszt (nikt nie jest jednocześnie lepszy i tańszy).' : ''} Kliknij
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
            legend: { top: 0, left: 'center', data: ['Zawodnicy', 'Twój klub', 'Granica wynik/koszt'] },
            xAxis: { type: 'log', name: os === 'Koszt' ? 'Koszt (€)' : 'Wartość (€)', nameLocation: 'middle', nameGap: 30,
              axisLabel: { formatter: (v: number) => eur(v) } },
            yAxis: { type: 'value', name: 'SCORE', scale: true },
            visualMap: { dimension: 2, min: 17, max: 35, calculable: true, right: 0, top: 'middle', seriesIndex: 0,
              inRange: { color: ['#12b886', '#4dabf7', '#be4bdb'] }, text: ['wiek', ''] },
            series: [
              { name: 'Zawodnicy', type: 'scatter', symbolSize: 12, data: punkty },
              { name: 'Twój klub', type: 'scatter', symbolSize: 14, data: moi,
                itemStyle: { color: '#fab005', borderColor: '#fff', borderWidth: 1 } },
              { name: 'Granica wynik/koszt', type: 'line', step: 'end', data: pareto, symbolSize: 5, z: 1,
                lineStyle: { color: '#868e96', type: 'dashed' }, itemStyle: { color: '#868e96' } },
            ],
          }}
        />
      </div>

      {wycena.zakres && (
        <div>
          <Title order={5}>Cena vs wycena wg wyniku</Title>
          <Text size="xs" c="dimmed">
            Wycena = cena typowa dla zawodnika tej pozycji z takim samym wynikiem, wiekiem i kontraktem. Punkty nad linią
            są tańsze, niż wynika z ich gry (okazje), pod linią - przepłacone. Kolor = wiek, bursztynowe = twój klub,
            romb = U21 (cena zawiera potencjał, którego model nie widzi, więc taki zawodnik leży niżej, niż powinien).
            {modelWyceny?.r2 !== null && modelWyceny?.r2 !== undefined && (
              <> Model: R² {modelWyceny.r2.toFixed(2).replace('.', ',')} na {modelWyceny.liczba} zawodnikach
                {modelWyceny.proc_za_10_score !== null ? `; +10 SCORE ≈ ${procent(modelWyceny.proc_za_10_score)} ceny` : ''}
                {modelWyceny.proc_za_rok_mlodszy !== null
                  ? `; rok młodszy ≈ ${procent(modelWyceny.proc_za_rok_mlodszy)} ceny` : ''}.</>
            )}
          </Text>
          {modelWyceny?.r2 !== null && modelWyceny?.r2 !== undefined && modelWyceny.r2 < PROG_SLABEGO_MODELU && (
            <Text size="xs" c="orange" mt={4}>
              Model słabo tłumaczy ceny w tej puli (R² poniżej {PROG_SLABEGO_MODELU.toString().replace('.', ',')}) -
              ceny zależą tu głównie od czegoś innego niż wynik, wiek i kontrakt. Traktuj niedowartościowanie ostrożnie.
            </Text>
          )}
          <Wykres
            wysokosc={480}
            naKlik={(d) => d && typeof d === 'object' && 'id' in d && naWybor(String((d as { id: unknown }).id))}
            opcje={{
              grid: { left: 70, right: 90, top: 30, bottom: 50 },
              tooltip: {
                formatter: (p: unknown) => {
                  const d = (p as { data: { name?: string; value: number[]; u21?: boolean } }).data;
                  if (!d.name) return '';
                  return `<b>${d.name}</b><br/>cena ${eur(d.value[0])}<br/>wycena ${eur(d.value[1])}`
                    + `<br/>×${(d.value[1] / d.value[0]).toFixed(1).replace('.', ',')} · SCORE ${Math.round(d.value[3])}`
                    + (d.u21 ? '<br/><i>U21 - wskaźnik zaniżony (potencjał)</i>' : '');
                },
              },
              legend: { top: 0, left: 'center', data: ['Zawodnicy', 'Twój klub', 'Cena = wycena'] },
              xAxis: { type: 'log', name: 'Cena (€)', nameLocation: 'middle', nameGap: 30,
                axisLabel: { formatter: (v: number) => eur(v) } },
              yAxis: { type: 'log', name: 'Wycena wg wyniku (€)', axisLabel: { formatter: (v: number) => eur(v) } },
              visualMap: { dimension: 2, min: 17, max: 35, calculable: true, right: 0, top: 'middle', seriesIndex: 0,
                inRange: { color: ['#12b886', '#4dabf7', '#be4bdb'] }, text: ['wiek', ''] },
              series: [
                { name: 'Zawodnicy', type: 'scatter', symbolSize: 8, data: wycena.punkty },
                { name: 'Twój klub', type: 'scatter', symbolSize: 11, data: wycena.moi,
                  itemStyle: { color: '#fab005', borderColor: '#fff', borderWidth: 1 } },
                { name: 'Cena = wycena', type: 'line', showSymbol: false, silent: true,
                  data: [[wycena.zakres[0], wycena.zakres[0]], [wycena.zakres[1], wycena.zakres[1]]],
                  lineStyle: { color: '#868e96', type: 'dashed' }, itemStyle: { color: '#868e96' } },
              ],
            }}
          />
        </div>
      )}

      <div>
        <Title order={5}>Wiek vs SCORE</Title>
        <Text size="xs" c="dimmed">
          Młodzi z wysokim wynikiem (lewy górny róg) to talenty, które warto kupić, zanim zdrożeją. Kolor = cena (zielony =
          tani), bursztynowe obramowanie = twój klub. Kliknij punkt, aby otworzyć kartę.
        </Text>
        <Wykres
          wysokosc={420}
          naKlik={klik}
          opcje={{
            grid: { left: 60, right: 90, top: 20, bottom: 50 },
            tooltip: tooltipWieku('SCORE'),
            xAxis: { type: 'value', name: 'Wiek', nameLocation: 'middle', nameGap: 30, scale: true },
            yAxis: { type: 'value', name: 'SCORE', scale: true },
            visualMap: mapaCeny,
            series: [{ type: 'scatter', symbolSize: 9, data: wiekowe.wynik }],
          }}
        />
      </div>

      {maRozwoj && wiekowe.rozwoj.length > 0 && (
        <div>
          <Title order={5}>Rozwój: Δ SCORE vs wiek</Title>
          <Text size="xs" c="dimmed">
            Zmiana SCORE względem poprzedniego sezonu (przy co najmniej 1000 minutach w obu). Wysoko i z lewej = młodzi,
            którzy rozwijają się najszybciej; kolor = cena.
          </Text>
          <Wykres
            wysokosc={380}
            naKlik={klik}
            opcje={{
              grid: { left: 60, right: 90, top: 20, bottom: 50 },
              tooltip: tooltipWieku('Δ SCORE'),
              xAxis: { type: 'value', name: 'Wiek', nameLocation: 'middle', nameGap: 30, scale: true },
              yAxis: { type: 'value', name: 'Δ SCORE' },
              visualMap: mapaCeny,
              series: [{ type: 'scatter', symbolSize: 9, data: wiekowe.rozwoj,
                markLine: { silent: true, symbol: 'none', data: [{ yAxis: 0 }], lineStyle: { color: '#868e96', type: 'dashed' } } }],
            }}
          />
        </div>
      )}
    </Stack>
  );
}
