# Instalação nativa (sem Docker)

**[Español](instalacion-nativa.md) · [English](instalacion-nativa.en.md) · Português**

O SquidManager pode ser implantado sem Docker, com o Squid, o painel, o
PostgreSQL e o nginx rodando como serviços do sistema. É a alternativa aos
contêineres, não um complemento: numa mesma máquina usa-se um **ou** o outro.

> A versão em espanhol, [instalacion-nativa.md](instalacion-nativa.md), é a
> fonte de verdade. Se houver divergência, o espanhol está certo.

Para quem faz sentido:

- Redes onde a política interna não permite Docker.
- Um equipamento que já faz de proxy e onde colocar um runtime de contêineres é
  acrescentar uma peça que ninguém queria.
- Appliances ou máquinas pequenas, onde economizar a camada de contêineres se
  nota.

## Requisitos

- Ubuntu 22.04/24.04 ou Debian 12, x86_64.
- Acesso root.
- Saída para a internet para baixar pacotes e clonar o repositório.

## Instalação

```bash
wget https://raw.githubusercontent.com/luislopezsanchez/squid-manager/main/install-nativo.sh
less install-nativo.sh          # leia o que ele vai fazer no seu servidor
chmod +x install-nativo.sh
sudo ./install-nativo.sh
```

Ao terminar, imprime a URL do painel e a senha inicial do `admin`, que precisa
ser trocada no primeiro acesso.

Pode ser ajustado com variáveis de ambiente:

```bash
WEB_PORT=8080 PROXY_PORT=3130 sudo -E ./install-nativo.sh
```

| Variável | Padrão | O que é |
|---|---|---|
| `WEB_PORT` | `3000` | Porta do painel |
| `PROXY_PORT` | `3128` | Porta do proxy |
| `API_PORT` | `8000` | Porta interna da API (só escuta em localhost) |
| `INSTALL_DIR` | `/opt/squid-manager` | Onde o código fica |
| `APP_USER` | `squidmgr` | Usuário com que o painel roda |
| `BRANCH` | `main` | Branch do repositório a implantar |

## Recém-instalado, o proxy não deixa ninguém passar

É de propósito, e convém saber antes de testar.

Entre o Squid subir e existir uma configuração de verdade passam alguns
segundos. A configuração desse intervalo **nega tudo exceto `localhost`**: se
permitisse a rede local, qualquer um da faixa privada poderia usar o proxy sem
credenciais durante esse tempo — e por todo o tempo que levasse até alguém
entrar no painel.

O painel substitui esse arranque pela configuração definitiva, com
autenticação, assim que o backend sobe. O instalador confere isso antes de
terminar e avisa se não tiver acontecido.

Consequência prática: **numa instalação nova ninguém navega**, porque ainda não
há nenhum usuário do proxy. Crie o primeiro no painel, em *Usuários → Novo
usuário*, e a partir daí o proxy pede usuário e senha.

```bash
# sem credenciais: 407, que é o correto
curl -x http://IP_DO_SERVIDOR:3128 -o /dev/null -w "%{http_code}\n" http://example.com
```

## O que instala, e por que assim

### `squid-openssl`, não `squid`

Debian e Ubuntu empacotam o Squid duas vezes. O pacote `squid` puro é a variante
**GnuTLS**: sem `--with-openssl`, sem `--enable-ssl-crtd` e sem
`security_file_certgen`. Com ele, o SSL Bump do painel não funciona, e a falha
aparece muito mais tarde e sem relação aparente com a causa.

O `squid-openssl` traz tudo o que o projeto precisa — OpenSSL, ssl-crtd, delay
pools, autenticação básica NCSA e LDAP, 65536 descritores de arquivo — de modo
que **não é preciso compilar nada**. O instalador verifica isso explicitamente e
aborta se o binário encontrado não for compilado com OpenSSL.

Os dois pacotes instalam o mesmo binário `/usr/sbin/squid` e não podem
coexistir: instalar um desinstala o outro.

### Privilégios: usuário próprio e três comandos

