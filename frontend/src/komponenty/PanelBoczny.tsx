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
import Boisko from './Boisko';
import { eur } from '../format';

export type Ustawienia = { k_baza: number; ignoruj_mnoznik: boolean };

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
  ligi: [], nogi: [], kraje: [], wiek: null, cena: null, pensja: null, bez_ceny: true, szukaj: '', kontrakt_mies: null,
  // domyslnie co najmniej 1000 minut (wiarygodniejsze statystyki /90); mozna zmienic w panelu
  min_minut: 1000,
  bez_mojego_klubu: false, okazje: [], min_rozwoj: null, kandydaci: false,
  min_score_kandydata: 60, min_niedowartosciowanie: null, kandydaci_z: [],
};

// Suwak ceny w skali pierwiastkowej: wiecej precyzji przy niskich kwotach
const doSuwaka = (x: number, max: number) => Math.sqrt(x / max) * 100;
const zSuwaka = (s: number, max: number, krok = 10_000) => Math.round(((s / 100) ** 2 * max) / krok) * krok;

export default function PanelBoczny(p: Props) {
  const { meta, filtry, setFiltry } = p;
  const zmien = <K extends keyof Filtry>(k: K, v: Filtry[K]) => setFiltry({ ...filtry, [k]: v });
  const sumaWag = Object.values(p.wagi).reduce((a, b) => a + b, 0);
  // rola, ktorej wagi dokladnie odpowiadaja obecnym (inaczej "wlasne wagi")
  const role = meta?.role ?? [];
  const takieSame = (a: Record<string, number>, b: Record<string, number>) => {
    const klucze = new Set([...Object.keys(a), ...Object.keys(b)]);
    return [...klucze].every((k) => (a[k] ?? 0) === (b[k] ?? 0));
  };
  const rola = role.find((r) => takieSame(r.wagi, p.wagi));
  const cenaMax = meta?.cena_max ?? 0;
  const cena = filtry.cena ?? [0, cenaMax];
  const pensjaMax = meta?.pensja_max ?? 0;
  const pensja = filtry.pensja ?? [0, pensjaMax];
  // zakres wieku jest wspolny dla pozycji - na suwaku przyciety do zakresu tej pozycji
  const wiek = filtry.wiek && meta?.wiek
    ? [Math.max(filtry.wiek[0], meta.wiek[0]), Math.min(filtry.wiek[1], meta.wiek[1])] as [number, number]
    : meta?.wiek;

  return (
    <ScrollArea h="100%" type="auto" offsetScrollbars>
      <Stack gap="sm" pb="xl">
        <Boisko pozycja={p.pozycja} liczby={p.liczby} naWybor={p.setPozycja} />

        {p.pozycja !== 'Bramkarz' && (
        <div>
          <Tooltip multiline w={300} withArrow position="right"
            label="Zawodnicy grający nominalnie na wybranych pozycjach, oceniani według kryteriów tej pozycji - kandydaci do przekwalifikowania w grze. Nie zmieniają wyników zawodników tej pozycji. Puste pole = wyłączone.">
            <MultiSelect size="xs" label="Kandydaci z innych pozycji" placeholder="Wyłączone - wybierz pozycje" clearable
              data={p.pozycje.filter((x) => x !== p.pozycja && x !== 'Bramkarz')}
              value={filtry.kandydaci_z}
              onChange={(v) => setFiltry({ ...filtry, kandydaci_z: v, kandydaci: v.length > 0 })} />
          </Tooltip>
          {filtry.kandydaci_z.length > 0 && (
            <>
              <Text size="xs" mt={6}>Minimalny SCORE kandydata: {filtry.min_score_kandydata}</Text>
              <Slider min={40} max={80} step={1} label={null} value={filtry.min_score_kandydata}
                onChange={(v) => zmien('min_score_kandydata', v)} />
            </>
          )}
        </div>
        )}

        <TextInput label="Szukaj (piłkarz / klub)" value={filtry.szukaj} onChange={(e) => zmien('szukaj', e.currentTarget.value)} />

        {meta?.wiek && (
          <div>
            <Text size="sm" fw={500}>Wiek: {(wiek ?? meta.wiek).join(' – ')}</Text>
            <RangeSlider min={meta.wiek[0]} max={meta.wiek[1]} minRange={0} value={wiek ?? meta.wiek}
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

        {pensjaMax > 0 && (
          <div>
            <Text size="sm" fw={500}>Pensja (tyg.): {eur(pensja[0] ?? 0)} – {eur(pensja[1] ?? pensjaMax)}</Text>
            <RangeSlider min={0} max={100} step={0.5} label={null}
              value={[doSuwaka(pensja[0] ?? 0, pensjaMax), doSuwaka(pensja[1] ?? pensjaMax, pensjaMax)]}
              onChange={([a, b]) => zmien('pensja', a <= 0 && b >= 100 ? null
                : [zSuwaka(a, pensjaMax, 1000), b >= 100 ? null : zSuwaka(b, pensjaMax, 1000)])} />
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

        <Select label="Niedowartościowanie co najmniej" clearable placeholder="Dowolne"
          description="Wycena wg wyniku / cena"
          value={filtry.min_niedowartosciowanie ? String(filtry.min_niedowartosciowanie) : null}
          onChange={(v) => zmien('min_niedowartosciowanie', v ? Number(v) : null)}
          data={[
            { value: '1.5', label: '×1,5 (wyraźnie tańszy)' },
            { value: '2', label: '×2 (dwa razy tańszy)' },
            { value: '3', label: '×3 i więcej' },
          ]} />

        {meta?.ma_historie && (
          <Select label="Rozwój w sezonie co najmniej" clearable placeholder="Dowolny"
            description={`Zmiana SCORE względem poprzedniego sezonu (migawka z ${meta.data_porownania ?? '–'}); `
              + `liczona przy co najmniej ${meta.min_minut_rozwoju} minutach w obu sezonach`}
            value={filtry.min_rozwoj !== null ? String(filtry.min_rozwoj) : null}
            onChange={(v) => zmien('min_rozwoj', v ? Number(v) : null)}
            data={[
              { value: '3', label: '+3 SCORE' },
              { value: '5', label: '+5 SCORE (szybki rozwój)' },
              { value: '10', label: '+10 SCORE i więcej' },
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
                {role.length > 0 && (
                  <>
                    <Select label="Rola (gotowe wagi)" size="xs" allowDeselect={false}
                      data={role.map((r) => r.nazwa)} value={rola?.nazwa ?? null} placeholder="Własne wagi"
                      onChange={(nazwa) => {
                        const wybrana = role.find((r) => r.nazwa === nazwa);
                        if (!wybrana) return;
                        // domyslna rola = brak wlasnych wag (nowe wagi domyslne w kolejnych wersjach)
                        p.setWagi(wybrana === role[0] ? null : { ...wybrana.wagi });
                      }} />
                    <Text size="xs" c="dimmed">
                      {rola ? rola.opis : 'Własne wagi - zmienione suwakami. Wybierz rolę, aby zacząć od gotowego zestawu.'}
                    </Text>
                  </>
                )}
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
                <Switch label="Ignoruj mnożnik ligowy" checked={p.ustawienia.ignoruj_mnoznik}
                  onChange={(e) => p.setUstawienia({ ...p.ustawienia, ignoruj_mnoznik: e.currentTarget.checked })} />
              </Stack>
            </Accordion.Panel>
          </Accordion.Item>
        </Accordion>
      </Stack>
    </ScrollArea>
  );
}
