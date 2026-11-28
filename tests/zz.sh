#!/bin/bash
# Vérification de fin de saison (ZZ) : chaque application, chaque page des Paramètres et chaque thème, captures + plantages relevés.
# Exécuté par labwc -s sur écran virtuel ; résultat dans /out (branche « zz »).
sleep 1
wlr-randr --output HEADLESS-1 --custom-mode 1600x900 >/dev/null 2>&1
mkdir -p /root/.config /root/Bureau /root/XIII/Concert-Dome/03_Documents; echo "XDG_DESKTOP_DIR=\"\$HOME/Bureau\"" > /root/.config/user-dirs.dirs
touch /root/Bureau/Notes.txt
# faux logiciels Blackmagic installés par Wine (comme sur le PC de Matthieu) : Blackmagic XIII doit les trouver
mkdir -p "/root/.local/share/applications/wine/Programs/Blackmagic Design/ATEM"
for n in "ATEM Software Control" "ATEM Setup"; do printf '[Desktop Entry]\nName=%s\nExec=env WINEPREFIX="/root/.wine" wine "C:\\\\Program Files\\\\Blackmagic Design\\\\%s.exe"\nType=Application\nIcon=atem\n' "$n" "$n" > "/root/.local/share/applications/wine/Programs/Blackmagic Design/ATEM/$n.desktop"; done
R=/out/zz.txt; : > $R
python3 -c 'import sys; sys.path.insert(0,"/usr/lib/xiii"); from xiii import config; config.modifier(_histo=False, visite_faite=True)'
export GSK_RENDERER=cairo MALLOC_ARENA_MAX=2      # comme une session OS XIII sans carte 3D (VM, xiii-demarrer-bureau)
xiii-shell > /out/shell.log 2>&1 &
sleep 6
pss_shell() { p=$(pgrep -f "xiii.shell import" | head -1); [ -n "$p" ] && awk '/^Pss:/{print int($2/1024)}' /proc/$p/smaps_rollup; }
echo "$(pss_shell)" > /tmp/pss-6s; (sleep 40; pss_shell > /tmp/pss-46s) &
verifier() {  # nom, motif du processus, journal
  local nom=$1 motif=$2 log=$3
  if grep -q "Traceback" "$log" 2>/dev/null; then echo "PLANTAGE  $nom" >> $R; sed -n '/Traceback/,/^[A-Za-z]*Error\|^[A-Za-z]*Exception/p' "$log" | tail -6 | sed 's/^/          /' >> $R
  elif ! pgrep -f "$motif" >/dev/null; then echo "FERMÉE    $nom (l'application s'est arrêtée seule)" >> $R; tail -3 "$log" | sed 's/^/          /' >> $R
  else echo "OK        $nom" >> $R; fi
}
echo "== Applications" >> $R
for a in regie prompteur mesure-audio mires lut multiview recuperer premiers-pas archives paquets acquisition bilan blackmagic console debit demarrage fichiers ia lecteurs logiciels qrwifi retour scanip somme store-github suite synthese taches tally timecode transferts windows bienvenue phonebox horloge assistance presse-telephone; do
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
for t in verre sombre clair sobre sobrec w2k xp mac9 cyber term gb regie soleil rainbow sepia; do
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
echo "== Phase B (graphisme)" >> $R
python3 -c 'import sys; sys.path.insert(0,"/usr/lib/xiii"); from xiii import theme
for f in ("/usr/share/xiii/wallpapers/xiii-sombre.png","/usr/share/xiii/wallpapers/xiii-clair.png"): print("OK        accent tiré du fond", f.split("/")[-1], ":", theme.accent_du_fond(f))' >> $R 2>&1
for m in flip logo; do xiii-veille $m > /out/veille-$m.log 2>&1 & sleep 3; grim -s 0.5 /out/veille-$m.png; verifier "Écran de veille $m" "xiii.veille" /out/veille-$m.log; pkill -f xiii.veille; sleep 0.4; done
python3 -c "import sys; sys.path.insert(0,'/usr/lib/xiii'); from xiii import config; config.modifier(_histo=False, widgets_bureau=['calendrier','disques','compte','systeme'], compte_nom='Concert Dôme', compte_date='2026-12-12')"
sleep 3; grim -s 0.5 /out/bureau-widgets.png
python3 -c "import sys; sys.path.insert(0,'/usr/lib/xiii'); from xiii import config; config.modifier(_histo=False, fond_anime=True)"
sleep 4; grim -s 0.5 /out/bureau-fond-anime.png; pgrep -f xiii.fond_anime >/dev/null && echo "OK        fond animé lancé" >> $R || echo "ÉCHEC     fond animé non lancé" >> $R
python3 -c "import sys; sys.path.insert(0,'/usr/lib/xiii'); from xiii import config; config.modifier(_histo=False, fond_anime=False, widgets_bureau=[])"
xiii-blackmagic > /out/bm.log 2>&1 & sleep 5; grim -s 0.5 /out/blackmagic-mes-logiciels.png; verifier "Blackmagic XIII (logiciels détectés)" "xiii.blackmagic" /out/bm.log; pkill -f xiii.blackmagic
python3 -c 'import sys; sys.path.insert(0,"/usr/lib/xiii"); from xiii import blackmagic as B; L=B.logiciels_installes(); print("OK        Blackmagic détectés :", {k:[x["nom"] for x in v] for k,v in L.items()})' >> $R 2>&1
for s in /usr/share/sounds/XIII/stereo/*.wav; do :; done; echo "OK        sons système : $(ls /usr/share/sounds/XIII/stereo | wc -l) fichiers" >> $R
echo "== Phase C (ergonomie)" >> $R
python3 -c 'import sys; sys.path.insert(0,"/usr/lib/xiii"); from xiii.conversions import convertir
for q in ("12 pouces en cm","50 Mb/s","100 °F","3 Go en Mo"): print("OK        conversion", q, "→", convertir(q)[0] if convertir(q) else "RIEN")' >> $R 2>&1
python3 -c 'import sys; sys.path.insert(0,"/usr/lib/xiii"); from xiii import raccourcis as R; print("OK        gestes :", len(R.GESTES), "· raccourci bureau suivant :", next((x["cle"] for x in R.lire() if x["actions"][0][0]=="GoToDesktop" and x["actions"][0][1].get("to")=="right"), "aucun"))' >> $R 2>&1
for s in /usr/local/bin/xiii-capture; do bash -n $s && echo "OK        syntaxe $(basename $s)" >> $R; done
python3 -c 'import ast; ast.parse(open("/usr/local/sbin/xiii-gestes").read()); print("OK        syntaxe xiii-gestes")' >> $R 2>&1
printf 'Texte copié pour le test\n' | wl-copy 2>/dev/null; sleep 0.5
xiii-ctl presse; sleep 1.5; grim -s 0.5 /out/presse-papiers.png; xiii-ctl fermer
notify-send -a Test "Notification de test" "Historique sur 7 jours"; sleep 1
python3 -c 'import sys; sys.path.insert(0,"/usr/lib/xiii"); from xiii.notifs import historique; print("OK        historique des notifications :", len(historique()), "entrée(s)")' >> $R 2>&1
grim -s 0.5 /out/barre-pastilles.png
python3 -c "import sys; sys.path.insert(0,'/usr/lib/xiii'); from xiii import config; config.modifier(_histo=False, menu_taille='grand')"; sleep 2
xiii-ctl demarrer; sleep 1.5; grim -s 0.5 /out/menu-grand.png; xiii-ctl fermer
python3 -c "import sys; sys.path.insert(0,'/usr/lib/xiii'); from xiii import config; config.modifier(_histo=False, menu_taille='normal')"
echo "== Phase D (Fichiers)" >> $R
mkdir -p /root/Rushes/A001 && ffmpeg -v quiet -f lavfi -i testsrc=duration=3:size=1920x1080:rate=25 -f lavfi -i sine=duration=3 -c:v libx264 -pix_fmt yuv420p -c:a aac -timecode 10:00:00:00 -metadata model="Pocket 6K" /root/Rushes/A001/A001_C001.mov
ffmpeg -v quiet -f lavfi -i testsrc2=duration=2:size=1280x720:rate=50 -c:v mpeg2video /root/Rushes/A001/A001_C002.mxf
for i in 1 2 3; do cp /root/Rushes/A001/A001_C001.mov /root/Rushes/plan_$i.mov; done
python3 -c 'import sys; sys.path.insert(0,"/usr/lib/xiii"); from xiii import medias
print("OK        miniature vidéo :", bool(medias.miniature("/root/Rushes/A001/A001_C001.mov")), "· MXF :", bool(medias.miniature("/root/Rushes/A001/A001_C002.mxf")))
print("OK        infos :", "; ".join("%s=%s" % kv for kv in medias.infos("/root/Rushes/A001/A001_C001.mov")))' >> $R 2>&1
python3 -c 'import sys; sys.path.insert(0,"/usr/lib/xiii"); from xiii import copie
t=copie.Tache(["/root/Rushes/A001"],"/tmp"); t.lancer(); print("OK" if t.etat=="terminée" else "ÉCHEC", "      copie vérifiée :", t.texte(lambda n: str(n)))' >> $R 2>&1
python3 -c 'import sys; sys.path.insert(0,"/usr/lib/xiii"); from xiii import etiquettes as E
E.poser("/root/Rushes/plan_1.mov","rouge"); print("OK        étiquette :", E.lire("/root/Rushes/plan_1.mov"), "·", len(E.chercher("rouge",["/root/Rushes"])), "trouvé(s)")' >> $R 2>&1
gio trash /root/Rushes/plan_3.mov 2>/dev/null
python3 -c 'import sys; sys.path.insert(0,"/usr/lib/xiii"); from xiii import corbeille as C; L=C.elements(); print("OK        corbeille :", len(L), "élément(s) ·", L[0]["origine"] if L else "")' >> $R 2>&1
python3 -c "import sys; sys.path.insert(0,'/usr/lib/xiii'); from xiii import config; config.modifier(_histo=False, fichiers_vue='galerie')"
xiii-fichiers /root/Rushes > /out/f-galerie.log 2>&1 & sleep 6; grim -s 0.5 /out/fichiers-galerie.png; verifier "Fichiers › Galerie" "xiii.fichiers" /out/f-galerie.log; pkill -f xiii.fichiers; sleep 0.5
xiii-fichiers --infos /root/Rushes/A001/A001_C001.mov > /out/f-infos.log 2>&1 & sleep 6; grim -s 0.5 /out/fichiers-infos.png; verifier "Fichiers › Informations" "xiii.fichiers" /out/f-infos.log; pkill -f xiii.fichiers; sleep 0.5
xiii-fichiers --corbeille /root > /out/f-corb.log 2>&1 & sleep 4; grim -s 0.5 /out/fichiers-corbeille.png; verifier "Fichiers › Corbeille" "xiii.fichiers" /out/f-corb.log; pkill -f xiii.fichiers
# Fichiers : onglets, volet d'aperçu, état du cloud (OneDrive factice : un dossier en ligne, un dossier gardé hors ligne)
mkdir -p "/root/Cloud/OneDrive/Projets" "/root/Cloud/OneDrive/Factures" "/root/Hors ligne/OneDrive/Projets"; echo "Bonjour" > "/root/Cloud/OneDrive/Projets/note.txt"; echo "Plan de tournage" > "/root/Hors ligne/OneDrive/Projets/plan.txt"
mkdir -p /root/.config/xiii; [ -f /root/.config/xiii/lecteurs.json ] && cp /root/.config/xiii/lecteurs.json /tmp/lecteurs.bak
echo '[{"nom": "OneDrive", "type": "onedrive", "hors_ligne": [{"distant": "Projets", "local": "/root/Hors ligne/OneDrive/Projets", "premiere": false}]}]' > /root/.config/xiii/lecteurs.json
python3 -c 'import sys; sys.path.insert(0,"/usr/lib/xiii"); from xiii import lecteurs as L
a=L.etat_cloud("/root/Cloud/OneDrive/Factures"); b=L.etat_cloud("/root/Cloud/OneDrive/Projets"); c=L.etat_cloud("/root/Hors ligne/OneDrive/Projets/plan.txt"); d=L.etat_cloud("/root/Bureau")
print("OK        état du cloud : en ligne / gardé hors ligne / copie locale / ailleurs" if (a and a[0]=="cloud") and (b and b[0]=="horsligne") and (c and c[0]=="horsligne") and d is None else "ÉCHEC     état du cloud : %r %r %r %r" % (a and a[0], b and b[0], c and c[0], d))' >> $R 2>&1
python3 -c 'import sys; sys.path.insert(0,"/usr/lib/xiii"); from xiii import config; config.modifier(_histo=False, fichiers_apercu=True, fichiers_vue="windows")'
xiii-fichiers /root/Cloud/OneDrive > /out/f-cloud.log 2>&1 & sleep 5; grim -s 0.5 /out/fichiers-cloud-apercu.png; verifier "Fichiers › état du cloud + volet d'aperçu" "xiii.fichiers" /out/f-cloud.log; pkill -f xiii.fichiers; sleep 0.5
python3 -c 'import sys; sys.path.insert(0,"/usr/lib/xiii"); from xiii import config; config.modifier(_histo=False, fichiers_apercu=False)'
[ -f /tmp/lecteurs.bak ] && cp /tmp/lecteurs.bak /root/.config/xiii/lecteurs.json || rm -f /root/.config/xiii/lecteurs.json
python3 -c "import sys; sys.path.insert(0,'/usr/lib/xiii'); from xiii import config; config.modifier(_histo=False, fichiers_vue='windows')"
echo "== Mode Production (barre latérale + tableau)" >> $R
CFG='import sys,time; sys.path.insert(0,"/usr/lib/xiii"); from xiii import config; '
python3 -c "$CFG"'t=int(time.time()); config.modifier(production_page="accueil", projet_actif="Test", production_recents=[["suite","callsheeto","CALL SHEETO",None,t-300],["suite","plano","PLANO",None,t-7200],["suite","deviso","DEVISO",None,t-90000],["suite","dossier","DOSSIER",None,t-200000],["app","xiii-blackmagic.desktop","Blackmagic","video",t-400000]], mode_bureau="production")'
# données de démonstration du Studio (projet « Test »)
python3 - <<'P'
import sys, time, datetime; sys.path.insert(0, "/usr/lib/xiii")
from xiii.studio import Donnees, aujourdhui
d = Donnees("Test"); t = d.nouveau_tableau("tournage", "Tournage — Concert")
c = t["colonnes"]
c[0]["cartes"] += [{"id": "a1", "titre": "Plan large de la scène", "type": "plan", "champs": {"sequence": "2", "plan": "4", "camera": "FX6 A"}, "etiquettes": ["orange"], "personnes": ["Léa Martin"], "echeance": aujourdhui().isoformat(), "checklist": [{"t": "Trépied", "ok": True}, {"t": "Batteries", "ok": False}]},
                   {"id": "a2", "titre": "Interview du chanteur", "etiquettes": ["violet"], "personnes": ["Hugo Bernard", "Léa Martin"], "commentaires": [{"date": "27/11", "texte": "Prévoir 2 micros"}]}]
c[1]["cartes"] += [{"id": "a3", "titre": "Balances et soundcheck", "etiquettes": ["bleu"], "echeance": (aujourdhui() + datetime.timedelta(days=1)).isoformat()}]
c[3]["cartes"] += [{"id": "a4", "titre": "Teaser 30 s — V2", "type": "validation", "champs": {"version": "V2", "client": "Label"}, "statut_valid": "Retours"}]
d.ecrire("organiser")
d.taches().extend([{"id": "t1", "titre": "Confirmer la régie mobile", "priorite": "haute", "statut": "en_cours", "echeance": aujourdhui().isoformat()},
                   {"id": "t2", "titre": "Envoyer la feuille de service", "priorite": "moyenne", "statut": "a_faire", "echeance": (aujourdhui() + datetime.timedelta(days=2)).isoformat()},
                   {"id": "t3", "titre": "Réserver les cartes CFexpress", "priorite": "basse", "statut": "fait"}]); d.ecrire("taches")
d.memos().extend([{"id": "m1", "titre": "Wi-Fi du lieu", "texte": "Réseau : Salle-Pro\nCode : xiii2026", "couleur": "ambre", "epingle": True, "modif": time.time()},
                  {"id": "m2", "titre": "Matériel à rendre", "liste": [{"t": "Rail 2 m", "ok": True}, {"t": "Mixette", "ok": False}], "couleur": "bleu", "modif": time.time() - 10},
                  {"id": "m3", "titre": "", "texte": "Idée : ouvrir sur la salle vide, la nuit.", "couleur": "violet", "etiquettes": ["idees"], "modif": time.time() - 20}]); d.ecrire("memos")
o = d.objectifs(); o["semaine"] += [{"t": "Tourner le concert", "ok": False}, {"t": "Sauvegarder 3-2-1", "ok": True}]; o["mois"] += [{"t": "Livrer le film", "ok": False}]; d.ecrire("objectifs")
d.lire("contacts", []).extend([{"id": "c1", "nom": "Léa Martin", "role": "Cheffe opératrice", "categorie": "Équipe", "tel": "06 12 34 56 78", "email": "lea@exemple.fr", "date": aujourdhui().isoformat()},
                               {"id": "c2", "nom": "Label Nuit", "role": "Production", "categorie": "Client", "email": "prod@label.fr"},
                               {"id": "c3", "nom": "Salle Pleyel", "role": "Régie lieu", "categorie": "Lieu", "tel": "01 00 00 00 00"}]); d.ecrire("contacts")
d.lire("materiel", []).extend([{"id": "x1", "nom": "Sony FX6", "categorie": "Caméra", "statut": "Sorti", "quantite": 2, "valeur": 6500.0, "retour": (aujourdhui() + datetime.timedelta(days=3)).isoformat(), "qui": "Léa"},
                               {"id": "x2", "nom": "Zoom F8n", "categorie": "Son", "statut": "Disponible", "quantite": 1, "valeur": 1100.0},
                               {"id": "x3", "nom": "Aputure 600d", "categorie": "Lumière", "statut": "En panne", "quantite": 1}]); d.ecrire("materiel")
d.lire("budget", []).extend([{"id": "b1", "libelle": "Prestation captation", "type": "Recette", "categorie": "Autre", "montant": 6000.0, "statut": "Engagé"},
                             {"id": "b2", "libelle": "Cadreurs (2 j)", "type": "Dépense", "categorie": "Équipe", "montant": 1400.0, "statut": "Prévu", "date": aujourdhui().isoformat()},
                             {"id": "b3", "libelle": "Location optiques", "type": "Dépense", "categorie": "Matériel", "montant": 650.0, "statut": "Payé"},
                             {"id": "b4", "libelle": "Repas équipe", "type": "Dépense", "categorie": "Repas", "montant": 240.0, "statut": "Prévu"}]); d.ecrire("budget")
import json, os
os.makedirs(os.path.expanduser("~/XIII/Test/03_Documents"), exist_ok=True)
json.dump({"format": "xiii-link", "kind": "workplan", "project": {"name": "Test"}, "days": [{"n": 1, "date": (aujourdhui() + datetime.timedelta(days=1)).isoformat(), "scenes": [{"seq": "12", "ie": "INT.", "decor": "Loges", "effet": "NUIT"}, {"seq": "13", "ie": "EXT.", "decor": "Parvis", "effet": "NUIT"}]}]},
          open(os.path.expanduser("~/XIII/Test/03_Documents/plan-de-travail.xiii.json"), "w"))
P
python3 -c "$CFG"'config.modifier(mode_bureau="classique")'; sleep 2
python3 -c "$CFG"'config.modifier(production_page="accueil", mode_bureau="production")'; sleep 4
grim -s 0.5 /out/production-accueil.png
for pg in organiser memos taches objectifs contacts materiel budget tableau planning; do
  python3 -c "$CFG"'config.modifier(mode_bureau="classique")'; sleep 2
  python3 -c "$CFG"'config.modifier(production_page="'$pg'", mode_bureau="production")'; sleep 4; grim -s 0.5 /out/production-$pg.png
done
python3 -c "$CFG"'config.modifier(mode_bureau="classique")'; sleep 2
journalctl --user -n 0 >/dev/null 2>&1; echo "OK        mode Production capturé (accueil, organiser, mémos, tâches, objectifs, tableau, planning)" >> $R
xiii-studio --test >> $R 2>&1 || echo "ÉCHEC     Studio XIII (test des données)" >> $R
xiii-memos > /out/xiii-memos.log 2>&1 & sleep 4; grim -s 0.5 /out/app-memos.png; verifier "Mémos XIII" "xiii.studio" /out/xiii-memos.log; pkill -f "xiii.studio import"; sleep 1
xiii-studio --page organiser > /out/xiii-studio.log 2>&1 & sleep 4; grim -s 0.5 /out/app-studio.png; verifier "Studio XIII" "xiii.studio" /out/xiii-studio.log; pkill -f "xiii.studio import"; sleep 1

echo "== Phase G (réseau : Envoi XIII compatible LocalSend)" >> $R
python3 -c "$CFG"'config.modifier(envoi_auto=True, envoi_actif=True, envoi_nom="Poste ZZ")'
pkill -f "xiii-envoi --recevoir"; sleep 1
xiii-envoi --recevoir > /out/envoi-recepteur.log 2>&1 & sleep 3
head -c 3000000 /dev/urandom > /tmp/essai-envoi.bin; echo "bonjour" > /tmp/essai-envoi.txt
r=$(xiii-envoi --envoyer 127.0.0.1 /tmp/essai-envoi.bin /tmp/essai-envoi.txt 2>&1 | tail -1)
f=$(find /root -path "*Reçus*" -name "essai-envoi.bin" 2>/dev/null | head -1)
if [ -n "$f" ] && cmp -s "$f" /tmp/essai-envoi.bin; then echo "OK        Envoi XIII : $r (fichier identique à l'arrivée)" >> $R; else echo "ÉCHEC     Envoi XIII : $r · reçu=$f" >> $R; fi
python3 -c "$CFG"'config.modifier(envoi_actif=False)'
r=$(xiii-envoi --envoyer 127.0.0.1 /tmp/essai-envoi.txt 2>&1 | tail -1)
case "$r" in *Refus*) echo "OK        Envoi XIII : réception désactivée → $r" >> $R;; *) echo "ÉCHEC     Envoi XIII refus attendu : $r" >> $R;; esac
python3 -c "$CFG"'config.modifier(envoi_actif=True)'
curl -s http://127.0.0.1:53317/api/localsend/v2/info | python3 -c 'import sys,json; d=json.load(sys.stdin); print("OK        LocalSend /info :", d["alias"], d["version"], d["protocol"])' >> $R 2>&1
xiii-envoi /tmp/essai-envoi.bin /tmp/essai-envoi.txt > /out/app-envoi.log 2>&1 & sleep 5; grim -s 0.5 /out/app-envoi.png; pkill -f "essai-envoi.bin"; sleep 1

echo "== Phase H (logiciels, Stream Deck, polices, Resolve, VM)" >> $R
python3 -c 'import sys; sys.path.insert(0,"/usr/lib/xiii"); from xiii import streamdeck; streamdeck.apercu("/out/streamdeck-pages.png")' >> $R 2>&1
python3 -c 'import sys; sys.path.insert(0,"/usr/lib/xiii"); from xiii import windows as W; import json; r=W.profil("setup", {"produit":"X32-Edit","editeur":"Behringer"}); print("OK        Wine : setup.exe de « X32-Edit » reconnu →", (r or {}).get("note","AUCUN")[:60])' >> $R 2>&1
python3 -c 'import sys; sys.path.insert(0,"/usr/lib/xiii"); from xiii import logiciels_plus as L, logiciels as C; R=L.chercher_partout("vlc", C.CATALOGUE); print("OK        recherche partout « vlc » :", ", ".join("%s %d" % (k, len(v)) for k, v in R) or "AUCUN RÉSULTAT")' >> $R 2>&1
python3 -c 'import sys; sys.path.insert(0,"/usr/lib/xiii"); from xiii import logiciels_plus as L; F=L.fiche("flatpak:org.videolan.VLC"); print("OK        fiche VLC :", F.get("version"), "·", F.get("popularite"), "·", len(F.get("captures", [])), "captures", F.get("erreur",""))' >> $R 2>&1
xiii-logiciels > /out/app-logiciels2.log 2>&1 & sleep 6; grim -s 0.5 /out/logiciels-accueil.png; pkill -f "xiii.logiciels import"; sleep 1
xiii-logiciels --page packs > /dev/null 2>&1 & sleep 5; grim -s 0.5 /out/logiciels-packs.png; pkill -f "xiii.logiciels import"; sleep 1
xiii-logiciels --page maj > /dev/null 2>&1 & sleep 12; grim -s 0.5 /out/logiciels-maj.png; pkill -f "xiii.logiciels import"; sleep 1
for app in xiii-polices xiii-resolve xiii-vm; do $app > /out/$app.log 2>&1 & sleep 6; grim -s 0.5 /out/$app.png; pkill -f "$app" ; pkill -f "xiii.$(echo $app | cut -c6-) import"; sleep 1; done

echo "== Calendrier : comptes en lecture / écriture (CalDAV)" >> $R
python3 -m venv /tmp/rv >/dev/null 2>&1 && /tmp/rv/bin/pip install -q radicale >/dev/null 2>&1
mkdir -p /tmp/radi && printf '[server]\nhosts = 127.0.0.1:5232\n[auth]\ntype = none\n[storage]\nfilesystem_folder = /tmp/radi/data\n' > /tmp/radi/conf
/tmp/rv/bin/python -m radicale --config /tmp/radi/conf > /tmp/radi/log 2>&1 & sleep 3
curl -s -u zz:x -X MKCALENDAR http://127.0.0.1:5232/zz/tournage/ -o /dev/null -w "INFO      MKCALENDAR %{http_code}\n" >> $R
python3 "${GITHUB_WORKSPACE:-.}/tests/caldav_test.py" >> $R 2>&1 || echo "ÉCHEC     test CalDAV (voir zz.txt)" >> $R
pkill -f radicale

echo "== Barre des tâches : position et forme" >> $R

for c in ; do LD_PRELOAD=$(ls /usr/lib/*/libgtk4-layer-shell.so.0 | head -1) timeout 10 python3 "${GITHUB_WORKSPACE:-.}/tests/repro_layer.py" $c > /out/repro-$c.log 2>&1; echo "INFO      repro $c : $(grep -E "OK|Error|error" /out/repro-$c.log | tail -2 | tr '\n' ' ')" >> $R; done
for pf in "gauche classique" "haut flottante" "droite dock" "bas flottante"; do set -- $pf
  python3 -c "$CFG"'config.modifier(barre_position="'$1'", barre_forme="'$2'")'; sleep 2.5; grim -s 0.5 /out/barre-$1-$2.png
  python3 -c "import sys; sys.path.insert(0,'/usr/lib/xiii')" ; gapplication action fr.xiii.Shell basculer "'demarrer'" 2>/dev/null; sleep 1; grim -s 0.5 /out/barre-$1-$2-menu.png; gapplication action fr.xiii.Shell fermer 2>/dev/null; sleep 0.5
