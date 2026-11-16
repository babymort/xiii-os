[ -f ~/.bashrc ] && . ~/.bashrc
# OS XIII : lance le bureau sur le premier écran
if [ -z "$WAYLAND_DISPLAY" ] && [ "$(tty)" = "/dev/tty1" ] && [ -z "$XIII_NO_GUI" ]; then
  exec xiii-demarrer-bureau
fi
