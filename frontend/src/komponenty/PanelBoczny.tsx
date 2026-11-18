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

import type { ReactNode } from 'react';

import type { Filtry, MetaPozycji, SezonStatystyk } from '../api';
import Boisko from './Boisko';
import { eur } from '../format';

export type Ustawienia = { k_baza: number; ignoruj_mnoznik: boolean };

type Props = {
  // sezon statystyk (opcja odczytu zapisu, dziala we wszystkich widokach); null - zrodlo bez zapisu gry
  sezonStatystyk: SezonStatystyk | null;
  setSezonStatystyk: (s: SezonStatystyk) => void;
  dataGry: string | null | undefined;
  sezonyUzyte: Record<string, number>;     // "2027/28" -> liczba zawodnikow (z odczytu zapisu)
  wczytywanie: boolean;
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
  // domyslnie prog automatyczny wg ligi zawodnika (1/3 minut typowego podstawowego zawodnika jego ligi w tej
  // chwili sezonu); staly prog 1000 min w trakcie sezonu ukrywal wiekszosc zawodnikow. Wlasna wartosc w panelu.
  min_minut: null,
  bez_mojego_klubu: false, okazje: [], min_rozwoj: null, kandydaci: false,
  min_score_kandydata: 60, min_niedowartosciowanie: null, kandydaci_z: [],
  rola_fm: null, silnik_fm: true, home_grown: null,
};

// Dymek z opisem filtra (po najechaniu na filtr) - ten sam wyglad przy kazdym filtrze panelu
function Podpowiedz({ opis, children }: { opis: ReactNode; children: ReactNode }) {
  return (
    <Tooltip multiline w={320} withArrow position="right" openDelay={300} label={opis}>
      <div>{children}</div>
    </Tooltip>
  );
}

