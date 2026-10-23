import { Badge, Button, Drawer, Group, Loader, SimpleGrid, Stack, Table, Text, Title } from '@mantine/core';
import { useQuery } from '@tanstack/react-query';

import { api, type Wiersz, type ZapytanieRankingu } from '../api';
import { eur, formatuj } from '../format';
import Wykres from './Wykres';

type Props = {
  id: string | null;
  wiersz: Wiersz | undefined;
  zapytanie: ZapytanieRankingu;
  wersja: number;
  zamknij: () => void;
  otworz: (id: string) => void;
  dodajDoPorownania: (id: string) => void;
};

function Pole({ etykieta, wartosc }: { etykieta: string; wartosc: string }) {
  return (
    <Stack gap={0}>
      <Text size="xs" c="dimmed">{etykieta}</Text>
      <Text size="sm" fw={600}>{wartosc}</Text>
    </Stack>
  );
}

export default function KartaZawodnika({ id, wiersz, zapytanie, wersja, zamknij, otworz, dodajDoPorownania }: Props) {
  const radar = useQuery({
    queryKey: ['radar', wersja, zapytanie.pozycja, id],
    queryFn: () => api.radar(zapytanie.pozycja, [id!]),
    enabled: !!id,
  });
  const podobni = useQuery({
    queryKey: ['podobni', wersja, zapytanie, id],
    queryFn: () => api.podobni({ ...zapytanie, id: id!, n: 8 }),
    enabled: !!id,
  });

  const w = wiersz ?? {};
  const seria = radar.data?.seria[0];

  return (
    <Drawer opened={!!id} onClose={zamknij} position="right" size="xl" title={<Title order={4}>{String(w['Piłkarz'] ?? id ?? '')}</Title>}>
      {id && (
        <Stack>
          <Group gap="xs">
            <Badge variant="light">{String(w['Klub'] ?? '–')}</Badge>
            <Badge variant="light" color="gray">{String(w['Liga'] ?? '–')}</Badge>
            {w['Pozycja'] ? <Badge variant="outline">{String(w['Pozycja'])}</Badge> : null}
            {w['Wypożyczony'] ? <Badge color="orange">wypożyczony</Badge> : null}
          </Group>
          <SimpleGrid cols={4}>
            <Pole etykieta="SCORE" wartosc={formatuj(w['SCORE'], 'score')} />
            <Pole etykieta="Percentyl" wartosc={formatuj(w['Percentyl'], 'pasek')} />
            <Pole etykieta="Wiarygodność" wartosc={formatuj(w['Wiarygodność'], 'pasek')} />
            <Pole etykieta="Wiek" wartosc={formatuj(w['Wiek'], 'int')} />
            <Pole etykieta="Wartość" wartosc={eur(w['Wartość_Numeryczna'] as number | null)} />
            <Pole etykieta="Płaca" wartosc={formatuj(w['Zarobki_Numeryczne'], 'eur_tyg')} />
            <Pole etykieta="Kontrakt do" wartosc={formatuj(w['Wygasa_Data'], 'data')} />
            <Pole etykieta="Minuty" wartosc={formatuj(w['Minuty'], 'int')} />
            <Pole etykieta="Noga" wartosc={String(w['Preferowana noga'] ?? '–')} />
            {w['CA'] !== undefined ? <Pole etykieta="CA / PA" wartosc={`${w['CA'] ?? '–'} / ${w['PA'] ?? '–'}`} /> : null}
          </SimpleGrid>

          <Button variant="light" onClick={() => dodajDoPorownania(id)}>Dodaj do porównania</Button>

          <Title order={5}>Profil statystyk (percentyl w pozycji)</Title>
          {radar.isLoading && <Loader size="sm" />}
          {seria && radar.data && (
            <Wykres
              wysokosc={380}
              opcje={{
                tooltip: {},
                radar: {
                  indicator: radar.data.etykiety.map((e) => ({ name: e.replace('/90', '/90\n'), max: 100 })),
                  radius: '62%',
                  axisName: { fontSize: 10 },
                },
                series: [{
                  type: 'radar',
                  data: [{ value: seria.percentyle, name: String(w['Piłkarz'] ?? id), areaStyle: { opacity: 0.35 } }],
                }],
              }}
            />
          )}

          <Title order={5}>Podobni zawodnicy (spośród widocznych w tabeli)</Title>
          {podobni.isLoading && <Loader size="sm" />}
          {podobni.data && (
            <Table striped highlightOnHover>
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>Piłkarz</Table.Th><Table.Th>Klub</Table.Th><Table.Th>Wiek</Table.Th>
                  <Table.Th>SCORE</Table.Th><Table.Th>Wartość</Table.Th><Table.Th>Zgodność</Table.Th>
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {podobni.data.wiersze.map((p) => (
                  <Table.Tr key={String(p['ID'])} style={{ cursor: 'pointer' }} onClick={() => otworz(String(p['ID']))}>
                    <Table.Td>{String(p['Piłkarz'])}</Table.Td>
                    <Table.Td>{String(p['Klub'] ?? '–')}</Table.Td>
                    <Table.Td>{formatuj(p['Wiek'], 'int')}</Table.Td>
                    <Table.Td>{formatuj(p['SCORE'], 'score')}</Table.Td>
                    <Table.Td>{eur(p['Wartość_Numeryczna'] as number | null)}</Table.Td>
                    <Table.Td>{Math.round(Math.max(0, Number(p['Podobieństwo'])) * 100)}%</Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          )}
        </Stack>
      )}
    </Drawer>
  );
}
