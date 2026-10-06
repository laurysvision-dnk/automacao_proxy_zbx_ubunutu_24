#!/usr/lib/zabbix/externalscripts/venv/bin/python3

import re
import json
from datetime import datetime, timedelta
from netmiko import ConnectHandler
import sys
import routeros_api

# Desenvolvido por: Bee Solutions
# Autor: Fernando Almondes
# Data: 19-09-2026 - 18:06

agora = datetime.now()

try:
    ip_bng = sys.argv[1]
    usuario_bng = sys.argv[2]
    senha_bng = sys.argv[3]
    porta_bng = sys.argv[4]
    vendor = sys.argv[5]
except:
    print()
    print('--> Desenvolvido por: Bee Solutions')
    print('--> Autor: Fernando Almondes')
    print('--> Agora:', agora)
    print(f"--> Use: python3 {sys.argv[0]} ip 'usuario' 'senha' porta cisco|huawei|mikrotik")
    print()
    sys.exit(1)

dados = []

def calcula_uptime_sec(horario):
    now = datetime.now()

    uptime_str = horario
    uptime_dt = datetime.strptime(uptime_str, '%Y-%m-%d %H:%M:%S')
    uptime_diferenca = now - uptime_dt
    uptime_sec = int(uptime_diferenca.total_seconds())

    return uptime_sec

def calcula_uptime(uptime):
    pattern = re.compile(r'(?:(\d+)w)?(?:(\d+)d)?(?:(\d+)h)?(?:(\d+):(\d+):(\d+))?')
    now = datetime.now()

    weeks, days, hours, minutes, seconds = 0, 0, 0, 0, 0
    match = pattern.match(uptime)
    if match.group(1): weeks = int(match.group(1))
    if match.group(2): days = int(match.group(2))
    if match.group(3): hours = int(match.group(3))
    if match.group(4): hours = int(match.group(4))  # Para a parte do formato HH:MM:SS
    if match.group(5): minutes = int(match.group(5))
    if match.group(6): seconds = int(match.group(6))

    total_timedelta = timedelta(weeks=weeks, days=days, hours=hours, minutes=minutes, seconds=seconds)
    data_conexao = now - total_timedelta
    uptime_ok = (data_conexao.strftime("%Y-%m-%d %H:%M:%S"))

    return uptime_ok

def bng_cisco():

    cisco_bee = {
        'device_type': 'cisco_xe',
        'host':   ip_bng,
        'username': usuario_bng,
        'password': senha_bng,
        'port' : porta_bng,
        'secret': 'ok',
    }

    try:
        net_connect = ConnectHandler(**cisco_bee)

    except Exception as e:
        print()
        print('--> Erro na conexao SSH.', e)
        print()
        return

    # Digitando enable e comandos
    net_connect.enable()

    conteudo = ''

    conteudo = net_connect.send_command('show subscriber session identifier authen-status authenticated detailed | include (Identity:|IPv4 Address:|Match Any|Interface:|Session Up-time:)', read_timeout=300)
    conteudo += net_connect.send_command('show pppoe session | include (Vi)', read_timeout=300)

    net_connect.disconnect()

    # Iniciando regex
    mac = re.findall(r'^\s+([0-9]+).*([0-9a-f]{4}\.[0-9a-f]{4}\.[0-9a-f]{4}).*(Te[0-9\/\.]+|Gi[0-9\/\.]+|Po[0-9\/\.]+).*(Vi[1-2][\.0-9]+)', conteudo, re.MULTILINE) # .*([0-9a-f]+\.[0-9a-f]+\.[0-9a-f]+)

    blocos = re.split(r'(?=UID:)', conteudo.strip())

    mac_dict = {(j[0], j[3]): j for j in mac}

    for bloco in blocos:
        if not bloco:
            continue

        user_id = re.search(r'UID:\s+([0-9]+)', bloco)
        username = re.search(r'Identity:\s+(.*)', bloco)
        ipv4 = re.search(r'IPv4 Address:\s+([0-9\.]+)', bloco)
        vi = re.search(r'Interface:\s+(.*)', bloco)
        bytes_in = re.search(r'In\s+[0-9]+\s+([0-9]+)', bloco)
        bytes_out = re.search(r'Out\s+[0-9]+\s+([0-9]+)', bloco)
        uptime = re.search(r'Session Up-time:\s+([0-9a-z\:]+)', bloco)

        if not user_id:
            continue

        uid = user_id.group(1) if user_id else None
        vi_pppoe = vi.group(1).replace('Virtual-Access', 'Vi') if vi else None
        uptime_pppoe = uptime.group(1) if uptime else None
        uptime_ts = calcula_uptime(uptime_pppoe)

        dados.append({
            'user_id': user_id.group(1) if user_id else None,
            'username': username.group(1) if username else None,
            'ipv4': ipv4.group(1) if ipv4 else '0.0.0.0',
            'vi': vi.group(1).replace('Virtual-Access', 'Vi') if vi else None,
            'bytes_in': bytes_in.group(1) if bytes_in else 0,
            'bytes_out': bytes_out.group(1) if bytes_out else 0,
            'uptime': uptime.group(1) if uptime else None,
            'uptime_ts': uptime_ts,
            'uptime_sec': calcula_uptime_sec(uptime_ts),
            'mac': mac_dict.get((uid, vi_pppoe))[1] if isinstance(mac_dict.get((uid, vi_pppoe)), tuple) else None,
            'interface': mac_dict.get((uid, vi_pppoe))[2] if isinstance(mac_dict.get((uid, vi_pppoe)), tuple) else None
        })

