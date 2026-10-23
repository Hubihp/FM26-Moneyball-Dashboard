import {
  Accordion,
  Badge,
  Button,
  Group,
  MultiSelect,
  NumberInput,
  RangeSlider,
  ScrollArea,
  Select,
  Slider,
  Stack,
  Switch,
  Text,
  TextInput,
  Tooltip,
} from '@mantine/core';

import type { Filtry, MetaPozycji } from '../api';
import { eur } from '../format';

export type Ustawienia = { k_baza: number; ignoruj_mnoznik: boolean; pokaz_ukryte: boolean };

type Props = {
  pozycje: string[];
  liczby: Record<string, number>;
  pozycja: string;
  setPozycja: (p: string) => void;
  meta: MetaPozycji | undefined;
  filtry: Filtry;
  setFiltry: (f: Filtry) => void;
  wagi: Record<string, number>;
  setWagi: (w: Record<string, number> | null) => void;
  ustawienia: Ustawienia;
  setUstawienia: (u: Ustawienia) => void;
  maMojKlub: boolean;
  pominiete: string[];
};

export const PUSTE_FILTRY: Filtry = {
  ligi: [], nogi: [], wiek: null, cena: null, bez_ceny: true, szukaj: '', kontrakt_mies: null, min_minut: 0,
  bez_mojego_klubu: false,
};

// Suwak ceny w skali pierwiastkowej: wiecej precyzji przy niskich kwotach
const doSuwaka = (x: number, max: number) => Math.sqrt(x / max) * 100;
const zSuwaka = (s: number, max: number) => Math.round(((s / 100) ** 2 * max) / 10_000) * 10_000;

