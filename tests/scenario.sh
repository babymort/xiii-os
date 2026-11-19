#!/bin/bash
# Scénario de captures du bureau XIII (exécuté par labwc -s sur écran virtuel)
sleep 1
wlr-randr --output HEADLESS-1 --custom-mode 1600x900 >/out/randr.log 2>&1
mkdir -p /root/.config; echo "XDG_DESKTOP_DIR=\"\$HOME/Bureau\"" > /root/.config/user-dirs.dirs; mkdir -p /root/Bureau /root/XIII/Concert-Dome/01_Rushes; touch "/root/Bureau/Conducteur.pdf" "/root/Bureau/Plan de feu.png" "/root/Bureau/Notes.txt"; mkdir -p "/root/Bureau/Rushes jour 1"
python3 -c 'import sys; sys.path.insert(0,"/usr/lib/xiii"); from xiii import config; config.modifier(timecode=True, projet_actif="Concert-Dome", profil="tournage")'
xiii-shell > /out/shell.log 2>&1 &
sleep 6
notify-send -a "Pilotes XIII" -i preferences-system --action=ouvrir="Ouvrir Pilotes XIII" "Pilotes à installer" "Carte NVIDIA détectée : le pilote nvidia-driver améliorera les performances." >/dev/null &
sleep 0.5
notify-send -a "Capture" -i camera-photo "Capture enregistrée" "Copiée dans le presse-papiers · capture-2026-11-16.png" &
mousepad >/dev/null 2>&1 &
sleep 2
for i in 1 2 3 4 5 6 7 8 9 10; do grim /out/v-$i.png; xiii-ctl visite-suivant; sleep 1; done
sleep 1
grim /out/01-bureau.png
for p in demarrer son wifi bluetooth batterie centre alim volet widgets; do
  xiii-ctl $p; sleep 2; grim /out/p-$p.png; xiii-ctl fermer; sleep 0.6
done
xiii-ctl demarrer-toutes; sleep 2; grim /out/p-toutes.png; xiii-ctl fermer; sleep 0.5
for p in vue dispositions presse emoji; do xiii-ctl $p; sleep 2; grim /out/q-$p.png; xiii-ctl fermer; sleep 0.3; done
pkill -f "xiii.shell" ; sleep 0.2
xiii-shell >> /out/shell.log 2>&1 &
sleep 5
xiii-veille horloge > /out/veille.log 2>&1 & sleep 3; grim /out/q-veille-horloge.png; pkill -f xiii.veille; sleep 0.5
xiii-veille mire >> /out/veille.log 2>&1 & sleep 3; grim /out/q-veille-mire.png; pkill -f xiii.veille; sleep 0.5
xiii-somme /root/Bureau > /out/somme.log 2>&1 & sleep 4; grim /out/q-somme.png; pkill -f xiii.somme; sleep 0.5
xiii-bilan --sante > /out/bilan.log 2>&1 & sleep 5; grim /out/q-sante.png; pkill -f xiii-bilan; sleep 0.5
xiii-parametres --page accueil >> /out/param.log 2>&1 &
sleep 6; grim /out/s-accueil.png
for pg in interfaces iface profilsreseau duo ethernet suite ndi xiii claude accueil profils historique bureau jeux projet outilsprod sauvegarde widgets xiii ecran son theme fond barre perso wifi bluetooth apropos alimentation stockage souris clavier xiii maj apps notifications heure; do
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
# Phase 09 — Suite XIII native, .xiii.json, DOSSIER, retour plateau
xiii-suite conduco > /out/suite.log 2>&1 & sleep 15; grim /out/x-conduco.png
xiii-suite index >> /out/suite.log 2>&1 & sleep 10; grim /out/x-index.png
xiii-ctl demarrer-toutes; sleep 2; grim /out/x-menu-suite.png; xiii-ctl fermer; sleep 0.5
printf '{"format":"xiii-link","version":1,"kind":"project","project":{"name":"Concert Dôme"},"fiche":{"title":"Concert Dôme de Paris"}}' > /root/XIII/Concert-Dome/fiche.xiii.json
xiii-suite --ouvrir /root/XIII/Concert-Dome/fiche.xiii.json >> /out/suite.log 2>&1 & sleep 4; grim /out/x-choix.png
printf '{"format":"xiii-link","version":1,"kind":"rundown","project":{"name":"Concert"},"conducteur":{"name":"Conducteur test","date":"2026-11-28"},"items":[{"title":"Ouverture"}]}' > /root/Bureau/conducteur.xiii.json
xiii-suite --ouvrir /root/Bureau/conducteur.xiii.json >> /out/suite.log 2>&1 & sleep 14; grim /out/x-rundown.png
xiii-suite --dossier "/root/Bureau/Notes.txt" >> /out/suite.log 2>&1 & sleep 14; grim /out/x-dossier.png
pkill -f "xiii.suite"; sleep 1
xiii-tally > /out/tally.log 2>&1 & sleep 6; grim /out/x-tally.png
wtype -k Page_Down 2>/dev/null; sleep 0.3; wtype -k Page_Down 2>/dev/null; sleep 0.3; wtype -k Page_Down 2>/dev/null; sleep 1; grim /out/x-tally-bas.png
pkill -f "xiii.tally"; sleep 0.5; xiii-tally --boitier >> /out/tally.log 2>&1 & sleep 5; grim /out/x-boitier.png; pkill -f "xiii.tally"; sleep 0.5
xiii-tally >> /out/tally.log 2>&1 & sleep 5
python3 -c '
import gi; gi.require_version("Gtk","4.0"); gi.require_version("WebKit","6.0")
from gi.repository import Gtk, WebKit, GLib
a = Gtk.Application(application_id="fr.xiii.testtel")
def act(app):
    w = Gtk.ApplicationWindow(application=app, title="Téléphone", default_width=390, default_height=780); v = WebKit.WebView(); w.set_child(v)
    v.load_uri("http://127.0.0.1:8790/?cam=1"); w.present()