def bng_huawei():
    bee_hw = {
        'device_type': 'huawei_vrp',
        'host':   ip_bng,
        'username': usuario_bng,
        'password': senha_bng,
        'port' : porta_bng,
        #'secret': 'ok',
    }

    horario = datetime.now().strftime('%d-%m-%Y_%H-%M-%S')

    try:
        net_connect = ConnectHandler(**bee_hw)

    except Exception as e:
        print()
        print('--> Erro na conexao SSH.', e)
        print()
        return

    # Digitando enable e comandos
    # net_connect.enable()

    conteudo = net_connect.send_command('display access-user user-type pppoe verbose nop | no-more | include (User access index|User name|User access interface|User MAC|User IP address|Accounting start time|Up bytes number|Down bytes number)', read_timeout=300)

    net_connect.disconnect()

    index = re.findall(r'User access index\s+:\s(.*)', conteudo)
    pppoe = re.findall(r'User name\s+:\s(.*)', conteudo)
    interface = re.findall(r'User access interface\s+:\s(.*)', conteudo)
    mac = re.findall(r'User MAC\s+:\s(.*)', conteudo)
    ipv4 = re.findall(r'User IP address\s+:\s(.*)', conteudo)
    acct_start_time = re.findall(r'Accounting start time\s+:\s(.*)', conteudo)

    ipv4_bytes_in = re.findall(r'^\s+Up bytes number\(high,low\)\s+:\s\((.*)\)', conteudo, re.MULTILINE)
    ipv4_bytes_out = re.findall(r'^\s+Down bytes number\(high,low\)\s+:\s\((.*)\)', conteudo, re.MULTILINE)
    ipv6_bytes_in = re.findall(r'IPV6 Up bytes number\(high,low\)\s+:\s\((.*)\)', conteudo)
    ipv6_bytes_out = re.findall(r'IPV6 Down bytes number\(high,low\)\s+:\s\((.*)\)', conteudo)

    # Calculando high + low de ipv4 e ipv6 (in e out)
    ipv4_bytes_in_f = [sum(map(int, item.split(','))) for item in ipv4_bytes_in]
    ipv4_bytes_out_f = [sum(map(int, item.split(','))) for item in ipv4_bytes_out]
    ipv6_bytes_in_f = [sum(map(int, item.split(','))) for item in ipv6_bytes_in]
    ipv6_bytes_out_f = [sum(map(int, item.split(','))) for item in ipv6_bytes_out]

    # Somando bytes ipv4 in/out + bytes ipv6 in/out
    bytes_in = [a + b for a, b in zip(ipv4_bytes_in_f, ipv6_bytes_in_f)]
    bytes_out = [a + b for a, b in zip(ipv4_bytes_out_f, ipv6_bytes_out_f)]

    tamanho = len(index)

    listas = [index, pppoe, interface, mac, ipv4, acct_start_time, bytes_in, bytes_out]

    validacao = all(tamanho == len(l) for l in listas)

    if validacao is False:
        print(f'--> Alguma das listas nao tem o mesmo tamanho ({tamanho}), aguardar proxima coleta...')
        print()
        return

    lista_final = list(zip(index, pppoe, interface, mac, ipv4, acct_start_time, bytes_in, bytes_out))

    if len(lista_final) < 1:
        print('--> Lista menor que 1 usuario ou invalida, aguardar proxima coleta...')
        print()
        return

    for d in lista_final:
        dados.append({
            'user_id': d[0],
            'username': d[1],
            'ipv4': d[4],
            'vi': d[0],
            'bytes_in': d[6],
            'bytes_out': d[7],
            'uptime': d[5],
            'uptime_ts': d[5],
            'uptime_sec': calcula_uptime_sec(d[5]),
            'mac': d[3],
            'interface': d[2]
        })

