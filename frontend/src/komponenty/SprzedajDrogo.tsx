import { Alert, Badge, Loader, Stack, Table, Text } from '@mantine/core';
import { useQuery } from '@tanstack/react-query';

import { api, type Wiersz, type ZapytanieKadry } from '../api';
import { eur, formatuj } from '../format';
import { kluczZawodnika } from '../pamiec';
import { PrzyciskGwiazdki } from './Gwiazdka';

type Props = {
  zapytanie: ZapytanieKadry;
  wersja: number;
  otworz: (pozycja: string, id: string, wiersz: Wiersz) => void;
  ulubione: Set<string>;
  przelaczUlubione: (wiersz: Wiersz, pozycja: string) => void;
};

function Kontrakt({ w }: { w: Wiersz }) {
  if (w['Wolny_agent']) return <Badge size="xs" color="teal" variant="light">wolny agent</Badge>;
  const lata = w['Lata_kontraktu'];
  return (
    <Text size="xs" c={typeof lata === 'number' && lata <= 1 ? 'orange' : 'dimmed'}>
      kontrakt do {formatuj(w['Wygasa_Data'], 'data')}
    </Text>
  );
}

// "Sprzedaj drogo": moi zawodnicy, za ktorych rynek placi wiecej, niz wynika z ich gry, i tanszy zastepca
export default function SprzedajDrogo({ zapytanie, wersja, otworz, ulubione, przelaczUlubione }: Props) {
  const dane = useQuery({
    queryKey: ['sprzedaj-drogo', wersja, zapytanie],
    queryFn: () => api.sprzedajDrogo(zapytanie),
  });
  if (dane.isLoading) return <Loader m="md" />;
  if (dane.error) return <Alert color="red">{(dane.error as Error).message}</Alert>;
  const d = dane.data;
  if (!d) return null;

  return (
    <Stack gap="sm">
      <Text size="sm" c="dimmed">
        Twoi zawodnicy, których cena rynkowa jest co najmniej {formatuj(d.prog, 'dec1')} raza wyższa niż wycena wg
        wyniku (tyle kosztuje typowy zawodnik grający tak samo), oraz najtańszy zastępca: spoza twojego klubu, spełniający
        filtry panelu, z SCORE niższym najwyżej o {d.tolerancja} i podobnym stylem gry. Zysk = cena twojego zawodnika
        − cena zastępcy. Ceny to wartości z gry; klub sprzedający zwykle żąda więcej, a kupujący płaci mniej.
      </Text>
      <Alert color="gray" variant="light" p="xs">
        <Text size="xs">
          Gwiazdy wychodzą tu często, bo ich cena zawiera reputację, której model nie widzi - i właśnie za nią rynek
          przepłaca. U zawodników do 21 lat cena zawiera też potencjał, więc „przepłacenie” bywa pozorne (oznaczone U21).
          Zastępca z ceną bliską zeru zwykle kończy kontrakt - latem przejdzie za darmo.
        </Text>
      </Alert>
      {d.wymiany.length === 0 ? (
        <Alert color="gray">Brak opłacalnych wymian przy obecnych filtrach panelu.</Alert>
      ) : (
        <Table striped highlightOnHover fz="sm">
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Pozycja</Table.Th>
              <Table.Th>Twój zawodnik</Table.Th>
              <Table.Th ta="right">Cena / wycena</Table.Th>
              <Table.Th>Zastępca</Table.Th>
              <Table.Th ta="right">Cena zastępcy</Table.Th>
              <Table.Th ta="right">Zysk</Table.Th>
              <Table.Th />
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {d.wymiany.map((w) => {
              const m = w.moj;
              const z = w.zastepca;
              return (
                <Table.Tr key={`${w.pozycja}|${String(m['ID'])}`}>
                  <Table.Td>{w.pozycja}</Table.Td>
                  <Table.Td style={{ cursor: 'pointer' }} onClick={() => otworz(w.pozycja, String(m['ID']), m)}>
                    <Text size="sm" fw={600}>
                      {String(m['Piłkarz'])} {m['U21'] ? <Badge size="xs" color="violet" variant="light">U21</Badge> : null}
                    </Text>
                    <Text size="xs" c="dimmed">
                      {formatuj(m['Wiek'], 'int')} lat · SCORE {formatuj(m['SCORE'], 'score')}
                    </Text>
                  </Table.Td>
                  <Table.Td ta="right">
                    <Text size="sm">{eur(m['Wartość_Numeryczna'] as number)}</Text>
                    <Text size="xs" c="dimmed">
                      wycena {eur(m['Wycena wg wyniku'] as number)} · ×{formatuj(w.przeplacenie, 'dec1')}
                    </Text>
                  </Table.Td>
                  <Table.Td style={{ cursor: 'pointer' }} onClick={() => otworz(w.pozycja, String(z['ID']), z)}>
                    <Text size="sm" fw={600}>{String(z['Piłkarz'])}</Text>
                    <Text size="xs" c="dimmed">
                      {String(z['Klub'] ?? '')} · {formatuj(z['Wiek'], 'int')} lat · SCORE {formatuj(z['SCORE'], 'score')}
                      {' '}· styl {Math.round((z['Podobieństwo'] as number) * 100)}%
                    </Text>
                    <Kontrakt w={z} />
                  </Table.Td>
                  <Table.Td ta="right">{eur(w.cena_zastepcy)}</Table.Td>
                  <Table.Td ta="right"><Text size="sm" fw={700} c="teal">+{eur(w.zysk)}</Text></Table.Td>
                  <Table.Td>
                    <PrzyciskGwiazdki aktywna={ulubione.has(kluczZawodnika(z))}
                      przelacz={() => przelaczUlubione(z, w.pozycja)} />
                  </Table.Td>
                </Table.Tr>
              );
            })}
          </Table.Tbody>
        </Table>
      )}
    </Stack>
  );
}
