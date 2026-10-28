import { Alert, Badge, Button, Card, Group, Loader, MultiSelect, NumberInput, SimpleGrid, Stack, Table, Text, Title } from '@mantine/core';
import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';

import { api, type PozycjaKadry, type Wiersz, type WyborOptymalizatora, type ZapytanieKadry } from '../api';
import { eur, formatuj } from '../format';
import { kluczZawodnika, usePamiec } from '../pamiec';
import { PrzyciskGwiazdki } from './Gwiazdka';

type Props = {
  zapytanie: ZapytanieKadry;
  wersja: number;
  pozycje: string[];
  kadra: PozycjaKadry[];
  otworz: (pozycja: string, id: string, wiersz: Wiersz) => void;
  ulubione: Set<string>;
  przelaczUlubione: (wiersz: Wiersz, pozycja: string) => void;
};

type Parametry = { budzet: number; budzet_plac: number; pozycje: string[] };

// Domyslnie: 3 pozycje, na ktorych moj najlepszy zawodnik jest najslabszy (brak zawodnika = najslabsza)
const najslabsze = (kadra: PozycjaKadry[]) =>
  [...kadra].sort((a, b) => (a.najlepszy ?? -1) - (b.najlepszy ?? -1)).slice(0, 3).map((p) => p.pozycja);

function Kontrakt({ w }: { w: Wiersz }) {
  if (w['Wolny_agent']) return <Badge size="xs" color="teal" variant="light">wolny agent</Badge>;
  const lata = w['Lata_kontraktu'];
  return <Text size="xs" c={typeof lata === 'number' && lata <= 1 ? 'orange' : 'dimmed'}>do {formatuj(w['Wygasa_Data'], 'data')}</Text>;
}

