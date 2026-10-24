import { Alert, Badge, Card, Group, Loader, Select, SimpleGrid, Stack, Table, Text, Title, Tooltip } from '@mantine/core';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';

import { api, type Faza, type FazaMiejsca, type GrupaRol, type MiejsceTaktyki } from '../api';
import { eur, formatuj } from '../format';

const NAZWA_FAZY: Record<Faza, string> = { IP: 'Przy piłce', OOP: 'Bez piłki' };

// Pozycja i rola jednej fazy miejsca. Zapis gry trzyma je jako numery - nieznane wybiera sie raz z listy,
// a wybor dotyczy kazdego miejsca (i kazdej taktyki) z tym samym numerem.
function Faza({ faza, dane, grupy, zapisz }: {
  faza: Faza; dane: FazaMiejsca; grupy: GrupaRol[];
  zapisz: (rodzaj: 'pozycja' | 'rola', klucz: string, wartosc: string | null) => void;
}) {
  const grupa = grupy.find((g) => g.grupa === dane.grupa);
  return (
    <Stack gap={4}>
      <Text size="xs" c="dimmed" fw={600}>{NAZWA_FAZY[faza]}</Text>
      <Select size="xs" placeholder={`Pozycja #${dane.klucz_pozycji}`} value={dane.grupa}
        error={!dane.grupa ? 'wybierz pozycję' : undefined}
        data={grupy.map((g) => ({ value: g.grupa, label: g.nazwa }))}
        onChange={(v) => zapisz('pozycja', dane.klucz_pozycji, v)} />
      {grupa && dane.klucz_roli && (
        <Select size="xs" placeholder={`Rola #${dane.bit_roli}`} value={dane.rola} clearable
          error={!dane.rola ? 'wybierz rolę' : undefined}
          data={grupa.role[faza]} onChange={(v) => zapisz('rola', dane.klucz_roli!, v)} />
      )}
    </Stack>
  );
}

function Miejsce({ m, grupy, zapisz }: {
  m: MiejsceTaktyki; grupy: GrupaRol[];
  zapisz: (rodzaj: 'pozycja' | 'rola', klucz: string, wartosc: string | null) => void;
}) {
  return (
    <Card withBorder padding="sm">
      <Stack gap="xs">
        <Text size="sm" fw={700}>Miejsce {m.nr + 1}</Text>
        <SimpleGrid cols={2} spacing="xs">
          <Faza faza="IP" dane={m.IP} grupy={grupy} zapisz={zapisz} />
          <Faza faza="OOP" dane={m.OOP} grupy={grupy} zapisz={zapisz} />
        </SimpleGrid>
        {m.zawodnicy.length > 0 ? (
          <Table striped withRowBorders={false} verticalSpacing={2} fz="xs">
            <Table.Thead>
              <Table.Tr>
                <Table.Th>Zawodnik</Table.Th>
                <Table.Th ta="right">IP</Table.Th>
                <Table.Th ta="right">OOP</Table.Th>
                <Table.Th ta="right">Razem</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {m.zawodnicy.map((z) => (
                <Table.Tr key={z.id}>
                  <Table.Td>
                    <Group gap={4} wrap="nowrap">
                      <Tooltip label={`${z.klub ?? '–'} · ${z.wiek ?? '–'} lat · ${z.pozycja ?? ''} · ${eur(z.cena)}`}>
                        <Text size="xs" fw={600} c={z.moj ? 'yellow' : undefined} truncate maw={150}>{z.pilkarz}</Text>
                      </Tooltip>
                      {z.moj
                        ? <Badge size="xs" color="yellow" variant="light">mój zespół</Badge>
                        : <Badge size="xs" color="gray" variant="light">transfer</Badge>}
                    </Group>
                  </Table.Td>
                  <Table.Td ta="right">{formatuj(z.ip, 'int')}</Table.Td>
                  <Table.Td ta="right">{formatuj(z.oop, 'int')}</Table.Td>
                  <Table.Td ta="right" fw={700}>{formatuj(z.razem, 'int')}</Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        ) : (
          <Text size="xs" c="dimmed">Ranking pojawi się po wybraniu pozycji i roli.</Text>
        )}
      </Stack>
    </Card>
  );
}

// Role z taktyki uzywanej w zapisie: 11 miejsc z rolami IP i OOP oraz ranking najlepiej dopasowanych zawodnikow
export default function MojaTaktyka({ wersja }: { wersja: number }) {
  const klient = useQueryClient();
  const [indeks, setIndeks] = useState<number | null>(null);
  const taktyka = useQuery({ queryKey: ['taktyka', wersja, indeks], queryFn: () => api.taktyka(indeks) });
  const [blad, setBlad] = useState<string | null>(null);

  if (taktyka.isLoading) return <Loader m="md" />;
  if (taktyka.error) return <Alert m="md" color="red">{(taktyka.error as Error).message}</Alert>;
  const dane = taktyka.data;
  if (!dane || dane.taktyki.length === 0) {
    return (
      <Alert m="md" color="gray">
        Taktyki są odczytywane z zapisu kariery (prowadzonego klubu). Dane demo i pliki CSV ich nie zawierają.
      </Alert>
    );
  }
  const zapisz = async (rodzaj: 'pozycja' | 'rola', klucz: string, wartosc: string | null) => {
    setBlad(null);
    try {
      await api.kalibruj(rodzaj, klucz, wartosc);
      await klient.invalidateQueries({ queryKey: ['taktyka'] });
    } catch (e) {
      setBlad((e as Error).message);
    }
  };
  const brakuje = dane.miejsca.some((m) => !m.IP.rola || !m.OOP.rola);

  return (
    <Stack p="md">
      <Group align="end">
        <Title order={4}>Moja taktyka</Title>
        <Select size="xs" w={260} value={String(dane.wybrana)} allowDeselect={false}
          data={dane.taktyki.map((t) => ({ value: String(t.indeks), label: t.nazwa }))}
          onChange={(v) => setIndeks(v === null ? null : Number(v))} />
      </Group>
      <Text size="sm" c="dimmed">
        Zapis gry nie mówi, która taktyka jest aktywna - wybierz ją z listy. Pozycje i role są w zapisie zapisane
        numerami, więc za pierwszym razem wybierz je tak jak w grze; wybór zapamiętuje się dla wszystkich miejsc i taktyk
        z tym samym numerem. Pod każdym miejscem: zawodnicy z najwyższą średnią dopasowania do ról IP i OOP (0-100),
        w tym zawsze najlepsi z twojego zespołu.
      </Text>
      {brakuje && <Alert color="yellow" variant="light">Niektóre miejsca nie mają jeszcze nazwanej pozycji lub roli.</Alert>}
      {blad && <Alert color="red">{blad}</Alert>}
      <SimpleGrid cols={{ base: 1, md: 2, xl: 3 }}>
        {dane.miejsca.map((m) => <Miejsce key={m.nr} m={m} grupy={dane.grupy} zapisz={zapisz} />)}
      </SimpleGrid>
    </Stack>
  );
}
