// Wyszukiwarka personelu wszystkich klubow po atrybutach liczbowych 1-20 (jak na ekranie personelu w grze):
// gotowe zestawy kluczowych atrybutow stanowisk, minimum dla wybranych atrybutow, stanowisko, charakter, wiek, placa.
import { Alert, Group, Loader, MultiSelect, NumberInput, RangeSlider, Select, SimpleGrid, Slider, Stack, Switch, Text,
  TextInput, Tooltip } from '@mantine/core';
import { useDebouncedValue } from '@mantine/hooks';
import { useQuery } from '@tanstack/react-query';
import { useMemo, useState, type ReactNode } from 'react';

import { api, type Kolumna, type Wiersz, type ZapytanieSzukajPersonelu } from '../api';
import { usePamiec } from '../pamiec';
import TabelaRankingu from './TabelaRankingu';

const MIN_DOMYSLNE = 15;
const WIEK: [number, number] = [18, 80];
const WLASNE = 'Własne';

function Podpowiedz({ opis, children }: { opis: ReactNode; children: ReactNode }) {
  return (
    <Tooltip multiline w={320} withArrow openDelay={300} label={opis}>
      <div>{children}</div>
    </Tooltip>
  );
}

const PUSTE: ZapytanieSzukajPersonelu = {
  stanowiska: [], min_atrybuty: {}, wiek: null, maks_placa: null, szukaj: '', bez_menedzerow: true, bez_mojego: true,
  charakter: [],
};