done
python3 -c "$CFG"'config.modifier(barre_position="bas", barre_forme="dock")'; sleep 2.5; grim -s 0.5 /out/dock-cache.png
xiii-ctl dock; sleep 1; grim -s 0.5 /out/dock-montre.png
mousepad /root/Bureau/Notes.txt >/dev/null 2>&1 & sleep 2
python3 -c "$CFG"'config.modifier(barre_position="bas", barre_forme="ile")'; sleep 3; grim -s 0.5 /out/ile-repliee.png
xiii-ctl ile; sleep 1.2; grim -s 0.5 /out/ile-ouverte.png; xiii-ctl ile; sleep 0.5
xiii-ctl minuteur-5; sleep 2.5; grim -s 0.5 /out/ile-minuteur.png
xiii-ctl ile; sleep 1.2; grim -s 0.5 /out/ile-minuteur-ouverte.png; xiii-ctl ile; xiii-ctl minuteur-zero; sleep 0.5
# faux Tally XIII sur le port 8790 : caméra 2 au programme, 3 en preview
python3 -c 'import http.server,json
class H(http.server.BaseHTTPRequestHandler):
    def do_GET(s):
        b=json.dumps({"cameras":{"2":{"etat":"programme","nom":"Cam 2"},"3":{"etat":"preview","nom":"Grue"}}}).encode(); s.send_response(200); s.end_headers(); s.wfile.write(b)
    def log_message(s,*a): pass
