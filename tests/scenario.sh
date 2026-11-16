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
sleep 3
grim /out/01-bureau.png
for p in demarrer son wifi bluetooth batterie centre alim volet meteo; do
  xiii-ctl $p; sleep 2; grim /out/p-$p.png; xiii-ctl fermer; sleep 0.6
done
xiii-ctl demarrer-toutes; sleep 2; grim /out/p-toutes.png; xiii-ctl fermer; sleep 0.5
xiii-ctl demarrer; sleep 1; wtype paramet 2>/dev/null; sleep 1; xiii-ctl fermer
xiii-parametres --page accueil >> /out/param.log 2>&1 &
sleep 6; grim /out/s-accueil.png
for pg in ecran son theme fond barre perso wifi bluetooth apropos alimentation stockage souris clavier xiii maj apps notifications heure; do
  xiii-parametres --page $pg >> /out/param.log 2>&1
  sleep 2.5; grim /out/s-$pg.png
done
cp /root/.config/xiii/reglages.json /out/ 2>/dev/null
labwc --exit