export default function WyszukiwarkaPersonelu({ wersja }: { wersja: number }) {
  const [z, setZ] = usePamiec<ZapytanieSzukajPersonelu>('fm-szukaj-personelu', PUSTE);
  const [zestaw, setZestaw] = useState<string>(WLASNE);
  const [opoznione] = useDebouncedValue(z, 300);
  const dane = useQuery({
    queryKey: ['szukaj-personelu', wersja, opoznione],
    queryFn: () => api.szukajPersonelu({ ...PUSTE, ...opoznione }),
    staleTime: Infinity, retry: false, placeholderData: (poprzednie) => poprzednie,
  });
  const zmien = <K extends keyof ZapytanieSzukajPersonelu>(k: K, v: ZapytanieSzukajPersonelu[K]) => {
    setZ({ ...z, [k]: v });
    if (k === 'min_atrybuty') setZestaw(WLASNE);
  };
  const r = dane.data;
  const nazwy = r?.atrybuty ?? {};
  const wybrane = Object.keys(z.min_atrybuty ?? {});

  // wiersze tabeli: osoba i atrybuty pod polskimi nazwami (kolumny tabeli)
  const [kolumny, wiersze] = useMemo(() => {
    if (!r) return [[], []] as [Kolumna[], Wiersz[]];
    const atr = [...wybrane, ...Object.keys(r.atrybuty).filter((a) => !wybrane.includes(a))];
    const kol: Kolumna[] = [
      { naglowek: 'Osoba', pole: 'Osoba', format: 'tekst', statystyka: false, nizsze_lepsze: false },
      { naglowek: 'Klub', pole: 'Klub', format: 'tekst', statystyka: false, nizsze_lepsze: false },
      { naglowek: 'Stanowisko', pole: 'Stanowisko', format: 'tekst', statystyka: false, nizsze_lepsze: false },
      { naglowek: 'Charakter', pole: 'Charakter', format: 'tekst', statystyka: false, nizsze_lepsze: false },
      { naglowek: 'Wiek', pole: 'Wiek', format: 'int', statystyka: false, nizsze_lepsze: false },
      { naglowek: 'Płaca / tydz.', pole: 'Płaca', format: 'eur', statystyka: false, nizsze_lepsze: false },
      { naglowek: 'Kontrakt do', pole: 'Kontrakt do', format: 'data', statystyka: false, nizsze_lepsze: false },
      ...atr.map((a) => ({ naglowek: r.atrybuty[a], pole: r.atrybuty[a], format: 'int' as const, statystyka: true,
        nizsze_lepsze: false })),
    ];
    const w: Wiersz[] = r.wyniki.map((o) => ({
      ID: o.uid, Osoba: o.nazwa, Klub: o.klub, Klub_UID: o.klub_uid, Stanowisko: o.stanowisko, Charakter: o.charakter,
      Wiek: o.wiek, Płaca: o.placa_tydzien, 'Kontrakt do': o.kontrakt_do,
      ...Object.fromEntries(Object.entries(o.atrybuty).map(([a, v]) => [r.atrybuty[a] ?? a, v])),
    }));
    return [kol, w];
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [r, wybrane.join('|')]);

  const ustawZestaw = (nazwa: string | null) => {
    const n = nazwa ?? WLASNE;
    setZestaw(n);
    const atr = r?.zestawy?.[n];
    if (atr) setZ({ ...z, min_atrybuty: Object.fromEntries(atr.map((a) => [a, z.min_atrybuty?.[a] ?? MIN_DOMYSLNE])) });
  };

  if (dane.isLoading) {
    return (
      <Group gap="sm"><Loader size="sm" /><Text size="sm">Odczyt personelu z zapisu gry (ok. 20 s, tylko za pierwszym razem)...</Text></Group>
    );
  }
  if (dane.error) return <Alert color="red">{(dane.error as Error).message}</Alert>;

  return (
    <Stack gap="sm" h="calc(100dvh / var(--skala, 1) - 250px)" mih={520}>
      <SimpleGrid cols={{ base: 2, lg: 4 }} spacing="sm" verticalSpacing="xs">
        <Podpowiedz opis={<>Gotowe zestawy kluczowych atrybutów stanowisk z FM: wybór zaznacza atrybuty z minimum {MIN_DOMYSLNE} (suwaki poniżej). Gra nie zapisuje tych zestawów w pliku - to lista programu. Nie zawęża stanowiska.</>}>
          <Select label="Szukam" allowDeselect={false} searchable value={zestaw} onChange={ustawZestaw}
            data={[WLASNE, ...Object.keys(r?.zestawy ?? {})]} />
        </Podpowiedz>
        <Podpowiedz opis="Obecne stanowisko pracownika w jego klubie. Puste pole = każde.">
          <MultiSelect label="Stanowisko" placeholder="Każde" clearable searchable data={r?.stanowiska ?? []}
            value={z.stanowiska} onChange={(v) => zmien('stanowiska', v)} />
        </Podpowiedz>
        <Podpowiedz opis="Charakter jak w opisie pracownika w grze - przybliżenie wyliczone z jego osobowości (samych cech program nie pokazuje). Puste pole = każdy.">
          <MultiSelect label="Charakter" placeholder="Każdy" clearable data={r?.charaktery ?? []}
            value={z.charakter ?? []} onChange={(v) => zmien('charakter', v)} />
        </Podpowiedz>
        <Podpowiedz opis="Fragment nazwiska albo nazwy klubu.">
          <TextInput label="Szukaj (osoba / klub)" value={z.szukaj} onChange={(e) => zmien('szukaj', e.currentTarget.value)} />
        </Podpowiedz>
        <Podpowiedz opis="Zakres wieku pracownika.">
          <div>
            <Text size="sm" fw={500}>Wiek: {(z.wiek ?? WIEK).join(' – ')}</Text>
            <RangeSlider min={WIEK[0]} max={WIEK[1]} value={z.wiek ?? WIEK} label={null}
              onChange={(v) => zmien('wiek', v[0] <= WIEK[0] && v[1] >= WIEK[1] ? null : v)} />
          </div>
        </Podpowiedz>
        <Podpowiedz opis="Najwyższa obecna płaca tygodniowa pracownika (EUR). Puste pole = bez limitu.">
          <NumberInput label="Maks. płaca / tydz. (€)" min={0} step={1000} thousandSeparator=" " value={z.maks_placa ?? ''}
            onChange={(v) => zmien('maks_placa', v === '' ? null : Number(v))} />
        </Podpowiedz>
        <Podpowiedz opis="Menedżerów (pierwszych trenerów) innych klubów nie zatrudnisz do sztabu - włączone: są ukryci.">
          <Switch mt={26} label="Bez menedżerów innych klubów" checked={z.bez_menedzerow}
            onChange={(e) => zmien('bez_menedzerow', e.currentTarget.checked)} />
        </Podpowiedz>
        <Podpowiedz opis="Włączone: bez osób z Twojego sztabu.">
          <Switch mt={26} label="Bez mojego sztabu" checked={z.bez_mojego}
            onChange={(e) => zmien('bez_mojego', e.currentTarget.checked)} />
        </Podpowiedz>
      </SimpleGrid>

      <Podpowiedz opis="Atrybuty w skali gry 1-20 (atrybuty personelu z zapisu, oznaczone przez fmsave jako niepotwierdzone; bezkompromisowość to pole „authority”). Dla każdego wybranego atrybutu ustaw minimum; wyniki są ułożone malejąco po sumie wybranych atrybutów.">
        <MultiSelect label="Atrybuty (minimum)" placeholder="Wybierz atrybuty" clearable searchable
          data={Object.entries(nazwy).map(([value, label]) => ({ value, label }))} value={wybrane}
          onChange={(v) => zmien('min_atrybuty', Object.fromEntries(v.map((a) => [a, z.min_atrybuty?.[a] ?? MIN_DOMYSLNE])))} />
      </Podpowiedz>
      {wybrane.length > 0 && (
        <SimpleGrid cols={{ base: 2, lg: 4 }} spacing="lg" verticalSpacing={4}>
          {wybrane.map((a) => (
            <div key={a}>
              <Text size="sm">{nazwy[a] ?? a}: <b>{z.min_atrybuty[a]}</b>+</Text>
              <Slider min={1} max={20} step={1} label={null} value={z.min_atrybuty[a]}
                onChange={(v) => zmien('min_atrybuty', { ...z.min_atrybuty, [a]: v })} />
            </div>
          ))}
        </SimpleGrid>
      )}

      <Text size="sm" c="dimmed">
        {r ? `Pasujących: ${r.liczba} z ${r.wszystkich} pracowników${r.liczba > r.wyniki.length ? ` (pokazane pierwsze ${r.wyniki.length})` : ''}.` : ''}
        {dane.isFetching ? ' Szukam...' : ''} Ulubionych ustawień (formacji) jeszcze nie ma - zapis nie podaje ich nazw.
      </Text>
      <div style={{ flex: 1, minHeight: 320 }}>
        <TabelaRankingu kolumny={kolumny} wiersze={wiersze} mojKlubUid={null} naWybor={() => undefined}
          kluczUkladu="personel-szukaj" bezMenuZawodnika />
      </div>
    </Stack>
  );
}