http.server.HTTPServer(("127.0.0.1",8790),H).serve_forever()' & TPID=$!; sleep 4.5; grim -s 0.5 /out/ile-tally.png
xiii-ctl ile; sleep 1.2; grim -s 0.5 /out/ile-tally-ouverte.png; xiii-ctl ile; kill $TPID; sleep 0.5
python3 -c "$CFG"'config.modifier(barre_position="haut")'; sleep 2.5; xiii-ctl ile; sleep 1.2; grim -s 0.5 /out/ile-haut-ouverte.png; xiii-ctl ile; pkill mousepad
python3 -c "$CFG"'config.modifier(barre_position="bas", barre_forme="dock", barre_taille="grande")'; sleep 2.5; xiii-ctl dock; sleep 1; grim -s 0.5 /out/dock-grand.png
python3 -c "$CFG"'config.modifier(barre_forme="classique", barre_taille="petite")'; sleep 2.5; grim -s 0.5 /out/barre-petite.png
python3 -c "$CFG"'config.modifier(barre_taille="normale")'; sleep 1
python3 -c "$CFG"'config.modifier(barre_position="bas", barre_forme="classique")'; sleep 2
pgrep -f "xiii.shell import" >/dev/null || { echo "FERMÉE    xiii-shell pendant les essais de la barre"; grep -E "Error" /out/shell.log | tail -3; } >> $R
pgrep -f "xiii.shell import" >/dev/null || { xiii-shell >> /out/shell.log 2>&1 & sleep 6; }
grep -q Traceback /out/shell.log && { echo "PLANTAGE  barre (position / forme)"; grep -A6 Traceback /out/shell.log | tail -8; } >> $R || echo "OK        barre en bas / haut / gauche / droite, classique / flottante / dock : sans erreur" >> $R

