[ -f ~/.bashrc ] && . ~/.bashrc
# Secours : sans écran de connexion, lance le bureau sur tty1
if [ -z "$WAYLAND_DISPLAY" ] && [ "$(tty)" = "/dev/tty1" ] && ! systemctl -q is-active lightdm 2>/dev/null; then
  exec xiii-demarrer-bureau
fi
