# Logo

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="../public/logo/zaehlkarte-logo-weiss.svg">
  <img src="../public/logo/zaehlkarte-logo.svg" width="480" alt="Logo der Zählkarte mit Schriftzug">
</picture>

Oben der Tagesgang eines Werktags mit Morgen- und Abendspitze, unten der eines Wochenendtags,
dazwischen die Straße mit Fußgänger, Rad und Auto – stilisiert, keine Messwerte. In
`public/logo/`: Logo mit Schriftzug, Signet und kleines Zeichen, je auch in Weiß
(`-weiss.svg`); Favicons und App-Icon in `public/`. Unter etwa 64 px das kleine Zeichen
nehmen, wie Favicon und Kopfzeile der Karte: Dort sind Fußgänger, Rad und Auto nicht mehr zu
erkennen. Schrift: Inter Display SemiBold (SIL Open Font License 1.1), in Pfade umgewandelt.

| Datei | Wofür |
|---|---|
| `public/logo/zaehlkarte-logo.svg` | Logo mit Schriftzug |
| `public/logo/zaehlkarte-signet.svg` | Signet ohne Schrift, ab etwa 64 px |
| `public/logo/zaehlkarte-zeichen.svg` | kleines Zeichen, darunter (wie Favicon und Kopfzeile) |
| `…-weiss.svg` | dieselben in Weiß für dunkle Flächen |
| `public/favicon.svg`, `public/favicon.ico` | Favicon (16, 32, 48 px) |
| `public/apple-touch-icon.png`, `public/logo/icon-512.png` | App-Icon, Profilbild |

Die SVGs ohne `-weiss` färben sich mit `currentColor`: eingebettet nehmen sie die Textfarbe an,
als Bild sind sie schwarz.
