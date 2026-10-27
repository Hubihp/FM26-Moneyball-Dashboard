import { Alert, Loader, MultiSelect, Stack, Table, Text } from '@mantine/core';
import { useQuery } from '@tanstack/react-query';

import { api, type Wiersz } from '../api';
import Wykres from './Wykres';

type Props = {
  pozycja: string;
  wersja: number;
  wiersze: Wiersz[];
  wybrani: string[];
  setWybrani: (ids: string[]) => void;
};

// Kolor komorki: najlepszy percentyl w wierszu na zielono, najgorszy na czerwono (percentyl jest juz
// odwrocony dla statystyk "mniej = lepiej"). Bez kolorow przy jednym zawodniku albo samych remisach.
function koloryWiersza(percentyle: (number | null)[]): (string | undefined)[] {
  const znane = percentyle.filter((p): p is number => p !== null);
  if (znane.length < 2) return percentyle.map(() => undefined);
  const max = Math.max(...znane);
  const min = Math.min(...znane);
  if (max === min) return percentyle.map(() => undefined);
  return percentyle.map((p) => (p === null ? undefined
    : p === max ? 'rgba(64, 192, 87, 0.28)' : p === min ? 'rgba(250, 82, 82, 0.28)' : undefined));
}

export default function Porownanie({ pozycja, wersja, wiersze, wybrani, setWybrani }: Props) {
  // zawodnicy spoza puli pozycji (kandydaci, lista zyczen) sa szukani wsrod wszystkich zawodnikow
  const radar = useQuery({
    queryKey: ['radar', wersja, pozycja, wybrani],
    queryFn: () => api.radar(pozycja, wybrani, true),
    enabled: wybrani.length > 0,
  });
  const nazwa = (id: string) => String(radar.data?.seria.find((s) => s.id === id)?.pilkarz
    ?? wiersze.find((w) => w['ID'] === id)?.['Piłkarz'] ?? id);
  const opcje = [...wiersze.map((w) => String(w['ID'])), ...wybrani.filter((id) => !wiersze.some((w) => w['ID'] === id))];

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
        data={opcje.map((id) => ({ value: id, label: id }))}
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
          <Text size="sm" c="dimmed">Percentyl w pozycji {pozycja} (100 = najlepszy w puli). Przy stratach piłki liczy się odwrotnie: mniej strat daje wyższy percentyl. W tabeli zielony = najlepsza wartość wśród porównywanych, czerwony = najgorsza.</Text>
          <Table striped withTableBorder>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>Statystyka</Table.Th>
                {radar.data.seria.map((s) => <Table.Th key={s.id}>{nazwa(s.id)}</Table.Th>)}
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {radar.data.etykiety.map((e, i) => {
                const kolory = koloryWiersza(radar.data!.seria.map((s) => (s.wartosci[i] === null ? null : s.percentyle[i])));
                return (
                <Table.Tr key={e}>
                  <Table.Td>{e}</Table.Td>
                  {radar.data!.seria.map((s, j) => (
                    <Table.Td key={s.id} style={{ backgroundColor: kolory[j] }}>
                      {s.wartosci[i] === null ? '–' : s.wartosci[i]!.toFixed(2).replace('.', ',')}
                      <Text span size="xs" c="dimmed"> ({Math.round(s.percentyle[i])})</Text>
                    </Table.Td>
                  ))}
                </Table.Tr>
                );
              })}
            </Table.Tbody>
          </Table>
        </>
      )}
    </Stack>
  );
}
