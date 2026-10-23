import { Text, Tooltip } from '@mantine/core';

// Miejsca na boisku (x, y w % od lewej i od gory) -> pula zawodnikow w aplikacji.
// Kilka miejsc moze nalezec do jednej puli (LO i PO = Boczny Obronca) - swieca wtedy razem.
const MIEJSCA: { skrot: string; nazwa: string; pozycja: string; x: number; y: number }[] = [
  { skrot: 'N', nazwa: 'Napastnik', pozycja: 'Napastnik', x: 50, y: 8 },
  { skrot: 'LS', nazwa: 'Lewy skrzydłowy', pozycja: 'Skrzydłowy', x: 16, y: 22 },
  { skrot: 'OP', nazwa: 'Ofensywny pomocnik', pozycja: 'Ofensywny Pomocnik', x: 50, y: 22 },
  { skrot: 'PS', nazwa: 'Prawy skrzydłowy', pozycja: 'Skrzydłowy', x: 84, y: 22 },
  { skrot: 'LP', nazwa: 'Lewy pomocnik', pozycja: 'Skrzydłowy', x: 12, y: 39 },
  { skrot: 'ŚP', nazwa: 'Środkowy pomocnik', pozycja: 'Środkowy Pomocnik', x: 50, y: 39 },
  { skrot: 'PP', nazwa: 'Prawy pomocnik', pozycja: 'Skrzydłowy', x: 88, y: 39 },
  { skrot: 'DP', nazwa: 'Defensywny pomocnik', pozycja: 'Defensywny Pomocnik', x: 50, y: 54 },
  { skrot: 'LWAH', nazwa: 'Lewy wahadłowy', pozycja: 'Wahadłowy', x: 12, y: 57 },
  { skrot: 'PWAH', nazwa: 'Prawy wahadłowy', pozycja: 'Wahadłowy', x: 88, y: 57 },
  { skrot: 'LO', nazwa: 'Lewy obrońca', pozycja: 'Boczny Obrońca', x: 21, y: 72 },
  { skrot: 'ŚO', nazwa: 'Środkowy obrońca', pozycja: 'Środkowy Obrońca', x: 50, y: 75 },
  { skrot: 'PO', nazwa: 'Prawy obrońca', pozycja: 'Boczny Obrońca', x: 79, y: 72 },
  { skrot: 'BR', nazwa: 'Bramkarz', pozycja: 'Bramkarz', x: 50, y: 91 },
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
            <Tooltip key={m.skrot} label={`${m.nazwa} · pula: ${m.pozycja} (${liczba(ile)})`} withArrow openDelay={250}>
              <button
                type="button"
                className={`boisko-miejsce${wybrana ? ' wybrane' : ''}${ile ? '' : ' puste'}`}
                style={{ left: `${m.x}%`, top: `${m.y}%` }}
                aria-label={`${m.nazwa} (${m.pozycja})`}
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