def bng_mikrotik():

    try:
        connection = routeros_api.RouterOsApiPool(ip_bng, username=usuario_bng, password=senha_bng, port=porta_bng, plaintext_login=True)
        api = connection.get_api()

    except Exception as e:
        print()
        print('--> Erro na conexao.', e)
        print()
        return

    # usuario = name, ipv4 = address, mac = caller-id, uptime = uptime
    ppps = api.get_resource('/ppp/active')
    ppp1 = ppps.get()
    #print(ppp3)

    lista_usuarios = []
    lista_ipv4 = []
    lista_macs = []
    lista_uptime = []

    for i in ppp1:
        lista_usuarios.append(i['name'])
        lista_ipv4.append(i['address'])
        lista_macs.append(i['caller-id'])
        lista_uptime.append(i['uptime'])

    # interface p1 = interface
    ppps = api.get_resource('/interface/pppoe-server/server')
    ppp2 = ppps.get(disabled='no', invalid='no')

    lista_service_names = []
    lista_interfaces_names = []

    for i in ppp2:
        lista_service_names.append(i['service-name'])
        lista_interfaces_names.append(i['interface'])

    lista_services_interfaces = list(zip(lista_service_names, lista_interfaces_names))

    #print(lista_services_interfaces)

    # interface p2 = service
    ppps = api.get_resource('/interface/pppoe-server')
    ppp3 = ppps.get() # Removendo o filtro running=true - agora adiciono um - traco caso nao tenha

    lista_usuarios_server = []
    lista_services = []
    lista_index = []

    for i in ppp3:
        #print(i)
        try:
            lista_services.append(i['service'])
        except:
            lista_services.append('-') # Caso nao tenha service

        lista_usuarios_server.append(i['name'])
        lista_index.append(i['id'])

    lista_usuarios_services = list(zip(lista_usuarios_server, lista_services))

    #print(lista_usuarios_services)

    lista_interfaces = []
    lista_pppoes = []

    lista_services_interfaces_dict = {(j[0]): j for j in lista_services_interfaces}

    # Verificando interface de cada um dos usuarios da lista de pppoes de /ppp/active
    for i in lista_usuarios_services:
        interface = i[0]
        service = i[1]
        try:
            if lista_services_interfaces_dict[service][0] == service:
                lista_pppoes.append(i[0])
                lista_interfaces.append(lista_services_interfaces_dict[service][1])
        except:
            lista_pppoes.append(i[0])
            lista_interfaces.append('-') # Caso nao tenha service

    # Tentativa de remover a parte do nome da interface pppoe para ficar somente o nome do usuario para comparacao seguinte
    #lista_pppoes_regex = [re.sub(r'pppoe-|-[0-9]>|[<>]', '', t) for t in lista_pppoes]
    lista_pppoes_regex = [re.sub(r'pppoe-|[<>]', '', t) for t in lista_pppoes]

    lista_pppoes_interfaces = list(zip(lista_pppoes_regex, lista_interfaces))
    #print(lista_pppoes_interfaces)

    lista_pppoes_interfaces_ok = []

    #print(lista_pppoes_interfaces)

    # Validando se o usuario pppoe vindo da lista de /interface/pppoe-server esta na lista inicial de /ppp/active

    lista_pppoes_interfaces_dict = {(j[0]): j for j in lista_pppoes_interfaces}

    lista_usuarios_com_problema = []

    for i in lista_usuarios:
        ppp = i
        try:
            if lista_pppoes_interfaces_dict[ppp][0] == ppp:
                lista_pppoes_interfaces_ok.append(lista_pppoes_interfaces_dict[ppp][1])
            else:
                lista_pppoes_interfaces_ok.append('-')
        except Exception as e:
            #print('--> Erro de chave nao encontrada.', e)
            lista_pppoes_interfaces_ok.append('-')
            lista_usuarios_com_problema.append(e)

    now = datetime.now()

    lista_uptime_ok = []

    # Ajustando uptime para horario | Ex: 1d6h37m43s para 2024-09-05 17:04:53
    for i in lista_uptime:
        semanas = int(re.search(r'(\d+)w', i).group(1)) if 'w' in i else 0
        dias = int(re.search(r'(\d+)d', i).group(1)) if 'd' in i else 0
        horas = int(re.search(r'(\d+)h', i).group(1)) if 'h' in i else 0
        minutos = int(re.search(r'(\d+)m', i).group(1)) if 'm' in i else 0
        segundos = int(re.search(r'(\d+)s', i).group(1)) if 's' in i else 0
        uptime_delta = timedelta(weeks=semanas, days=dias, hours=horas, minutes=minutos, seconds=segundos)
        uptime_diferenca = now - uptime_delta
        uptime = uptime_diferenca.strftime("%Y-%m-%d %H:%M:%S")
        lista_uptime_ok.append(uptime)

    ppps = api.get_resource('/interface')
    conteudo = list(ppps.get(type='pppoe-in'))

    # Desconectando
    connection.disconnect()

    bytes_in = []
    bytes_out = []

    for ppp in conteudo:
        bytes_in.append(int(ppp['tx-byte']))
        bytes_out.append(int(ppp['rx-byte']))

    tamanho = len(lista_index)

    listas = [lista_index, lista_usuarios, lista_pppoes_interfaces_ok, lista_macs, lista_ipv4, lista_uptime_ok, bytes_in, bytes_out]

    validacao = all(tamanho == len(l) for l in listas)

    if validacao is False:
        print(f'--> Alguma das listas nao tem o mesmo tamanho ({tamanho}), aguardar proxima coleta...')
        print()
        return

    lista_final = list(zip(lista_index, lista_usuarios, lista_pppoes_interfaces_ok, lista_macs, lista_ipv4, lista_uptime_ok, bytes_in, bytes_out))

    '''
    print('--> Tamanho da lista de Index:', len(lista_index))
    print('--> Tamanho da lista de usuario:', len(lista_usuarios))
    print('--> Tamanho da lista de interfaces', len(lista_pppoes_interfaces_ok))
    print('--> Tamanho da lista de MACs:', len(lista_macs))
    print('--> Tamanho da lista de Ipv4:', len(lista_ipv4))
    print('--> Tamanho da lista de Uptimes:', len(lista_uptime_ok))
    print('--> Tamanho da lista de bytes_in:', len(bytes_in))
    print('--> Tamanho da lista de bytes_out:', len(bytes_out))
    '''

    if len(lista_final) < 1:
        print('--> Lista menor que 1 usuario ou invalida, aguardar proxima coleta...')
        print()
        return

    for d in lista_final:
        dados.append({
            'user_id': d[0],
            'username': d[1],
            'ipv4': d[4],
            'vi': d[0],
            'bytes_in': d[6],
            'bytes_out': d[7],
            'uptime': d[5],
            'uptime_ts': d[5],
            'uptime_sec': calcula_uptime_sec(d[5]),
            'mac': d[3],
            'interface': d[2]
        })

if vendor == 'cisco':
    bng_cisco()
elif vendor == 'huawei':
    bng_huawei()
elif vendor == 'mikrotik':
    bng_mikrotik()
else:
    print()
    print('--> Vendor invalido!')
    print()
    sys.exit(1)

if isinstance(dados, (list, dict)) and len(dados) > 1:
    print(json.dumps(dados, indent=3))
else:
    print({'Erro': 'Falha na verificacao!'})