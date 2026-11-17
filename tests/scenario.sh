#!/bin/bash
# Scénario de captures du bureau XIII (exécuté par labwc -s sur écran virtuel)
sleep 1
wlr-randr --output HEADLESS-1 --custom-mode 1600x900 >/out/randr.log 2>&1
xiii-shell > /out/shell.log 2>&1 &
sleep 6
notify-send -a "Pilotes XIII" -i preferences-system --action=ouvrir="Ouvrir Pilotes XIII" "Pilotes à installer" "Carte NVIDIA détectée : le pilote nvidia-driver améliorera les performances." >/dev/null &
sleep 0.5
notify-send -a "Capture" -i camera-photo "Capture enregistrée" "Copiée dans le presse-papiers · capture-2026-11-16.png" &
mousepad >/dev/null 2>&1 &
sleep 2
for i in 1 2 3 4 5 6 7 8 9; do grim /out/v-$i.png; xiii-ctl visite-suivant; sleep 1; done
sleep 1
grim /out/01-bureau.png
for p in demarrer son wifi bluetooth batterie centre alim volet widgets; do
  xiii-ctl $p; sleep 2; grim /out/p-$p.png; xiii-ctl fermer; sleep 0.6
done
xiii-ctl demarrer-toutes; sleep 2; grim /out/p-toutes.png; xiii-ctl fermer; sleep 0.5
xiii-parametres --page accueil >> /out/param.log 2>&1 &
sleep 6; grim /out/s-accueil.png
for pg in widgets xiii ecran son theme fond barre perso wifi bluetooth apropos alimentation stockage souris clavier xiii maj apps notifications heure; do
  xiii-parametres --page $pg >> /out/param.log 2>&1
  sleep 2.5; grim /out/s-$pg.png
done
pkill -f xiii.parametres; sleep 1
cp /bin/true "/tmp/VLC-3.0.21-win64-setup.exe"
xiii-windows "/tmp/VLC-3.0.21-win64-setup.exe" > /out/windows.log 2>&1 &
sleep 5; grim /out/w-preparer.png; pkill -f xiii.windows; sleep 1
xiii-windows > /out/windows2.log 2>&1 &
sleep 4; grim /out/w-accueil.png; pkill -f xiii.windows; sleep 1
xiii-bienvenue > /out/bienvenue.log 2>&1 &
sleep 4; grim /out/b-bienvenue.png; pkill -f xiii.bienvenue; sleep 1
python3 -c 'import sys; sys.path.insert(0,"/usr/lib/xiii"); from xiii import config; config.modifier(theme="clair", accent="#3d8bfd")'
sleep 3; xiii-ctl demarrer; sleep 2; grim /out/c-clair-menu.png; xiii-ctl fermer
xiii-ctl centre; sleep 2; grim /out/c-clair-centre.png; xiii-ctl fermer
python3 -c 'import sys; sys.path.insert(0,"/usr/lib/xiii"); from xiii import config; config.modifier(theme="sobre", accent="#f0b378", barre_alignement="gauche")'
sleep 3; xiii-ctl demarrer; sleep 2; grim /out/c-sobre-menu.png; xiii-ctl fermer
cp /root/.config/xiii/reglages.json /out/ 2>/dev/null
labwc --exit
# relance
