import { Alert, Autocomplete, Badge, Button, Group, Loader, NumberInput, Stack, Table, Text, TextInput, Title } from '@mantine/core';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';

import { api, type Kraj, type Liga, type Ligi as DaneLig } from '../api';
import { SZEROKOSC } from '../wyglad';

function WierszLigi({ liga, dane }: { liga: Liga; dane: DaneLig }) {
  const klient = useQueryClient();
  const [nazwa, setNazwa] = useState(liga.nazwa ?? '');
  const [mnoznik, setMnoznik] = useState<number | ''>(liga.mnoznik ?? '');
  const [blad, setBlad] = useState<string | null>(null);
  const [zapisuje, setZapisuje] = useState(false);
  const zmieniona = nazwa.trim() !== (liga.nazwa ?? '') || (mnoznik === '' ? null : mnoznik) !== liga.mnoznik;

  const zapisz = async () => {
    if (liga.klucz === null) return;
    setZapisuje(true);
    setBlad(null);
    try {
      await api.zmienLige(liga.klucz, nazwa.trim(), mnoznik === '' ? null : mnoznik);
      // nowa wersja danych na serwerze -> odswiezenie stanu, lig i rankingu
      await klient.invalidateQueries({ queryKey: ['stan'] });
    } catch (e) {
      setBlad((e as Error).message);
    } finally {
      setZapisuje(false);
    }
  };

  return (
    <Table.Tr>
      <Table.Td>
        <Text size="sm" fw={600}>{liga.nazwa ?? liga.domyslna}</Text>
        <Text size="xs" c="dimmed">
          {liga.nazwa_auto ? 'nazwa automatyczna · ' : ''}nr {liga.klucz ?? '–'} · {liga.liczba} klubów
        </Text>
      </Table.Td>
      <Table.Td><Text size="xs">{liga.kluby.join(', ')}</Text></Table.Td>
      <Table.Td>
        <Text size="sm" fw={600}>{liga.mnoznik_auto?.toFixed(3).replace('.', ',') ?? '–'}</Text>
        <Text size="xs" c="dimmed">
          {liga.zrodlo_mnoznika === 'transfery' ? 'z transferów' : 'z reputacji'}
          {liga.reputacja ? ` · rep. ${Math.round(liga.reputacja)}` : ''}
        </Text>
      </Table.Td>
      <Table.Td miw={200}>
        <Autocomplete placeholder={liga.nazwa ?? 'Nazwa z gry'} data={dane.znane_nazwy} value={nazwa} limit={30}
          onChange={setNazwa} />
      </Table.Td>
      <Table.Td w={130}>
        <NumberInput min={0.3} max={1.2} step={0.01} decimalScale={3} value={mnoznik}
          placeholder="auto" onChange={(v) => setMnoznik(v === '' ? '' : Number(v))} />
      </Table.Td>
      <Table.Td>
        <Button onClick={zapisz} loading={zapisuje} disabled={!zmieniona || !nazwa.trim() || liga.klucz === null}>
          Zapisz
        </Button>
        {blad && <Text size="xs" c="red">{blad}</Text>}
      </Table.Td>
    </Table.Tr>
  );
}

const ZRODLA_KRAJU: Record<string, string> = {
  baza: ' · z bazy gry', liga: ' · z ligi', kluby: ' · z klubów krajowych', 'ręcznie': ' · Twoja nazwa',
};

function WierszKraju({ kraj }: { kraj: Kraj }) {
  const klient = useQueryClient();
  const [nazwa, setNazwa] = useState(kraj.reczna ? kraj.nazwa ?? '' : '');
  const [zapisuje, setZapisuje] = useState(false);
  const zapisz = async () => {
    if (kraj.id === null) return;
    setZapisuje(true);
    try {
      await api.zmienKraj(kraj.id, nazwa.trim());
      await klient.invalidateQueries({ queryKey: ['stan'] });
    } finally {
      setZapisuje(false);
    }
  };
  return (
    <Table.Tr>
      <Table.Td>
        <Text size="sm" fw={600}>{kraj.nazwa ?? `Kraj #${kraj.id}`}</Text>
        <Text size="xs" c="dimmed">
          {kraj.id !== null ? `id ${kraj.id}` : ''}
          {ZRODLA_KRAJU[kraj.zrodlo ?? ''] ?? ''}
        </Text>
      </Table.Td>
      <Table.Td>{kraj.liczba}</Table.Td>
      <Table.Td><Text size="xs">{kraj.przyklady.join(', ')}</Text></Table.Td>
      {kraj.id !== null && (
        <>
          <Table.Td miw={200}>
            <TextInput placeholder={kraj.nazwa ?? 'Nazwa kraju'} value={nazwa}
              onChange={(e) => setNazwa(e.currentTarget.value)} />
          </Table.Td>
          <Table.Td>
            <Button onClick={zapisz} loading={zapisuje} disabled={nazwa.trim() === (kraj.reczna ? kraj.nazwa ?? '' : '')}>
              Zapisz
            </Button>
          </Table.Td>
        </>
      )}
    </Table.Tr>
  );
}

