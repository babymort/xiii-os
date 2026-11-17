# OS XIII — Claude intégré : état de Claude Desktop et Claude Code, Cowork (virtualisation),
# connexion de l'OS à Claude par le serveur MCP « OS XIII », lancements sans terminal.
# Application développée par Matthieu Lamotte.
import os, json, shutil, subprocess, grp, pwd, re

DESKTOP_ID = "com.anthropic.Claude.desktop"
CONFIG_DESKTOP = os.path.expanduser("~/.config/Claude/claude_desktop_config.json")
CONFIG_CODE = os.path.expanduser("~/.claude.json")
MCP_NOM = "os-xiii"
MCP_CMD = "/usr/local/bin/xiii-mcp"


def _out(cmd, t=6):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=t).stdout.strip()
    except Exception:
        return ""


def version_paquet(p):
    v = _out(["dpkg-query", "-W", "-f=${Status}|${Version}", p])
    return v.split("|", 1)[1] if v.startswith("install ok installed") else None


def desktop_installe():
    return bool(shutil.which("claude-desktop"))


def code_installe():
    return bool(shutil.which("claude"))


def version_code():
    v = _out(["claude", "--version"])
    return v.split()[0] if v else version_paquet("claude-code")


def connecte_code():
    """Vrai si un compte est déjà configuré pour Claude Code."""
    try:
        o = json.load(open(CONFIG_CODE))
        return bool(o.get("oauthAccount") or o.get("primaryApiKey"))
    except Exception:
        return bool(os.environ.get("ANTHROPIC_API_KEY"))


# ------------------------------------------------------------- Cowork : virtualisation
def cowork():
    """[(intitulé, ok, conseil)] — conditions de Cowork sur Linux."""
    cpu = open("/proc/cpuinfo").read()
    virt = bool(re.search(r"\b(vmx|svm)\b", cpu))
    kvm = os.path.exists("/dev/kvm")
    try:
        groupe = grp.getgrnam("kvm").gr_name in [g.gr_name for g in grp.getgrall() if pwd.getpwuid(os.getuid()).pw_name in g.gr_mem] \
                 or grp.getgrnam("kvm").gr_gid == os.getgid()
    except KeyError:
        groupe = False
    acces = kvm and os.access("/dev/kvm", os.R_OK | os.W_OK)
    vsock = os.path.exists("/dev/vhost-vsock") and os.access("/dev/vhost-vsock", os.R_OK | os.W_OK)
    qemu = bool(shutil.which("qemu-system-x86_64"))
    return [
        ("Processeur compatible virtualisation", virt, "Ce processeur ne gère pas la virtualisation : Cowork n'est pas disponible."),
        ("Virtualisation activée dans le BIOS / UEFI", kvm, "Activez « Intel VT-x » ou « AMD-V / SVM » dans les réglages du BIOS au démarrage."),
        ("Accès à la virtualisation", acces or groupe, "Bouton « Réparer » ci-dessous, puis fermer la session."),
        ("Module vsock", vsock, "Bouton « Réparer » ci-dessous."),
        ("QEMU installé", qemu, "Bouton « Réparer » ci-dessous."),
    ]


def reparer_cowork():
    u = pwd.getpwuid(os.getuid()).pw_name
    script = "modprobe kvm_intel 2>/dev/null; modprobe kvm_amd 2>/dev/null; modprobe vhost_vsock; usermod -aG kvm %s; " \
             "command -v qemu-system-x86_64 >/dev/null || (apt-get update && apt-get install -y qemu-system-x86 ovmf virtiofsd)" % u
    return subprocess.run(["pkexec", "sh", "-c", script]).returncode == 0


# ------------------------------------------------------------- MCP « OS XIII »
def _entree():
    return {"command": MCP_CMD, "args": []}


def mcp_desktop():
    try:
        return MCP_NOM in json.load(open(CONFIG_DESKTOP)).get("mcpServers", {})
    except Exception:
        return False


def mcp_code():
    try:
        return MCP_NOM in json.load(open(CONFIG_CODE)).get("mcpServers", {})
    except Exception:
        return False


def regler_mcp_desktop(on):
    try:
        o = json.load(open(CONFIG_DESKTOP))
    except Exception:
        o = {}
    s = o.setdefault("mcpServers", {})
    if on: s[MCP_NOM] = _entree()
    else: s.pop(MCP_NOM, None)
    os.makedirs(os.path.dirname(CONFIG_DESKTOP), exist_ok=True)
    tmp = CONFIG_DESKTOP + ".xiii"
    json.dump(o, open(tmp, "w"), indent=2, ensure_ascii=False); os.replace(tmp, CONFIG_DESKTOP)


def regler_mcp_code(on):
    if not code_installe():
        return False
    subprocess.run(["claude", "mcp", "remove", "-s", "user", MCP_NOM], capture_output=True, timeout=20)
    if on:
        return subprocess.run(["claude", "mcp", "add", "-s", "user", MCP_NOM, "--", MCP_CMD], capture_output=True, timeout=20).returncode == 0
    return True


def premier_lancement():
    """Au premier démarrage d'une session : relie OS XIII à Claude Desktop (Claude Code : à la demande)."""
    drapeau = os.path.expanduser("~/.config/xiii/claude-relie")
    if os.path.exists(drapeau):
        return
    try:
        regler_mcp_desktop(True)
        os.makedirs(os.path.dirname(drapeau), exist_ok=True); open(drapeau, "w").close()
    except Exception:
        pass


# ------------------------------------------------------------- lancements
def ouvrir(lien=None):
    subprocess.Popen(["claude-desktop"] + ([lien] if lien else []), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)


def demander(question):
    """Ouvre une nouvelle conversation avec la question (app Claude si présente, sinon claude.ai)."""
    from urllib.parse import quote
    if desktop_installe():
        ouvrir("claude://claude.ai/new?q=" + quote(question))
    else:
        subprocess.Popen(["xdg-open", "https://claude.ai/new?q=" + quote(question)], start_new_session=True)


def code_dans(dossier=None):
    subprocess.Popen(["xiii-claude-code"] + ([dossier] if dossier else []), start_new_session=True)
