import { Badge, Button, Drawer, Group, Loader, SimpleGrid, Stack, Table, Text, Title, Tooltip } from '@mantine/core';
import { useQuery } from '@tanstack/react-query';

import { api, type Wiersz, type ZapytanieRankingu } from '../api';
import { eur, formatuj } from '../format';
import HistoriaZawodnika from './HistoriaZawodnika';
import NaTleMojego from './NaTleMojego';
import Wykres from './Wykres';

type Props = {
  id: string | null;
  wiersz: Wiersz | undefined;
  zapytanie: ZapytanieRankingu;
  wersja: number;
  mojKlubUid: number | null | undefined;
  mojKlub?: string | null;
  ulubiona: boolean;
  przelaczUlubiona: () => void;
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

export default function KartaZawodnika({ id, wiersz, zapytanie, wersja, mojKlubUid, mojKlub, ulubiona, przelaczUlubiona, zamknij,
  otworz, dodajDoPorownania }: Props) {
  const radar = useQuery({
    queryKey: ['radar', wersja, zapytanie.pozycja, id, zapytanie.filtry.kandydaci],
    queryFn: () => api.radar(zapytanie.pozycja, [id!], zapytanie.filtry.kandydaci),
    enabled: !!id,
  });
  const podobni = useQuery({
    queryKey: ['podobni', wersja, zapytanie, id],
    queryFn: () => api.podobni({ ...zapytanie, id: id!, n: 8 }),
    enabled: !!id,
  });

  const w = wiersz ?? {};
  const seria = radar.data?.seria[0];
  const moj = (x: Wiersz) => mojKlubUid !== null && mojKlubUid !== undefined && x['Klub_UID'] === mojKlubUid;
  const okazje = typeof w['Okazje'] === 'string' && w['Okazje'] ? (w['Okazje'] as string).split('; ') : [];

  return (
    <Drawer opened={!!id} onClose={zamknij} position="right" size="xl" title={<Title order={4}>{String(w['Piłkarz'] ?? id ?? '')}</Title>}>
      {id && (
        <Stack>
          <Group gap="xs">
            {moj(w) && <Badge color="yellow" variant="filled">Twój zawodnik</Badge>}
            <Badge variant="light">{String(w['Klub'] ?? '–')}</Badge>
            <Badge variant="light" color="gray">{String(w['Liga'] ?? '–')}</Badge>
            {w['Pozycja'] ? <Badge variant="outline">pozycje: {String(w['Pozycja'])}</Badge> : null}
            {w['Wypożyczony'] ? (
              <Badge color="orange">wypożyczony{w['Wypożyczenie_do'] ? ` do ${formatuj(w['Wypożyczenie_do'], 'data')}` : ''}</Badge>
            ) : null}
            {w['Pareto'] ? (
              <Tooltip label="Nikt w tabeli nie ma jednocześnie wyższego SCORE i niższego kosztu">
                <Badge color="teal" variant="outline">granica wynik/koszt</Badge>
              </Tooltip>
            ) : null}
            {okazje.map((o) => <Badge key={o} color="grape" variant="light">{o}</Badge>)}
            {w['Kandydat'] ? (
              <Tooltip label="Gra nominalnie na innej pozycji - wynik według kryteriów wybranej pozycji">
                <Badge color="grape" variant="outline">
                  kandydat do przekwalifikowania: z {String(w['Kandydat z pozycji'] ?? '?')}
                  {typeof w['Ocena na pozycji'] === 'number' ? ` · ocena na pozycji ${w['Ocena na pozycji']}/20` : ''}
                </Badge>
              </Tooltip>
            ) : null}
          </Group>
          <SimpleGrid cols={4}>
            <Pole etykieta="SCORE" wartosc={formatuj(w['SCORE'], 'score')} />
            <Pole etykieta="Percentyl" wartosc={formatuj(w['Percentyl'], 'pasek')} />
            <Pole etykieta="Wiek" wartosc={formatuj(w['Wiek'], 'int')} />
            <Pole etykieta="Wartość" wartosc={eur(w['Wartość_Numeryczna'] as number | null)} />
            <Pole etykieta="Płaca" wartosc={formatuj(w['Zarobki_Numeryczne'], 'eur_tyg')} />
            <Pole etykieta="Kontrakt do" wartosc={formatuj(w['Wygasa_Data'], 'data')} />
            <Pole etykieta="Minuty" wartosc={formatuj(w['Minuty'], 'int')} />
            <Pole etykieta="Noga" wartosc={String(w['Preferowana noga'] ?? '–')} />
            <Pole etykieta="Koszt (cena + 3 lata pensji)" wartosc={eur(w['Koszt'] as number | null)} />
            <Pole etykieta={w['Wycena_ograniczona'] ? 'Wycena wg wyniku (ograniczona)' : 'Wycena wg wyniku'}
              wartosc={eur(w['Wycena wg wyniku'] as number | null)} />
            <Pole etykieta={w['U21'] ? 'Niedowartościowanie (U21)' : 'Niedowartościowanie'}
              wartosc={formatuj(w['Niedowartościowanie'], 'mnoznik')} />
            {w['Kontuzje_2_lata'] !== undefined ? (
              <Pole etykieta="Kontuzje (2 lata)" wartosc={formatuj(w['Kontuzje_2_lata'], 'int')} />
            ) : null}
          </SimpleGrid>
          {w['Wycena_ograniczona'] ? (
            <Text size="xs" c="dimmed">
              Wycena ograniczona do zakresu danych modelu: zawodnik ma wynik lub wiek poza zakresem zawodników tej
              pozycji, na których model się uczy, więc wycena nie jest ekstrapolowana i nie przekracza najwyższej ceny w puli.
            </Text>
          ) : null}
          {w['U21'] ? (
            <Text size="xs" c="dimmed">
              U21: cena młodego zawodnika zawiera potencjał, którego model wyceny nie widzi (zna tylko wynik, wiek i
              kontrakt), więc niedowartościowanie jest zaniżone - zawodnik może być tańszy, niż wynika z tej liczby.
            </Text>
          ) : null}

          {!moj(w) && <NaTleMojego id={id} zapytanie={zapytanie} wersja={wersja} mojKlub={mojKlub} />}


          <Group grow>
            <Button variant="light" onClick={() => dodajDoPorownania(id)}>Dodaj do porównania</Button>
            <Button variant={ulubiona ? 'filled' : 'light'} color="yellow" onClick={przelaczUlubiona} disabled={!wiersz}>
              {ulubiona ? 'Usuń z listy życzeń' : 'Dodaj do listy życzeń'}
            </Button>
          </Group>

          {wiersz && <HistoriaZawodnika id={id} wiersz={wiersz} zapytanie={zapytanie} wersja={wersja} />}

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
                  <Table.Tr key={String(p['ID'])} style={{ cursor: 'pointer' }} onClick={() => otworz(String(p['ID']))}
                    className={moj(p) ? 'wiersz-moj-klub' : undefined}>
                    <Table.Td fw={moj(p) ? 700 : undefined} c={moj(p) ? 'yellow' : undefined}>{String(p['Piłkarz'])}</Table.Td>
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
