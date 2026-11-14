// Kontrola jakosci odczytu zapisu (panel "Zrodlo danych"): czy gole i minuty zawodnikow zgadzaja sie z tabelami
// lig, testy pol statystyk. Biblioteka fmsave czyta niezweryfikowane wersje gry - tu widac, czy dane sa spojne.
import { Badge, Group, Loader, Stack, Table, Text } from '@mantine/core';
import { useQuery } from '@tanstack/react-query';

import { api } from '../api';

const KOLOR: Record<string, string> = {
  'ok': 'teal', 'uwaga': 'yellow', 'błąd': 'red', 'info': 'gray', 'mało danych': 'gray', 'brak odniesienia': 'gray',
};

export default function KontrolaOdczytu({ wersja }: { wersja: number }) {
  const k = useQuery({ queryKey: ['kontrola', wersja], queryFn: api.kontrola });
  if (k.isLoading) return <Loader size="sm" />;
  if (!k.data || (!k.data.ligi.length && !k.data.pola.length)) {
    return <Text size="sm" c="dimmed">{k.data?.blad ? `Kontrola nie powiodła się: ${k.data.blad}` : 'Kontrola jest dostępna po wczytaniu zapisu gry.'}</Text>;
  }
  const ocenione = k.data.ligi.filter((l) => ['ok', 'uwaga', 'błąd'].includes(l.status));
  const zgodne = ocenione.filter((l) => l.status === 'ok').length;
  const reszta = k.data.ligi.length - ocenione.length;
  return (
    <Stack gap="xs">
      <Text size="sm">
        Ligi zgodne z tabelami: <b>{zgodne} z {ocenione.length}</b>
        {reszta > 0 && <Text span c="dimmed"> · bez oceny: {reszta} (mało klubów do porównania albo brak tabeli w zapisie)</Text>}
      </Text>
      <Table fz="sm" verticalSpacing={4}>
        <Table.Thead>
          <Table.Tr>
            <Table.Th>Liga</Table.Th><Table.Th>Stan</Table.Th>
            <Table.Th ta="right" title="Kluby, których minuty pasują do tabel ligi">Kluby</Table.Th>
            <Table.Th ta="right" title="Kluby, w których suma goli zawodników nie zgadza się z tabelą">Gole niezgodne</Table.Th>
            <Table.Th ta="right" title="Gole / xG w całej lidze (typowo 0,9-1,2)">Gole / xG</Table.Th>
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {ocenione.map((l) => (
            <Table.Tr key={l.competition_id}>
              <Table.Td>{l.nazwa}</Table.Td>
              <Table.Td><Badge size="sm" variant="light" color={KOLOR[l.status]}>{l.status}</Badge></Table.Td>
              <Table.Td ta="right">{l.kluby}</Table.Td>
              <Table.Td ta="right" c={l.gole_niezgodne ? 'orange' : undefined}>{l.gole_niezgodne}</Table.Td>
              <Table.Td ta="right">{l.gole_xg?.toFixed(2).replace('.', ',') ?? '–'}</Table.Td>
            </Table.Tr>
          ))}
        </Table.Tbody>
      </Table>
      {k.data.pola.map((p) => (
        <Group key={p.nazwa} gap="xs" wrap="nowrap" align="flex-start">
          <Badge size="sm" variant="light" color={KOLOR[p.status] ?? 'gray'} style={{ flexShrink: 0 }}>{p.status}</Badge>
          <Text size="sm"><b>{p.nazwa}:</b> {p.opis}</Text>
        </Group>
      ))}
      <Text size="xs" c="dimmed">
        Gole zawodników są porównywane z tabelą ligi (różnica to głównie gole samobójcze rywali), tylko dla klubów,
        których minuty pasują do liczby meczów w tabelach. Niezgodności wskazują pola, które biblioteka fmsave mogła
        odczytać błędnie w tej wersji gry.
      </Text>
    </Stack>
  );
}
