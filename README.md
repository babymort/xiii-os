# OS XIII

Un Linux léger et complet aux couleurs de la Suite XIII, pour redonner vie aux vieux ordinateurs.
Basé sur Debian 13 « Trixie ». Application développée par Matthieu Lamotte.

## Télécharger l'ISO
Onglet **Actions** → dernier « Build ISO OS XIII » réussi → section *Artifacts* → `OS-XIII-beta` (ou `OS-XIII-main`).
Le fichier est un zip contenant l'ISO et sa somme SHA256.

## Tester
- **VirtualBox** : nouvelle VM « Linux / Debian 64-bit », 2 Go de RAM, 20 Go de disque, démarrer sur l'ISO.
- **Vrai PC** : copier l'ISO sur une clé formatée avec Ventoy.

## Branches
- `beta` : versions de test, chaque push compile une ISO.
- `main` : version publique (on n'y met que ce qui a été validé).

## Construire en local (Debian/Ubuntu)
```
sudo apt install live-build
lb config && sudo lb build
```
