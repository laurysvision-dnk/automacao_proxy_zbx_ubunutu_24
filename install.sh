#!/usr/bin/env bash
set -Eeuo pipefail
umask 077
ROOT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
server='' proxy_name='' pppoe_target='' pppoe_host='' community_file='' psk_file='' psk_identity=''
dry_run=0 no_start=0 replace_config=0 install_go=0
usage() {
  cat <<'HELP'
Uso: sudo bash install.sh --server IP_OU_DNS --hostname NOME_PROXY [opções]
  --pppoe-target IP          Habilitar coletor PPPoE neste BNG
  --pppoe-host NOME          Nome técnico do host no Zabbix
  --community-file ARQUIVO   Arquivo local com a comunidade SNMP; não é copiado ao Git
  --psk-file ARQUIVO         PSK hexadecimal para criptografia Zabbix
  --psk-identity NOME        Identidade PSK cadastrada no Zabbix
  --install-go              Instalar ferramenta Go do Ubuntu (opcional)
  --replace-config          Permitir substituir configuração de proxy existente
  --no-start                Instalar e validar arquivos sem iniciar/habilitar serviços
  --dry-run                 Mostrar plano sem alterar o sistema
Suporte desta versão: Ubuntu 24.04 ou 24.10, Linux amd64, Zabbix 7.0, SQLite.
HELP
}
fail() { printf 'Erro: %s\n' "$*" >&2; exit 1; }
while (($#)); do
  case "$1" in
    --server|--hostname|--pppoe-target|--pppoe-host|--community-file|--psk-file|--psk-identity)
      (($# >= 2)) || fail "Falta valor para $1"
      case "$1" in
        --server) server=$2;; --hostname) proxy_name=$2;; --pppoe-target) pppoe_target=$2;;
        --pppoe-host) pppoe_host=$2;; --community-file) community_file=$2;; --psk-file) psk_file=$2;; --psk-identity) psk_identity=$2;;
      esac
      shift 2;;
    --dry-run) dry_run=1; shift;; --no-start) no_start=1; shift;; --replace-config) replace_config=1; shift;; --install-go) install_go=1; shift;;
    -h|--help) usage; exit 0;; *) fail "Opção desconhecida: $1";;
  esac
