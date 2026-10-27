import { Text, Tooltip } from '@mantine/core';

// Miejsca na boisku (x, y w % od lewej i od gory) -> pozycja (pula zawodnikow) w aplikacji.
// Kazde miejsce to osobna pozycja: w puli sa tylko zawodnicy, ktorzy maja ja w kolumnie "Pozycje".
const MIEJSCA: { skrot: string; pozycja: string; x: number; y: number }[] = [
  { skrot: 'N', pozycja: 'Napastnik', x: 50, y: 9 },
  { skrot: 'LS', pozycja: 'Lewy Skrzydłowy', x: 14, y: 22 },
  { skrot: 'OP', pozycja: 'Ofensywny Pomocnik', x: 50, y: 24 },
  { skrot: 'PS', pozycja: 'Prawy Skrzydłowy', x: 86, y: 22 },
  { skrot: 'LP', pozycja: 'Lewy Pomocnik', x: 12, y: 39 },
  { skrot: 'ŚP', pozycja: 'Środkowy Pomocnik', x: 50, y: 40 },
  { skrot: 'PP', pozycja: 'Prawy Pomocnik', x: 88, y: 39 },
  { skrot: 'LWAH', pozycja: 'Lewy Wahadłowy', x: 11, y: 56 },
  { skrot: 'DP', pozycja: 'Defensywny Pomocnik', x: 50, y: 56 },
  { skrot: 'PWAH', pozycja: 'Prawy Wahadłowy', x: 89, y: 56 },
  { skrot: 'LO', pozycja: 'Lewy Obrońca', x: 16, y: 73 },
  { skrot: 'ŚO', pozycja: 'Środkowy Obrońca', x: 50, y: 74 },
  { skrot: 'PO', pozycja: 'Prawy Obrońca', x: 84, y: 73 },
  { skrot: 'BR', pozycja: 'Bramkarz', x: 50, y: 91 },
];

type Props = { pozycja: string; liczby: Record<string, number>; naWybor: (pozycja: string) => void };

const liczba = (n: number) => n.toLocaleString('pl-PL');

// Wybor pozycji kliknieciem w miejsce na boisku
export default function Boisko({ pozycja, liczby, naWybor }: Props) {
  return (
    <div>
      <Text size="sm" fw={500} mb={6}>Pozycja</Text>
      <div className="boisko" role="group" aria-label="Wybór pozycji">
        <div className="boisko-linia-srodkowa" />
        <div className="boisko-kolo" />
        <div className="boisko-pole boisko-pole-gora" />
        <div className="boisko-pole boisko-pole-dol" />
        {MIEJSCA.map((m) => {
          const ile = liczby[m.pozycja] ?? 0;
          const wybrana = m.pozycja === pozycja;
          return (
            <Tooltip key={m.pozycja} label={`${m.pozycja} (${liczba(ile)})`} withArrow openDelay={250}>
              <button
                type="button"
                className={`boisko-miejsce${wybrana ? ' wybrane' : ''}${ile ? '' : ' puste'}${m.skrot.length > 3 ? ' dlugi' : ''}`}
                style={{ left: `${m.x}%`, top: `${m.y}%` }}
                aria-label={m.pozycja}
                aria-pressed={wybrana}
                disabled={!ile && !wybrana}
                onClick={() => naWybor(m.pozycja)}
              >
                {m.skrot}
              </button>
            </Tooltip>
          );
        })}
      </div>
      <Text size="sm" mt={6} ta="center">
        <Text span fw={700} c="teal.4">{pozycja}</Text>
        <Text span c="dimmed"> · {liczba(liczby[pozycja] ?? 0)} zawodników</Text>
      </Text>
    </div>
  );
}
