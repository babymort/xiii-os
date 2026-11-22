#!/bin/bash
# Vérification de fin de saison (ZZ) : chaque application, chaque page des Paramètres et chaque thème, captures + plantages relevés.
# Exécuté par labwc -s sur écran virtuel ; résultat dans /out (branche « zz »).
sleep 1
wlr-randr --output HEADLESS-1 --custom-mode 1600x900 >/dev/null 2>&1
mkdir -p /root/.config /root/Bureau /root/XIII/Concert-Dome/03_Documents; echo "XDG_DESKTOP_DIR=\"\$HOME/Bureau\"" > /root/.config/user-dirs.dirs
touch /root/Bureau/Notes.txt
R=/out/zz.txt; : > $R
python3 -c 'import sys; sys.path.insert(0,"/usr/lib/xiii"); from xiii import config; config.modifier(_histo=False, visite_faite=True)'
xiii-shell > /out/shell.log 2>&1 &
sleep 6
verifier() {  # nom, motif du processus, journal
  local nom=$1 motif=$2 log=$3
  if grep -q "Traceback" "$log" 2>/dev/null; then echo "PLANTAGE  $nom" >> $R; sed -n '/Traceback/,/^[A-Za-z]*Error\|^[A-Za-z]*Exception/p' "$log" | tail -6 | sed 's/^/          /' >> $R
  elif ! pgrep -f "$motif" >/dev/null; then echo "FERMÉE    $nom (l'application s'est arrêtée seule)" >> $R; tail -3 "$log" | sed 's/^/          /' >> $R
  else echo "OK        $nom" >> $R; fi
}
echo "== Applications" >> $R
for a in archives paquets acquisition bilan blackmagic console debit demarrage fichiers ia lecteurs logiciels qrwifi retour scanip somme store-github suite synthese taches tally timecode transferts windows bienvenue phonebox; do
  command -v xiii-$a >/dev/null || { echo "ABSENTE   xiii-$a" >> $R; continue; }
  xiii-$a > /out/app-$a.log 2>&1 &
  sleep 5; grim -s 0.5 /out/app-$a.png
  m="xiii.$(echo $a | tr - _)"; [ $a = bilan ] && m=xiii-bilan; [ $a = timecode ] && m=xiii.ltc; [ $a = acquisition ] && continue; [ $a = phonebox ] && m=phonebox
  verifier "xiii-$a" "$m" /out/app-$a.log
  pkill -f "$m"; pkill -f WebKitWebProcess; sleep 0.6
done
echo "== Pages des Paramètres" >> $R
for pg in $(python3 -c 'import sys; sys.path.insert(0,"/usr/lib/xiii"); from xiii.pages_index import PAGES; print(" ".join(p[0] for p in PAGES))'); do
  : > /out/p.log
  xiii-parametres --page $pg > /out/p.log 2>&1 &
  sleep 2.6; grim -s 0.5 /out/page-$pg.png
  verifier "Paramètres › $pg" "xiii.parametres" /out/p.log
  grep -q Traceback /out/p.log && cp /out/p.log /out/page-$pg.log
  pkill -f xiii.parametres; sleep 0.4
done
echo "== Thèmes (bureau + Paramètres + menu Démarrer)" >> $R
for t in sombre clair sobre sobrec w2k xp mac9 cyber term gb regie soleil rainbow sepia; do
  python3 -c "import sys; sys.path.insert(0,'/usr/lib/xiii'); from xiii import config; config.modifier(_histo=False, theme='$t')"
  sleep 2
  xiii-parametres --page theme > /out/t.log 2>&1 & sleep 3; grim -s 0.5 /out/theme-$t.png
  verifier "Thème $t" "xiii.parametres" /out/t.log; pkill -f xiii.parametres; sleep 0.4
  xiii-ctl demarrer; sleep 1.5; grim -s 0.5 /out/theme-$t-menu.png; xiii-ctl fermer; sleep 0.4
