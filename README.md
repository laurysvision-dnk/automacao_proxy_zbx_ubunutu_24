# Instalador do proxy Observa

Pacote extraído e auditado no proxy da Conecta em **04/10/2026**. Instala Zabbix Proxy **7.0**, SQLite, Agent2, `fping` para verificações ICMP, ferramentas SNMP, Python com ambiente virtual, whois e os coletores ópticos, BGP e PPPoE. Também instala o coletor Beeppp para Cisco e MikroTik. O caminho de `fping` é detectado e configurado no proxy. Durante a instalação normal, sincroniza o relógio via NTP antes de iniciar o proxy, preservando o fuso horário existente.

Esta versão atende **Ubuntu 24.04 e 24.10 / Linux amd64**. No 24.04, usa o repositório oficial do Zabbix 7.0; no 24.10, usa os pacotes Zabbix 7.0 do próprio Ubuntu. O instalador confirma que Proxy, Agent2 e Sender disponíveis são da série 7.0 antes de instalá-los. Ubuntu 24.10 já chegou ao fim do suporte: mantenha uma fonte de pacotes acessível e planeje migrar a VM para uma versão LTS. Os dois executáveis Go são os binários originais em produção, com SHA-256 registrado em `manifest.json`. Seus fontes não foram localizados na VM nem no Mac; não é possível recompilar para ARM nesta versão. Go não é necessário para executar esses binários. `--install-go` instala a ferramenta oferecida pelo Ubuntu para desenvolvimento.

## Instalação a partir do Git

Use as URLs deste repositório abaixo. Em repositório privado, configure antes uma chave de leitura para o Git; não inclua tokens na URL.

```bash
INSTALLER_URL='https://raw.githubusercontent.com/laurysvision-dnk/automacao_proxy_zbx_ubunutu_24/main/bootstrap.sh'
REPO_GIT='https://github.com/laurysvision-dnk/automacao_proxy_zbx_ubunutu_24.git'
curl -fsSL "$INSTALLER_URL" -o /tmp/observa-proxy-bootstrap.sh
sudo bash /tmp/observa-proxy-bootstrap.sh \
  --repo "$REPO_GIT" --ref main \
  --server zabbix.exemplo.com.br \
  --hostname PRX-NOVO-PROVEDOR
```

Para Git privado via SSH, clone o repositório usando sua chave e execute `sudo bash install.sh ...`, ou forneça `--repo git@github.com:laurysvision-dnk/automacao_proxy_zbx_ubunutu_24.git` ao bootstrap já baixado. A identidade que executa o clone precisa ter acesso ao repositório e conhecer a chave SSH do servidor Git.

O bootstrap baixa uma revisão explícita, exibe seu commit e chama o instalador. Depois da publicação, use a nova tag de versão para repetir a mesma instalação. A tag `v1.0.1` é anterior ao suporte 24.10 e continuará recusando essa versão. `--dry-run` mostra o plano; `--no-start` instala e valida os arquivos sem habilitar ou iniciar os serviços e, por isso, não sincroniza o horário.

## PPPoE

Crie um arquivo local protegido contendo a comunidade SNMP. O instalador recebe somente o caminho; a comunidade não precisa aparecer no comando nem no Git.

```bash
sudo install -m 600 /dev/null /root/pppoe-community
sudo nano /root/pppoe-community
sudo bash install.sh \
  --server zabbix.exemplo.com.br --hostname PRX-NOVO-PROVEDOR \
  --pppoe-target 198.51.100.10 --pppoe-host PPPOE-NOVO-PROVEDOR \
  --community-file /root/pppoe-community
```

A instalação cria `pppoe-sessions.service` e `pppoe-sessions.timer`, com execução a cada cinco minutos, mantendo o contrato existente:

- Arquivo local: `/var/lib/pppoe-sessions/current.json`, acessível somente ao root.
- Envio ao proxy local: `127.0.0.1:10051`.
- Nome técnico do host: valor de `--pppoe-host`.
- Item trapper: **`pppoe.sessions.snapshot.gzbase64`**.

O host deve existir no Zabbix, estar associado a este proxy e ter esse item trapper/template. O coletor exige conectividade SNMP com o BNG. A primeira coleta automática ocorre na próxima janela de cinco minutos. Depois de configurar o host, é possível testar com `sudo systemctl start pppoe-sessions.service`.

Nesta versão há **um concentrador PPPoE por proxy**, reproduzindo a instalação encontrada. Reexecutar o instalador sem parâmetros PPPoE preserva a configuração anterior.

## Beeppp para Cisco e MikroTik

