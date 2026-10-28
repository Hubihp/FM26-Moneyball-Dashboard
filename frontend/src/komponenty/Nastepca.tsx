import { Alert, Box, Group, Loader, Modal, Stack, Text } from '@mantine/core';
import { useQuery } from '@tanstack/react-query';

import { api, type Wiersz, type ZapytanieRankingu } from '../api';
import { eur } from '../format';
import TabelaRankingu from './TabelaRankingu';

type Props = {
  zawodnik: { pozycja: string; id: string; pilkarz: string } | null;
  zapytanie: ZapytanieRankingu | null; // ustawienia i filtry pozycji zawodnika
  wersja: number;
  mojKlubUid: number | null | undefined;
  zamknij: () => void;
  otworz: (pozycja: string, id: string, wiersz: Wiersz) => void;
};

// Opis filtrow pozycji, ktore zawezaja wyszukiwanie nastepcy
function opisFiltrow(z: ZapytanieRankingu) {
  const f = z.filtry;
  const czesci = [`min. ${f.min_minut} minut`];
  if (f.wiek) czesci.push(`wiek ${f.wiek[0]}–${f.wiek[1]}`);
  if (f.cena) czesci.push(`cena ${eur(f.cena[0] ?? 0)} – ${f.cena[1] === null ? 'bez limitu' : eur(f.cena[1])}`);
  if (f.pensja) czesci.push(`pensja ${eur(f.pensja[0] ?? 0)} – ${f.pensja[1] === null ? 'bez limitu' : eur(f.pensja[1])} tyg.`);
  if (f.kontrakt_mies) czesci.push(`kontrakt ≤ ${f.kontrakt_mies} mies.`);
  if (f.nogi.length) czesci.push(`noga: ${f.nogi.join(', ')}`);
  return czesci.join(' · ');
}

// "Znajdz nastepce": zawodnicy o najbardziej podobnym stylu gry (takze z innych pozycji)
export default function Nastepca({ zawodnik, zapytanie, wersja, mojKlubUid, zamknij, otworz }: Props) {
  const wynik = useQuery({
    queryKey: ['nastepca', wersja, zawodnik?.id, zapytanie],
    queryFn: () => api.nastepca({ ...zapytanie!, id: zawodnik!.id, n: 15 }),
    enabled: !!zawodnik && !!zapytanie,
  });

  return (
    <Modal opened={!!zawodnik} onClose={zamknij} size="90%" title={<b>Następca: {zawodnik?.pilkarz} ({zawodnik?.pozycja})</b>}>
      {zawodnik && zapytanie && (
        <Stack gap="xs">
          <Text size="sm" c="dimmed">
            Zawodnicy o najbardziej podobnym stylu gry, także z innych pozycji (fioletowy pasek). Podobieństwo =
            cosinus kąta między wektorami statystyk /90 pozycji {zawodnik.pozycja}, przeliczonych na odchylenia od średniej
            pozycji (z-score) ważone minutami i skurczone przy małej liczbie minut; 100% = identyczne proporcje
            statystyk. Liczy się styl, nie poziom - poziom pokazuje SCORE. Bez twojego klubu, z filtrami
            panelu: {opisFiltrow(zapytanie)}.
          </Text>
          {wynik.isLoading && <Loader size="sm" />}
          {wynik.error && <Alert color="red">{(wynik.error as Error).message}</Alert>}
          {wynik.data && (
            <>
              <Group gap="xs">
                <Text size="xs" c="dimmed">Spełnia filtry: {wynik.data.liczba_po_filtrach} zawodników; pokazano 15 najbardziej podobnych.</Text>
              </Group>
              <Box style={{ height: 520 }}>
                <TabelaRankingu kolumny={wynik.data.kolumny} wiersze={wynik.data.wiersze} mojKlubUid={mojKlubUid}
                  naWybor={(id, w) => w && otworz(zawodnik.pozycja, id, w)} />
              </Box>
            </>
          )}
        </Stack>
      )}
    </Modal>
  );
}
