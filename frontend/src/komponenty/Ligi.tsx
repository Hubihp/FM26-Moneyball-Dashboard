import { Alert, Autocomplete, Badge, Button, Group, Loader, NumberInput, Stack, Table, Text, TextInput, Title } from '@mantine/core';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';

import { api, type Kraj, type Liga, type Ligi as DaneLig } from '../api';

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
        <Text size="sm" fw={600}>{liga.domyslna}</Text>
        <Text size="xs" c="dimmed">klucz {liga.klucz ?? '–'}</Text>
      </Table.Td>
      <Table.Td>{liga.liczba}</Table.Td>
      <Table.Td><Text size="xs">{liga.kluby.join(', ')}</Text></Table.Td>
      <Table.Td miw={220}>
        <Autocomplete size="xs" placeholder="Nazwa z gry" data={dane.znane_nazwy} value={nazwa} limit={30}
          onChange={(v) => {
            setNazwa(v);
            if (v in dane.mnozniki) setMnoznik(dane.mnozniki[v]);
          }} />
      </Table.Td>
      <Table.Td w={120}>
        <NumberInput size="xs" min={0.3} max={1.2} step={0.01} decimalScale={3} value={mnoznik}
          placeholder={String(dane.mnoznik_nieznanej)} onChange={(v) => setMnoznik(v === '' ? '' : Number(v))} />
      </Table.Td>
      <Table.Td>
        <Button size="xs" onClick={zapisz} loading={zapisuje} disabled={!zmieniona || !nazwa.trim() || liga.klucz === null}>
          Zapisz
        </Button>
        {blad && <Text size="xs" c="red">{blad}</Text>}
      </Table.Td>
    </Table.Tr>
  );
}

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
          {kraj.zrodlo === 'liga' ? ' · nazwa z ligi' : kraj.zrodlo === 'kluby' ? ' · nazwa z klubów krajowych' : ''}
        </Text>
      </Table.Td>
      <Table.Td>{kraj.liczba}</Table.Td>
      <Table.Td><Text size="xs">{kraj.przyklady.join(', ')}</Text></Table.Td>
      {kraj.id !== null && (
        <>
          <Table.Td miw={200}>
            <TextInput size="xs" placeholder={kraj.nazwa ?? 'Nazwa kraju'} value={nazwa}
              onChange={(e) => setNazwa(e.currentTarget.value)} />
          </Table.Td>
          <Table.Td>
            <Button size="xs" onClick={zapisz} loading={zapisuje} disabled={nazwa.trim() === (kraj.reczna ? kraj.nazwa ?? '' : '')}>
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
    <Button variant="subtle" size="xs" onClick={przelacz} style={{ alignSelf: 'flex-start' }}>
      {rozwiniete ? 'Pokaż mniej' : `Pokaż więcej (${ukryte} z ${wszystkich})`}
    </Button>
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
  const bezNazwy = dane.ligi.filter((l) => !l.nazwa).length;
  const posortowane = [...dane.ligi].sort((a, b) => b.liczba - a.liczba);
  const { widoczne, ukryte } = zwin(posortowane, (l) => !!l.nazwa, rozwiniete);

  return (
    <Stack>
      <Group gap="xs">
        {naglowek}
        <Badge color={bezNazwy ? 'yellow' : 'teal'} variant="light">bez nazwy: {bezNazwy}</Badge>
        <Badge color="gray" variant="light">wszystkich: {dane.ligi.length}</Badge>
      </Group>
      <Text size="sm" c="dimmed">
        Zapis gry nie zawiera nazw lig - tylko numery rozgrywek. Nazwę sprawdzisz w grze, otwierając jeden z klubów z listy.
        Liga bez nazwy dostaje najniższy mnożnik ({dane.mnoznik_nieznanej}). Mnożnik to siła ligi (Premier League ≈ 0,92,
        Ekstraklasa ≈ 0,80); dla nazw z podpowiedzi uzupełnia się sam. Zmiany zapisują się na stałe.
      </Text>
      <Table striped highlightOnHover>
        <Table.Thead>
          <Table.Tr>
            <Table.Th>Rozgrywki</Table.Th><Table.Th>Kluby</Table.Th><Table.Th>Przykładowe kluby</Table.Th>
            <Table.Th>Nazwa</Table.Th><Table.Th>Mnożnik</Table.Th><Table.Th />
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
  const posortowane = [...wszystkie].sort((a, b) => b.liczba - a.liczba);
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
          Narodowości zawodników. Zapis nie zawiera nazw krajów - aplikacja nadaje je sama: z nazwanych lig (zawodnicy
          Ekstraklasy → Polska) i ze składów typowo krajowych klubów (np. Hibernian, Aberdeen → Szkocja). Złą albo brakującą
          nazwę możesz tu poprawić; pusta nazwa przywraca nazwę automatyczną.
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