O instalador copia `collectors/externalscripts/beeppp_api_zbx.py` para `/usr/lib/zabbix/externalscripts/beeppp_api_zbx.py` e instala `netmiko==4.4.0`, `RouterOS-api==0.18.1` e `paramiko==3.5.1` em `/usr/lib/zabbix/externalscripts/venv`. O script é a versão original Bee Solutions do pacote fornecido, com apenas finais de linha normalizados para LF, como pede a documentação; a licença MIT acompanha o pacote. Paramiko 3.5.1 foi validado com o Cisco da Hycom, cujo SSH oferece algoritmos legados. O teste real como usuário `zabbix` retornou JSON válido com 90 sessões PPPoE.

O instalador **não importa o template Beeppp nem configura macros ou credenciais**. Depois de criar o host e vinculá-lo ao proxy, importe/vincule o template manualmente e configure no host `{$BEEPPP_USUARIO}`, `{$BEEPPP_SENHA}`, `{$BEEPPP_PORTA}` e `{$BEEPPP_VENDOR}` (`cisco` ou `mikrotik`). Para a senha, use macro do tipo Secret text. Confirme que a saída do item `beeppp_api_zbx.py[...]` é JSON válido antes de usar os itens dependentes.

Esse coletor é separado do serviço `pppoe-sessions` por SNMP/trapper descrito acima. Instalar o Beeppp não modifica o serviço existente nem configura Huawei com esse template. A instalação do arquivo não substitui o teste de conectividade SSH/API do equipamento a partir do proxy.

## Rede e TLS

O instalador não instala nem configura WireGuard. A conectividade da VM com o servidor Zabbix e os equipamentos deve ser preparada separadamente.

Para sincronizar data e hora, usa Chrony ou `systemd-timesyncd` se este já estiver ativo. Em VM sem serviço NTP ativo, instala e habilita Chrony. A instalação para com erro claro se não conseguir confirmar a sincronização; libere o acesso às fontes NTP configuradas antes de repetir. O fuso horário não é alterado. Verifique com `timedatectl status` e, quando usar Chrony, `chronyc tracking`.

Para TLS PSK acrescente `--psk-file /root/proxy.psk --psk-identity PRX-NOVO-PROVEDOR`. A chave precisa conter 32 a 512 caracteres hexadecimais, em quantidade par. Cadastre a mesma identidade/chave na configuração do proxy e, se monitorar o Agent2, na configuração daquele host no Zabbix.

## Depois da instalação

1. Cadastre no Zabbix um **proxy ativo**, usando exatamente o nome de `--hostname`.
2. Vincule o proxy ao provedor no painel Observa.
3. Adicione ou importe os hosts manualmente no Zabbix, associando-os ao proxy e aos grupos do provedor.
4. Vincule manualmente os templates que chamam os scripts externos e configure as macros necessárias em cada host.
5. Para PPPoE, confira também o item trapper acima.

Este instalador prepara a VM. Ele não cria hosts, não importa templates, não cria o cadastro do proxy no servidor e não configura o vínculo do provedor no backend. Essas são operações distintas do cadastro automático de grupos pelo backend.

## Atualização e verificação

```bash
sudo systemctl status zabbix-proxy zabbix-agent2 --no-pager
sudo systemctl list-timers 'pppoe*' --no-pager
sudo journalctl -u pppoe-sessions.service -n 30 --no-pager
sudo zabbix_proxy -T -c /etc/zabbix/zabbix_proxy.conf
```

O instalador valida o sistema e os checksums, mantém o banco SQLite, faz backup dos arquivos existentes em `/var/backups/observa-proxy/` e valida as configurações antes de iniciar os serviços. Não faz migração automática entre versões maiores do Zabbix. Em um proxy anterior a este instalador, exige `--replace-config` para substituir configurações; esse parâmetro autoriza a atualização e os reinícios correspondentes. Faça atualizações de proxies existentes em uma janela de manutenção.

O backup contém configurações/segredos locais e deve permanecer protegido no servidor. Não copie esse diretório ao Git.

Testes locais: `python3 -m unittest discover -s tests -v` e `bash -n install.sh bootstrap.sh`. Também foi feita instalação em contêiner Ubuntu 24.04 amd64, validação das configurações reais do Zabbix, execução do proxy para criar SQLite e reinstalação verificando preservação do banco. Os serviços systemd do proxy de produção foram somente consultados.

Documentação oficial: [pacotes Zabbix 7.0](https://www.zabbix.com/documentation/7.0/en/manual/installation/install_from_packages), [scripts externos](https://www.zabbix.com/documentation/7.0/en/manual/config/items/itemtypes/external).
