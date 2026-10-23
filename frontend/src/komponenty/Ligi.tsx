import { Alert, Autocomplete, Badge, Button, Group, Loader, NumberInput, Stack, Table, Text } from '@mantine/core';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';

import { api, type Liga, type Ligi as DaneLig } from '../api';

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

// Edycja nazw i mnoznikow lig wykrytych w zapisie (zapis nie zawiera nazw rozgrywek)
export default function Ligi({ wersja }: { wersja: number }) {
  const ligi = useQuery({ queryKey: ['ligi', wersja], queryFn: api.ligi });
  if (ligi.isLoading) return <Loader m="md" />;
  if (ligi.error) return <Alert m="md" color="red">{(ligi.error as Error).message}</Alert>;
  const dane = ligi.data;
  if (!dane || dane.ligi.length === 0) {
    return <Alert m="md" color="gray">Lista lig jest dostępna po wczytaniu zapisu kariery.</Alert>;
  }
  const bezNazwy = dane.ligi.filter((l) => !l.nazwa).length;

  return (
    <Stack p="md">
      <Group gap="xs">
        <Badge color={bezNazwy ? 'yellow' : 'teal'} variant="light">bez nazwy: {bezNazwy}</Badge>
        <Badge color="gray" variant="light">wszystkich lig: {dane.ligi.length}</Badge>
      </Group>
      <Text size="sm" c="dimmed">
        Zapis gry nie zawiera nazw lig - tylko numery rozgrywek. Nazwę sprawdzisz w grze, otwierając jeden z klubów z listy.
        Liga bez nazwy dostaje najniższy mnożnik ({dane.mnoznik_nieznanej}). Mnożnik to siła ligi (Premier League ≈ 0,92,
        Ekstraklasa ≈ 0,80); dla nazw z podpowiedzi uzupełnia się sam. Zmiany zapisują się na stałe (folder dane/).
      </Text>
      <Table striped highlightOnHover>
        <Table.Thead>
          <Table.Tr>
            <Table.Th>Rozgrywki</Table.Th><Table.Th>Kluby</Table.Th><Table.Th>Przykładowe kluby</Table.Th>
            <Table.Th>Nazwa</Table.Th><Table.Th>Mnożnik</Table.Th><Table.Th />
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {dane.ligi.map((l) => (
            <WierszLigi key={`${l.klucz}-${l.nazwa ?? ''}-${l.mnoznik ?? ''}`} liga={l} dane={dane} />
          ))}
        </Table.Tbody>
      </Table>
    </Stack>
  );
}
