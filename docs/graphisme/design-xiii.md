# Design XIII — règles graphiques d'OS XIII

Ce fichier est la référence de la direction artistique d'OS XIII et de la Suite XIII. Il est inspiré du « Liquid Glass » fourni par Matthieu Lamotte (formes, ombres, boutons, mouvements), en gardant l'identité XIII : **ambre et brun**, cuivre, Space Grotesk.
Le code qui l'applique : `config/includes.chroot/usr/lib/xiii/xiii/theme.py` (palettes, CSS) et `imitation.py` (thèmes Façon Windows 11 / macOS).

## 1. Couleurs

| Rôle | Sombre (signature) | Verre XIII | Clair |
|---|---|---|---|
| Fond | `#1e1e1e` | `#17120e` | `#eef0f2` |
| Panneau | `#1c1b1a` (verre .93) | `#1d1712` (verre .78) | `#faf9f7` |
| Carte | `#2a2928` | `#2a221b` | `#ffffff` |
| Texte | `#eee9e3` | `#f3ece4` | `#1d1b19` |
| Texte atténué | `#9b938a` | `#a89a8b` | `#6d675f` |
| Bordure | blanc 8 % | crème 14 % | noir 9 % |
| **Accent** | **Cuivre XIII `#f0b378`** | idem | idem |

- L'accent sert aux actions principales, à la sélection et aux repères ; jamais pour de grands aplats.
- Lueur « glassglow » : dégradé ambre `#f0b429` → orangé `#ff8a3d` mêlé à l'accent (45 %), pour la pilule d'action et la lueur des panneaux.
- Contraste : tout texte atténué est recalculé pour rester lisible (rapport ≥ 4,5 sur son fond).
- Couleurs d'état : réussite `#81c784`, alerte `#ffd43b`, erreur et enregistrement `#e5534b`, tally programme rouge, preview vert `#3fb950`.

## 2. Typographie

- **Titres** : Space Grotesk (600–700), interlettrage légèrement négatif (−0,3 à −0,5 px). Page 26 px, panneau 18 px, héros 22 px.
- **Texte** : IBM Plex Sans 13–14 px ; petit texte 11,5 px ; timecode et chiffres en IBM Plex Mono.
- Thèmes imités : Selawik (Windows 11), Inter (macOS).

## 3. Formes

- Arrondis : panneaux et cartes **14 px** (Verre XIII 16 px), contrôles 7–8 px, pilules 999 px.
- Bordure fine (1 px) toujours présente sur le verre : elle tient la forme quand le fond est chargé.
- Icônes : Lucide au trait, épaisseur 1,75, teintées (accent, texte ou atténué). 16 px dans les barres, 18–20 px dans les panneaux.

## 4. Verre et ombres (inspiré du Liquid Glass)

- Panneaux translucides : opacité .93 (sombre), .78 (Verre XIII).
- Reflet : `inset 0 1px 0` blanc 10 % en haut des surfaces ; reflet irisé très léger (ambre 12 % → lavande 5 % → bleu 4 %).
- Ombres douces et larges : `0 12px 32–40px` noir 38–50 %.
- Flou : option **« Flou derrière la barre et les panneaux (effet Mica) »** — le fond d'écran flouté transparaît, teinté de la couleur du panneau. Désactivée par défaut, sans effet en mode léger. Le flou en direct des fenêtres n'existe pas avec labwc.

## 5. Boutons

- **Action principale** : pilule pleine (dégradé glassglow), texte sombre en gras, lueur de l'accent.
- **Secondaire (fantôme)** : contour accent 55 %, fond transparent, survol accent 12 %.
- **Plat** : sans fond, survol 6 % de blanc (ou de noir en clair).
- Verre XIII : les boutons « respirent » au survol (`scale(1.03)`, 220 ms, `cubic-bezier(.2,.8,.2,1)`), s'enfoncent de 1 px au clic.

## 6. Mouvements

- Ouverture des panneaux : fondu + glissé de 8 px, 140–190 ms, `cubic-bezier(.2,.8,.2,1)`.
- Indicateur de la barre des tâches : 3 px, s'allonge de 6 à 16 px sur l'appli active (220 ms, léger rebond).
- Dock : grossissement 1,32 au survol, rebond au lancement (900 ms).
- Tout s'éteint avec « Animations » désactivé ou « Réduire les animations » (Accessibilité).

## 7. Composants

- **Barre des tâches** : 48 px (petite 40, grande 58) ; formes classique, flottante, dock, île dynamique ; à gauche la météo, au centre Démarrer + applis, à droite notifications, heure, bande « Afficher le bureau ».
- **Barre du haut** : 32 px ; accueil, logo, projet, modes au centre, outils et état à droite.
- **Cartes** : fond carte, bordure fine, 10–12 px de marge intérieure.
- **Réglages** (Paramètres) : une ligne par réglage, icône à gauche, titre + sous-titre atténué, contrôle à droite.

## 8. À ne pas faire

- Pas de logos, polices ou fonds d'écran d'autres marques (Apple, Microsoft…) : uniquement des équivalents libres.
- Pas de couleur vive en grand aplat (l'accent reste un repère).
- Pas d'animation qui dure plus de 300 ms dans l'interface (hors démarrage).