echo "== Thèmes Façon Windows 11 et Façon macOS" >> $R
ls /usr/share/icons | grep -E "^(Fluent|WhiteSur)" | tr '\n' ' ' | sed 's/^/INFO      icônes : /' >> $R; echo >> $R
fc-list | grep -ciE "selawik|/Inter" | sed 's/^/INFO      polices Selawik + Inter : /' >> $R
python3 -c "$CFG"'config.modifier(barre_forme="flottante", barre_position="bas", barre_taille="petite")'; sleep 2
for v in clair sombre; do
  python3 -c "$CFG"'config.modifier(theme="onze", imitation_apparence="'$v'")'; sleep 4
  mousepad /root/Bureau/Notes.txt >/dev/null 2>&1 & sleep 2.5; grim -s 0.5 /out/onze-$v.png; grim /out/onze-$v-plein.png
  gapplication action fr.xiii.Shell basculer "'demarrer'"; sleep 1.2; grim -s 0.5 /out/onze-$v-demarrer.png; gapplication action fr.xiii.Shell fermer; sleep 0.4
  gapplication action fr.xiii.Shell basculer "'wifi'"; sleep 1.2; grim -s 0.5 /out/onze-$v-reglages-rapides.png; gapplication action fr.xiii.Shell fermer; sleep 0.4
  gapplication action fr.xiii.Shell basculer "'volet'"; sleep 1.2; grim -s 0.5 /out/onze-$v-notifications.png; gapplication action fr.xiii.Shell fermer; sleep 0.4
  xiii-parametres --page theme > /out/onze-p.log 2>&1 & sleep 3.5; grim -s 0.5 /out/onze-$v-parametres.png; pkill -f xiii.parametres; pkill mousepad; sleep 0.5
done
grep -A12 "<theme>" /root/.config/labwc/rc.xml | grep -E "name>|layout" | tr -s ' ' | sed 's/^/INFO      labwc : /' >> $R
for v in clair sombre; do
  python3 -c "$CFG"'config.modifier(theme="macos", imitation_apparence="'$v'")'; sleep 4
  mousepad /root/Bureau/Notes.txt >/dev/null 2>&1 & sleep 2.5; grim -s 0.5 /out/macos-$v.png; grim /out/macos-$v-plein.png
  xiii-ctl menu-mac-3; sleep 1; grim -s 0.5 /out/macos-$v-menu-edition.png; gapplication action fr.xiii.Shell fermer; xiii-ctl menu-mac-3; sleep 0.4
  xiii-ctl launchpad; sleep 1.5; grim -s 0.5 /out/macos-$v-launchpad.png; gapplication action fr.xiii.Shell fermer; sleep 0.5
  xiii-ctl spotlight; sleep 1; wtype "mou"; sleep 1.2; grim -s 0.5 /out/macos-$v-spotlight.png; gapplication action fr.xiii.Shell fermer; sleep 0.4
  gapplication action fr.xiii.Shell basculer "'centre'"; sleep 1.2; grim -s 0.5 /out/macos-$v-centre.png; gapplication action fr.xiii.Shell fermer; sleep 0.4
  xiii-parametres --page theme > /out/macos-p.log 2>&1 & sleep 3.5; grim -s 0.5 /out/macos-$v-parametres.png; pkill -f xiii.parametres; pkill mousepad; sleep 0.5
done
grep -A12 "<theme>" /root/.config/labwc/rc.xml | grep -E "name>|layout" | tr -s ' ' | sed 's/^/INFO      labwc : /' >> $R
python3 -c "$CFG"'config.modifier(theme="sombre")'; sleep 4
python3 -c "$CFG"'c=config.charger(); print("OK        retour au thème XIII : barre d avant rendue" if (c["barre_forme"], c["barre_taille"]) == ("flottante", "petite") and not c.get("avant_imitation") else "ÉCHEC     retour au thème XIII : barre %s %s" % (c["barre_forme"], c["barre_taille"]))' >> $R
grim -s 0.5 /out/imitation-retour.png
python3 -c "$CFG"'config.modifier(barre_forme="classique", barre_taille="normale")'; sleep 2
pgrep -f "xiii.shell import" >/dev/null || { echo "FERMÉE    xiii-shell pendant les thèmes Windows 11 / macOS"; grep -E "Error" /out/shell.log | tail -3; xiii-shell >> /out/shell.log 2>&1 & sleep 6; } >> $R
grep -q Traceback /out/shell.log && { echo "PLANTAGE  thèmes Windows 11 / macOS"; grep -A8 Traceback /out/shell.log | tail -10; } >> $R || echo "OK        thèmes Façon Windows 11 et Façon macOS : sans erreur" >> $R
for f in /out/onze-p.log /out/macos-p.log; do grep -q Traceback $f && { echo "PLANTAGE  Paramètres (thème imité)"; grep -A6 Traceback $f | tail -7; } >> $R; done

echo "== Icônes XIII (changer le logo d'une appli)" >> $R
xiii-icones --test 2>&1 | tail -1 | sed 's/^/INFO      bibliothèques : /' >> $R
xiii-icones --app xiii-fichiers.desktop > /out/icones.log 2>&1 & sleep 4; grim -s 0.5 /out/app-icones.png
python3 -c 'import gi; gi.require_version("Gtk","4.0"); from gi.repository import Gio; import sys; sys.path.insert(0,"/usr/lib/xiii"); from xiii import icones_perso as IP
a=Gio.DesktopAppInfo.new("xiii-fichiers.desktop"); s=IP.dessiner("tabler","folder-heart","#ffffff",2,"degrade","#e05a8a") or IP.dessiner("lucide","folder-heart","#ffffff",2,"degrade","#e05a8a"); print("OK        logo appliqué :", IP.appliquer(a, svg=s))' >> $R 2>&1
sleep 2.5; grim -s 0.5 /out/icones-barre-perso.png
python3 -c 'import gi; gi.require_version("Gtk","4.0"); from gi.repository import Gio; import sys,os; sys.path.insert(0,"/usr/lib/xiii"); from xiii import icones_perso as IP
a=Gio.DesktopAppInfo.new("xiii-fichiers.desktop"); print("OK        logo vu par les applis :", a.get_icon().to_string()) if IP.personnalisee(a) else print("ÉCHEC     logo personnalisé non pris en compte")
print("OK        logo d origine rétabli" if IP.retablir(a) and not os.path.exists(os.path.expanduser("~/.local/share/applications/xiii-fichiers.desktop")) else "ÉCHEC     retour au logo d origine")' >> $R 2>&1
sleep 1; pkill -f "xiii.icones"; grep -q Traceback /out/icones.log && { echo "PLANTAGE  Icônes XIII"; grep -A6 Traceback /out/icones.log | tail -7; } >> $R

echo "== Fonds d'écran en anneau" >> $R
F0=$(python3 -c "$CFG"'print(config.charger()["fond"])')
xiii-fonds > /out/fonds.log 2>&1 & sleep 3.5; grim -s 0.5 /out/fonds-anneau.png
wtype -k Right; sleep 1.2; grim -s 0.5 /out/fonds-anneau-tourne.png
wtype -k Return; sleep 1.5
F1=$(python3 -c "$CFG"'print(config.charger()["fond"])')
[ "$F0" != "$F1" ] && echo "OK        anneau : fond changé ($(basename "$F1"))" >> $R || echo "ÉCHEC     anneau : le fond n'a pas changé" >> $R
wtype -k Escape; sleep 1
pgrep -f "xiii.fonds import" >/dev/null && { echo "ÉCHEC     anneau : Échap ne ferme pas"; pkill -f "xiii.fonds import"; } >> $R
grep -q Traceback /out/fonds.log && { echo "PLANTAGE  Fonds d'écran"; grep -A6 Traceback /out/fonds.log | tail -7; } >> $R
python3 -c "$CFG"'config.modifier(fond="'"$F0"'")'; sleep 1

echo "== Diffuser l'écran (navigateur du réseau)" >> $R
xiii-diffuser --serveur --duree 12 > /out/diffusion.log 2>&1 & sleep 5
curl -s -m 3 http://127.0.0.1:8791/ | grep -q "flux.mjpg" && echo "OK        diffusion : page servie" >> $R || echo "ÉCHEC     diffusion : page absente" >> $R
curl -s -m 4 http://127.0.0.1:8791/flux.mjpg -o /tmp/flux.bin; n=$(grep -ac "Content-Type: image/" /tmp/flux.bin 2>/dev/null)
[ "${n:-0}" -gt 2 ] && echo "OK        diffusion : $n images reçues en 4 s par un navigateur" >> $R || echo "ÉCHEC     diffusion : ${n:-0} image reçue" >> $R
curl -s -m 3 http://127.0.0.1:8791/image.jpg -o /out/diffusion-image.jpg
sleep 8; cat /out/diffusion.log | grep -E "moteur|Traceback" | sed 's/^/INFO      /' >> $R
tail -2 /tmp/xiii-diffusion-wf-recorder.log 2>/dev/null | tr -d '\r' | cut -c1-160 | sed 's/^/INFO      wf-recorder : /' >> $R
xiii-diffuser > /out/diffuser.log 2>&1 & sleep 3; grim -s 0.5 /out/app-diffuser.png; pkill -f "xiii.diffusion"
grep -q Traceback /out/diffuser.log && { echo "PLANTAGE  Diffuser XIII"; grep -A6 Traceback /out/diffuser.log | tail -7; } >> $R

echo "== Effet Mica, barre masquée automatiquement, barre Tournage" >> $R
python3 -c "$CFG"'config.modifier(flou_panneaux=True)'; sleep 3; grim -s 0.5 /out/mica-barre.png
gapplication action fr.xiii.Shell basculer "'demarrer'"; sleep 1.5; grim -s 0.5 /out/mica-demarrer.png; gapplication action fr.xiii.Shell fermer; sleep 0.5
python3 -c "$CFG"'config.modifier(flou_panneaux=False, barre_auto=True)'; sleep 2.5; grim -s 0.5 /out/barre-auto-cachee.png
xiii-ctl dock; sleep 1; grim -s 0.5 /out/barre-auto-montree.png
python3 -c "$CFG"'config.modifier(barre_auto=False, profil="tournage", mode_tournage=True)'; sleep 3.5; grim -s 0.5 /out/barre-tournage.png
python3 -c "$CFG"'config.modifier(profil="normal", mode_tournage=False)'; sleep 2
pgrep -f "xiii.shell import" >/dev/null || { echo "FERMÉE    xiii-shell (Mica, masquage, Tournage)"; xiii-shell >> /out/shell.log 2>&1 & sleep 6; } >> $R
grep -q Traceback /out/shell.log && { echo "PLANTAGE  Mica / masquage / Tournage"; grep -A8 Traceback /out/shell.log | tail -10; } >> $R || echo "OK        effet Mica, barre masquée automatiquement, barre Tournage : sans erreur" >> $R

