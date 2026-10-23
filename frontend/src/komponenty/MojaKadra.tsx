import { Alert, Badge, Button, Card, Group, Loader, SimpleGrid, Stack, Table, Text, Title } from '@mantine/core';
import { useQuery } from '@tanstack/react-query';

import { api, type Wiersz } from '../api';
import { formatuj } from '../format';
import type { Ustawienia } from './PanelBoczny';

type Props = {
  wersja: number;
  wagi: Record<string, Record<string, number>>;
  ustawienia: Ustawienia;
  szukajNastepcy: (pozycja: string) => void;
  otworz: (pozycja: string, id: string, wiersz: Wiersz) => void;
};

const kolorLuki = (luka: number | null) => (luka === null ? 'gray' : luka > 10 ? 'red' : luka > 3 ? 'yellow' : 'teal');
const zeZnakiem = (x: number) => `${x > 0 ? '+' : ''}${Math.round(x)}`;

// Analiza kadry: na ktorych pozycjach najbardziej brakuje jakosci (luka do 80. percentyla puli)
export default function MojaKadra({ wersja, wagi, ustawienia, szukajNastepcy, otworz }: Props) {
  const kadra = useQuery({
    queryKey: ['kadra', wersja, wagi, ustawienia.k_baza, ustawienia.ignoruj_mnoznik],
    queryFn: () => api.mojaKadra({ wagi, ignoruj_mnoznik: ustawienia.ignoruj_mnoznik, k_baza: ustawienia.k_baza }),
  });

  if (kadra.isLoading) return <Loader m="md" />;
  if (kadra.error) return <Alert m="md" color="red">{(kadra.error as Error).message}</Alert>;
  if (!kadra.data) return null;

  return (
    <Stack p="md">
      <Text size="sm" c="dimmed">
        Pozycje posortowane od największej luki. Luka = SCORE zawodnika z 80. percentyla puli minus twój najlepszy na
        pozycji (dodatnia = brakuje ci jakości). Twoi zawodnicy są liczeni nawet poniżej progu minut, więc ich wynik może
        mieć niską wiarygodność.
      </Text>
      <SimpleGrid cols={{ base: 1, lg: 2 }}>
        {kadra.data.pozycje.map((p) => (
          <Card key={p.pozycja} withBorder padding="sm">
            <Group justify="space-between" mb="xs">
              <Title order={5}>{p.pozycja}</Title>
              {p.liczba === 0 ? (
                <Badge color="red" variant="light" size="lg">brak zawodnika</Badge>
              ) : (
                <Badge color={kolorLuki(p.luka)} variant="light" size="lg">
                  luka {p.luka === null ? '–' : zeZnakiem(p.luka)}
                </Badge>
              )}
            </Group>
            <Group gap="xs" mb="xs">
              <Badge variant="outline" color="gray">zawodników: {p.liczba}</Badge>
              <Badge variant="outline" color="gray">najlepszy: {formatuj(p.najlepszy, 'score')}</Badge>
              <Badge variant="outline" color="gray">cel: {formatuj(p.cel, 'score')}</Badge>
              <Badge variant="outline" color="gray">śr. wiek: {formatuj(p.sredni_wiek, 'dec1')}</Badge>
              {p.konczace_kontrakty > 0 && (
                <Badge variant="light" color="orange">kontrakt ≤ 12 mies.: {p.konczace_kontrakty}</Badge>
              )}
            </Group>
            {p.zawodnicy.length > 0 ? (
              <Table striped highlightOnHover fz="sm">
                <Table.Thead>
                  <Table.Tr>
                    <Table.Th>Piłkarz</Table.Th><Table.Th>Wiek</Table.Th><Table.Th>SCORE</Table.Th>
                    <Table.Th>Minuty</Table.Th><Table.Th>Kontrakt do</Table.Th>
                  </Table.Tr>
                </Table.Thead>
                <Table.Tbody>
                  {p.zawodnicy.map((z) => (
                    <Table.Tr key={String(z['ID'])} style={{ cursor: 'pointer' }} onClick={() => otworz(p.pozycja, String(z['ID']), z)}>
                      <Table.Td fw={600}>{String(z['Piłkarz'])}</Table.Td>
                      <Table.Td>{formatuj(z['Wiek'], 'int')}</Table.Td>
                      <Table.Td>{formatuj(z['SCORE'], 'score')}</Table.Td>
                      <Table.Td>{formatuj(z['Minuty'], 'int')}</Table.Td>
                      <Table.Td c={typeof z['Lata_kontraktu'] === 'number' && z['Lata_kontraktu'] <= 1 ? 'orange' : undefined}>
                        {formatuj(z['Wygasa_Data'], 'data')}
                      </Table.Td>
                    </Table.Tr>
                  ))}
                </Table.Tbody>
              </Table>
            ) : (
              <Text size="sm" c="dimmed">Brak zawodników na tej pozycji.</Text>
            )}
            <Button mt="sm" variant="light" size="xs" onClick={() => szukajNastepcy(p.pozycja)}>
              Szukaj wzmocnienia
            </Button>
          </Card>
        ))}
      </SimpleGrid>
    </Stack>
  );
}
