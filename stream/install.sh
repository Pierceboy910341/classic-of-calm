#!/usr/bin/env bash
# Classic of Calm — 24/7 stream host installer (Ubuntu 24.04, x86_64 or ARM64)
#
# Fresh server, one line (as the default ubuntu user):
#   curl -fsSL https://raw.githubusercontent.com/OWNER/classic-of-calm/main/stream/install.sh | sudo bash
# From a checkout of the repo:
#   sudo bash stream/install.sh
# Change the stream key / Kaggle settings later:
#   sudo coc setup            (same as: sudo bash /opt/classic-of-calm/install.sh --configure)
#
# Safe to run again: it upgrades the code and keeps your settings and music.
# Non-interactive use: export YOUTUBE_STREAM_KEY, KAGGLE_USERNAME, KAGGLE_KEY (or
# KAGGLE_API_TOKEN) and KAGGLE_NOTEBOOK before running, and pass --yes.
set -euo pipefail

# Where to download the code from when run via curl. Private repo: also export
# GITHUB_TOKEN=... (a read-only token) before running.
COC_REPO="${COC_REPO:-OWNER/classic-of-calm}"
COC_REF="${COC_REF:-main}"

APP_DIR=/opt/classic-of-calm
ETC_DIR=/etc/classic-of-calm
ENV_FILE=$ETC_DIR/env
DATA_DIR=/var/lib/classic-of-calm
SVC_USER=stream

MODE=install
ASSUME_YES=0
for a in "$@"; do
  case "$a" in
    --configure) MODE=configure ;;
    --yes|-y) ASSUME_YES=1 ;;
    -h|--help) sed -n '2,15p' "$0"; exit 0 ;;
  esac
done

# ---------------------------------------------------------------- helpers ---
bold() { printf '\033[1m%s\033[0m\n' "$*"; }
ok()   { printf '\033[32m✔ %s\033[0m\n' "$*"; }
warn() { printf '\033[33m! %s\033[0m\n' "$*"; }
die()  { printf '\033[31m✘ %s\033[0m\n' "$*" >&2; exit 1; }
step() { echo; bold "==> $*"; }

HAVE_TTY=0
if [ "$ASSUME_YES" -eq 0 ] && { : </dev/tty; } 2>/dev/null; then HAVE_TTY=1; fi

# get_kv KEY -> current value from the env file (empty if none)
get_kv() {
  [ -f "$ENV_FILE" ] || return 0
  grep -E "^$1=" "$ENV_FILE" | tail -n1 | cut -d= -f2- | sed -e 's/^"\(.*\)"$/\1/' || true
}

# set_kv KEY VALUE  (VALUE empty -> remove the line)
set_kv() {
  local k="$1" v="$2" tmp
  tmp="$(mktemp "$ETC_DIR/.env.XXXXXX")"
  if [ -f "$ENV_FILE" ]; then grep -vE "^#?$k=" "$ENV_FILE" > "$tmp" || true; fi
  if [ -n "$v" ]; then printf '%s=%s\n' "$k" "$v" >> "$tmp"; fi
  chmod 600 "$tmp"
  mv "$tmp" "$ENV_FILE"
}

