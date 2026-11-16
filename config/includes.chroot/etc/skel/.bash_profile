[ -f ~/.bashrc ] && . ~/.bashrc
# OS XIII : lance le bureau sur le premier écran
if [ -z "$WAYLAND_DISPLAY" ] && [ "$(tty)" = "/dev/tty1" ]; then
  exec labwc
fi
