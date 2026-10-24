import { Badge, Button, Drawer, Group, Loader, Progress, SimpleGrid, Stack, Table, Text, Title, Tooltip } from '@mantine/core';
import { useQuery } from '@tanstack/react-query';

import { api, type Wiersz, type ZapytanieRankingu } from '../api';
import { eur, formatuj } from '../format';
import Wykres from './Wykres';

type Props = {
  id: string | null;
  wiersz: Wiersz | undefined;
  zapytanie: ZapytanieRankingu;
  wersja: number;
  mojKlubUid: number | null | undefined;
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

// Pelne listy rol z kolumn 'Rola|IP|nazwa' wiersza, posortowane malejaco
function listaRol(w: Wiersz, faza: 'IP' | 'OOP') {
  const prefiks = `Rola|${faza}|`;
  return Object.entries(w)
    .filter(([k, v]) => k.startsWith(prefiks) && typeof v === 'number')
    .map(([k, v]) => ({ nazwa: k.slice(prefiks.length), wynik: v as number }))
    .sort((a, b) => b.wynik - a.wynik);
}

function ListaRol({ tytul, role }: { tytul: string; role: { nazwa: string; wynik: number }[] }) {
  return (
    <Stack gap={4}>
      <Text size="sm" fw={600}>{tytul}</Text>
      {role.map((r, i) => (
        <div key={r.nazwa}>
          <Group justify="space-between" gap={4}>
            <Text size="xs" fw={i === 0 ? 700 : 400}>{r.nazwa}</Text>
            <Text size="xs" fw={600}>{formatuj(r.wynik, 'int')}</Text>
          </Group>
          <Progress value={r.wynik} size="sm" color={i === 0 ? 'teal' : 'gray'} />
        </div>
      ))}
    </Stack>
  );
}

const UKRYTE = ['Regularność', 'Ważne mecze', 'Podatność na kontuzje', 'Determinacja', 'Profesjonalizm', 'Ambicja',
  'Adaptacja'];

export default function KartaZawodnika({ id, wiersz, zapytanie, wersja, mojKlubUid, ulubiona, przelaczUlubiona, zamknij,
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
  const ukryte = UKRYTE.filter((k) => typeof w[k] === 'number');
  const rolaIP = listaRol(w, 'IP');
  const rolaOOP = listaRol(w, 'OOP');

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
            <Pole etykieta="Wiarygodność" wartosc={formatuj(w['Wiarygodność'], 'pasek')} />
            <Pole etykieta="Wiek" wartosc={formatuj(w['Wiek'], 'int')} />
            <Pole etykieta="Wartość" wartosc={eur(w['Wartość_Numeryczna'] as number | null)} />
            <Pole etykieta="Płaca" wartosc={formatuj(w['Zarobki_Numeryczne'], 'eur_tyg')} />
            <Pole etykieta="Kontrakt do" wartosc={formatuj(w['Wygasa_Data'], 'data')} />
            <Pole etykieta="Minuty" wartosc={formatuj(w['Minuty'], 'int')} />
            <Pole etykieta="Noga" wartosc={String(w['Preferowana noga'] ?? '–')} />
            {w['CA'] !== undefined ? <Pole etykieta="CA / PA" wartosc={`${w['CA'] ?? '–'} / ${w['PA'] ?? '–'}`} /> : null}
            <Pole etykieta="Koszt (cena + 3 lata pensji)" wartosc={eur(w['Koszt'] as number | null)} />
            <Pole etykieta="Wycena wg wyniku" wartosc={eur(w['Wycena wg wyniku'] as number | null)} />
            <Pole etykieta="Niedowartościowanie" wartosc={formatuj(w['Niedowartościowanie'], 'mnoznik')} />
            {w['Wynik ponad CA'] !== undefined ? (
              <Pole etykieta="Wynik ponad CA" wartosc={formatuj(w['Wynik ponad CA'], 'dec1')} />
            ) : null}
            {w['Ryzyko'] !== undefined ? <Pole etykieta="Ryzyko (0-100)" wartosc={formatuj(w['Ryzyko'], 'int')} /> : null}
            {w['Kontuzje_2_lata'] !== undefined ? (
              <Pole etykieta="Kontuzje (2 lata)" wartosc={formatuj(w['Kontuzje_2_lata'], 'int')} />
            ) : null}
          </SimpleGrid>

          {ukryte.length > 0 && (
            <>
              <Title order={6}>Atrybuty ukryte i osobowość (1-20)</Title>
              <SimpleGrid cols={4}>
                {ukryte.map((k) => <Pole key={k} etykieta={k} wartosc={formatuj(w[k], 'int')} />)}
              </SimpleGrid>
            </>
          )}

          {rolaIP.length > 0 && (
            <>
              <Tooltip multiline w={340} withArrow
                label="Dopasowanie 0-100: atrybuty kluczowe roli mają wagę 2, dodatkowe 1; przy rolach ze statystykami do 25% wyniku daje percentyl statystyk meczowych w pozycji (pełny udział od 900 minut).">
                <Title order={6}>Dopasowanie do ról FM26 (0-100)</Title>
              </Tooltip>
              <SimpleGrid cols={2}>
                <ListaRol tytul="Przy piłce (IP)" role={rolaIP} />
                <ListaRol tytul="Bez piłki (OOP)" role={rolaOOP} />
              </SimpleGrid>
            </>
          )}

          <Group grow>
            <Button variant="light" onClick={() => dodajDoPorownania(id)}>Dodaj do porównania</Button>
            <Button variant={ulubiona ? 'filled' : 'light'} color="yellow" onClick={przelaczUlubiona} disabled={!wiersz}>
              {ulubiona ? 'Usuń z listy życzeń' : 'Dodaj do listy życzeń'}
            </Button>
          </Group>

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
