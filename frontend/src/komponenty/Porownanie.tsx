import { Alert, Loader, MultiSelect, Stack, Table, Text } from '@mantine/core';
import { useQuery } from '@tanstack/react-query';

import { api, type Wiersz } from '../api';
import Wykres from './Wykres';

type Props = { pozycja: string; wersja: number; wiersze: Wiersz[]; wybrani: string[]; setWybrani: (ids: string[]) => void };

export default function Porownanie({ pozycja, wersja, wiersze, wybrani, setWybrani }: Props) {
  const radar = useQuery({
    queryKey: ['radar', wersja, pozycja, wybrani],
    queryFn: () => api.radar(pozycja, wybrani),
    enabled: wybrani.length > 0,
  });
  const nazwa = (id: string) => String(wiersze.find((w) => w['ID'] === id)?.['Piłkarz'] ?? id);

  return (
    <Stack p="md">
      <MultiSelect
        label="Zawodnicy do porównania (maks. 4)"
        description="Zaznacz zawodników w tabeli rankingu albo wyszukaj tutaj."
        searchable
        clearable
        maxValues={4}
        limit={50}
        value={wybrani}
        onChange={setWybrani}
        data={wiersze.map((w) => ({ value: String(w['ID']), label: String(w['ID']) }))}
      />
      {wybrani.length === 0 && <Alert color="gray">Wybierz co najmniej jednego zawodnika.</Alert>}
      {radar.isLoading && <Loader />}
      {radar.data && radar.data.seria.length > 0 && (
        <>
          <Wykres
            wysokosc={520}
            opcje={{
              tooltip: {},
              legend: { bottom: 0, type: 'scroll' },
              radar: {
                indicator: radar.data.etykiety.map((e) => ({ name: e.replace('/90', '/90\n'), max: 100 })),
                radius: '65%',
                axisName: { fontSize: 11 },
              },
              series: [{
                type: 'radar',
                data: radar.data.seria.map((s) => ({ value: s.percentyle, name: nazwa(s.id), areaStyle: { opacity: 0.2 } })),
              }],
            }}
          />
          <Text size="sm" c="dimmed">Percentyl w pozycji (100 = najlepszy w puli). Statystyki „odwrócone”: mniej = lepiej.</Text>
          <Table striped withTableBorder>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>Statystyka</Table.Th>
                {radar.data.seria.map((s) => <Table.Th key={s.id}>{nazwa(s.id)}</Table.Th>)}
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {radar.data.etykiety.map((e, i) => (
                <Table.Tr key={e}>
                  <Table.Td>{e}</Table.Td>
                  {radar.data!.seria.map((s) => (
                    <Table.Td key={s.id}>
                      {s.wartosci[i] === null ? '–' : s.wartosci[i]!.toFixed(2).replace('.', ',')}
                      <Text span size="xs" c="dimmed"> ({Math.round(s.percentyle[i])})</Text>
                    </Table.Td>
                  ))}
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </>
      )}
    </Stack>
  );
}