const ROK_SEZONU = (iso: string | null | undefined) => {
  const d = iso ? new Date(iso) : new Date();
  return d.getMonth() >= 6 ? d.getFullYear() : d.getFullYear() - 1;
};
const etykietaSezonu = (rok: number) => `${rok}/${String((rok + 1) % 100).padStart(2, '0')}`;

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

        {p.sezonStatystyk !== null && (() => {
          const rok = ROK_SEZONU(p.dataGry);
          // dawne wartosci (ostatni / przedostatni) pokazane jako rok
          const wartosc = p.sezonStatystyk === 'ostatni' ? String(rok - 1)
            : p.sezonStatystyk === 'przedostatni' ? String(rok - 2) : p.sezonStatystyk;
          const uzyte = Object.entries(p.sezonyUzyte ?? {});
          return (
            <div>
              <Podpowiedz opis={<>
                Z którego sezonu są statystyki we wszystkich zakładkach (SCORE, ranking, kadra, wykresy). Zmiana
                wczytuje zapis ponownie (ok. minuty).<br />
                <b>Automatycznie</b>: każdy zawodnik ma swój ostatni sezon z minutami - bieżący, gdy rozegrał w nim
                co najmniej 450 minut, inaczej ostatni zakończony (archiwum gry). Ligi zmieniają sezon w różnych dniach
                (np. w lipcu Serie A ma już nowy sezon, a LaLiga jeszcze nie), więc rok ustalany jest dla każdej ligi
                osobno.<br />
                <b>Rok sezonu</b>: wszyscy zawodnicy z tego sezonu (bieżący sezon ligi albo archiwum). Zawodnik, który
                w nim nie grał, nie ma statystyk.<br />
                Minimum minut liczy się z minut wybranego sezonu.
              </>}>
                <Select label="Sezon statystyk" allowDeselect={false} value={wartosc} disabled={p.wczytywanie}
                  onChange={(v) => v && v !== wartosc && p.setSezonStatystyk(v as SezonStatystyk)}
                  data={[
                    { value: 'auto', label: 'Automatycznie (ostatni z minutami)' },
                    ...[rok, rok - 1, rok - 2].map((r) => ({ value: String(r), label: `Sezon ${etykietaSezonu(r)}` })),
                  ]} />
              </Podpowiedz>
              <Text size="xs" c="dimmed" mt={4}>
                {p.wczytywanie ? 'Wczytywanie zapisu...'
                  : uzyte.length ? `Użyte: ${uzyte.map(([sez, n]) => `${sez} (${n})`).join(', ')}`
                    : 'Użyty: bieżący sezon każdej ligi'}
              </Text>
            </div>
          );
        })()}

        {p.pozycja !== 'Bramkarz' && (
        <div>
          <Podpowiedz
            opis="Zawodnicy grający nominalnie na wybranych pozycjach, oceniani według kryteriów tej pozycji - kandydaci do przekwalifikowania w grze. Nie zmieniają wyników zawodników tej pozycji. Puste pole = wyłączone.">
            <MultiSelect label="Kandydaci z innych pozycji" placeholder="Wyłączone - wybierz pozycje" clearable
              data={p.pozycje.filter((x) => x !== p.pozycja && x !== 'Bramkarz')}
              value={filtry.kandydaci_z}
              onChange={(v) => setFiltry({ ...filtry, kandydaci_z: v, kandydaci: v.length > 0 })} />
          </Podpowiedz>
          {filtry.kandydaci_z.length > 0 && (
            <>
              <Podpowiedz opis="Kandydaci z innych pozycji z SCORE niższym niż ten próg są ukryci (ich wynik jest liczony według kryteriów wybranej pozycji).">
                <Text size="xs" mt={6}>Minimalny SCORE kandydata: {filtry.min_score_kandydata}</Text>
              </Podpowiedz>
              <Slider min={40} max={80} step={1} label={null} value={filtry.min_score_kandydata}
                onChange={(v) => zmien('min_score_kandydata', v)} />
            </>
          )}
        </div>
        )}

        <Podpowiedz opis="Pokazuje tylko zawodników, których nazwisko albo klub zawiera wpisany tekst (wielkość liter bez znaczenia).">
          <TextInput label="Szukaj (piłkarz / klub)" value={filtry.szukaj} onChange={(e) => zmien('szukaj', e.currentTarget.value)} />
        </Podpowiedz>

        {meta?.wiek && (
          <div>
            <Podpowiedz opis="Zakres wieku zawodników. Wspólny dla wszystkich pozycji; suwak pokazuje zakres wieku w tej pozycji.">
              <Text size="sm" fw={500}>Wiek: {(wiek ?? meta.wiek).join(' – ')}</Text>
            </Podpowiedz>
            <RangeSlider min={meta.wiek[0]} max={meta.wiek[1]} minRange={0} value={wiek ?? meta.wiek}
              onChange={(v) => zmien('wiek', v)} label={null} />
          </div>
        )}

        {cenaMax > 0 && (
          <div>
            <Podpowiedz opis="Zakres wartości transferowej z zapisu gry. Suwak ma skalę pierwiastkową - więcej precyzji przy niższych kwotach.">
              <Text size="sm" fw={500}>Cena: {eur(cena[0] ?? 0)} – {eur(cena[1] ?? cenaMax)}</Text>
            </Podpowiedz>
            <RangeSlider min={0} max={100} step={0.5} label={null}
              value={[doSuwaka(cena[0] ?? 0, cenaMax), doSuwaka(cena[1] ?? cenaMax, cenaMax)]}
              onChange={([a, b]) => zmien('cena', a <= 0 && b >= 100 ? null : [zSuwaka(a, cenaMax), b >= 100 ? null : zSuwaka(b, cenaMax)])} />
            <Podpowiedz opis="Zawodnicy bez wartości transferowej (np. „nie na sprzedaż”) - włączone: zostają mimo filtra ceny; wyłączone: są ukryci.">
              <Switch mt={6} label="Uwzględnij zawodników bez ceny" checked={filtry.bez_ceny}
                onChange={(e) => zmien('bez_ceny', e.currentTarget.checked)} />
            </Podpowiedz>
          </div>
        )}

        {pensjaMax > 0 && (
          <div>
            <Podpowiedz opis="Zakres obecnej pensji tygodniowej zawodnika. Zawodnicy bez pensji w danych zostają.">
              <Text size="sm" fw={500}>Pensja (tyg.): {eur(pensja[0] ?? 0)} – {eur(pensja[1] ?? pensjaMax)}</Text>
            </Podpowiedz>
            <RangeSlider min={0} max={100} step={0.5} label={null}
              value={[doSuwaka(pensja[0] ?? 0, pensjaMax), doSuwaka(pensja[1] ?? pensjaMax, pensjaMax)]}
              onChange={([a, b]) => zmien('pensja', a <= 0 && b >= 100 ? null
                : [zSuwaka(a, pensjaMax, 1000), b >= 100 ? null : zSuwaka(b, pensjaMax, 1000)])} />
          </div>
        )}

        {meta?.ma_kontrakty && (
          <Podpowiedz opis="Tylko zawodnicy, którym kontrakt kończy się w wybranym czasie od daty w grze. W ciągu 6 miesięcy można z nimi podpisać umowę przedwstępną za darmo.">
          <Select label="Kontrakt wygasa (od daty w grze)" clearable placeholder="Dowolnie"
            value={filtry.kontrakt_mies ? String(filtry.kontrakt_mies) : null}
            onChange={(v) => zmien('kontrakt_mies', v ? Number(v) : null)}
            data={[
              { value: '6', label: 'w ciągu 6 mies. (możliwy pre-kontrakt)' },
              { value: '12', label: 'w ciągu 12 mies.' },
              { value: '18', label: 'w ciągu 18 mies.' },
            ]} />
          </Podpowiedz>
        )}

        <Podpowiedz opis="Wycena wg wyniku / cena: ×2 = zawodnik gra jak typowy zawodnik dwa razy droższy (o tym samym wieku i kontrakcie). Ukrywa zawodników poniżej progu i bez ceny.">
        <Select label="Niedowartościowanie co najmniej" clearable placeholder="Dowolne"
          value={filtry.min_niedowartosciowanie ? String(filtry.min_niedowartosciowanie) : null}
          onChange={(v) => zmien('min_niedowartosciowanie', v ? Number(v) : null)}
          data={[
            { value: '1.5', label: '×1,5 (wyraźnie tańszy)' },
            { value: '2', label: '×2 (dwa razy tańszy)' },
            { value: '3', label: '×3 i więcej' },
          ]} />
        </Podpowiedz>

        {meta?.ma_historie && (
          <Podpowiedz opis={`Zmiana SCORE względem poprzedniego sezonu (migawka historii z ${meta.data_porownania ?? '–'}), `
            + `liczona tylko przy co najmniej ${meta.min_minut_rozwoju} minutach w obu sezonach. Ukrywa zawodników z mniejszym wzrostem i bez historii.`}>
          <Select label="Rozwój w sezonie co najmniej" clearable placeholder="Dowolny"
            value={filtry.min_rozwoj !== null ? String(filtry.min_rozwoj) : null}
            onChange={(v) => zmien('min_rozwoj', v ? Number(v) : null)}
            data={[
              { value: '3', label: '+3 SCORE' },
              { value: '5', label: '+5 SCORE (szybki rozwój)' },
              { value: '10', label: '+10 SCORE i więcej' },
            ]} />
          </Podpowiedz>
        )}

        <Podpowiedz opis="Tylko zawodnicy z wybraną lepszą nogą (np. lewonożni na lewą stronę). Puste pole = każda noga.">
          <MultiSelect label="Lepsza noga" placeholder="Dowolna" clearable data={meta?.nogi ?? []} value={filtry.nogi}
            onChange={(v) => zmien('nogi', v)} />
        </Podpowiedz>

        {meta?.minuty_max ? (
          <Podpowiedz opis={<>
            Ukrywa zawodników z mniejszą liczbą minut w sezonie statystyk (mała próba to często przypadek).<br />
            <b>auto</b> (puste pole): osobno dla każdej ligi - 1/3 minut typowego podstawowego zawodnika tej ligi
            w tej chwili sezonu (cała pula: {meta.min_minut_auto}). Wpisz 0, aby pokazać wszystkich.
          </>}>
          <NumberInput label="Minimum minut" min={0} step={90} value={filtry.min_minut ?? ''}
            placeholder={`auto wg ligi (cała pula: ${meta.min_minut_auto})`}
            rightSectionWidth={56}
            rightSection={filtry.min_minut !== null ? (
              <Button variant="subtle" size="compact-xs" onClick={() => zmien('min_minut', null)}>auto</Button>
            ) : null}
            onChange={(v) => zmien('min_minut', v === '' ? null : Number(v) || 0)} />
          </Podpowiedz>
        ) : null}

        {(meta?.role_fm ?? []).length > 0 && (
          <div>
            <Podpowiedz opis="Kolumna Ocena roli: średnia ważona atrybutów wybranej roli FM w skali 1-20 (kluczowe ×1, zalecane ×0,5). Puste pole = najlepsza rola z piłką każdego zawodnika (najlepsza rola bez piłki jest w osobnej kolumnie). Nie ukrywa zawodników - zmienia tylko ocenę roli.">
            <Select label="Rola FM (ocena z atrybutów)" clearable placeholder="Najlepsza rola zawodnika"
              value={filtry.rola_fm && meta?.role_fm?.some((r) => r.nazwa === filtry.rola_fm) ? filtry.rola_fm : null}
              onChange={(v) => zmien('rola_fm', v)}
              renderOption={({ option }) => {
                const r = meta?.role_fm?.find((x) => x.nazwa === option.value);
                return (
                  <Tooltip multiline w={280} withArrow position="right" openDelay={300}
                    label={r ? `Kluczowe: ${r.kluczowe.join(', ')}. Zalecane: ${r.zalecane.join(', ')}.` : ''}>
                    <span style={{ width: '100%' }}>{option.label}</span>
                  </Tooltip>
                );
              }}
              data={[
                { group: 'Z piłką', items: (meta?.role_fm ?? []).filter((r) => r.faza !== 'bez').map((r) => r.nazwa) },
                { group: 'Bez piłki', items: (meta?.role_fm ?? []).filter((r) => r.faza === 'bez').map((r) => r.nazwa) },
              ].filter((g) => g.items.length)} />
            </Podpowiedz>
            <Podpowiedz
              opis="Testy silnika meczowego społeczności FM-Arena: najwięcej punktów daje szybkość i przyspieszenie, potem skoczność, zwinność i drybling. Włączone - te atrybuty mają większą wagę w ocenie roli (bez bramkarzy).">
              <Switch mt={6} label="Wagi atrybutów wg testów silnika" checked={filtry.silnik_fm}
                onChange={(e) => zmien('silnik_fm', e.currentTarget.checked)} />
            </Podpowiedz>
          </div>
        )}

        {p.maMojKlub && meta?.ma_hg && (
          <Podpowiedz opis="Wychowankowie: co najmniej 3 lata w klubach kraju Twojego klubu (albo w samym klubie) między 15. a 21. rokiem życia. Liczą się do limitów rejestracji, np. 8 z 25 w Lidze Mistrzów.">
          <Select label="Home-grown" clearable placeholder="Dowolnie"
            value={filtry.home_grown} onChange={(v) => zmien('home_grown', v)}
            data={[
              { value: 'kraj', label: 'wychowanek kraju mojego klubu' },
              { value: 'klub', label: 'wychowanek mojego klubu' },
            ]} />
          </Podpowiedz>
        )}

        {p.maMojKlub && (
          <Podpowiedz opis="Ukrywa zawodników Twojego klubu - zostają tylko kandydaci do kupienia.">
            <Switch label="Pomiń mój klub" checked={filtry.bez_mojego_klubu}
              onChange={(e) => zmien('bez_mojego_klubu', e.currentTarget.checked)} />
          </Podpowiedz>
        )}

        <Podpowiedz opis="Przywraca wszystkie filtry panelu i filtry kolumn tabeli do ustawień domyślnych (sezon statystyk i wagi zostają).">
          <Button variant="subtle" fullWidth onClick={() => setFiltry(PUSTE_FILTRY)}>Wyczyść filtry</Button>
        </Podpowiedz>

        <Accordion variant="separated" multiple defaultValue={[]}>
          <Accordion.Item value="wagi">
            <Accordion.Control>Wagi statystyk</Accordion.Control>
            <Accordion.Panel>
              <Stack gap="xs">
                {role.length > 0 && (
                  <>
                    <Select label="Rola (gotowe wagi)" allowDeselect={false}
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
                {(meta?.statystyki_niedostepne ?? []).length > 0 && (
                  <Text size="xs" c="dimmed">
                    Niedostępne w zapisie gry (pominięte w SCORE): {meta!.statystyki_niedostepne.join(', ')}.
                  </Text>
                )}
                {Object.entries(p.wagi).filter(([cecha]) => !(meta?.statystyki_niedostepne ?? []).includes(cecha))
                  .map(([cecha, waga]) => (
                  <div key={cecha}>
                    <Group justify="space-between" gap={4}>
                      <Text size="xs" c={p.pominiete.includes(cecha) ? 'dimmed' : undefined}>{cecha}</Text>
                      <Badge size="xs" variant="light">{sumaWag ? Math.round((waga / sumaWag) * 100) : 0}%</Badge>
                    </Group>
                    <Slider min={0} max={100} step={5} value={waga} label={null}
                      onChange={(v) => p.setWagi({ ...p.wagi, [cecha]: v })} />
                  </div>
                ))}
                <Button variant="subtle" onClick={() => p.setWagi(null)}>Przywróć domyślne wagi</Button>
              </Stack>
            </Accordion.Panel>
          </Accordion.Item>
          <Accordion.Item value="model">
            <Accordion.Control>Ustawienia wyniku</Accordion.Control>
            <Accordion.Panel>
              <Stack gap="sm">
                <Podpowiedz opis="Wyłącza korektę siły ligi w SCORE - zawodnicy są porównywani tak, jakby wszyscy grali w tej samej lidze.">
                  <Switch label="Ignoruj mnożnik ligowy" checked={p.ustawienia.ignoruj_mnoznik}
                    onChange={(e) => p.setUstawienia({ ...p.ustawienia, ignoruj_mnoznik: e.currentTarget.checked })} />
                </Podpowiedz>
              </Stack>
            </Accordion.Panel>
          </Accordion.Item>
        </Accordion>
      </Stack>
    </ScrollArea>
  );
}