done
python3 -c "import sys; sys.path.insert(0,'/usr/lib/xiii'); from xiii import config; config.modifier(_histo=False, theme='sombre')"
sleep 3; xiii-ctl demarrer-categorie; sleep 2; grim /out/menu-categorie.png; xiii-ctl fermer; sleep 0.4
grim /out/bureau-fond.png
cd /tmp && mkdir -p demo && echo bonjour > demo/a.txt && zip -qr demo.zip demo && cd - >/dev/null
xiii-archives /tmp/demo.zip > /out/archives.log 2>&1 & sleep 4; grim /out/archives-zip.png; pkill -f xiii.archives
python3 -c 'import sys; sys.path.insert(0,"/usr/lib/xiii"); from xiii import theme, config; c=config.charger(); print(theme.image_verrou("/usr/share/xiii/wallpapers/xiii-connexion.png", theme.palette(c)))' > /out/verrou.txt 2>&1
cp "$(tail -1 /out/verrou.txt)" /out/verrou.png 2>/dev/null
xiii-parametres --page connexion > /out/p.log 2>&1 & sleep 3; grim /out/page-connexion-visage.png; pkill -f xiii.parametres
# clic en dehors d'un menu ouvert : il doit se fermer (souris virtuelle wlrctl)
if command -v wlrctl >/dev/null; then
  for pan in demarrer son centre; do
    xiii-ctl $pan; sleep 1.5; grim -s 0.5 /out/clic-$pan-avant.png
    wlrctl pointer move -3000 -3000; wlrctl pointer move 120 450; sleep 0.3; wlrctl pointer click left; sleep 1
    grim -s 0.5 /out/clic-$pan-apres.png
    python3 -c "import sys,json; sys.path.insert(0,'/usr/lib/xiii')" 
    xiii-ctl fermer; sleep 0.4
  done
  echo "INFO      clic en dehors : voir clic-*-avant/apres.png" >> $R
fi
echo "== Fichiers : vue Mac (colonnes) et Arbre" >> $R
timeout 60 xiii-fichiers --test-colonnes > /out/colonnes.log 2>&1
grep "^COLONNES" /out/colonnes.log | sed 's/^COLONNES //' >> $R
grep -q "^COLONNES" /out/colonnes.log || { echo "ÉCHEC     test des colonnes non exécuté" >> $R; tail -5 /out/colonnes.log | sed 's/^/          /' >> $R; }
echo "== Fiabilité (phase A)" >> $R
python3 -c 'import sys; sys.path.insert(0,"/usr/lib/xiii"); from xiii import fiabilite as F; L=F.evenements(); print("OK        journal des événements :", len(L), "entrée(s)")' >> $R 2>&1
python3 -c 'import sys; sys.path.insert(0,"/usr/lib/xiii"); from xiii import raccourcis as R; L=R.lire(); print("OK        raccourcis clavier :", len(L), "lus,", sum(1 for s in L if s["categorie"]=="Personnalisés"), "sans nom")' >> $R 2>&1
python3 -c 'import sys; sys.path.insert(0,"/usr/lib/xiii"); import xiii; from xiii import rapport, fiabilite as F
try: 1/0
except ZeroDivisionError: f=rapport.ecrire(*sys.exc_info())
print("OK        rapport de plantage écrit :", f.split("/")[-1])' >> $R 2>&1
xiii-parametres --page evenements > /out/p.log 2>&1 & sleep 4; grim -s 0.5 /out/page-evenements-rempli.png; pkill -f xiii.parametres
for s in /etc/grub.d/41_xiii_secours /usr/local/sbin/xiii-instantanes /usr/local/sbin/xiii-demarrage-suivi /usr/local/sbin/xiii-reparer-menu; do
  bash -n $s && echo "OK        syntaxe $(basename $s)" >> $R || echo "ÉCHEC     syntaxe $(basename $s)" >> $R; done
echo "== Bureau" >> $R
grep -q Traceback /out/shell.log && { echo "PLANTAGE  xiii-shell" >> $R; grep -A8 Traceback /out/shell.log | tail -12 >> $R; } || echo "OK        xiii-shell (aucune erreur Python)" >> $R
pgrep -f xiii.shell >/dev/null || echo "FERMÉE    xiii-shell" >> $R
echo "== Menu « Toutes les applications » (doublons ?)" >> $R
python3 -c 'import sys; sys.path.insert(0,"/usr/lib/xiii"); from xiii import apps
L=[(a.get_display_name(), a.get_id()) for a in apps.toutes()]
import collections; c=collections.Counter(n.lower() for n,_ in L)
for n,i in L: print(("DOUBLON   " if c[n.lower()]>1 else "          ")+n+"  ("+i+")")' >> $R 2>&1
echo "== Fin" >> $R
labwc --exit
