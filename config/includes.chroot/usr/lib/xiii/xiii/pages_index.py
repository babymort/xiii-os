# OS XIII — plan des Paramètres : catégories, sous-pages, mots-clés (aussi utilisé par la recherche du menu Démarrer).
# (clé, titre, icône Lucide, parent, description, mots-clés)
PAGES = [
    ("accueil", "Accueil", "house", None, "Vue d'ensemble de l'ordinateur", "accueil"),
    ("systeme", "Système", "monitor", None, "Écran, son, notifications, alimentation, stockage", "systeme"),
    ("ecran", "Écran", "monitor", "systeme", "Résolution, échelle, orientation, lumière nocturne", "resolution echelle rotation moniteur luminosite nuit hz frequence"),
    ("son", "Son", "volume-2", "systeme", "Sorties, entrées, volume des applications", "audio haut-parleur casque micro volume focusrite"),
    ("notifications", "Notifications", "bell", "systeme", "Ne pas déranger, applications bloquées", "alertes ne pas deranger"),
    ("alimentation", "Alimentation et batterie", "battery-full", "systeme", "Mode d'alimentation, mise en veille, capot", "batterie energie veille economie performance"),
    ("stockage", "Stockage", "hard-drive", "systeme", "Espace utilisé, nettoyage", "disque espace nettoyer corbeille"),
    ("multitache", "Multitâche", "app-window", "systeme", "Ancrage des fenêtres, bureaux virtuels", "fenetres snap bureaux virtuels alt tab"),
    ("apropos", "À propos", "info", "systeme", "Nom de l'appareil, caractéristiques, version", "version materiel nom pc processeur memoire"),
    ("appareils", "Bluetooth et appareils", "bluetooth", None, "Bluetooth, imprimantes, souris, clavier", "peripheriques"),
    ("bluetooth", "Bluetooth", "bluetooth", "appareils", "Appareils appairés, ajouter un appareil", "casque enceinte appairer"),
    ("imprimantes", "Imprimantes et scanners", "printer", "appareils", "Ajouter, imprimante par défaut", "imprimer scanner"),
    ("souris", "Souris et pavé tactile", "mouse", "appareils", "Vitesse, défilement, tap pour cliquer", "touchpad trackpad pointeur defilement"),
    ("clavier", "Clavier", "keyboard", "appareils", "Disposition, répétition, raccourcis", "azerty qwerty raccourcis disposition"),
    ("webcam", "Caméras", "webcam", "appareils", "Tester la webcam", "camera video"),
    ("autoplay", "Exécution automatique", "usb", "appareils", "Montage des clés et disques", "cle usb disque montage"),
    ("reseau", "Réseau et Internet", "globe", None, "Wi-Fi, Ethernet, VPN, partage de connexion", "internet"),
    ("wifi", "Wi-Fi", "wifi", "reseau", "Réseaux, mots de passe, QR code", "sans fil reseau mot de passe qr code"),
    ("ethernet", "Ethernet", "ethernet-port", "reseau", "Câble réseau, adresse IP", "cable rj45 ip"),
    ("vpn", "VPN", "shield", "reseau", "Connexions VPN", "wireguard openvpn"),
    ("partage", "Partage de connexion", "radio-tower", "reseau", "Point d'accès Wi-Fi", "hotspot point d'acces"),
    ("duo", "XIII Duo", "network", "reseau", "Wi-Fi + câble ensemble", "agregation plexo double bande passante"),
    ("perso", "Personnalisation", "palette", None, "Thème, couleurs, fond, barre des tâches", "personnaliser apparence"),
    ("theme", "Thème et couleurs", "palette", "perso", "Sombre, clair, sobre, couleur d'accent", "couleur accent sombre clair sobre transparence"),
    ("fond", "Arrière-plan", "image", "perso", "Fond d'écran", "fond d'ecran wallpaper image"),
    ("verrou", "Écran de verrouillage", "lock", "perso", "Image, délai", "verrouillage"),
    ("barre", "Barre des tâches", "panel-bottom", "perso", "Alignement, épingles, météo", "taskbar epingler alignement"),
    ("demarrer", "Menu Démarrer", "layout-grid", "perso", "Épingles, recommandations", "menu demarrer"),
    ("haut", "Barre du haut", "panel-top", "perso", "Horloge, titre, batterie", "horloge secondes"),
    ("polices", "Polices", "type", "perso", "Police et taille du texte", "police texte taille"),
    ("curseur", "Curseur", "mouse-pointer-2", "perso", "Taille du pointeur", "pointeur souris"),
    ("demarrage", "Animation de démarrage", "clapperboard", "perso", "Choisir ou importer", "boot plymouth animation"),
    ("applications", "Applications", "layout-grid", None, "Installées, par défaut, démarrage", "logiciels"),
    ("apps", "Applications installées", "package", "applications", "Désinstaller", "desinstaller logiciels"),
    ("defaut", "Applications par défaut", "star", "applications", "Navigateur, lecteur vidéo…", "navigateur defaut ouvrir avec"),
    ("autostart", "Démarrage", "rocket", "applications", "Applications lancées à l'ouverture", "autostart demarrage"),
    ("comptes", "Comptes", "circle-user-round", None, "Vos informations, connexion", "utilisateur"),
    ("compte", "Vos informations", "user", "comptes", "Nom, photo", "avatar photo nom"),
    ("connexion", "Options de connexion", "lock", "comptes", "Mot de passe, connexion automatique", "mot de passe autologin"),
    ("heurelangue", "Heure et langue", "clock", None, "Date, fuseau horaire, langue", "temps"),
    ("heure", "Date et heure", "calendar", "heurelangue", "Fuseau horaire, synchronisation", "date heure fuseau horloge"),
    ("langue", "Langue et région", "languages", "heurelangue", "Langue du système", "langue francais anglais region"),
    ("accessibilite", "Accessibilité", "accessibility", None, "Texte, effets visuels, contraste", "accessibilite"),
    ("texte", "Taille du texte", "type", "accessibilite", "Agrandir le texte", "grand texte zoom"),
    ("effets", "Effets visuels", "sparkles", "accessibilite", "Animations, transparence, contraste", "animations transparence contraste"),
    ("securite", "Confidentialité et sécurité", "shield-check", None, "Pare-feu, historique", "securite"),
    ("parefeu", "Pare-feu", "flame", "securite", "Protection réseau", "firewall ufw"),
    ("confidentialite", "Historique et localisation", "eye", "securite", "Fichiers récents, ville météo", "historique recents localisation"),
    ("maj", "Mises à jour", "refresh-cw", None, "Mettre à jour OS XIII", "update mise a jour"),
    ("xiii", "Suite XIII", "zap", None, "Mode tournage, météo, réglages partagés", "tournage xiii suite"),
    ("meteo", "Météo", "cloud-sun", "xiii", "Ville affichée dans la barre des tâches", "meteo ville"),
]
ALIAS = {"avion": "reseau", "duo": "duo"}
PAR_CLE = {p[0]: p for p in PAGES}
CATEGORIES = [p for p in PAGES if p[3] is None]

def chemin(cle):
    p = PAR_CLE.get(cle)
    if not p: return ""
    return ("Paramètres › " + PAR_CLE[p[3]][1] + " › " + p[1]) if p[3] else ("Paramètres › " + p[1])

INDEX = [(p[0], p[1], p[2], chemin(p[0]), p[4] + " " + p[5]) for p in PAGES]