O painel **não roda como root**. É criado o usuário `squidmgr`, cujo grupo
primário é `proxy`, e um arquivo de sudoers com três comandos literais, sem
curingas:

```
squidmgr ALL=(root) NOPASSWD: /usr/sbin/squid -f /etc/squid/squid.conf -k reconfigure
squidmgr ALL=(root) NOPASSWD: /usr/sbin/squid -k parse -f /etc/squid/squid.conf.candidate
squidmgr ALL=(root) NOPASSWD: /usr/bin/systemctl restart squid
```

É bem menos do que o modo Docker, onde o backend precisa do socket do daemon —
que equivale a root na máquina.

Que o grupo primário seja `proxy` não é um detalhe: é o que permite ao painel
gravar os arquivos que o Squid precisa ler (o htpasswd dos usuários, a
configuração de LDAP) sem precisar de `chown`, que exigiria privilégios. Os
arquivos com segredos são criados com modo 640 e grupo `proxy`, de modo que só
root, o painel e o Squid podem lê-los.

### Banco de dados

PostgreSQL na mesma máquina. **SQLite não serve**: há nove operações nas
migrações (`drop_column`, `drop_constraint`, `create_foreign_key`…) que o SQLite
não suporta sem `batch_alter_table`, e o projeto não o usa.

### Rotação de logs

O pacote do Squid traz o seu próprio `/etc/logrotate.d/squid`; o instalador o
move para `squid.dpkg-orig` e coloca o do projeto. A diferença importa: o nosso
força o Squid a reabrir o arquivo depois de rotacioná-lo. Sem isso, o Squid
continua gravando no arquivo já renomeado, o `/var/log/squid/access.log` deixa
de existir, e o painel vai a zero — cartões, gráficos, registros e estatísticas
saem todos dali — enquanto a navegação continua funcionando normalmente, então
nada denuncia a falha.

## Diferenças de comportamento em relação ao Docker

São três, todas deliberadas.

**A porta vive no `squid.conf`.** No Docker, o Squid escuta sempre numa porta
interna fixa e o Docker publica a que se escolhe no painel. No modo nativo não
há tradução: o Squid escuta diretamente onde o painel disser, e mudar de porta é
reescrever o arquivo e reiniciar o serviço, sem recriar nada.

**O tráfego é medido da máquina inteira**, não de uma interface virtual dedicada
ao proxy. Num equipamento que faz de proxy e pouco mais a diferença é
desprezível; se a máquina faz outras coisas, o tráfego dela também conta no
cartão de tráfego em tempo real.

**O estado é consultado ao systemd.** O painel mostra `active` / `failed` em vez
de `running` / `exited`.

## Operação

```bash
systemctl status squid squidmanager nginx    # estado
journalctl -u squidmanager -f                # registros do painel
journalctl -u squid -f                       # registros do Squid
```

A configuração fica em `/opt/squid-manager/.env`. Depois de editá-la:

```bash
systemctl restart squidmanager
```

## Atualizar

```bash
cd /opt/squid-manager
sudo git pull
sudo backend/.venv/bin/pip install -q -r backend/requirements.txt
cd frontend && sudo npm install --silent && sudo npm run build
sudo systemctl restart squidmanager
```

**O `npm run build` não é opcional**, e é o equivalente exato do `--build` do
Docker: o nginx serve os arquivos já compilados de `frontend/dist`, então sem
recompilar o painel continua rodando a versão anterior mesmo que o `git pull`
tenha dado certo.

O painel aplica as migrações do banco de dados ao iniciar, então não há um passo
separado para isso.

## Desinstalar

```bash
sudo systemctl disable --now squidmanager squid
sudo rm -f /etc/systemd/system/squidmanager.service /etc/sudoers.d/squidmanager
sudo rm -f /etc/nginx/sites-enabled/squidmanager
sudo systemctl daemon-reload && sudo systemctl reload nginx
sudo rm -rf /opt/squid-manager
```

O banco de dados, o `/etc/squid` e os certificados são preservados de propósito:
apague-os à parte se realmente quiser começar do zero.
