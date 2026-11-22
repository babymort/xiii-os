#!/bin/bash
# OS XIII — test du retour arrière (xiii-instantanes) sur un vrai Btrfs en fichier image (CI GitHub, sudo).
set -u
S=config/includes.chroot/usr/local/sbin/xiii-instantanes
ok=0; ko=0; t() { if eval "$2"; then echo "OK      $1"; ok=$((ok+1)); else echo "ÉCHEC   $1"; ko=$((ko+1)); fi; }
img=/tmp/xiii-btrfs.img; truncate -s 1G $img; L=$(losetup -f --show $img); mkfs.btrfs -q $L
H=/mnt/haut; T=/mnt/top; RAC=/mnt/racine; mkdir -p $T $RAC
mount $L $T
btrfs subvolume create $T/@ >/dev/null; btrfs subvolume create $T/@snapshots >/dev/null
echo v1 > $T/@/version; mkdir -p $T/@/var/lib/xiii $T/@/boot
mkdir -p $T/@snapshots/1; btrfs subvolume snapshot -r $T/@ $T/@snapshots/1/snapshot >/dev/null
printf '<?xml version="1.0"?>\n<snapshot>\n  <type>pre</type>\n  <num>1</num>\n  <date>2026-11-22 10:00:00</date>\n  <description>apt</description>\n</snapshot>\n' > $T/@snapshots/1/info.xml
echo v2-casse > $T/@/version
mount -o subvol=@ $L $RAC; mkdir -p $RAC/.snapshots; mount -o subvol=@snapshots $L $RAC/.snapshots
export XIII_RACINE=$RAC XIII_HAUT=$H
t "état : btrfs, 1 instantané" '[ "$($S etat | cut -d" " -f1-3)" = "btrfs 1 @" ]'
t "liste lisible" '$S liste | grep -q "^1|2026-11-22 10:00:00|pre|apt$"'
t "instantané inconnu refusé sans rien casser" '! $S restaurer 9 >/dev/null && [ "$(cat $T/@/version)" = v2-casse ]'
t "restauration depuis le système en marche" '$S restaurer 1 auto | grep -q OK'
t "  @ refait depuis l'instantané (v1)" '[ "$(cat $T/@/version)" = v1 ]'
t "  @ restauré modifiable" 'touch $T/@/ecriture && rm $T/@/ecriture'
t "  ancien système gardé (v2)" '[ "$(cat $T/@ancien-*/version)" = v2-casse ]'
t "  note pour l'annonce au prochain démarrage" 'grep -q "^1|auto|@ancien-" $T/@/var/lib/xiii/restauration.txt'
t "  instantané toujours là" '[ -d $T/@snapshots/1/snapshot ]'
umount $RAC/.snapshots $RAC; umount $H 2>/dev/null
# démarré sur l'instantané (menu « Revenir à… ») : c'est @ qu'on remplace
echo v3-casse > $T/@/version
mount -o ro,subvol=@snapshots/1/snapshot $L $RAC
t "restauration depuis un démarrage sur l'instantané" '$S restaurer 1 manuel | grep -q OK'
t "  @ refait (v1)" '[ "$(cat $T/@/version)" = v1 ]'
t "  deux anciens systèmes gardés" '[ $(ls -d $T/@ancien-* | wc -l) = 2 ]'
umount $RAC; umount $H 2>/dev/null
# nettoyage des anciens systèmes de plus de 7 jours
for a in $T/@ancien-*; do touch -d "10 days ago" "$a"; done
mount -o subvol=@ $L $RAC
t "nettoyage après 7 jours" '$S nettoyer; [ $(ls -d $T/@ancien-* 2>/dev/null | wc -l) = 0 ]'
umount $RAC; umount $H 2>/dev/null; umount $T; losetup -d $L
for f in config/includes.chroot/etc/grub.d/41_xiii_secours config/includes.chroot/usr/local/sbin/xiii-demarrage-suivi config/includes.chroot/usr/local/sbin/xiii-reparer-menu; do t "syntaxe $(basename $f)" "bash -n $f"; done
echo "== $ok réussi(s), $ko échec(s)"; [ $ko = 0 ]
