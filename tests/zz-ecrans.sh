#!/bin/bash
# Vérification ZZ à deux écrans (labwc headless, WLR_HEADLESS_OUTPUTS=2) : écran principal, barre de chaque écran,
# un mode par écran, applis de chaque barre. Les résultats s'ajoutent à /out/zz.txt.
sleep 1
for o in HEADLESS-1 HEADLESS-2; do wlr-randr --output $o --custom-mode 1280x720 >/dev/null 2>&1; done
wlr-randr --output HEADLESS-1 --pos 0,0 >/dev/null 2>&1; wlr-randr --output HEADLESS-2 --pos 1280,0 >/dev/null 2>&1
R=/out/zz.txt
echo "== Deux écrans (écran principal, barre et mode de chaque écran)" >> $R
wlr-randr | grep -E "^[A-Z]" | tr '\n' ' ' | sed 's/^/INFO      écrans : /' >> $R; echo >> $R
CFG='import sys; sys.path.insert(0,"/usr/lib/xiii"); from xiii import config; '
python3 -c "$CFG"'config.modifier(_histo=False, theme="sombre", mode_bureau="classique", modes_ecrans={}, ecran_principal=None, barre_tous_ecrans=True, barre_applis_ecrans="toutes", barre_forme="classique", barre_position="bas", barre_masquee=False)'
export GSK_RENDERER=cairo MALLOC_ARENA_MAX=2 XIII_VRAIS_ECRANS=1
xiii-shell > /out/shell-ecrans.log 2>&1 &
sleep 7
mousepad /root/Bureau/Notes.txt >/dev/null 2>&1 & sleep 2.5
grim -s 0.5 /out/ecrans-deux-barres.png
python3 -c "$CFG"'config.modifier(modes_ecrans={"HEADLESS-2": "multicam"}, mode_bureau="fiction")'; sleep 5
grim -s 0.5 /out/ecrans-fiction-multicam.png
python3 -c "$CFG"'config.modifier(modes_ecrans={"HEADLESS-2": "backup"}, mode_bureau="classique")'; sleep 4
grim -s 0.5 /out/ecrans-classique-backup.png
python3 -c "$CFG"'config.modifier(modes_ecrans={}, ecran_principal="HEADLESS-2", barre_applis_ecrans="ecran")'; sleep 4
grim -s 0.5 /out/ecrans-principal-2.png
gapplication action fr.xiii.Shell basculer "'demarrer'"; sleep 1.2; grim -s 0.5 /out/ecrans-menu-principal-2.png; gapplication action fr.xiii.Shell fermer; sleep 0.5
python3 -c "$CFG"'config.modifier(ecran_principal=None, barre_applis_ecrans="toutes", barre_tous_ecrans=False)'; sleep 3
grim -s 0.5 /out/ecrans-barre-principale-seule.png
xiii-parametres --page ecran > /out/p-ecrans.log 2>&1 & sleep 4; grim -s 0.5 /out/ecrans-parametres.png; pkill -f xiii.parametres
grep -q Traceback /out/p-ecrans.log && { echo "PLANTAGE  Paramètres › Écran (deux écrans)"; grep -A6 Traceback /out/p-ecrans.log | tail -7; } >> $R
pkill mousepad
pgrep -f "xiii.shell import" >/dev/null || echo "FERMÉE    xiii-shell à deux écrans" >> $R
grep -q Traceback /out/shell-ecrans.log && { echo "PLANTAGE  xiii-shell à deux écrans"; grep -A8 Traceback /out/shell-ecrans.log | tail -10; } >> $R || echo "OK        deux écrans : barres, modes par écran, écran principal, sans erreur" >> $R
grep -iE "protocol error|Error 71" /out/shell-ecrans.log | head -2 | sed 's/^/INFO      /' >> $R
python3 -c "$CFG"'config.modifier(_histo=False, barre_tous_ecrans=True)'
pkill -f "xiii.shell import"; sleep 1
labwc --exit 2>/dev/null || kill $LABWC_PID 2>/dev/null
