# Base auditada no proxy

Levantamento por SSH em **04/10/2026**. Nenhum serviço de produção foi reinstalado ou reiniciado.

## Plataforma e dependências

- Ubuntu 24.04 LTS, amd64.
- `zabbix-proxy-sqlite3` e `zabbix-agent2`: **7.0.31**; repositório oficial 7.0.
- Proxy e Agent2 ativos e habilitados.
- Proxy ativo com SQLite em `/var/lib/zabbix/zabbix_proxy.db`; timeout de 30 segundos.
- Python 3.12.3 e `python3-venv`; o ambiente ASN instalado contém somente pip, sem bibliotecas Python adicionais.
- Net-SNMP 5.9.4; ferramentas `snmpwalk`, `snmpbulkwalk`, `snmpget` e whois usadas pelos scripts.
- Go 1.27.1 instalado na VM. Os coletores não dependem de um runtime Go separado.
- WireGuard `wg0` ativo, com rota para o servidor Zabbix.

## Coletores encontrados

| Arquivo / comando | Função | Dependências / argumentos |
| --- | --- | --- |
| `discovery_hw_interfaces_opticas_debian11.py` | Descobre interfaces ópticas Huawei, relacionando ifName, ifAlias e entPhysicalName | Python, snmpbulkwalk; host, comunidade, porta e opcional M/S |
| `run_signal` → `/etc/eras/snmp_project/snmp_monitor` | Leitura de potência óptica RX/TX, incluindo portas multilane | Binário Linux amd64; comunidade, host, índice físico, porta, RX/TX, M/S |
| `run_asnname` → `/opt/asnname/asnamev4.py` | Descoberta BGP IPv4 e resolução de nome ASN | Python, snmpwalk e whois; host, comunidade, porta |
| `run_asnamev6` → `/opt/asnname/asnamev6.py` | Descoberta BGP IPv6 e resolução de nome ASN | Python, snmpwalk e whois; host, comunidade, porta |
| `status_asn` → `/opt/asnname/status_as.py` | Estado de uma sessão BGP Huawei; retorna inteiro de 1 a 6 | Python, snmpbulkwalk e snmpget; comunidade, host, porta, peer |
| `asname` | Consulta ASN via whois, mantida para compatibilidade | Bash e whois; interface antiga com três argumentos |
| `/usr/local/bin/pppoe-sessions` | Coleta sessões PPPoE via SNMP, salva snapshot e envia trapper comprimido | Comunidade em arquivo root; target, output, zabbix-address, zabbix-host, zabbix-key |

Todos os scripts externos estão em `/usr/lib/zabbix/externalscripts`. Os caminhos e a ordem dos argumentos foram preservados no instalador, pois os templates do Zabbix dependem deles.

## Ajustes confirmados

- Descoberta óptica: a cópia antiga usava `head -80` nas tabelas SNMP. A versão atual percorre as tabelas sem esse corte e faz correspondência pelo nome físico, incluindo 100GE, 40GE, 25GE, 10GE, XGE/GE e GigabitEthernet.
- Descoberta BGP: índices IPv4/IPv6 são extraídos separadamente; os peers precisam ser endereços válidos. A descoberta imprime JSON com a chave `data`.
- Permissões ASN: diretório virtualenv pertence a `root:zabbix` e permite execução pelo usuário `zabbix`. O instalador aplica isso para evitar o `Permission denied` anterior.
- Status BGP: wrapper e Python recebem comunidade, host, porta e peer na ordem correta. Falhas ou estados ambíguos terminam com erro, sem devolver `-1` para item unsigned.
- PPPoE: o serviço `pppoe-sessions-conecta.service` usa proteção de filesystem, arquivo de comunidade 0600 e snapshot em diretório 0700. O timer executa a cada cinco minutos; última execução consultada terminou com sucesso.

## Proveniência e limites

- Óptico: binário compilado com Go 1.21.1 e `github.com/gosnmp/gosnmp` v1.38.0, para Linux amd64, CGO desativado.
- PPPoE: binário compilado com Go 1.26.5 e a mesma versão gosnmp, para Linux amd64, CGO desativado.
- Os fontes de ambos os binários não foram encontrados. A primeira versão distribui exatamente esses executáveis, registrados por SHA-256; ARM e recompilação dependem da recuperação dos fontes.
- A comunidade SNMP em uso não está embutida nos executáveis examinados. Nenhuma comunidade, chave WireGuard/PSK, banco do proxy ou snapshot de assinantes foi copiado ao pacote.
- Scripts BGP de descoberta ainda usam whois síncrono sem timeout próprio. Muitos ASNs diferentes ou whois indisponível podem ultrapassar o timeout do Zabbix. Isso foi identificado e documentado, sem alterar o comportamento dessa base em produção.
- O whois requer resolução DNS e acesso à porta TCP 43; SNMP depende da conectividade com os equipamentos.
- O ZIP ASN original foi localizado nos Downloads, mas o pacote usa os arquivos **corrigidos da VM**, não as cópias antigas do ZIP.
- As cópias `.backup-*` presentes na VM foram usadas para comparação e não entram na instalação.
- O coletor óptico de descoberta antigo identificava Bee Solutions / Fernando Almondes no cabeçalho. A versão corrigida instalada foi mantida como encontrada; não foi atribuída autoria nova aos coletores existentes.

## Validação do pacote

- Testes de descoberta 100GE além da linha 80, correspondência do índice físico, separação IPv4/IPv6, argumentos de status BGP e falha SNMP sem valor negativo.
- Checksums de todos os arquivos distribuídos.
- Validação dos argumentos do instalador e recusa de credencial embutida na URL Git.
- Instalação real em ambiente descartável Ubuntu 24.04 amd64, com Zabbix 7.0.31 e verificação de permissões.

A comunicação completa com o servidor Zabbix, o túnel e os equipamentos em uma VM nova exige os parâmetros reais daquela VM e deve ser validada após o cadastro do proxy e dos hosts.