done
[[ $server =~ ^[A-Za-z0-9_.:-]+$ ]] || fail 'Informe --server com IP ou DNS válido.'
[[ $proxy_name =~ ^[A-Za-z0-9_.\ -]+$ && ${#proxy_name} -le 128 ]] || fail 'Informe --hostname (até 128 caracteres, sem quebras de linha).'
if [[ -n $pppoe_target || -n $pppoe_host || -n $community_file ]]; then
  [[ $pppoe_target =~ ^[A-Za-z0-9_.:-]+$ && $pppoe_host =~ ^[A-Za-z0-9_.\ -]+$ && -n $community_file ]] || fail 'PPPoE exige --pppoe-target, --pppoe-host e --community-file juntos.'
  [[ ${#pppoe_host} -le 128 ]] || fail 'Nome técnico PPPoE excede 128 caracteres.'
  [[ -s $community_file && -r $community_file ]] || fail 'Arquivo de comunidade SNMP não está acessível.'
fi
if [[ -n $psk_file || -n $psk_identity ]]; then
  [[ -f $psk_file && -r $psk_file && $psk_identity =~ ^[A-Za-z0-9_.\ -]+$ ]] || fail 'PSK exige arquivo legível e identidade válida.'
  psk=$(cat -- "$psk_file")
  [[ $psk =~ ^[[:xdigit:]]+$ && ${#psk} -ge 32 && ${#psk} -le 512 && $((${#psk} % 2)) -eq 0 ]] || fail 'PSK precisa de 32 a 512 caracteres hexadecimais, em quantidade par.'
  unset psk
fi
if ((dry_run)); then
  printf 'Plano: sincronizar horário por NTP, Zabbix Proxy 7.0 SQLite + Agent2, SNMP, Python/venv, whois e coletores ópticos/BGP.\nServidor: %s\nProxy: %s\n' "$server" "$proxy_name"
  [[ -z $pppoe_target ]] || printf 'PPPoE: %s, host %s, timer de cinco minutos; segredo vindo de arquivo local.\n' "$pppoe_target" "$pppoe_host"
  [[ -z $psk_file ]] || printf 'TLS PSK habilitado; conteúdo não será exibido.\n'
  exit 0
fi
((EUID == 0)) || fail 'Execute como root ou com sudo.'
# shellcheck source=/dev/null
source /etc/os-release
[[ $ID == ubuntu && ( $VERSION_ID == 24.04 || $VERSION_ID == 24.10 ) && $(uname -m) == x86_64 ]] || fail 'Esta versão requer Ubuntu 24.04 ou 24.10 amd64; os fontes Go ainda não estão disponíveis para outras arquiteturas.'
if ((!no_start)); then
  [[ -d /run/systemd/system ]] || fail 'systemd não está ativo. Para validar em contêiner use --no-start.'
fi
if [[ -s /var/lib/zabbix/zabbix_proxy.db ]] && ((!replace_config)) && ! grep -q '^# Managed by Observa proxy installer' /etc/zabbix/zabbix_proxy.conf; then
  fail 'Proxy existente detectado. Use --replace-config somente se pretende atualizar sua configuração.'
fi
installed_version=$(dpkg-query -W -f='${Version}' zabbix-proxy-sqlite3 2>/dev/null || true)
[[ -z $installed_version || $installed_version =~ ^(1:)?7\.0\. ]] || fail 'Proxy instalado não é da série 7.0; migração de versão não é automática.'
work_dir=$(mktemp -d /tmp/observa-proxy-install.XXXXXX)
policy_changed=0
restore_policy() {
  if ((policy_changed)); then
    if [[ -f $work_dir/policy-original ]]; then cp -p "$work_dir/policy-original" /usr/sbin/policy-rc.d; else rm -f /usr/sbin/policy-rc.d; fi
  fi
  rm -rf -- "$work_dir"
}
trap restore_policy EXIT
backup_dir="/var/backups/observa-proxy/$(date -u +%Y%m%dT%H%M%SZ)-$$"
install -d -m 700 "$backup_dir"
for path in /etc/zabbix/zabbix_proxy.conf /etc/zabbix/zabbix_agent2.conf /etc/zabbix/observa.psk /etc/pppoe-sessions/community /etc/pppoe-sessions/collector.env /opt/asnname/asnamev4.py /opt/asnname/asnamev6.py /opt/asnname/status_as.py /etc/eras/snmp_project/snmp_monitor /usr/local/bin/pppoe-sessions /etc/systemd/system/pppoe-sessions.service /etc/systemd/system/pppoe-sessions.timer; do
  if [[ -f $path ]]; then cp --parents -- "$path" "$backup_dir/"; fi
done
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq ca-certificates curl fping git python3 python3-venv snmp whois sqlite3
fping_path=$(command -v fping)
fping6_path=$(command -v fping6 || true)
if ((!no_start)); then
  if systemctl is-active --quiet chrony.service; then
    clock_service=chrony
  elif systemctl is-active --quiet systemd-timesyncd.service; then
    clock_service=systemd-timesyncd
  else
    apt-get install -y -qq chrony
    systemctl enable --now chrony.service
    clock_service=chrony
  fi
  if [[ $clock_service == chrony ]]; then
    chronyc -a 'makestep 0.1 1' >/dev/null
    chronyc -a burst 4/4 >/dev/null
    chronyc waitsync 12 0 0 5 || fail 'O relógio não sincronizou pelo Chrony. Verifique as fontes NTP e o acesso à rede.'
  else
    timedatectl set-ntp true
    systemctl restart systemd-timesyncd.service
    clock_synchronized=0
    for ((attempt=0; attempt<30; attempt++)); do
      if [[ $(timedatectl show --property=NTPSynchronized --value) == yes ]]; then
        clock_synchronized=1
        break
      fi
      sleep 2
    done
    ((clock_synchronized)) || fail 'O relógio não sincronizou pelo systemd-timesyncd. Verifique as fontes NTP e o acesso à rede.'
  fi
  printf 'Relógio sincronizado por %s: %s\n' "$clock_service" "$(date --iso-8601=seconds)"
else
  printf 'Sincronização NTP ignorada em --no-start (systemd inativo).\n'
fi
python3 - "$ROOT_DIR" <<'PY'
import hashlib,json,pathlib,sys
root=pathlib.Path(sys.argv[1])
for name,expected in json.loads((root/'manifest.json').read_text()).items():
    path=(root/name).resolve()
    if root.resolve() not in path.parents or hashlib.sha256(path.read_bytes()).hexdigest()!=expected:
        raise SystemExit('Pacote alterado ou incompleto: '+name)
print('Checksums dos coletores conferidos.')
PY
if [[ $VERSION_ID == 24.04 ]]; then
  curl --fail --silent --show-error --location --proto '=https' --tlsv1.2 'https://repo.zabbix.com/zabbix/7.0/ubuntu/pool/main/z/zabbix-release/zabbix-release_7.0-5+ubuntu24.04_all.deb' -o "$work_dir/zabbix-release.deb"
  dpkg -i "$work_dir/zabbix-release.deb" >/dev/null
  apt-get update -qq
else
  for package in zabbix-proxy-sqlite3 zabbix-agent2 zabbix-sender; do
    candidate=$(apt-cache policy "$package" | awk '/Candidate:/ {print $2}')
    [[ $candidate =~ ^(1:)?7\.0\. ]] || fail "Ubuntu 24.10 precisa oferecer $package da série 7.0; candidato atual: $candidate"
  done
fi
if [[ -f /usr/sbin/policy-rc.d ]]; then cp -p /usr/sbin/policy-rc.d "$work_dir/policy-original"; fi
policy_changed=1
cat > /usr/sbin/policy-rc.d <<POLICY
#!/bin/sh
case "\$1" in zabbix-proxy|zabbix-agent2) exit 101;; esac
if [ -x "$work_dir/policy-original" ]; then exec "$work_dir/policy-original" "\$@"; fi
exit 0
POLICY
chmod 755 /usr/sbin/policy-rc.d
apt-get install -y -qq -o Dpkg::Options::=--force-confold zabbix-proxy-sqlite3 zabbix-agent2 zabbix-sender

((!install_go)) || apt-get install -y -qq golang-go
install -d -m 755 /opt/asnname /etc/eras/snmp_project /usr/lib/zabbix/externalscripts
if [[ ! -x /opt/asnname/venv/bin/python3 ]]; then python3 -m venv /opt/asnname/venv; fi
chown -R root:zabbix /opt/asnname/venv
chmod -R g+rX,o-rwx /opt/asnname/venv
install -m 644 "$ROOT_DIR"/collectors/asnname/*.py /opt/asnname/
for script in asname discovery_hw_interfaces_opticas_debian11.py run_signal run_asnname run_asnamev6 status_asn; do
  if [[ -f /usr/lib/zabbix/externalscripts/$script ]]; then
    cp --parents -- "/usr/lib/zabbix/externalscripts/$script" "$backup_dir/"
  fi
  install -m 755 "$ROOT_DIR/collectors/externalscripts/$script" /usr/lib/zabbix/externalscripts/
done
install -m 755 "$ROOT_DIR/bin/linux-amd64/snmp_monitor" /etc/eras/snmp_project/snmp_monitor
install -m 755 "$ROOT_DIR/bin/linux-amd64/pppoe-sessions" /usr/local/bin/pppoe-sessions
install -d -o zabbix -g zabbix -m 750 /var/lib/zabbix /var/log/zabbix /run/zabbix
cat > "$work_dir/proxy.conf" <<CONF
# Managed by Observa proxy installer
ProxyMode=0
Server=$server
Hostname=$proxy_name
DBName=/var/lib/zabbix/zabbix_proxy.db
LogFile=/var/log/zabbix/zabbix_proxy.log
PidFile=/run/zabbix/zabbix_proxy.pid
ExternalScripts=/usr/lib/zabbix/externalscripts
FpingLocation=$fping_path
Fping6Location=$fping6_path
Timeout=30
CONF
cat > "$work_dir/agent.conf" <<CONF
# Managed by Observa proxy installer
Server=127.0.0.1
ServerActive=$server
Hostname=$proxy_name
ListenIP=127.0.0.1
LogFile=/var/log/zabbix/zabbix_agent2.log
PidFile=/run/zabbix/zabbix_agent2.pid
Timeout=30
CONF
if [[ -n $psk_file ]]; then
  if [[ $(realpath "$psk_file") != /etc/zabbix/observa.psk ]]; then install -o root -g zabbix -m 640 "$psk_file" /etc/zabbix/observa.psk; fi
  chown root:zabbix /etc/zabbix/observa.psk
  chmod 640 /etc/zabbix/observa.psk
  for path in "$work_dir/proxy.conf" "$work_dir/agent.conf"; do
    cat >> "$path" <<CONF
TLSConnect=psk
TLSAccept=psk
TLSPSKIdentity=$psk_identity
TLSPSKFile=/etc/zabbix/observa.psk
CONF
  done
fi
zabbix_proxy -T -c "$work_dir/proxy.conf"
zabbix_agent2 -T -c "$work_dir/agent.conf"
install -o root -g zabbix -m 640 "$work_dir/proxy.conf" /etc/zabbix/zabbix_proxy.conf
install -o root -g zabbix -m 640 "$work_dir/agent.conf" /etc/zabbix/zabbix_agent2.conf
if [[ -n $pppoe_target ]]; then
  install -d -m 700 /etc/pppoe-sessions /var/lib/pppoe-sessions
  if [[ $(realpath "$community_file") != /etc/pppoe-sessions/community ]]; then install -m 600 "$community_file" /etc/pppoe-sessions/community; fi
  chown root:root /etc/pppoe-sessions/community
  chmod 600 /etc/pppoe-sessions/community
  printf 'PPPOE_TARGET="%s"\nPPPOE_HOST="%s"\n' "$pppoe_target" "$pppoe_host" > /etc/pppoe-sessions/collector.env
  cat > /etc/systemd/system/pppoe-sessions.service <<'UNIT'
[Unit]
Description=Observa - coleta Huawei PPPoE via SNMP
After=network-online.target zabbix-proxy.service
Wants=network-online.target

[Service]
Type=oneshot
EnvironmentFile=/etc/pppoe-sessions/collector.env
ExecStart=/usr/local/bin/pppoe-sessions -target ${PPPOE_TARGET} -community-file /etc/pppoe-sessions/community -output /var/lib/pppoe-sessions/current.json -zabbix-address 127.0.0.1:10051 -zabbix-host ${PPPOE_HOST} -zabbix-key pppoe.sessions.snapshot.gzbase64
TimeoutStartSec=90
StateDirectory=pppoe-sessions
StateDirectoryMode=0700
NoNewPrivileges=yes
ProtectSystem=strict
ProtectHome=yes
PrivateTmp=yes
ReadWritePaths=/var/lib/pppoe-sessions
UNIT
  cat > /etc/systemd/system/pppoe-sessions.timer <<'UNIT'
[Unit]
Description=Observa - coleta PPPoE a cada cinco minutos

[Timer]
OnCalendar=*:0/5
AccuracySec=30s
Persistent=true
Unit=pppoe-sessions.service

[Install]
WantedBy=timers.target
UNIT
fi
runuser -u zabbix -- /opt/asnname/venv/bin/python3 -c 'import sys; print("Python acessível ao usuário zabbix:", sys.version.split()[0])'
runuser -u zabbix -- test -x /etc/eras/snmp_project/snmp_monitor
if ((!no_start)); then
  systemctl daemon-reload
  systemctl enable zabbix-proxy zabbix-agent2
  systemctl restart zabbix-proxy zabbix-agent2
  [[ -z $pppoe_target ]] || systemctl enable --now pppoe-sessions.timer
  systemctl is-active --quiet zabbix-proxy zabbix-agent2
fi
printf 'Instalação concluída. Backup das configurações: %s\n' "$backup_dir"
printf 'Cadastre no servidor um proxy ativo com o nome %s e associe os hosts e templates a ele.\n' "$proxy_name"
printf 'PPPoE precisa do item trapper pppoe.sessions.snapshot.gzbase64 no host técnico informado.\n'