// Optymalizator budzetu: najwiekszy przyrost SCORE za dany budzet (zestaw, nie jedna gwiazda)
export default function Optymalizator({ zapytanie, wersja, pozycje, kadra, otworz, ulubione, przelaczUlubione }: Props) {
  const [budzetMln, setBudzetMln] = usePamiec('fm-opt-budzet', 50);
  const [placTys, setPlacTys] = usePamiec('fm-opt-plac', 200);
  const [wybrane, setWybrane] = usePamiec<string[] | null>('fm-opt-pozycje', null);
  const pozycjeWybrane = wybrane ?? najslabsze(kadra);
  const [parametry, setParametry] = useState<Parametry | null>(null);

  const wynik = useQuery({
    queryKey: ['optymalizator', wersja, zapytanie, parametry],
    queryFn: () => api.optymalizator({ ...zapytanie, ...parametry! }),
    enabled: !!parametry,
  });
  const policz = () => setParametry({ budzet: budzetMln * 1e6, budzet_plac: placTys * 1e3, pozycje: pozycjeWybrane });
  const d = wynik.data;

  const wiersz = (w: WyborOptymalizatora) => {
    const z = w.zawodnik;
    return (
      <Table.Tr key={w.pozycja}>
        <Table.Td>{w.pozycja}</Table.Td>
        <Table.Td style={{ cursor: 'pointer' }} onClick={() => otworz(w.pozycja, String(z['ID']), z)}>
          <Text size="sm" fw={600}>{String(z['Piłkarz'])}</Text>
          <Text size="xs" c="dimmed">{String(z['Klub'] ?? '')} · {String(z['Liga'] ?? '')}</Text>
        </Table.Td>
        <Table.Td ta="right">{formatuj(z['Wiek'], 'int')}</Table.Td>
        <Table.Td ta="right">
          <Text size="sm" fw={700}>{formatuj(z['SCORE'], 'score')}</Text>
          <Text size="xs" c="dimmed">{w.poziom_zastepczy ? 'poziom zast.' : 'twój'} {formatuj(w.moj_score, 'score')}</Text>
        </Table.Td>
        <Table.Td ta="right"><Text size="sm" fw={700} c="teal">+{formatuj(w.zysk, 'dec1')}</Text></Table.Td>
        <Table.Td ta="right">{eur(w.cena)}<Kontrakt w={z} /></Table.Td>
        <Table.Td ta="right">{eur(w.pensja)}</Table.Td>
        <Table.Td>
          <PrzyciskGwiazdki aktywna={ulubione.has(kluczZawodnika(z))} przelacz={() => przelaczUlubione(z, w.pozycja)} />
        </Table.Td>
      </Table.Tr>
    );
  };

  return (
    <Stack gap="sm">
      <Text size="sm" c="dimmed">
        Najlepszy zestaw wzmocnień za podany budżet, a nie jedna gwiazda. Zysk zawodnika = o ile jego SCORE przewyższa
        twojego najlepszego na tej pozycji (gdy go nie masz - „poziom zastępczy”, 25. percentyl pozycji). Na każdej pozycji
        co najwyżej jeden nowy zawodnik; liczą się filtry panelu (wiek, minuty, ligi, kontrakt, pensja). Cena to wartość
        z gry (wolny agent: 0 €), pensja - obecna tygodniowa; klub zwykle żąda więcej, a zawodnik może chcieć podwyżki.
      </Text>
      <Group align="end" gap="sm">
        <NumberInput label="Budżet transferowy (mln €)" w={190} min={0} step={5} decimalScale={1} value={budzetMln}
          onChange={(v) => setBudzetMln(Number(v) || 0)} />
        <NumberInput label="Pensje nowych (tys. € / tydz.)" w={210} min={0} step={10} value={placTys}
          onChange={(v) => setPlacTys(Number(v) || 0)} />
        <MultiSelect label="Pozycje do wzmocnienia" w={420} data={pozycje} value={pozycjeWybrane}
          onChange={setWybrane} maxValues={8} placeholder="Wybierz pozycje" />
        <Button onClick={policz} disabled={!pozycjeWybrane.length} loading={wynik.isFetching}>Policz</Button>
      </Group>
      {wynik.error && <Alert color="red">{(wynik.error as Error).message}</Alert>}
      {wynik.isLoading && <Loader size="sm" />}
      {d && (
        <>
          <SimpleGrid cols={{ base: 1, md: 2 }}>
            <Card withBorder padding="sm">
              <Title order={5}>Zestaw: +{formatuj(d.zysk, 'dec1')} SCORE</Title>
              <Text size="sm">
                Wydane {eur(d.wydane)} (zostaje {eur(d.zostalo)}), pensje {eur(d.pensje)} / tydz.
                {d.wydane > 0 ? ` · ${formatuj(d.zysk / (d.wydane / 1e6), 'dec1')} pkt na 1 mln €` : ''}
              </Text>
            </Card>
            <Card withBorder padding="sm">
              <Title order={5} c="dimmed">
                Jedna gwiazda: {d.jedna_gwiazda ? `+${formatuj(d.jedna_gwiazda.zysk, 'dec1')} SCORE` : 'brak'}
              </Title>
              {d.jedna_gwiazda && (
                <Text size="sm" c="dimmed">
                  {String(d.jedna_gwiazda.zawodnik['Piłkarz'])} ({d.jedna_gwiazda.pozycja}) za {eur(d.jedna_gwiazda.cena)} -
                  najlepszy pojedynczy zawodnik w tym budżecie. {d.zysk > d.jedna_gwiazda.zysk
                    ? `Zestaw daje o ${formatuj(d.zysk - d.jedna_gwiazda.zysk, 'dec1')} pkt więcej.` : ''}
                </Text>
              )}
            </Card>
          </SimpleGrid>
          {d.zestaw.length === 0 ? (
            <Alert color="gray">Nikt w tym budżecie nie jest lepszy od twoich zawodników na wybranych pozycjach.</Alert>
          ) : (
            <Table striped highlightOnHover fz="sm">
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>Pozycja</Table.Th><Table.Th>Zawodnik</Table.Th><Table.Th ta="right">Wiek</Table.Th>
                  <Table.Th ta="right">SCORE</Table.Th><Table.Th ta="right">Zysk</Table.Th>
                  <Table.Th ta="right">Cena</Table.Th><Table.Th ta="right">Pensja / tydz.</Table.Th><Table.Th />
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>{d.zestaw.map(wiersz)}</Table.Tbody>
            </Table>
          )}
          {d.pozycje_bez_wzmocnienia.length > 0 && (
            <Text size="xs" c="dimmed">Bez wzmocnienia (nie opłaca się w tym budżecie): {d.pozycje_bez_wzmocnienia.join(', ')}.</Text>
          )}
          <Text size="xs" c="dimmed">
            Przeanalizowano {d.liczba_kandydatow} kandydatów w {d.czas_ms} ms{d.optimum_pewne ? ' - wynik optymalny' : ''}.
          </Text>
        </>
      )}
    </Stack>
  );
}