const NA_START = 5;

// Pierwsze NA_START wierszy od razu, reszta po "Pokaz wiecej". Wiersze bez nazwy ida na gore (to je trzeba
// uzupelnic), dalej wg liczebnosci - lista wejsciowa jest juz posortowana malejaco.
function zwin<T>(lista: T[], maNazwe: (x: T) => boolean, rozwiniete: boolean): { widoczne: T[]; ukryte: number } {
  const kolejnosc = [...lista.filter((x) => !maNazwe(x)), ...lista.filter(maNazwe)];
  const widoczne = rozwiniete ? kolejnosc : kolejnosc.slice(0, NA_START);
  return { widoczne, ukryte: lista.length - widoczne.length };
}

function PokazWiecej({ rozwiniete, ukryte, przelacz, wszystkich }: {
  rozwiniete: boolean; ukryte: number; przelacz: () => void; wszystkich: number;
}) {
  if (!rozwiniete && ukryte === 0) return null;
  return (
    <Button variant="subtle" onClick={przelacz} style={{ alignSelf: 'flex-start' }}>
      {rozwiniete ? 'Pokaż mniej' : `Pokaż więcej (${ukryte} z ${wszystkich})`}
    </Button>
  );
}

// Mnoznik minut rozegranych w rezerwach, druzynach mlodziezowych i ligach niewykrytych
function MnoznikRezerw({ dane }: { dane: DaneLig }) {
  const klient = useQueryClient();
  const [mnoznik, setMnoznik] = useState<number | ''>(dane.mnoznik_rezerw ?? '');
  const [zapisuje, setZapisuje] = useState(false);
  const [blad, setBlad] = useState<string | null>(null);
  const zapisz = async () => {
    setZapisuje(true);
    setBlad(null);
    try {
      await api.zmienMnoznikRezerw(mnoznik === '' ? null : mnoznik);
      await klient.invalidateQueries({ queryKey: ['stan'] });
    } catch (e) {
      setBlad((e as Error).message);
    } finally {
      setZapisuje(false);
    }
  };
  return (
    <Group align="end" gap="xs">
      <NumberInput w={SZEROKOSC.szeroka} label="Mnożnik rezerw, drużyn młodzieżowych i innych rozgrywek" min={0.3} max={1.2}
        step={0.01} decimalScale={3} value={mnoznik} placeholder={`auto: ${dane.mnoznik_rezerw_auto}`}
        onChange={(v) => setMnoznik(v === '' ? '' : Number(v))} />
      <Button onClick={zapisz} loading={zapisuje}
        disabled={(mnoznik === '' ? null : mnoznik) === dane.mnoznik_rezerw}>Zapisz</Button>
      {blad && <Text size="xs" c="red">{blad}</Text>}
    </Group>
  );
}