export default function PanelBoczny(p: Props) {
  const { meta, filtry, setFiltry } = p;
  const zmien = <K extends keyof Filtry>(k: K, v: Filtry[K]) => setFiltry({ ...filtry, [k]: v });
  const sumaWag = Object.values(p.wagi).reduce((a, b) => a + b, 0);
  const cenaMax = meta?.cena_max ?? 0;
  const cena = filtry.cena ?? [0, cenaMax];

  return (
    <ScrollArea h="100%" type="auto" offsetScrollbars>
      <Stack gap="sm" pb="xl">
        <Select
          label="Pozycja"
          value={p.pozycja}
          onChange={(v) => v && p.setPozycja(v)}
          allowDeselect={false}
          data={p.pozycje.map((poz) => ({ value: poz, label: `${poz} (${p.liczby[poz] ?? 0})` }))}
        />

        <TextInput label="Szukaj (piłkarz / klub)" value={filtry.szukaj} onChange={(e) => zmien('szukaj', e.currentTarget.value)} />

        <MultiSelect label="Ligi" placeholder="Wszystkie" searchable clearable data={meta?.ligi ?? []} value={filtry.ligi}
          onChange={(v) => zmien('ligi', v)} />

        {meta?.wiek && (
          <div>
            <Text size="sm" fw={500}>Wiek: {(filtry.wiek ?? meta.wiek).join(' – ')}</Text>
            <RangeSlider min={meta.wiek[0]} max={meta.wiek[1]} minRange={0} value={filtry.wiek ?? meta.wiek}
              onChange={(v) => zmien('wiek', v)} label={null} />
          </div>
        )}

        {cenaMax > 0 && (
          <div>
            <Text size="sm" fw={500}>Cena: {eur(cena[0] ?? 0)} – {eur(cena[1] ?? cenaMax)}</Text>
            <RangeSlider min={0} max={100} step={0.5} label={null}
              value={[doSuwaka(cena[0] ?? 0, cenaMax), doSuwaka(cena[1] ?? cenaMax, cenaMax)]}
              onChange={([a, b]) => zmien('cena', a <= 0 && b >= 100 ? null : [zSuwaka(a, cenaMax), b >= 100 ? null : zSuwaka(b, cenaMax)])} />
            <Switch mt={6} size="xs" label="Uwzględnij zawodników bez ceny" checked={filtry.bez_ceny}
              onChange={(e) => zmien('bez_ceny', e.currentTarget.checked)} />
          </div>
        )}

        {meta?.ma_kontrakty && (
          <Select label="Kontrakt wygasa (od daty w grze)" clearable placeholder="Dowolnie"
            value={filtry.kontrakt_mies ? String(filtry.kontrakt_mies) : null}
            onChange={(v) => zmien('kontrakt_mies', v ? Number(v) : null)}
            data={[
              { value: '6', label: 'w ciągu 6 mies. (możliwy pre-kontrakt)' },
              { value: '12', label: 'w ciągu 12 mies.' },
              { value: '18', label: 'w ciągu 18 mies.' },
            ]} />
        )}

        <MultiSelect label="Lepsza noga" placeholder="Dowolna" clearable data={meta?.nogi ?? []} value={filtry.nogi}
          onChange={(v) => zmien('nogi', v)} />

        {meta?.minuty_max ? (
          <NumberInput label="Minimum minut" min={0} step={90} value={filtry.min_minut}
            onChange={(v) => zmien('min_minut', Number(v) || 0)} />
        ) : null}

        {p.maMojKlub && (
          <Switch label="Pomiń mój klub" checked={filtry.bez_mojego_klubu}
            onChange={(e) => zmien('bez_mojego_klubu', e.currentTarget.checked)} />
        )}

        <Button variant="subtle" size="xs" onClick={() => setFiltry(PUSTE_FILTRY)}>Wyczyść filtry</Button>

        <Accordion variant="separated" multiple defaultValue={[]}>
          <Accordion.Item value="wagi">
            <Accordion.Control>Wagi statystyk</Accordion.Control>
            <Accordion.Panel>
              <Stack gap="xs">
                <Text size="xs" c="dimmed">Ważność 0-100. Liczą się proporcje (wagi są normalizowane do sumy 1).</Text>
                {Object.entries(p.wagi).map(([cecha, waga]) => (
                  <div key={cecha}>
                    <Group justify="space-between" gap={4}>
                      <Text size="xs" c={p.pominiete.includes(cecha) ? 'dimmed' : undefined}>{cecha}</Text>
                      <Badge size="xs" variant="light">{sumaWag ? Math.round((waga / sumaWag) * 100) : 0}%</Badge>
                    </Group>
                    <Slider min={0} max={100} step={5} value={waga} label={null}
                      onChange={(v) => p.setWagi({ ...p.wagi, [cecha]: v })} />
                  </div>
                ))}
                <Button variant="subtle" size="xs" onClick={() => p.setWagi(null)}>Przywróć domyślne wagi</Button>
              </Stack>
            </Accordion.Panel>
          </Accordion.Item>
          <Accordion.Item value="model">
            <Accordion.Control>Ustawienia wyniku</Accordion.Control>
            <Accordion.Panel>
              <Stack gap="sm">
                <div>
                  <Tooltip multiline w={280} label="Zawodnik z małą liczbą minut jest przyciągany do średniej pozycji. 0 = wyłączone.">
                    <Text size="sm">Skurczenie przy małej próbie: {p.ustawienia.k_baza} mecz.</Text>
                  </Tooltip>
                  <Slider min={0} max={15} value={p.ustawienia.k_baza} label={null}
                    onChange={(v) => p.setUstawienia({ ...p.ustawienia, k_baza: v })} />
                </div>
                <Switch label="Ignoruj mnożnik ligowy" checked={p.ustawienia.ignoruj_mnoznik}
                  onChange={(e) => p.setUstawienia({ ...p.ustawienia, ignoruj_mnoznik: e.currentTarget.checked })} />
                {meta?.ma_ukryte && (
                  <Switch label="Pokaż dane ukryte w grze (CA/PA)" checked={p.ustawienia.pokaz_ukryte}
                    onChange={(e) => p.setUstawienia({ ...p.ustawienia, pokaz_ukryte: e.currentTarget.checked })} />
                )}
              </Stack>
            </Accordion.Panel>
          </Accordion.Item>
        </Accordion>
      </Stack>
    </ScrollArea>
  );
}