echo "== Pack conseillé (icônes dans le menu, téléchargement au premier lancement)" >> $R
n=$(ls /usr/share/applications/xiii-pack-*.desktop 2>/dev/null | wc -l); m=$(ls /usr/share/icons/hicolor/*/apps/xiii-pack-* 2>/dev/null | wc -l)
[ "$n" -ge 20 ] && [ "$m" -ge 20 ] && echo "OK        pack : $n raccourcis et $m icônes" >> $R || echo "ÉCHEC     pack : $n raccourcis, $m icônes" >> $R
gapplication action fr.xiii.Shell basculer "'demarrer-toutes'"; sleep 1.2; wtype "o"; sleep 1.5; grim -s 0.5 /out/pack-menu.png; gapplication action fr.xiii.Shell fermer; sleep 0.5
xiii-pack czkawka > /out/pack.log 2>&1 & sleep 6; grim -s 0.5 /out/pack-premier-lancement.png; pkill -f "xiii.pack import"
grep -q Traceback /out/pack.log && { echo "PLANTAGE  premier lancement d'un logiciel du pack"; grep -A6 Traceback /out/pack.log | tail -7; } >> $R || echo "OK        premier lancement : fenêtre d'installation sans erreur" >> $R

echo "== Horloge, concentration, vignette, animations, menus macOS, dossiers, devises" >> $R
python3 - >> $R 2>&1 <<'PY'
import sys, datetime, json, os; sys.path.insert(0, "/usr/lib/xiii")
from xiii import horloge as H, concentration as C, conversions as V, config
d = H.charger(); d["alarmes"] = [{"id": "t1", "h": 7, "m": 30, "jours": [0, 1, 2, 3, 4], "nom": "Réveil", "on": True}, {"id": "t2", "h": 7, "m": 30, "jours": [], "nom": "Une fois", "on": True}]; H.enregistrer(d)
lun = datetime.datetime(2026, 11, 30, 7, 30); sam = datetime.datetime(2026, 11, 28, 7, 30)
a1 = [x["nom"] for x in H.alarmes_dues(lun)]; a2 = H.alarmes_dues(lun); a3 = [x["nom"] for x in H.alarmes_dues(sam)]
ok = a1 == ["Réveil", "Une fois"] and a2 == [] and a3 == []
print(("OK        " if ok else "ÉCHEC     ") + "alarmes : lundi 7 h 30 %s, 2e passage %s, samedi %s" % (a1, a2, a3))
H.enregistrer({"villes": ["New York", "Tokyo"], "alarmes": []})
cfg = dict(config.DEFAUTS); cfg["concentration_modes"] = {"sommeil": {"horaires": {"on": True, "debut": "23:00", "fin": "07:00", "jours": [4]}}}
n1 = datetime.datetime(2026, 11, 27, 23, 30); n2 = datetime.datetime(2026, 11, 28, 6, 59); n3 = datetime.datetime(2026, 11, 28, 7, 1)
r = (C.actif(cfg, n1), C.actif(cfg, n2), C.actif(cfg, n3))
cfg2 = dict(config.DEFAUTS, concentration="travail")
lp = (C.laisse_passer(cfg2, "Slack"), C.laisse_passer(cfg2, "Steam"), C.laisse_passer(cfg2, "Steam", 2))
ok = r[0] and r[0][0] == "sommeil" and r[1] and not r[2] and lp == (True, False, True)
print(("OK        " if ok else "ÉCHEC     ") + "concentration : horaires de nuit %s, Travail laisse passer Slack/Steam/urgent %s" % ([x and x[0] for x in r], lp))
V.F_DEVISES = "/tmp/devises.json"
V.maj_devises("<Cube time='2026-11-27'><Cube currency='USD' rate='1.08'/><Cube currency='GBP' rate='0.84'/></Cube>")
dv = V.devises("100 usd en eur"); df = V.extraire_definitions("== Français ==\n=== Nom commun ===\nchat \\ʃa\\ masculin\nMammifère carnivore félin domestiqué de taille moyenne.\n== Anglais ==\n")
ok = dv and dv[0].startswith("100 USD = 92,59 EUR") and df and df[0][1].startswith("Mammifère") and V.mot_a_definir("définition de chat") == "chat"
print(("OK        " if ok else "ÉCHEC     ") + "recherche : devises %s, définition %s" % (dv[:1], df[:1]))
from xiii import imitation_bureau as IB
m = IB.menus_de("firefox-esr"); f = IB.menus_de("fr.xiii.fichiers")
print(("OK        " if m and f and "Historique" in [t for t, _ in m] and "Aller" in [t for t, _ in f] and IB.menus_de("inconnu") is None else "ÉCHEC     ") + "menus macOS par appli : Firefox %s, Fichiers %s" % ([t for t, _ in m], [t for t, _ in f]))
from xiii.anim_fenetres import AnimFenetres
class F:
    def __init__(s, i, red=False): s.id, s.reduite = i, red
class Sh: cfg = {"animations": True}
an = AnimFenetres(Sh()); vus = []; an.jouer = lambda s_, b: vus.append(s_)
import gi; from gi.repository import GLib
an.changement([F(1)], lambda: {}, lambda f: "a"); an.changement([F(1), F(2)], lambda: {}, lambda f: "a"); an.changement([F(1, True)], lambda: {}, lambda f: "a")
ctx = GLib.MainContext.default()
import time; t = time.time()
while time.time() - t < .3: ctx.iteration(False)
print(("OK        " if vus == ["ouvrir", "reduire", "fermer"] else "ÉCHEC     ") + "animations des fenêtres : événements %s" % vus)
from xiii.shell import EST_PIP
print(("OK        " if EST_PIP("Picture-in-Picture") and EST_PIP("Vignette XIII — film.mp4") and not EST_PIP("Firefox") else "ÉCHEC     ") + "vignettes vidéo reconnues (toujours au premier plan)")
PY
xiii-horloge --sonner "Test ZZ" > /out/horloge-sonne.log 2>&1 & sleep 3; grim -s 0.5 /out/horloge-sonnerie.png
verifier "Horloge › sonnerie d'alarme" "xiii.horloge" /out/horloge-sonne.log; pkill -f "xiii.horloge"; pkill -f alarm-clock-elapsed; sleep 0.5
xiii-ctl concentration-travail; sleep 1.5; grim -s 0.5 /out/concentration-barre.png
gapplication action fr.xiii.Shell basculer "'centre'"; sleep 1.2; grim -s 0.5 /out/concentration-centre.png; gapplication action fr.xiii.Shell fermer
xiii-ctl concentration-off; sleep 0.5
python3 -c 'import sys; sys.path.insert(0,"/usr/lib/xiii"); from xiii import config; c=config.charger(); print("OK        concentration activée puis coupée depuis xiii-ctl" if c.get("concentration") is None else "ÉCHEC     concentration : %r" % c.get("concentration"))' >> $R
python3 -c 'import xml.etree.ElementTree as E; E.parse("/etc/skel/.config/labwc/rc.xml")' 2>/dev/null && grep -q 'title="Picture-in-Picture"' /etc/skel/.config/labwc/rc.xml && grep -q "xiii-ctl epingle" /etc/skel/.config/labwc/rc.xml \
  && echo "OK        rc.xml : règles des vignettes vidéo + Ctrl+Super+T signalé à la barre" >> $R || echo "ÉCHEC     rc.xml (vignettes / épingle)" >> $R
grep -q Traceback /out/shell.log && { echo "PLANTAGE  barre (après concentration)"; grep -A8 Traceback /out/shell.log | tail -9; } >> $R

echo "== Bureaux virtuels, captures avancées, presse-papiers avec le téléphone" >> $R
B0=$(python3 -c 'import sys; sys.path.insert(0,"/usr/lib/xiii"); from xiii import bureaux; print(bureaux.lire()[0])')
xiii-ctl bureau-nouveau; sleep 1.5
python3 -c 'import sys; sys.path.insert(0,"/usr/lib/xiii"); from xiii import bureaux; bureaux.renommer(1, "Montage")'
xiii-ctl bureau-est-2; sleep 0.5; xiii-ctl vue; sleep 1.5; grim -s 0.5 /out/bureaux-vue.png; wtype -k Escape; sleep 0.4
python3 - "$B0" >> $R 2>&1 <<'PY'
import sys; sys.path.insert(0, "/usr/lib/xiii"); from xiii import bureaux
n, noms = bureaux.lire(); b0 = int(sys.argv[1])
ok = n == b0 + 1 and noms[0] == "Montage" and bureaux.courant() == 2
print(("OK        " if ok else "ÉCHEC     ") + "bureaux virtuels : %d → %d bureaux %s, bureau affiché %d" % (b0, n, noms, bureaux.courant()))
PY
xiii-ctl bureau-retirer; sleep 1
python3 -c 'import sys; sys.path.insert(0,"/usr/lib/xiii"); from xiii import bureaux; n=bureaux.lire()[0]; print(("OK        bureau retiré (%d), retour au bureau %d" if bureaux.courant() <= n else "ÉCHEC     bureau retiré : %d bureaux, courant %d") % (n, bureaux.courant()))' >> $R
python3 -c 'import sys; sys.path.insert(0,"/usr/lib/xiii"); from xiii import bureaux; bureaux.renommer(1, "Bureau 1")'
# reconnaissance de caractères et QR code (outils utilisés par xiii-capture texte / qr)
python3 -c 'from PIL import Image, ImageDraw, ImageFont; im=Image.new("RGB",(900,120),"white"); d=ImageDraw.Draw(im); d.text((20,30),"Réunion de production à 14 heures",fill="black",font=ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",44)); im.save("/tmp/ocr.png")'
o=$(tesseract /tmp/ocr.png - -l fra+eng --psm 6 2>/dev/null | tr -s ' \n' ' ')
echo "$o" | grep -qi "production" && echo "OK        copier le texte d'une zone : « $(echo $o | head -c 60) »" >> $R || echo "ÉCHEC     reconnaissance de caractères : « $o »" >> $R
qrencode -o /tmp/qr.png -s 6 "https://os-xiii.fr/test"; q=$(zbarimg -q --raw /tmp/qr.png 2>/dev/null)
[ "$q" = "https://os-xiii.fr/test" ] && echo "OK        lire un QR code à l'écran : $q" >> $R || echo "ÉCHEC     lecture du QR code : « $q »" >> $R
ffmpeg -loglevel error -y -f lavfi -i testsrc=duration=1:size=320x240:rate=10 -pix_fmt yuv420p /tmp/rec.mp4 && \
ffmpeg -loglevel error -y -i /tmp/rec.mp4 -vf "fps=12,scale='min(960,iw)':-1:flags=lanczos,split[a][b];[a]palettegen=stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=4" /tmp/rec.gif
[ -s /tmp/rec.gif ] && echo "OK        enregistrement en GIF animé : conversion ($(du -k /tmp/rec.gif | cut -f1) Ko)" >> $R || echo "ÉCHEC     conversion GIF" >> $R
echo "$(($(date +%s) - 65)) gif" > ${XDG_RUNTIME_DIR:-/tmp}/xiii-enregistrement; sleep 2.2; grim -s 0.5 /out/enregistrement-pastille.png; rm -f ${XDG_RUNTIME_DIR:-/tmp}/xiii-enregistrement
python3 - >> $R 2>&1 <<'PY'
import sys, json, time, subprocess, urllib.request; sys.path.insert(0, "/usr/lib/xiii")
from xiii.presse_telephone import Serveur
try:
  sv = Serveur(port=8790)  ; sv.demarrer(); base = "http://127.0.0.1:%d" % sv.port
  try: urllib.request.urlopen(base + "/etat?k=faux", timeout=3); refus = False
  except Exception as e: refus = "403" in str(e)
  urllib.request.urlopen(urllib.request.Request(base + "/envoyer?k=" + sv.cle, data="Bonjour du téléphone".encode(), method="POST"), timeout=5)
  time.sleep(0.5); pc = subprocess.run(["wl-paste", "--no-newline"], capture_output=True, text=True, timeout=3).stdout
  subprocess.run(["wl-copy"], input=b"Texte du PC", timeout=3); time.sleep(0.5)
  et = json.loads(urllib.request.urlopen(base + "/etat?k=" + sv.cle, timeout=5).read())
  page = urllib.request.urlopen(base + "/?k=" + sv.cle, timeout=5).read().decode()
  sv.arreter()
  ok = refus and pc == "Bonjour du téléphone" and et["texte"] == "Texte du PC" and "Envoyer au PC" in page
  print(("OK        " if ok else "ÉCHEC     ") + "presse-papiers avec le téléphone : clé exigée %s, téléphone → PC « %s », PC → téléphone « %s »" % (refus, pc, et.get("texte")))
except Exception as e:
  print("ÉCHEC     presse-papiers avec le téléphone : %s" % e)
PY
grep -q Traceback /out/shell.log && { echo "PLANTAGE  barre (après bureaux / enregistrement)"; grep -A8 Traceback /out/shell.log | tail -9; } >> $R

echo "== Outils du quotidien (redimensionner, listes de raccourcis, pipette)" >> $R
mkdir -p /tmp/redim; cp /usr/share/xiii/wallpapers/xiii-sombre.png /tmp/redim/photo.png
xiii-outil redimensionner --largeur 640 --format jpg /tmp/redim/photo.png > /tmp/redim.log 2>&1
python3 -c 'from PIL import Image; im=Image.open("/tmp/redim/photo (640).jpg"); print("OK        redimensionner : %dx%d en JPEG" % im.size if im.width == 640 else "ÉCHEC     redimensionner : %r" % (im.size,))' >> $R 2>&1 || echo "ÉCHEC     redimensionner : $(tail -2 /tmp/redim.log)" >> $R
python3 -c 'import sys; sys.path.insert(0,"/usr/lib/xiii"); from xiii.outils import lire_ppm; print("OK        pipette : lecture du pixel" if lire_ppm(b"P6\n1 1\n255\n\x12\x34\x56") == (18, 52, 86) else "ÉCHEC     pipette")' >> $R 2>&1
mkdir -p /root/.local/share; cat > /root/.local/share/recently-used.xbel <<'XBEL'
<?xml version="1.0" encoding="UTF-8"?>
<xbel version="1.0" xmlns:bookmark="http://www.freedesktop.org/standards/desktop-bookmarks">
<bookmark href="file:///root/Bureau/Notes.txt" added="2026-11-28T08:00:00Z" modified="2026-11-28T08:00:00Z" visited="2026-11-28T08:00:00Z">
<info><metadata owner="http://freedesktop.org"><mime:mime-type type="text/plain"/><bookmark:applications><bookmark:application name="Mousepad" exec="&apos;mousepad %u&apos;" modified="2026-11-28T08:00:00Z" count="1"/></bookmark:applications></metadata></info></bookmark>
</xbel>
XBEL
python3 -c 'import gi; gi.require_version("Gtk","4.0"); import sys; sys.path.insert(0,"/usr/lib/xiii"); from xiii import apps
a=apps.par_id("org.xfce.mousepad.desktop") or apps.pour_fenetre("mousepad"); r=apps.recents_de(a) if a else []
print("OK        liste de raccourcis : fichiers récents de Mousepad (%s), %d action(s)" % (", ".join(r), len(a.list_actions())) if "/root/Bureau/Notes.txt" in r else "ÉCHEC     liste de raccourcis : %r" % r)' >> $R 2>&1

echo "== Modes sans barre des tâches (applis ouvertes en tuiles)" >> $R
mousepad /root/Bureau/Notes.txt >/dev/null 2>&1 & sleep 2
python3 -c "$CFG"'config.modifier(mode_bureau="fiction", haut_applis=True)'; sleep 4; grim -s 0.5 /out/mode-fiction-applis.png
python3 -c "$CFG"'config.modifier(mode_bureau="classique")'; sleep 2
python3 -c "$CFG"'config.modifier(production_page="accueil", mode_bureau="production")'; sleep 4; grim -s 0.5 /out/mode-production-applis.png
python3 -c "$CFG"'config.modifier(mode_bureau="classique", haut_applis=False)'; sleep 2; pkill mousepad; sleep 1
grep -q Traceback /out/shell.log && { echo "PLANTAGE  modes sans barre"; grep -A6 Traceback /out/shell.log | tail -8; } >> $R || echo "OK        modes sans barre des tâches : sans erreur" >> $R

echo "== Étape 4 (bureau)" >> $R
mousepad /root/Bureau/Notes.txt >/dev/null 2>&1 & sleep 2; mousepad --new-window >/dev/null 2>&1 & sleep 2
xiii-ctl alttab; sleep 0.3; grim -s 0.5 /out/alttab.png; sleep 1
xiii-ctl bureau; sleep 1; grim -s 0.5 /out/bureau-affiche.png; xiii-ctl bureau; sleep 1
grep -q Traceback /out/shell.log && { echo "PLANTAGE  bureau (étape 4)"; grep -A6 Traceback /out/shell.log | tail -8; } >> $R || echo "OK        Alt+Tab, Afficher le bureau : sans erreur" >> $R
pkill mousepad; sleep 1

echo "== Étape 3 (capture, heure, son, webcam)" >> $R
xiii-outil-capture > /out/xiii-outil-capture.log 2>&1 & sleep 3; grim -s 0.5 /out/app-outil-capture.png
pgrep -f "capture import main" >/dev/null && echo "OK        Outil Capture ouvert" >> $R || { echo "FERMÉE    Outil Capture"; tail -4 /out/xiii-outil-capture.log; } >> $R
pkill -f "capture import main"; sleep 1
grep -q Traceback /out/xiii-outil-capture.log && { echo "PLANTAGE  Outil Capture"; tail -6 /out/xiii-outil-capture.log; } >> $R
xiii-parametres --page heure > /out/p.log 2>&1 & sleep 4; grim -s 0.5 /out/page-heure-manuelle.png; pkill -f xiii.parametres; sleep 1
python3 -c 'import sys; sys.path.insert(0,"/usr/lib/xiii"); from xiii import systeme as S; print("OK        sorties multiples (démo) :", S.sorties_multiples(["a","b"]))' >> $R 2>&1

echo "== Cloud hors ligne (copie locale synchronisée)" >> $R
rclone version 2>/dev/null | head -1 | sed 's/^/INFO      /' >> $R
rclone config create xiii-cloud-test local >/dev/null 2>&1; mkdir -p /tmp/cloud/XIII/Concert; echo devis > /tmp/cloud/XIII/Concert/devis.txt
python3 - >> $R 2>&1 <<'P'
import sys, os, json; sys.path.insert(0, "/usr/lib/xiii")
from xiii import lecteurs as L
L.sauver([{"nom": "Cloud test", "type": "onedrive"}]); L.ident = lambda n: "xiii-cloud-test"
L.ajouter_hors_ligne({"nom": "Cloud test"}, "/tmp/cloud/XIII", "/tmp/local-xiii")
l, d = L.hors_ligne()[0]; ok, m = L.synchroniser_un(l, d)
a = os.path.exists("/tmp/local-xiii/Concert/devis.txt")
if not a: print("ÉCHEC     hors ligne, premier téléchargement :", ok, m[-300:]); raise SystemExit
open("/tmp/local-xiii/Concert/note.txt", "w").write("ajout local")
l, d = L.hors_ligne()[0]; ok2, m2 = L.synchroniser_un(l, d)
b = os.path.exists("/tmp/cloud/XIII/Concert/note.txt")
print(("OK        " if ok and a and ok2 and b else "ÉCHEC     ") + "hors ligne : téléchargé %s, renvoyé vers le cloud %s %s" % (a, b, (m or m2)[:200]))
P

echo "== Mise à jour d'OS XIII (depuis GitHub, comme Paramètres › Mises à jour)" >> $R
echo "# ancienne version" >> /usr/lib/xiii/xiii/modes.py; printf '{"version": "ancienne", "branche": "beta", "commit": "4087913"}' > /usr/share/xiii/VERSION.json
v=$(python3 -c 'import sys; sys.path.insert(0,"/usr/lib/xiii"); from xiii import maj; r=maj.verifier("beta"); print(r["dispo"], r["distant"], len(r["nouveautes"]))' 2>&1)
echo "INFO      vérification : $v" >> $R
sha=${GITHUB_SHA:-beta}; XIII_MAJ_TEST=1 timeout 300 xiii-maj-systeme appliquer beta "${sha:0:7}" --sans-instantane > /tmp/maj.log 2>&1
if ! grep -q "ancienne version" /usr/lib/xiii/xiii/modes.py && grep -q '"branche": "beta"' /usr/share/xiii/VERSION.json; then echo "OK        mise à jour appliquée : $(grep -o "Fichiers d'OS XIII mis à jour : [0-9]*" /tmp/maj.log), version $(python3 -c 'import json; print(json.load(open("/usr/share/xiii/VERSION.json"))["version"])')" >> $R
else echo "ÉCHEC     mise à jour d'OS XIII : $(tail -4 /tmp/maj.log | tr '\n' ' ')" >> $R; fi
p1=$(pgrep -f "xiii.shell import" | head -1); xiii-relancer-bureau; sleep 5; p2=$(pgrep -f "xiii.shell import" | head -1)
[ -n "$p2" ] && [ "$p1" != "$p2" ] && echo "OK        bureau relancé après la mise à jour (fenêtres gardées)" >> $R || echo "ÉCHEC     relance du bureau ($p1 → $p2)" >> $R
grim -s 0.5 /out/apres-maj.png
xiii-parametres --page maj > /out/p.log 2>&1 & sleep 6; grim -s 0.5 /out/page-maj-verif.png; pkill -f xiii.parametres; sleep 1

echo "== Version Stable (mémoire, démarrage)" >> $R
mkdir -p /etc/xiii; rm -f /etc/xiii/parefeu.json; command -v ufw > /tmp/pf.log 2>&1; XIII_PAREFEU_HORS_LIGNE=1 XIII_PAREFEU_BAVARD=1 /usr/local/sbin/xiii-parefeu init >> /tmp/pf.log 2>&1
n=$(cat /etc/ufw/user.rules /etc/ufw/user6.rules 2>/dev/null | grep -c "^### tuple"); grep -q "^ENABLED=yes" /etc/ufw/ufw.conf 2>/dev/null && [ "${n:-0}" -gt 0 ] && echo "OK        pare-feu écrit à la construction de l'ISO : $n lignes d'exceptions, actif au 1er démarrage" >> $R || echo "ÉCHEC     pare-feu hors ligne : $(tail -3 /tmp/pf.log | tr '\n' ' ')" >> $R
rm -f /etc/xiii/parefeu.json
# fuite de mémoire ? 3 séries de 20 ouvertures de tous les panneaux, puis 10 changements de thème : la mémoire doit se stabiliser
serie() { for i in $(seq 1 20); do for pn in son wifi centre volet widgets presse emoji demarrer; do gapplication action fr.xiii.Shell basculer "'$pn'" 2>/dev/null; sleep 0.15; done; gapplication action fr.xiii.Shell fermer 2>/dev/null; done; sleep 4; }
serie; m1=$(pss_shell); serie; m2=$(pss_shell); serie; m3=$(pss_shell)
L=""; for pn in son wifi centre volet widgets presse emoji demarrer bluetooth batterie alim; do
  for i in $(seq 1 5); do gapplication action fr.xiii.Shell basculer "'$pn'"; sleep 0.2; gapplication action fr.xiii.Shell fermer; done; sleep 1; a=$(pss_shell)
  for i in $(seq 1 50); do gapplication action fr.xiii.Shell basculer "'$pn'"; sleep 0.2; gapplication action fr.xiii.Shell fermer; sleep 0.05; done; sleep 4; L="$L $pn:+$(( $(pss_shell) - a ))"
done; echo "INFO      fuite par panneau (Mo pour 50 ouvertures) :$L" >> $R
for t in clair sombre clair sombre clair sombre clair sombre clair sombre; do python3 -c "import sys; sys.path.insert(0,'/usr/lib/xiii'); from xiii import config; config.modifier(_histo=False, theme='$t')"; sleep 1.2; done; sleep 26; m4=$(pss_shell)
for t in clair sombre clair sombre clair sombre clair sombre clair sombre; do python3 -c "import sys; sys.path.insert(0,'/usr/lib/xiii'); from xiii import config; config.modifier(_histo=False, theme='$t')"; sleep 1.2; done; sleep 26; m5=$(pss_shell)
echo "INFO      fuite ? panneaux ×160 : $m1 → $m2 → $m3 Mo ; thèmes ×10 : $m4 Mo, ×10 encore : $m5 Mo" >> $R
echo "INFO      mémoire du shell (PSS) : $(cat /tmp/pss-6s) Mo à 6 s, $(cat /tmp/pss-46s 2>/dev/null) Mo à 46 s (après libération), $(pss_shell) Mo maintenant (après des centaines d'ouvertures et 20 changements de thème)" >> $R

echo "== Phase M (distribution)" >> $R
truncate -s 60M /tmp/f.iso; printf 'label: dos\n,40M,83\n' | sfdisk -q /tmp/f.iso; truncate -s 800M /tmp/cle.img
if xiii-cle-ecrire /tmp/f.iso /tmp/cle.img > /tmp/cle.log 2>&1 && grep -q FINI /tmp/cle.log; then
  o=$(sfdisk -J /tmp/cle.img | python3 -c 'import json,sys; p=json.load(sys.stdin)["partitiontable"]["partitions"]; print(len(p), p[-1]["start"]*512)')
  n=${o% *}; off=${o#* }; c=$(debugfs -R "cat persistence.conf" "/tmp/cle.img?offset=$off" 2>/dev/null)
  echo "OK        Clé OS XIII : $n partitions, persistance « $c », $(grep INFO /tmp/cle.log | tail -1)" >> $R
else echo "ÉCHEC     Clé OS XIII : $(tr '\n' ' ' < /tmp/cle.log | tail -c 300)" >> $R; fi
truncate -s 70M /tmp/petite.img; xiii-cle-ecrire /tmp/f.iso /tmp/petite.img > /tmp/cle2.log 2>&1; grep -q "pas de persistance" /tmp/cle2.log && echo "OK        Clé trop petite : image copiée sans persistance" >> $R || echo "ÉCHEC     clé trop petite : $(cat /tmp/cle2.log | tail -2)" >> $R
xiii-cle > /out/xiii-cle.log 2>&1 & sleep 4; grim -s 0.5 /out/app-cle.png; pkill -f "xiii.cle import"; sleep 1
fc-list | grep -qi "Space Grotesk" && echo "OK        police des titres : Space Grotesk installée" >> $R || echo "ÉCHEC     police Space Grotesk absente" >> $R

echo "== Phase L (accessibilité)" >> $R
espeak-ng -v fr -s 140 -w /tmp/st.wav "bonjour à tous, nous tournons demain matin" 2>/dev/null
XIII_TEST_WAV=/tmp/st.wav xiii-acces --test >> $R 2>&1 || echo "ÉCHEC     accessibilité (voir zz.txt)" >> $R
xiii-soustitres > /out/xiii-soustitres.log 2>&1 & sleep 4; grim -s 0.5 /out/app-soustitres.png; xiii-acces --soustitres; sleep 1
pgrep -f "acces import main.*--soustitres" >/dev/null && echo "ÉCHEC     sous-titres : le second appui ne ferme pas" >> $R || echo "OK        sous-titres : second appui = fermeture" >> $R
grep -q 'ZoomIn' /root/.config/labwc/rc.xml && echo "OK        loupe : raccourcis Super + = / Super + -" >> $R

echo "== Phase K (sécurité)" >> $R
xiii-coffre --test >> $R 2>&1 || echo "ÉCHEC     Coffre XIII" >> $R
xiii-sauvegarde --test >> $R 2>&1 || echo "ÉCHEC     Sauvegarde XIII" >> $R
python3 -c 'import sys; sys.path.insert(0,"/usr/lib/xiii"); from xiii import antivol as A; E=[]; A.envoyer=lambda t, c=None, **k: E.append(t); A.cfg=lambda: {"antivol": True, "antivol_canal": "x"}
A.agir("etat"); A.agir("bonjour"); c=A.nouveau_canal(); print("OK        Antivol : canal secret de %d caractères, réponses :" % (len(c)-5), [e.split(chr(10))[0][:50] for e in E])' >> $R 2>&1
python3 -c 'import ast,sys; ast.parse(open("/usr/local/sbin/xiii-parefeu").read()); sys.path.insert(0,"/usr/local/sbin"); import importlib.machinery as m; P=m.SourceFileLoader("pf","/usr/local/sbin/xiii-parefeu").load_module(); print("OK        pare-feu : %d exceptions dont %d ouvertes par défaut (réseau local seulement)" % (len(P.EXCEPTIONS), sum(1 for v in P.EXCEPTIONS.values() if v[3])))' >> $R 2>&1
xiii-coffre > /out/xiii-coffre.log 2>&1 & sleep 5; grim -s 0.5 /out/app-coffre.png; pkill -f "xiii.coffre import"; sleep 1
xiii-sauvegarde > /out/xiii-sauvegarde.log 2>&1 & sleep 5; grim -s 0.5 /out/app-sauvegarde.png; pkill -f "xiii.sauvegarde import"; sleep 1

echo "== Phase J (performance)" >> $R
p=$(xiii-bilan --rapport /tmp/compat.html 2>&1 | tail -1); grep -q "Compatibilité OS XIII" /tmp/compat.html && echo "OK        rapport de compatibilité : $(grep -o '[0-9]* / [0-9]*</span> éléments reconnus' /tmp/compat.html | sed 's/<[^>]*>//g')" >> $R || echo "ÉCHEC     rapport de compatibilité : $p" >> $R
cp /tmp/compat.html /out/compatibilite.html 2>/dev/null
python3 -c 'import sys; sys.path.insert(0,"/usr/lib/xiii"); from xiii import envoi; print("OK        Envoi XIII sans GTK :", "gi" not in sys.modules)' >> $R 2>&1

echo "== Phase I (applis XIII)" >> $R
for q in "ouvre conduco" "cherche les vidéos de cette semaine" "mode production" "quelle heure est-il" "trouve le devis dupont"; do
  echo "OK        voix « $q » → $(xiii-voix --comprendre "$q")" >> $R
done
python3 - <<'PY' >> $R 2>&1
from PIL import Image, ImageDraw, ImageFont
f = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 42)
im = Image.new("RGB", (1600, 1200), (55, 48, 44)); d = ImageDraw.Draw(im)
d.polygon([(160, 96), (1440, 144), (1408, 1104), (192, 1080)], fill=(236, 231, 222))
for i, t in enumerate(["DEVIS XIII", "Tournage Concert Dome", "Camera principale 1200 euros", "Total 4800 euros"]): d.text((330, 260 + i * 120), t, font=f, fill=(25, 25, 25))
im.save("/tmp/scan-test.jpg"); print("OK        image de document créée")
PY
xiii-scanner --test /tmp/scan-test.jpg /tmp/scan-test.pdf >> $R 2>&1
t=$(pdftotext /tmp/scan-test.pdf - 2>/dev/null | tr '\n' ' ' | cut -c1-90); case "$t" in *DEVIS*|*Tournage*) echo "OK        OCR : « $t »" >> $R;; *) echo "ÉCHEC     OCR : « $t »" >> $R;; esac
pdftoppm -r 40 -png -singlefile /tmp/scan-test.pdf /out/scanner-pdf
mkdir -p /root/Images/Essai; for c in 1 2 3; do ffmpeg -loglevel error -y -f lavfi -i "testsrc2=s=3000x2000,format=yuv420p" -frames:v 1 /root/Images/Essai/photo-$c.jpg; done
xiii-photos /root/Images/Essai/photo-1.jpg > /out/xiii-photos.log 2>&1 & sleep 6; grim -s 0.5 /out/app-photos.png; pkill -f "xiii.photos import"; sleep 1
mkdir -p /root/XIII/Test/03_Documents/Notes; printf '# Réunion de prod\n\n- [x] Valider le devis\n- [ ] Repérage **jeudi**\n- [ ] Appeler la *régie*\n' > /root/XIII/Test/03_Documents/Notes/Reunion.md
xiii-notes > /out/xiii-notes.log 2>&1 & sleep 5; grim -s 0.5 /out/app-notes.png; pkill -f "xiii.carnet import"; sleep 1
python3 -c 'import json,os,datetime as d; n=d.datetime.now().astimezone(); os.makedirs("/root/.local/share/xiii", exist_ok=True); json.dump([{"id":"a1","titre":"Repérage Lyon","debut":(n.replace(hour=10,minute=0)).isoformat(),"fin":(n.replace(hour=12,minute=0)).isoformat(),"journee":False,"lieu":"Halle Tony Garnier","rappel":15}], open("/root/.local/share/xiii/agenda.json","w"))'
xiii-calendrier > /out/xiii-calendrier.log 2>&1 & sleep 5; grim -s 0.5 /out/app-calendrier.png; pkill -f "xiii.agenda import"; sleep 1
xiii-scanner > /out/xiii-scanner.log 2>&1 & sleep 5; grim -s 0.5 /out/app-scanner.png; pkill -f "xiii.scanner import"; sleep 1
xiii-enregistreur > /out/xiii-enregistreur.log 2>&1 & sleep 5; grim -s 0.5 /out/app-enregistreur.png; pkill -f "xiii.enregistreur import"; sleep 1
xiii-taches > /out/xiii-taches.log 2>&1 & sleep 6; grim -s 0.5 /out/app-moniteur.png; pkill -f "xiii.taches import"; sleep 1
ffmpeg -loglevel error -y -f lavfi -i "testsrc2=s=1280x720:r=25:d=20" -f lavfi -i "sine=d=20" -timecode 10:00:00:00 -c:v libx264 -preset ultrafast -c:a aac /tmp/essai-tc.mov
xiii-lecteur --input-ipc-server=/tmp/mpv.sock --pause --start=4 /tmp/essai-tc.mov > /out/xiii-lecteur.log 2>&1 & sleep 5
echo '{ "command": ["script-binding", "xiii/waveform"] }' | socat - /tmp/mpv.sock >/dev/null 2>&1; sleep 2; grim -s 0.5 /out/app-lecteur.png
grep -i "error\|erreur\|lua" /out/xiii-lecteur.log | head -3 | sed 's/^/INFO      lecteur : /' >> $R
echo '{ "command": ["quit"] }' | socat - /tmp/mpv.sock >/dev/null 2>&1; sleep 1; pkill mpv

echo "== Phase E (régie, déchargement → BACKUPO + DOSSIER)" >> $R
mkdir -p /root/Navette
python3 - >> $R 2>&1 <<'PY'
import sys, time, json, os, glob
sys.path.insert(0, "/usr/lib/xiii")
from xiii import config, backup
config.modifier(_histo=False, backup_destination="/root/XIII/Test/01_Rushes", backup_destination2="/root/Navette", backup_nom="J01", projet_actif="Test", backup_vers_suite=True)
class Shell: cfg = config.charger()
B = backup.Moteur(Shell())
B.demarrer({"nom": "CARTE_A001", "chemin": "/root/Rushes/A001", "mount": None})
for _ in range(120):
    if B.transferts[0]["etat"] in ("fini", "erreur"): break
    time.sleep(0.5)
t = B.transferts[0]
print("OK " if t["etat"] == "fini" else "ÉCHEC", "      déchargement :", t["texte"])
print("OK " if t.get("pdf") and os.path.exists(t["pdf"]) else "ÉCHEC", "      rapport PDF :", os.path.basename(t.get("pdf") or "absent"))
d = json.load(open(t["lien"]))["data"]
print("OK " if len(d["destinations"]) == 2 and all(x["statut"] == "OK" for x in d["destinations"]) else "ÉCHEC", "      deux copies vérifiées :", [x["statut"] for x in d["destinations"]])
print("OK        rapport BACKUPO : %d fichiers, premier %s, dernier %s, DIT %s" % (len(d["fichiers"]), d["premier"], d["dernier"], d["dit"]))
print("OK " if glob.glob("/root/Navette/J01/CARTE_A001/*.pdf") else "ÉCHEC", "      rapports aussi sur la 2e copie")
f = B.rapport_journee(envoyer=False); print("OK " if f and os.path.exists(f) else "ÉCHEC", "      rapport de la journée :", os.path.basename(f or "absent"))
open("/out/pdf-chemins.txt", "w").write(t["pdf"] + "\n" + (f or "") + "\n")
PY
pdftoppm -r 70 -png -f 1 -l 1 "$(sed -n 1p /out/pdf-chemins.txt)" /out/rapport-dechargement 2>/dev/null
pdftoppm -r 70 -png -f 1 -l 1 "$(sed -n 2p /out/pdf-chemins.txt)" /out/rapport-journee 2>/dev/null
sleep 6; pkill -f xiii.suite; pkill -f WebKitWebProcess; sleep 1
xiii-suite --backupo "$(ls /root/XIII/Test/01_Rushes/J01/CARTE_A001/*.xiii.json | head -1)" > /out/suite-backupo.log 2>&1 & sleep 14; grim -s 0.5 /out/backupo-journal.png
grep "import dans" /out/suite-backupo.log | sed 's/^/INFO      BACKUPO /' >> $R
pkill -f xiii.suite; pkill -f WebKitWebProcess; sleep 1
xiii-suite --dossier "$(sed -n 1p /out/pdf-chemins.txt)" > /out/suite-dossier.log 2>&1 & sleep 18; grim -s 0.5 /out/dossier-reception.png
grep "import dans" /out/suite-dossier.log | sed 's/^/INFO      DOSSIER /' >> $R
pkill -f xiii.suite; pkill -f WebKitWebProcess; sleep 1
# pupitre ATEM face à un ATEM simulé
python3 - >> $R 2>&1 <<'PY'
import socket, struct, threading, time, sys
sys.path.insert(0, "/usr/lib/xiii")
from xiii.atem import ATEM
srv = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); srv.bind(("127.0.0.1", 9910)); srv.settimeout(4); recu = []
blk = lambda n, d: struct.pack(">HH4s", 8 + len(d), 0, n) + d
def faux():
    d, a = srv.recvfrom(100); srv.sendto(struct.pack(">HHHHHH", (2 << 11) | 20, 0x53AB, 0, 0, 0, 0) + bytes([2] + [0] * 7), a); srv.recvfrom(100)
    pl = blk(b"_pin", b"ATEM Mini Pro\0") + b"".join(blk(b"InPr", struct.pack(">H", i) + ("Camera %d" % i).encode().ljust(20, b"\0") + ("CAM%d" % i).encode().ljust(4, b"\0") + bytes(6)) for i in (1, 2, 3, 4)) \
         + blk(b"PrgI", struct.pack(">BBH", 0, 0, 1)) + blk(b"PrvI", struct.pack(">BBH", 0, 0, 2)) \
         + blk(b"MPrp", struct.pack(">HBBHH", 0, 1, 0, 9, 0) + b"Ouverture") + blk(b"MPrp", struct.pack(">HBBHH", 2, 1, 0, 7, 0) + b"Rappels") + blk(b"InCm", bytes(4))
    srv.sendto(struct.pack(">HHHHHH", (1 << 11) | (12 + len(pl)), 0x8001, 0, 0, 0, 1) + pl, a)
    while True:
        try: d, a = srv.recvfrom(500)
        except Exception: break
        if len(d) > 12: recu.append(d[16:20].decode())
threading.Thread(target=faux, daemon=True).start(); E = []
c = ATEM("127.0.0.1", E.append); c.start(); time.sleep(1.2); c.preview(3); c.cut(); c.auto(); c.macro(2); time.sleep(.5); c.arreter()
print("OK " if E and E[-1]["connecte"] else "ÉCHEC", "      ATEM :", E[-1]["message"] if E else "rien", "· commandes envoyées", recu, "· macros lues", E[-1].get("macros") if E else None)
PY
python3 -c 'import sys; sys.path.insert(0,"/usr/lib/xiii"); from xiii import mesure_audio as M; import subprocess
subprocess.run(["ffmpeg","-v","quiet","-y","-f","lavfi","-i","sine=f=1000:d=3","-af","volume=-20dB","/tmp/t.wav"])
o=subprocess.run(["ffmpeg","-nostats","-hide_banner","-nostdin","-i","/tmp/t.wav","-af","ebur128=peak=true:framelog=info","-f","null","-"],capture_output=True,text=True).stderr
L=[M.RE.search(l).groups() for l in o.splitlines() if M.RE.search(l)]; print("OK        mesure LUFS :", len(L), "mesures, dernière", L[-1][:3], "crête", L[-1][4])' >> $R 2>&1
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