// Edycja nazw i mnoznikow lig wykrytych w zapisie (zapis nie zawiera nazw rozgrywek)
function SekcjaLig({ wersja }: { wersja: number }) {
  const ligi = useQuery({ queryKey: ['ligi', wersja], queryFn: api.ligi });
  const [rozwiniete, setRozwiniete] = useState(false);
  const naglowek = <Title order={4}>Ligi</Title>;
  if (ligi.isLoading) return <Stack>{naglowek}<Loader size="sm" /></Stack>;
  if (ligi.error) return <Stack>{naglowek}<Alert color="red">{(ligi.error as Error).message}</Alert></Stack>;
  const dane = ligi.data;
  if (!dane || dane.ligi.length === 0) {
    return (
      <Stack>
        {naglowek}
        <Alert color="gray">Lista lig jest dostępna po wczytaniu zapisu kariery (dane demo nie mają numerów rozgrywek).</Alert>
      </Stack>
    );
  }
  const posortowane = [...dane.ligi].sort((a, b) => (b.mnoznik_auto ?? 0) - (a.mnoznik_auto ?? 0));
  const { widoczne, ukryte } = zwin(posortowane, () => true, rozwiniete);

  return (
    <Stack>
      <Group gap="xs">
        {naglowek}
        <Badge color="gray" variant="light">wszystkich: {dane.ligi.length}</Badge>
      </Group>
      <Text size="sm" c="dimmed">
        Nazwy i mnożniki lig ustawiają się same - nic nie musisz wpisywać. Nazwy pochodzą z tabeli numerów rozgrywek
        (zapis gry podaje tylko numer); liga spoza tabeli dostaje nazwę z kraju swoich klubów. Mnożnik (siła ligi) jest
        liczony z danych: z tego, jak zmienia się gra zawodników po zmianie ligi (ligi z wieloma transferami), i z
        reputacji klubów ligi odczytanej z zapisu (pozostałe). W SCORE liczy się średnia mnożników lig, w których
        zawodnik grał, ważona minutami. Własną nazwę lub mnożnik możesz wpisać opcjonalnie - puste pole przywraca wartość
        automatyczną.
      </Text>
      <MnoznikRezerw key={String(dane.mnoznik_rezerw)} dane={dane} />
      <Table striped highlightOnHover>
        <Table.Thead>
          <Table.Tr>
            <Table.Th>Liga</Table.Th><Table.Th>Przykładowe kluby</Table.Th><Table.Th>Mnożnik</Table.Th>
            <Table.Th>Własna nazwa</Table.Th><Table.Th>Własny mnożnik</Table.Th><Table.Th />
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {widoczne.map((l) => (
            <WierszLigi key={`${l.klucz}-${l.nazwa ?? ''}-${l.mnoznik ?? ''}`} liga={l} dane={dane} />
          ))}
        </Table.Tbody>
      </Table>
      <PokazWiecej rozwiniete={rozwiniete} ukryte={ukryte} wszystkich={dane.ligi.length}
        przelacz={() => setRozwiniete(!rozwiniete)} />
    </Stack>
  );
}

// Narodowosci: zapis nie zawiera nazw krajow - czesc wynika z nazwanych lig i klubow, reszte wpisuje uzytkownik
function SekcjaKrajow({ wersja }: { wersja: number }) {
  const kraje = useQuery({ queryKey: ['kraje', wersja], queryFn: api.kraje });
  const [rozwiniete, setRozwiniete] = useState(false);
  if (!kraje.data || kraje.data.kraje.length === 0) return null;
  const wszystkie = kraje.data.kraje;
  const edycja = wszystkie.some((k) => k.id !== null);
  const bezNazwy = wszystkie.filter((k) => !k.nazwa).length;
  const posortowane = [...wszystkie].sort((a, b) => b.liczba - a.liczba);   // kraje bez nazwy i tak na gorze
  const { widoczne, ukryte } = zwin(posortowane, (k) => !!k.nazwa, rozwiniete);
  return (
    <Stack>
      <Group gap="xs">
        <Title order={4}>Kraje</Title>
        {edycja && <Badge color={bezNazwy ? 'yellow' : 'teal'} variant="light">bez nazwy: {bezNazwy}</Badge>}
        <Badge color="gray" variant="light">wszystkich: {wszystkie.length}</Badge>
      </Group>
      {edycja && (
        <Text size="sm" c="dimmed">
          Narodowości zawodników nadawane automatycznie: zapis podaje stały numer kraju w bazie gry, a program ma tabelę
          nazw dla wszystkich krajów z zawodnikami. Nazwę możesz opcjonalnie zmienić; pusta przywraca automatyczną.
        </Text>
      )}
      <Table striped highlightOnHover>
        <Table.Thead>
          <Table.Tr>
            <Table.Th>Kraj</Table.Th><Table.Th>Zawodników</Table.Th><Table.Th>Najdrożsi zawodnicy</Table.Th>
            {edycja && <><Table.Th>Nazwa</Table.Th><Table.Th /></>}
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {widoczne.map((k) => <WierszKraju key={`${k.id ?? k.nazwa}-${k.nazwa ?? ''}`} kraj={k} />)}
        </Table.Tbody>
      </Table>
      <PokazWiecej rozwiniete={rozwiniete} ukryte={ukryte} wszystkich={wszystkie.length}
        przelacz={() => setRozwiniete(!rozwiniete)} />
    </Stack>
  );
}

// Zakladka "Ligi i kraje": ligi wykryte w zapisie i narodowosci zawodnikow
export default function Ligi({ wersja }: { wersja: number }) {
  return (
    <Stack p="md" gap="xl">
      <SekcjaLig wersja={wersja} />
      <SekcjaKrajow wersja={wersja} />
    </Stack>
  );
}