mask() { local s="$1"; [ ${#s} -gt 4 ] && echo "****${s: -4}" || echo "****"; }

# ask VAR "English question" "中文問題" secret(0/1) [validate-regex]
ask() {
  local var="$1" en="$2" zh="$3" secret="$4" re="${5:-}" cur ans shown
  cur="${!var:-$(get_kv "$var")}"
  if [ "$HAVE_TTY" -eq 0 ]; then printf -v "$var" '%s' "$cur"; return; fi
  while true; do
    echo
    bold "$en"
    echo "$zh"
    if [ -n "$cur" ]; then
      shown="$cur"; [ "$secret" = 1 ] && shown="$(mask "$cur")"
      echo "(Press Enter to keep 直接按 Enter 保留: $shown)"
    fi
    if [ "$secret" = 1 ]; then
      read -r -s -p "> " ans </dev/tty; echo
    else
      read -r -p "> " ans </dev/tty
    fi
    ans="$(printf '%s' "$ans" | tr -d '[:space:]')"
    [ -z "$ans" ] && ans="$cur"
    if [ -z "$ans" ]; then
      warn "Skipped — you can add it later with: sudo coc setup   已略過，之後可用 sudo coc setup 補上"
      break
    fi
    if [ -n "$re" ] && ! [[ "$ans" =~ $re ]]; then
      warn "That doesn't look right, please try again. 格式好像不對，請再試一次。"
      continue
    fi
    [ "$secret" = 1 ] && ok "Got it 收到 ($(mask "$ans"))"
    break
  done
  printf -v "$var" '%s' "$ans"
}

# ------------------------------------------------------------ preflight ---
[ "$(id -u)" -eq 0 ] || die "Please run as root: put 'sudo' in front. 請在指令前加上 sudo 再執行。"
if [ -r /etc/os-release ]; then
  # shellcheck disable=SC1091
  . /etc/os-release
  if [ "${ID:-}" != ubuntu ] || [ "${VERSION_ID:-}" != "24.04" ]; then
    warn "Tested on Ubuntu 24.04; this is ${PRETTY_NAME:-unknown}. Continuing anyway."
  fi
fi

find_source() {
  local here
  here="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd || true)"
  if [ -n "$here" ] && [ -f "$here/coc/streamer.py" ]; then SRC_DIR="$here"; return; fi
  step "Downloading the stream software 下載直播程式 ($COC_REPO@$COC_REF)"
  local tmp hdr=()
  tmp="$(mktemp -d)"
  [ -n "${GITHUB_TOKEN:-}" ] && hdr=(-H "Authorization: Bearer $GITHUB_TOKEN")
  curl -fsSL "${hdr[@]}" "https://api.github.com/repos/$COC_REPO/tarball/$COC_REF" -o "$tmp/src.tgz" \
    || die "Could not download $COC_REPO. If the repo is private, run: export GITHUB_TOKEN=... first."
  tar -xzf "$tmp/src.tgz" -C "$tmp"
  SRC_DIR="$(find "$tmp" -maxdepth 3 -type f -path '*/stream/coc/streamer.py' -printf '%h\n' | head -n1)"
  SRC_DIR="${SRC_DIR%/coc}"
  [ -f "$SRC_DIR/coc/streamer.py" ] || die "Downloaded archive has no stream/ folder."
}

install_packages() {
  step "Installing system packages 安裝系統套件 (ffmpeg, python3, ...)"
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -qq
  apt-get install -y -qq ffmpeg python3 python3-venv ca-certificates curl \
    unattended-upgrades logrotate acl >/dev/null
  ok "ffmpeg $(ffmpeg -version | head -n1 | awk '{print $3}')"
}

setup_swap() {
  local mem_kb swap_kb
  mem_kb="$(awk '/MemTotal/ {print $2}' /proc/meminfo)"
  swap_kb="$(awk '/SwapTotal/ {print $2}' /proc/meminfo)"
  if [ "$mem_kb" -lt 2000000 ] && [ "$swap_kb" -lt 1000000 ] && [ ! -f /swapfile ]; then
    step "Low memory: adding a 2 GB swap file 記憶體較小，加入 2 GB 交換空間"
    fallocate -l 2G /swapfile || dd if=/dev/zero of=/swapfile bs=1M count=2048 status=none
    chmod 600 /swapfile
    mkswap /swapfile >/dev/null
    swapon /swapfile
    grep -q '^/swapfile ' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
    ok "swap on"
  fi
}

setup_user_and_files() {
  step "Installing the stream software 安裝直播程式到 $APP_DIR"
  if ! id "$SVC_USER" >/dev/null 2>&1; then
    useradd --system --home-dir "$DATA_DIR" --no-create-home --shell /usr/sbin/nologin "$SVC_USER"
  fi
  install -d -m 755 "$APP_DIR" "$APP_DIR/bin"
  install -d -m 755 -o "$SVC_USER" -g "$SVC_USER" "$DATA_DIR" "$DATA_DIR/library" \
    "$DATA_DIR/staging" "$DATA_DIR/state"
  install -d -m 700 "$ETC_DIR"
  if [ "$(realpath "$SRC_DIR")" != "$(realpath "$APP_DIR")" ]; then
    rm -rf "$APP_DIR/coc"
    cp -r "$SRC_DIR/coc" "$APP_DIR/coc"
    install -m 755 "$SRC_DIR/bin/coc" "$APP_DIR/bin/coc"
    install -m 755 "$SRC_DIR/install.sh" "$APP_DIR/install.sh"
    install -m 644 "$SRC_DIR/README.md" "$APP_DIR/README.md" 2>/dev/null || true
    rm -rf "$APP_DIR/systemd" "$APP_DIR/config"
    cp -r "$SRC_DIR/systemd" "$SRC_DIR/config" "$APP_DIR/"
  fi
  find "$APP_DIR/coc" -name '__pycache__' -prune -exec rm -rf {} +
  chmod -R a+rX "$APP_DIR"
  ln -sf "$APP_DIR/bin/coc" /usr/local/bin/coc

  if [ ! -x "$APP_DIR/venv/bin/kaggle" ] || [ "$MODE" = install ]; then
    step "Installing the Kaggle tool 安裝 Kaggle 工具"
    [ -d "$APP_DIR/venv" ] || python3 -m venv "$APP_DIR/venv"
    "$APP_DIR/venv/bin/pip" install -q --upgrade pip >/dev/null
    # 'six' is listed explicitly: some kaggle releases import it without declaring it.
    "$APP_DIR/venv/bin/pip" install -q --upgrade kaggle six >/dev/null
    ok "kaggle $("$APP_DIR/venv/bin/kaggle" --version 2>/dev/null | awk '{print $NF}')"
  fi

  # A calm placeholder picture so the stream can start before the first sync.
  if [ ! -f "$DATA_DIR/placeholder_loop.mp4" ]; then
    ffmpeg -nostdin -v error -y -f lavfi -i "color=c=0x1f3b36:s=1920x1080:r=30" -t 10 \
      -vf "drawbox=x=0:y=ih*0.62:w=iw:h=ih*0.38:color=0x2d5a4f@0.8:t=fill" \
      -c:v libx264 -preset veryfast -profile:v high -pix_fmt yuv420p -b:v 1500k \
      -g 60 -keyint_min 60 -sc_threshold 0 -an -movflags +faststart \
      "$DATA_DIR/placeholder_loop.mp4"
    chown "$SVC_USER:$SVC_USER" "$DATA_DIR/placeholder_loop.mp4"
  fi
}

configure() {
  step "Settings 設定  (answers are saved in $ENV_FILE, readable by root only)"
  if [ "$HAVE_TTY" -eq 1 ]; then
    cat <<'EOF'
We need 4 answers. You can paste with right-click or Ctrl+Shift+V.
需要回答 4 個問題。可以用滑鼠右鍵或 Ctrl+Shift+V 貼上。
  1. YouTube stream key 串流金鑰:  YouTube Studio → Create 建立 → Go live 進行直播
     → Stream 串流 → "Stream key 串流金鑰" → Copy 複製
  2. Your Kaggle username 你的 Kaggle 使用者名稱
  3. Kaggle API token:  kaggle.com → your picture 頭像 → Settings 設定 → API
     → "Generate New Token 產生新權杖"
  4. The address of your "02 Assemble" notebook on Kaggle 「02 Assemble」筆記本的網址
     (e.g. https://www.kaggle.com/code/yourname/02-assemble)
EOF
  fi
  install -d -m 700 "$ETC_DIR"
  [ -f "$ENV_FILE" ] || { cp "$APP_DIR/config/env.example" "$ENV_FILE"; chmod 600 "$ENV_FILE"; }

  ask YOUTUBE_STREAM_KEY "1/4  Paste your YouTube stream key (hidden while typing):" \
      "     貼上 YouTube 串流金鑰（輸入時不會顯示）：" 1 '^[A-Za-z0-9_-]{8,}$'
  ask KAGGLE_USERNAME "2/4  Your Kaggle username:" "     你的 Kaggle 使用者名稱：" 0 '^[A-Za-z0-9_-]+$'
  local cur_token
  cur_token="$(get_kv KAGGLE_API_TOKEN)"; [ -n "$cur_token" ] || cur_token="$(get_kv KAGGLE_KEY)"
  KAGGLE_SECRET="${KAGGLE_API_TOKEN:-${KAGGLE_KEY:-$cur_token}}"
  ask KAGGLE_SECRET "3/4  Paste your Kaggle API token or key (hidden):" \
      "     貼上 Kaggle API 權杖或金鑰（輸入時不會顯示）：" 1 '^[A-Za-z0-9_.-]{16,}$'
  ask KAGGLE_NOTEBOOK "4/4  Paste the address of the \"02 Assemble\" notebook (or username/notebook-name):" \
      "     貼上「02 Assemble」筆記本的網址（或 使用者名稱/筆記本名稱）：" 0

  # Normalise the notebook to owner/slug.
  local nb="${KAGGLE_NOTEBOOK:-}"
  nb="${nb%/}"; nb="${nb%%\?*}"
  if [[ "$nb" =~ kaggle\.com/(code/)?([^/]+)/([^/]+) ]]; then nb="${BASH_REMATCH[2]}/${BASH_REMATCH[3]}"; fi
  if [ -n "$nb" ] && [[ "$nb" != */* ]] && [ -n "${KAGGLE_USERNAME:-}" ]; then nb="$KAGGLE_USERNAME/$nb"; fi
  KAGGLE_NOTEBOOK="$nb"

  set_kv YOUTUBE_STREAM_KEY "${YOUTUBE_STREAM_KEY:-}"
  set_kv KAGGLE_USERNAME "${KAGGLE_USERNAME:-}"
  set_kv KAGGLE_NOTEBOOK "${KAGGLE_NOTEBOOK:-}"
  # New-style tokens start with KGAT_; anything else is a legacy kaggle.json key.
  # Only ever write one of the two: an empty KAGGLE_KEY breaks token auth.
  if [[ "${KAGGLE_SECRET:-}" == KGAT_* ]]; then
    set_kv KAGGLE_API_TOKEN "$KAGGLE_SECRET"; set_kv KAGGLE_KEY ""
  else
    set_kv KAGGLE_KEY "${KAGGLE_SECRET:-}"; set_kv KAGGLE_API_TOKEN ""
  fi
  chown root:root "$ENV_FILE"; chmod 600 "$ENV_FILE"
  ok "Settings saved 設定已儲存"
}

check_kaggle() {
  [ -n "$(get_kv KAGGLE_NOTEBOOK)" ] || return 0
  step "Checking the Kaggle login 檢查 Kaggle 登入"
  if systemd-run --quiet --wait --pipe --collect -p User="$SVC_USER" -p EnvironmentFile="$ENV_FILE" \
       -E HOME="$DATA_DIR" -E KAGGLE_CONFIG_DIR="$DATA_DIR/.kaggle" \
       "$APP_DIR/venv/bin/kaggle" kernels status "$(get_kv KAGGLE_NOTEBOOK)" >/dev/null 2>&1; then
    ok "Kaggle works and the notebook was found 已連上 Kaggle，也找到筆記本"
  else
    warn "Could not reach that Kaggle notebook. Check the username/token/address with: sudo coc setup"
    warn "無法讀取那個 Kaggle 筆記本。請用 sudo coc setup 檢查帳號、權杖和網址。"
  fi
}

install_services() {
  step "Starting the services 啟動服務"
  install -m 644 "$APP_DIR"/systemd/coc-streamer.service "$APP_DIR"/systemd/coc-sync.service \
    "$APP_DIR"/systemd/coc-sync.timer /etc/systemd/system/
  install -d /etc/systemd/journald.conf.d
  install -m 644 "$APP_DIR/config/journald.conf" /etc/systemd/journald.conf.d/classic-of-calm.conf
  install -m 644 "$APP_DIR/config/logrotate" /etc/logrotate.d/classic-of-calm
  systemctl restart systemd-journald || true
  systemctl daemon-reload
  systemctl enable --now coc-sync.timer >/dev/null
  systemctl enable coc-streamer.service >/dev/null
  systemctl restart coc-streamer.service
  ok "Stream service running 直播服務已啟動"
}

setup_auto_updates() {
  step "Turning on automatic security updates 開啟自動安全更新"
  cat > /etc/apt/apt.conf.d/20auto-upgrades <<'EOF'
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
APT::Periodic::AutocleanInterval "7";
EOF
  # Reboot (only when an update needs it) in the same quiet hour as the daily reconnect.
  cat > /etc/apt/apt.conf.d/52classic-of-calm <<'EOF'
Unattended-Upgrade::Automatic-Reboot "true";
Unattended-Upgrade::Automatic-Reboot-Time "04:20";
Unattended-Upgrade::Remove-Unused-Kernel-Packages "true";
EOF
  systemctl enable --now unattended-upgrades >/dev/null 2>&1 || true
  ok "Automatic updates on 已開啟自動更新"
}

first_sync() {
  [ -n "$(get_kv KAGGLE_NOTEBOOK)" ] || return 0
  if [ -z "$(ls -A "$DATA_DIR/library/batches" 2>/dev/null)" ]; then
    step "Downloading this week's music in the background 在背景下載本週音樂"
    systemctl start --no-block coc-sync.service
    echo "This takes a few minutes; the stream picks the songs up by itself."
    echo "需要幾分鐘；下載完成後直播會自動開始播放新歌。"
  fi
}

# ------------------------------------------------------------------ main ---
if [ "$MODE" = configure ]; then
  [ -d "$APP_DIR/coc" ] || die "Not installed yet. Run the full installer first. 尚未安裝，請先執行完整安裝。"
  configure
  check_kaggle
  systemctl restart coc-streamer.service
  ok "Restarted with the new settings 已用新設定重新啟動"
  sleep 3
  /usr/local/bin/coc status || true
  exit 0
fi

bold "Classic of Calm — stream host setup 直播主機安裝"
find_source
install_packages
setup_swap
setup_user_and_files
configure
check_kaggle
setup_auto_updates
install_services
first_sync
sleep 5
echo
bold "All done! 安裝完成！"
echo "Check the stream any time with:   coc"
echo "隨時輸入 coc 就能查看直播狀態。"
echo "In YouTube Studio → Go live, the preview should appear within ~1 minute."
echo "約 1 分鐘內，YouTube Studio 的直播頁面就會出現預覽畫面。"
echo
/usr/local/bin/coc status || true
