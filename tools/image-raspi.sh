#!/bin/sh
# OS XIII — image pour Raspberry Pi 4 / 400 / 5 (arm64), fabriquée à partir du système construit par live-build (chroot/).
# Carte SD : partition FAT « RASPIFIRM » (micrologiciel, noyau) + ext4 « RASPIROOT » (système), agrandie au premier démarrage.
# Usage (root, sur une machine arm64) : tools/image-raspi.sh chroot OS-XIII-raspi.img
set -e
SRC="$1"; IMG="$2"; TAILLE="${3:-12G}"
[ -d "$SRC/usr" ] || { echo "système introuvable : $SRC"; exit 1; }
rm -f "$IMG"; truncate -s "$TAILLE" "$IMG"
parted -s "$IMG" mklabel msdos mkpart primary fat32 4MiB 516MiB mkpart primary ext4 516MiB 100% set 1 lba on
# pas d'udev dans le conteneur : une boucle par partition, par décalage
P1=$(losetup --show -f -o $((4*1024*1024)) --sizelimit $((512*1024*1024)) "$IMG")
P2=$(losetup --show -f -o $((516*1024*1024)) "$IMG")
mkfs.vfat -F 32 -n RASPIFIRM "$P1"
mkfs.ext4 -q -L RASPIROOT "$P2"
M=$(mktemp -d); mount "$P2" "$M"
rsync -aHAX --numeric-ids --exclude=/proc/* --exclude=/sys/* --exclude=/dev/* --exclude=/run/* --exclude=/tmp/* "$SRC"/ "$M"/
mkdir -p "$M/boot/firmware"; mount "$P1" "$M/boot/firmware"
for d in dev dev/pts proc sys run; do mount --bind /$d "$M/$d"; done
cp /etc/resolv.conf "$M/etc/resolv.conf" 2>/dev/null || true
cat > "$M/etc/fstab" <<F
LABEL=RASPIROOT /              ext4 rw,noatime 0 1
LABEL=RASPIFIRM /boot/firmware vfat rw,noatime 0 2
F
mkdir -p "$M/etc/default"
cat > "$M/etc/default/raspi-firmware" <<F
ROOTPART=LABEL=RASPIROOT
CONSOLES="tty1"
KERNEL_ARCH=arm64
F
echo "quiet splash" > "$M/etc/default/raspi-extra-cmdline"
cat > "$M/tmp/pi.sh" <<'F'
set -e
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
# système installé, plus « live » : on retire live-boot / live-config
apt-get purge -y live-boot live-boot-initramfs-tools live-config live-config-systemd calamares calamares-settings-debian || true
apt-get install -y --no-install-recommends raspi-firmware firmware-brcm80211 cloud-guest-utils linux-image-arm64 wireless-regdb
# compte « xiii » (mot de passe « xiii », à changer au premier démarrage), connexion automatique
id xiii >/dev/null 2>&1 || useradd -m -s /bin/bash -c "OS XIII" -G sudo,audio,video,plugdev,netdev,bluetooth,input,render,dialout,lpadmin xiii
echo "xiii:xiii" | chpasswd; passwd -e xiii || true
mkdir -p /etc/lightdm/lightdm.conf.d; printf '[Seat:*]\nautologin-user=xiii\nautologin-session=xiii\n' > /etc/lightdm/lightdm.conf.d/60-autologin.conf
echo xiii-pi > /etc/hostname
# agrandir la partition système au premier démarrage
cat > /usr/local/sbin/xiii-agrandir <<'S'
#!/bin/sh
R=$(findmnt -no SOURCE /); D=/dev/$(lsblk -no PKNAME "$R"); N=$(echo "$R" | grep -o '[0-9]*$')
growpart "$D" "$N" && resize2fs "$R"; systemctl disable xiii-agrandir.service
S
chmod +x /usr/local/sbin/xiii-agrandir
printf '[Unit]\nDescription=OS XIII : agrandir la carte SD\n[Service]\nType=oneshot\nExecStart=/usr/local/sbin/xiii-agrandir\n[Install]\nWantedBy=multi-user.target\n' > /etc/systemd/system/xiii-agrandir.service
systemctl enable xiii-agrandir.service
update-initramfs -u -k all
apt-get clean
F
chroot "$M" sh /tmp/pi.sh; rm -f "$M/tmp/pi.sh"
ls -la "$M/boot/firmware" | head -30
for d in run sys proc dev/pts dev; do umount "$M/$d"; done
umount "$M/boot/firmware"; umount "$M"; losetup -d "$P1" "$P2"
echo "Image prête : $IMG"