a.connect("activate", act); a.run(None)' > /out/tel.log 2>&1 & sleep 9; grim /out/x-telephone.png
curl -s http://127.0.0.1:8790/api/etat > /out/tally-etat.json; curl -s http://127.0.0.1:8790/api/cam/1 >> /out/tally-etat.json
pkill -f fr.xiii.testtel; pkill -f "xiii.tally"; sleep 0.5
xiii-retour > /out/retour.log 2>&1 & sleep 4; grim /out/x-retour.png; pkill -f "xiii.retour"; sleep 0.5
# Phase 11 — thèmes de la suite
for th in cyber gb sepia; do
  python3 -c "import sys; sys.path.insert(0,'/usr/lib/xiii'); from xiii import config, theme; c=config.charger(); c['theme']='$th'; config.modifier(theme='$th', fond=theme.fond_assorti(c))"
  sleep 2.5; xiii-ctl demarrer; sleep 1.8; grim /out/t-$th.png; xiii-ctl fermer; sleep 0.4
done
xiii-parametres --page theme >> /out/param.log 2>&1 & sleep 5; grim /out/t-parametres-perso.png; pkill -f xiii.parametres; sleep 0.5
python3 -c 'import sys; sys.path.insert(0,"/usr/lib/xiii"); from xiii import config; config.modifier(theme="sombre", fond="/usr/share/xiii/wallpapers/xiii-sombre.png")'
sleep 2; grim /out/t-sombre-barre.png
python3 -c 'import sys; sys.path.insert(0,"/usr/lib/xiii"); from xiii import config; config.modifier(theme="clair", accent="#3d8bfd")'
sleep 3; xiii-ctl demarrer; sleep 2; grim /out/c-clair-menu.png; xiii-ctl fermer
xiii-ctl centre; sleep 2; grim /out/c-clair-centre.png; xiii-ctl fermer
python3 -c 'import sys; sys.path.insert(0,"/usr/lib/xiii"); from xiii import config; config.modifier(theme="sobre", accent="#f0b378", barre_alignement="gauche")'
sleep 3; xiii-ctl demarrer; sleep 2; grim /out/c-sobre-menu.png; xiii-ctl fermer
# Phase 11b — finitions
python3 -c 'import sys; sys.path.insert(0,"/usr/lib/xiii"); from xiii import config; config.modifier(theme="sombre", accent="#f0b378", barre_alignement="centre")'
sleep 2
mkdir -p /root/Images; cp /usr/share/xiii/wallpapers/xiii-sombre.png /root/Images/plateau.png 2>/dev/null
printf 'CONDUCTEUR\n10:00 Ouverture\n10:05 Plateau\n' > /root/Images/notes.txt
mousepad /root/Images/notes.txt >/dev/null 2>&1 & sleep 3
imv /root/Images/plateau.png >/dev/null 2>&1 & sleep 3
sleep 2; xiii-ctl vue; sleep 2; grim /out/f-vue-miniatures.png; xiii-ctl fermer; sleep 0.5
ls -la /root/.cache/xiii/miniatures > /out/miniatures.txt 2>&1
python3 -c 'import sys; sys.path.insert(0,"/usr/lib/xiii"); from xiii import config; config.modifier(barre_style="onglets")'
sleep 2; grim /out/f-barre-onglets.png
gdbus emit --session --object-path /fr/xiii/progres --signal com.canonical.Unity.LauncherEntry.Update "application://org.xfce.mousepad.desktop" "{'progress': <0.6>, 'progress-visible': <true>}" 2>>/out/f.log
sleep 1; grim /out/f-barre-progres.png
python3 -c 'import sys; sys.path.insert(0,"/usr/lib/xiii"); from xiii import config; config.modifier(barre_style="icones")'
sleep 1.5; grim /out/f-barre-progres-icones.png
wtype -M logo -k space -m logo; sleep 2; grim /out/f-super-espace.png; xiii-ctl fermer; sleep 0.5
xiii-apercu /root/Images/plateau.png >> /out/f.log 2>&1 & sleep 3; grim /out/f-apercu-image.png; pkill -f xiii.apercu; sleep 0.5
xiii-apercu /root/Images/notes.txt >> /out/f.log 2>&1 & sleep 3; grim /out/f-apercu-texte.png; pkill -f xiii.apercu; sleep 0.5
xiii-timecode >> /out/f.log 2>&1 & sleep 3; grim /out/f-timecode.png; pkill -f xiii.ltc; sleep 0.5
xiii-ctl widgets; sleep 3; grim /out/f-widgets.png; wtype -k Page_Down; sleep 1; grim /out/f-widgets-bas.png; xiii-ctl fermer; sleep 0.5
for pg in acquisition outilsprod barre; do xiii-parametres --page $pg >> /out/param.log 2>&1 & sleep 4; grim /out/f-p-$pg.png; pkill -f xiii.parametres; sleep 0.5; done
python3 -c 'import sys; sys.path.insert(0,"/usr/lib/xiii"); from xiii import theme; [print(k, theme.SKINS[k].get("police") if hasattr(theme,"SKINS") else "") for k in ("cyber","gb","sepia")]' >> /out/f.log 2>&1
pkill mousepad; pkill imv
cp /root/.config/xiii/reglages.json /out/ 2>/dev/null
labwc --exit
# relance
