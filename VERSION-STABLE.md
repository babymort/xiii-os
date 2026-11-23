# OS XIII 1.0 — préparation de la version Stable

État au 23/11/2026 : **prête à être figée, non publiée**. Rien n'a été fusionné dans `main`, aucune étiquette `v*` n'existe.

## Comment les versions sont numérotées
- Le fichier `VERSION` (à la racine) donne le numéro : `1.0`.
- **Beta** (branche `beta`) : `1.0-beta.20261123.6e37ec5`, canal Beta dans Paramètres › Mises à jour.
- **Stable** (branche `main`) : `1.0`, canal Stable.
- **Version publiée** (étiquette `v1.0`) : ISO nommées `OS-XIII-1.0.iso` et `OS-XIII-Leger-1.0.iso`, page Releases de GitHub avec les notes de `NOUVEAUTES-1.0.md`.

## Ce que fait chaque étape (attention : les étapes 2 et 3 sont visibles)
1. **Geler la beta** : plus de nouvelles fonctions, seulement des corrections. Le test ZZ et les VM d'essai doivent passer.
2. **Passer en Stable** : `git push origin beta:main`. Les PC réglés sur le canal Stable reçoivent la 1.0 à leur prochaine vérification, et des ISO `1.0` sont construites (téléchargeables depuis GitHub Actions, pas publiques).
3. **Publier** : `git tag v1.0 && git push origin v1.0`. Les deux ISO sont mises en ligne sur la page Releases de GitHub. **C'est la seule étape publique.**

## À faire avant l'étape 2
- [ ] Essais sur du vrai matériel avec la dernière ISO beta (prévu par Matthieu une fois la version finale prête) :
  clé persistante, installation avec disque chiffré, pare-feu avec les appareils du plateau (NDI, ATEM, tally, téléphone),
  Stream Deck, deux cartes Wi-Fi, Orca, loupe, comptes Google / Outlook du Calendrier.
- [x] Édition légère sous 2 Go : 1,77 Go (construction du 23/11).

## À faire avant l'étape 3 (publication)
- [ ] Choisir la licence du code d'OS XIII et de la Suite XIII (voir `LICENCES.md`).
- [ ] Relire l'EULA du SDK NDI et l'intégrer à celle d'OS XIII ; vérifier `Processing.NDI.Lib.Licenses.txt` dans `/opt/ndi-xiii`.
- [ ] Mettre en ligne le site de présentation (`site/`) avec les liens de téléchargement de la page Releases.
- [ ] Relire `NOUVEAUTES-1.0.md`.

## Après la 1.0
- Les corrections vont sur `beta`, puis passent sur `main` (canal Stable) quand elles ont été essayées.
- Version suivante : passer `VERSION` à `1.1` sur `beta`.
