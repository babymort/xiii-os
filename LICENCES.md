# OS XIII — licences des composants

OS XIII est construit sur Debian 13 (trixie). Chaque paquet Debian garde sa propre licence, lisible dans
`/usr/share/doc/<paquet>/copyright` sur le système installé. Ce document liste ce que OS XIII ajoute par-dessus.

Application développée par Matthieu Lamotte.

## Code d'OS XIII
| Composant | Licence | Remarque |
|---|---|---|
| Applications XIII (`/usr/lib/xiii`, `/usr/local/bin/xiii-*`) | À choisir avant publication | Code de Matthieu Lamotte. Une licence libre (GPL-3.0 ou MIT) est conseillée pour une distribution. |
| Suite XIII hors ligne (`/usr/share/xiii/suite`) | À choisir avant publication | Copie du site public de la Suite XIII. |

## Polices
| Police | Licence | Usage |
|---|---|---|
| Space Grotesk (Florian Karsten) | SIL Open Font License 1.1 | Titres. Texte de licence : `/usr/share/fonts/truetype/xiii/SpaceGrotesk-OFL.txt` |
| IBM Plex Sans / Mono | SIL Open Font License 1.1 | Texte |
| Noto, DejaVu (paquets Debian) | OFL 1.1 / licence libre DejaVu | Repli, émojis |
| Selawik (Microsoft) | SIL Open Font License 1.1 | Thème « Façon Windows 11 » (remplaçant libre de Segoe UI, qui n'est pas redistribuable) |
| Inter (Rasmus Andersson) | SIL Open Font License 1.1 | Thème « Façon macOS » (San Francisco d'Apple n'est pas redistribuable) |

La police Astoria n'est plus utilisée (remplacée le 23/11/2026) : plus aucune question de droits sur les titres.

## Icônes et images
| Élément | Licence |
|---|---|
| Icônes Tabler (Paweł Kuna) et Phosphor (Phosphor Icons) | MIT — bibliothèque d'Icônes XIII (`/usr/share/xiii/icones`), avec Lucide (ISC) |
| Icônes et curseurs Fluent, WhiteSur (vinceliuice) | GPL 3 — thèmes « Façon Windows 11 » et « Façon macOS ». Aucun logo, fond d'écran ni icône d'Apple ou de Microsoft : fonds dessinés par OS XIII, bouton Démarrer = icône générique à quatre carreaux |
| Icônes Lucide | ISC |
| Papirus (paquet Debian) | GPL-3.0 |
| Animations de démarrage adi1090x | GPL-3.0 |
| Logos XIII, fonds d'écran XIII | Matthieu Lamotte |

## Logiciels tiers non libres ou à conditions
| Logiciel | Conditions à respecter | État |
|---|---|---|
| NDI® (bibliothèque de NDI XIII, `/opt/ndi-xiii`) | SDK NDI gratuit, redistribution des binaires permise si l'EULA d'OS XIII reprend les conditions de l'EULA du SDK NDI ; mention « NDI® is a registered trademark of Vizrt NDI AB » dans l'« À propos » ; fichier `Processing.NDI.Lib.Licenses.txt` livré à côté des binaires. | Mention ajoutée dans Paramètres › Système › À propos. **À faire avant publication :** relire l'EULA du SDK fourni avec NDI XIII, l'ajouter à l'EULA d'OS XIII, vérifier la présence du fichier de licences. |
| Microcodes et firmwares non libres (paquets Debian `non-free-firmware`) | Redistribuables selon Debian | Inclus comme sur l'image officielle Debian. |
| Claude Desktop, Claude Code (édition complète) | Conditions d'Anthropic | Installés depuis les dépôts officiels d'Anthropic. |
| Tailscale, LocalSend, Parsec, Steam (à la demande) | Conditions de chaque éditeur | Téléchargés depuis les sources officielles. |

## Avant toute publication publique
1. Choisir la licence du code d'OS XIII et de la Suite XIII.
2. Relire l'EULA du SDK NDI et l'intégrer à l'EULA d'OS XIII.
3. Vérifier qu'aucun logo ou nom de marque tiers n'apparaît dans les captures du site de présentation.
